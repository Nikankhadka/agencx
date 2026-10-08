"""Conversations persistence: list + full transcript with trace extraction.

Moved from api/conversations.py. cost_logs has no message_id column (only
conversation_id) - the cost of one turn is attributed to the assistant message
that immediately preceded it via a lateral join on created_at. This is exact,
not approximate: every cost_logs write happens right after the assistant
message insert on every code path in features/chat (a durable fix - a
message_id column on cost_logs - is a future migration, flagged in T-031
rather than silently built here).
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Literal

from app.shared import config, db
from app.shared.limits import TenantLimits

logger = logging.getLogger("app.features.conversations.service")

# RF-14 / D38 as amended by D43: the queue is answered by the server over the
# whole tenant dataset. The filter is derived from state the row already
# carries - an open escalation, the human-takeover status, whose turn it is,
# and the RF-18 read marker - so no new column is needed. Every count is the
# same predicate run as a query.
#
# An "open" escalation is any row that is not resolved, matching the
# pending_summary/needs_attention subqueries below and the D38 definition.
#
# The last non-system message decides whose turn it is. A system row is a
# stamp (takeover, handback, resolution), never a reply, so it can never hand
# the turn to anyone.
_LAST_ROLE_SQL = (
    "(select m.role from messages m"
    " where m.tenant_id = $1 and m.conversation_id = c.id and m.role <> 'system'"
    " order by m.created_at desc, m.id desc limit 1)"
)

# D43: a taken-over thread whose last word came from the customer needs the
# owner; one whose last word came from the owner or the assistant does not.
# An open escalation always needs the owner, takeover or not. A resolved
# conversation never does, until a customer reply clears resolved_at.
_NEEDS_YOU_SQL = (
    "(c.resolved_at is null and ("
    f" (c.status = 'human' and {_LAST_ROLE_SQL} = 'customer')"
    " or exists ("
    " select 1 from escalations e"
    " where e.tenant_id = $1 and e.conversation_id = c.id and e.status <> 'resolved')))"
)

# D43: the owner spoke last on a taken-over thread, so the ball is with the
# customer. A label, not a tab - there is nothing to act on.
_WAITING_ON_CUSTOMER_SQL = (
    "(c.resolved_at is null and c.status = 'human'"
    f" and coalesce({_LAST_ROLE_SQL} in ('assistant', 'human_agent'), false))"
)

# RF-18's unread definition, kept in exactly one place: a customer message
# newer than the owner's read marker, or no marker yet. The list column and the
# unread filter both read this string so the two can never drift.
_UNREAD_SQL = (
    "exists (select 1 from messages m"
    " where m.tenant_id = $1 and m.conversation_id = c.id"
    "   and m.role = 'customer'"
    "   and (c.owner_read_at is null or m.created_at > c.owner_read_at))"
)

_FILTER_SQL: dict[str, str] = {
    "all": "true",
    "needs_you": _NEEDS_YOU_SQL,
    "unread": _UNREAD_SQL,
    "resolved": "c.resolved_at is not null",
}

# Search matches the whole tenant dataset: customer name, the conversation
# reference (the id's hex with dashes removed), and the latest open
# escalation's summary. A leading "#" is ignored only for the reference match,
# so a value copied from the list as "#4F9A2C" still finds its row. $3 is the
# trimmed query; empty means no search. The value is always bound, never
# interpolated.
_SEARCH_SQL = (
    "($3 = '' or "
    " strpos(lower(c.customer_ref), lower($3)) > 0 "
    " or strpos(lower(replace(c.id::text, '-', '')), "
    "      lower(case when left($3, 1) = '#' then substr($3, 2) else $3 end)) > 0 "
    " or strpos(lower((select e.summary from escalations e"
    "      where e.tenant_id = $1 and e.conversation_id = c.id and e.status <> 'resolved'"
    "      order by e.created_at desc limit 1)), lower($3)) > 0)"
)


def _where_sql(*, filter_sql: str) -> str:
    """The tenant scope + status + search + one queue filter, shared by the
    items and total queries. The counts query uses the same scope with no queue
    filter and applies each predicate as an aggregate filter instead."""
    return (
        "c.tenant_id = $1 "
        "and ($2::text is null or c.status = $2) "
        f"and {_SEARCH_SQL} "
        f"and {filter_sql}"
    )


def _items_sql(*, filter_sql: str) -> str:
    # C-6 adds the three things the owner's Chats list reads at a glance:
    # whether a human is wanted (an open escalation), what it is about (that
    # escalation's summary), and the last thing said. All three are correlated
    # subqueries against the row being listed rather than a join + group-by,
    # which keeps one row per conversation without the list having to
    # de-duplicate anything. RF-14 adds handler, derived from status.
    return (
        "select c.id, c.customer_ref, c.status, c.created_at, "
        "  (select count(*) from messages m "
        "   where m.tenant_id = $1 and m.conversation_id = c.id and m.role <> 'system') "
        "   as message_count, "
        "  (select e.summary from escalations e "
        "   where e.tenant_id = $1 and e.conversation_id = c.id and e.status <> 'resolved' "
        "   order by e.created_at desc limit 1) as pending_summary, "
        "  (select e.created_at from escalations e "
        "   where e.tenant_id = $1 and e.conversation_id = c.id and e.status <> 'resolved' "
        "   order by e.created_at desc limit 1) as pending_since, "
        "  exists (select 1 from escalations e "
        "   where e.tenant_id = $1 and e.conversation_id = c.id and e.status <> 'resolved') "
        "   as needs_attention, "
        f"  {_UNREAD_SQL} as unread, "
        "  (select m.content from messages m "
        "   where m.tenant_id = $1 and m.conversation_id = c.id and m.role <> 'system' "
        "   order by m.created_at desc, m.id desc limit 1) as last_message, "
        "  (select m.created_at from messages m "
        "   where m.tenant_id = $1 and m.conversation_id = c.id "
        "   order by m.created_at desc, m.id desc limit 1) as last_activity_at, "
        "  case when c.status = 'human' then 'human' else 'assistant' end as handler, "
        f"  {_WAITING_ON_CUSTOMER_SQL} as waiting_on_customer, "
        "  c.resolved_at "
        "from conversations c "
        f"where {_where_sql(filter_sql=filter_sql)} "
        # Ordered by the stamp the row actually shows. Nulls last puts a
        # conversation with nothing said in it at the bottom, which is where
        # an empty thread belongs. c.id desc is a unique final key: without it
        # two rows tied on both stamps have no stable position, so an
        # offset page can skip or duplicate them under load.
        "order by last_activity_at desc nulls last, c.created_at desc, c.id desc "
        "limit $4 offset $5"
    )


def _total_sql(*, filter_sql: str) -> str:
    return f"select count(*) from conversations c where {_where_sql(filter_sql=filter_sql)}"


def _counts_sql() -> str:
    """Every tab count over the tenant's whole dataset with q applied but the
    active filter and pagination ignored. The active filter's count equals the
    total whenever there is no search, which is the invariant the client's
    "Load more" relies on."""
    where = _where_sql(filter_sql="true")
    return (
        'select count(*) as "all", '
        f"  count(*) filter (where {_NEEDS_YOU_SQL}) as needs_you, "
        f"  count(*) filter (where {_UNREAD_SQL}) as unread, "
        "  count(*) filter (where c.resolved_at is not null) as resolved "
        f"from conversations c where {where}"
    )


async def list_conversations(
    *,
    tenant_id: str,
    status_filter: str | None,
    limit: int,
    offset: int,
    queue_filter: Literal["all", "needs_you", "unread", "resolved"] = "all",
    q: str | None = None,
    role: str = "tenant_admin",
) -> dict[str, Any]:
    """One queue page plus the server total and the per-tab counts, all read
    inside a single tenant context. The throttled auto-resolve sweep runs
    first, so the page and its counts describe the same world (D45)."""
    await maybe_auto_resolve(tenant_id=tenant_id, role=role)
    search = (q or "").strip()
    filter_sql = _FILTER_SQL[queue_filter]
    async with db.tenant_context(tenant_id, role) as conn:
        item_rows = await conn.fetch(
            _items_sql(filter_sql=filter_sql),
            tenant_id,
            status_filter,
            search,
            limit,
            offset,
        )
        total = await conn.fetchval(
            _total_sql(filter_sql=filter_sql), tenant_id, status_filter, search
        )
        counts = await conn.fetchrow(_counts_sql(), tenant_id, status_filter, search)
        assert counts is not None
    return {
        "items": [dict(row) for row in item_rows],
        "total": int(total),
        "counts": {
            "all": int(counts["all"]),
            "needs_you": int(counts["needs_you"]),
            "unread": int(counts["unread"]),
            "resolved": int(counts["resolved"]),
        },
    }


async def get_conversation(
    *, tenant_id: str, conversation_id: str, role: str = "tenant_admin"
) -> dict[str, Any] | None:
    """The conversation shell + messages + tool calls + per-message cost; None
    when the conversation does not belong to this tenant. The throttled
    auto-resolve sweep runs first (D45), so an ignored thread is resolved by
    the time its own detail page reads it."""
    await maybe_auto_resolve(tenant_id=tenant_id, role=role)
    async with db.tenant_context(tenant_id, role) as conn:
        conversation = await conn.fetchrow(
            "select c.id, c.customer_ref, c.customer_email, c.channel, c.status, c.created_at, "
            "  (select e.id from escalations e "
            "   where e.tenant_id = $1 and e.conversation_id = c.id "
            "     and e.status <> 'resolved' "
            "   order by e.created_at desc, e.id desc limit 1) as pending_escalation_id, "
            "  c.resolved_at "
            "from conversations c "
            "where c.tenant_id = $1 and c.id = $2",
            tenant_id,
            conversation_id,
        )
        if conversation is None:
            return None

        message_rows = await conn.fetch(
            "select id, role, content, agent_node, created_at, metadata "
            "from messages where tenant_id = $1 and conversation_id = $2 "
            "order by created_at asc",
            tenant_id,
            conversation_id,
        )
        tool_call_rows = await conn.fetch(
            "select tc.id, tc.message_id, tc.tool_name, tc.arguments, tc.result, "
            "  tc.success, tc.latency_ms "
            "from tool_calls tc "
            "join messages m on m.id = tc.message_id and m.tenant_id = tc.tenant_id "
            "where tc.tenant_id = $1 and m.conversation_id = $2",
            tenant_id,
            conversation_id,
        )
        # Attribute each cost_logs row to the assistant message immediately
        # preceding it (see module docstring) - a lateral join per message.
        cost_rows = await conn.fetch(
            "select m.id as message_id, coalesce(sum(cl.cost_usd), 0) as cost_usd "
            "from messages m "
            "left join lateral ( "
            "  select cost_usd from cost_logs cl "
            "  where cl.tenant_id = m.tenant_id and cl.conversation_id = m.conversation_id "
            "    and cl.created_at >= m.created_at "
            "    and cl.created_at < coalesce("
            "      (select min(m2.created_at) from messages m2 "
            "       where m2.tenant_id = m.tenant_id and m2.conversation_id = m.conversation_id "
            "         and m2.created_at > m.created_at), "
            "      'infinity'::timestamptz)"
            ") cl on true "
            "where m.tenant_id = $1 and m.conversation_id = $2 and m.role = 'assistant' "
            "group by m.id",
            tenant_id,
            conversation_id,
        )
        total_cost = await conn.fetchval(
            "select coalesce(sum(cost_usd), 0) from cost_logs "
            "where tenant_id = $1 and conversation_id = $2",
            tenant_id,
            conversation_id,
        )

    return {
        "conversation": dict(conversation),
        "messages": [dict(row) for row in message_rows],
        "tool_calls": [dict(row) for row in tool_call_rows],
        "cost_rows": [dict(row) for row in cost_rows],
        "total_cost": float(total_cost),
    }


async def mark_read(*, tenant_id: str, conversation_id: str, role: str = "tenant_admin") -> bool:
    """RF-18: the owner opened the thread, so advance the read marker.

    Idempotent and never backwards: `greatest(owner_read_at, now())` only ever
    moves the marker later, and a repeat call on an already-read conversation
    still matches and returns True. False means the conversation is not this
    tenant's (or does not exist), which the controller turns into a 404.
    """
    async with db.tenant_context(tenant_id, role) as conn:
        updated = await conn.fetchval(
            "update conversations set owner_read_at = greatest(owner_read_at, now()) "
            "where id = $1 and tenant_id = $2 "
            "returning id",
            conversation_id,
            tenant_id,
        )
    return updated is not None


async def delete_conversation(
    *, tenant_id: str, conversation_id: str, role: str = "tenant_admin"
) -> Literal["deleted", "not_found", "has_quotes"]:
    """T-028: forget one customer conversation. Messages, tool calls and
    escalations cascade; cost_logs.conversation_id is set null, so the unit
    economics survive detached. A conversation with a quote is refused: quotes
    are tamper-proof records (wren_app has no DELETE on them), and excluding
    those conversations here means the cascade never reaches `quotes` at all.
    They go through the operator offboarding path instead.
    """
    async with db.tenant_context(tenant_id, role) as conn:
        deleted = await conn.fetchval(
            "delete from conversations "
            "where id = $1 and tenant_id = $2 "
            "  and not exists (select 1 from quotes q "
            "                  where q.tenant_id = $2 and q.conversation_id = $1) "
            "returning id",
            conversation_id,
            tenant_id,
        )
        if deleted is not None:
            return "deleted"
        exists = await conn.fetchval(
            "select 1 from conversations where id = $1 and tenant_id = $2",
            conversation_id,
            tenant_id,
        )
    return "has_quotes" if exists else "not_found"


# D44/D45: the two resolution stamps, owner-only like the takeover/handback
# stamps in features/chat. Written as ``system`` messages so the owner's thread
# reads that it was closed on purpose; the public transcript filters ``system``
# out, so a customer never reads them.
CONVERSATION_RESOLVED_STAMP = "You resolved this conversation"
AUTO_RESOLVED_STAMP = "Resolved automatically after {days} days"


async def resolve_conversation(
    *,
    tenant_id: str,
    conversation_id: str,
    message: str | None = None,
    stamp: str = CONVERSATION_RESOLVED_STAMP,
    role: str = "tenant_admin",
) -> Literal["resolved", "already_resolved", "not_found"]:
    """D44: mark a conversation resolved, close any open escalation, and write
    the owner-only stamp (plus the optional customer-facing message).

    Resolution is a marker, not a status: the ownership axis (open/human/
    escalated) is untouched, and a later customer message clears the marker
    (chat.service.resolve_conversation). The UPDATE is guarded on
    ``resolved_at is null`` so a repeat call cannot write a second stamp;
    "already_resolved" is a no-op the caller treats as success. "not_found"
    means the conversation is not this tenant's.
    """
    async with db.tenant_context(tenant_id, role) as conn:
        updated = await conn.fetchval(
            "update conversations set resolved_at = now() "
            "where id = $1 and tenant_id = $2 and resolved_at is null "
            "returning id",
            conversation_id,
            tenant_id,
        )
        if updated is None:
            exists = await conn.fetchval(
                "select 1 from conversations where id = $1 and tenant_id = $2",
                conversation_id,
                tenant_id,
            )
            return "already_resolved" if exists is not None else "not_found"

        await conn.execute(
            "update escalations set status = 'resolved', resolved_at = now() "
            "where tenant_id = $1 and conversation_id = $2 and status in ('open', 'claimed')",
            tenant_id,
            conversation_id,
        )
        await conn.execute(
            "insert into messages (tenant_id, conversation_id, role, content) "
            "values ($1, $2, 'system', $3)",
            tenant_id,
            conversation_id,
            stamp,
        )
        if message is not None:
            # Same ordering rule as the escalation resolve: Postgres ``now()``
            # is transaction-stable, so the message gets an explicit +1
            # microsecond to read after the stamp.
            await conn.execute(
                "insert into messages (tenant_id, conversation_id, role, content, created_at) "
                "values ($1, $2, 'human_agent', $3, now() + interval '1 microsecond')",
                tenant_id,
                conversation_id,
                message,
            )
    return "resolved"


# D45: how long a tenant's sweep result stays trusted. The console and Home
# poll every few seconds; without this every read would re-run the sweep query.
_AUTO_RESOLVE_TTL_S = 60.0
_auto_resolve_checked: dict[str, float] = {}


def clear_auto_resolve_cache() -> None:
    """Test hook - force the next read to sweep instead of trusting the TTL."""
    _auto_resolve_checked.clear()


async def maybe_auto_resolve(*, tenant_id: str, role: str = "tenant_admin") -> int:
    """Run the sweep at most once per TTL per tenant; never fail a read over
    it."""
    now = time.monotonic()
    last = _auto_resolve_checked.get(tenant_id)
    if last is not None and now - last < _AUTO_RESOLVE_TTL_S:
        return 0
    _auto_resolve_checked[tenant_id] = now
    try:
        return await sweep_auto_resolve(tenant_id=tenant_id, role=role)
    except Exception:
        logger.exception("auto-resolve sweep failed for tenant %s", tenant_id)
        return 0


async def sweep_auto_resolve(*, tenant_id: str, role: str = "tenant_admin") -> int:
    """D45: resolve conversations whose last word came from the business more
    than the tenant's configured window ago.

    Lazy, not scheduled: the queue and Home already poll, so the read that
    would show a stale row is the read that clears it. No unattended mutating
    process exists anywhere in this codebase (D36), and this adds none. A
    customer reply reopens the thread through chat.service.resolve_conversation,
    so the marker is safe to write without asking anyone. Applies to an open
    escalation too: seven days of customer silence is disengagement, and the
    resolved escalation stays readable in the thread.
    """
    async with db.tenant_context(tenant_id, role) as conn:
        config_row = await conn.fetchrow(
            "select config from tenant_config where tenant_id = $1", tenant_id
        )
        limits = TenantLimits.resolve(
            json.loads(config_row["config"]) if config_row and config_row["config"] else {},
            config.get_settings(),
        )
        days = limits.auto_resolve_days
        rows = await conn.fetch(
            "select c.id from conversations c "
            "where c.tenant_id = $1 and c.resolved_at is null "
            f"  and {_LAST_ROLE_SQL} in ('assistant', 'human_agent') "
            "  and (select m.created_at from messages m "
            "       where m.tenant_id = $1 and m.conversation_id = c.id "
            "         and m.role <> 'system' "
            "       order by m.created_at desc, m.id desc limit 1) "
            "      < now() - make_interval(days => $2)",
            tenant_id,
            days,
        )
        ids = [row["id"] for row in rows]
        if not ids:
            return 0
        await conn.execute(
            "update conversations set resolved_at = now() "
            "where tenant_id = $1 and id = any($2::uuid[]) and resolved_at is null",
            tenant_id,
            ids,
        )
        await conn.execute(
            "update escalations set status = 'resolved', resolved_at = now() "
            "where tenant_id = $1 and conversation_id = any($2::uuid[]) "
            "  and status in ('open', 'claimed')",
            tenant_id,
            ids,
        )
        stamp = AUTO_RESOLVED_STAMP.format(days=days)
        await conn.executemany(
            "insert into messages (tenant_id, conversation_id, role, content) "
            "values ($1, $2, 'system', $3)",
            [(tenant_id, conversation_id, stamp) for conversation_id in ids],
        )
    return len(ids)
