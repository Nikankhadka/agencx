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

from typing import Any, Literal

from app.shared import db

# RF-14 / D38: the queue is answered by the server over the whole tenant
# dataset. The filter is derived from state the row already carries - an open
# escalation, the human-takeover status, and the RF-18 read marker - so no new
# column is needed. Every count is the same predicate run as a query.
#
# An "open" escalation is any row that is not resolved, matching the
# pending_summary/needs_attention subqueries below and the D38 definition.
_NEEDS_YOU_SQL = (
    "(c.status = 'human' or exists ("
    " select 1 from escalations e"
    " where e.tenant_id = $1 and e.conversation_id = c.id and e.status <> 'resolved'))"
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
    "human": "c.status = 'human'",
    "unread": _UNREAD_SQL,
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
        "  case when c.status = 'human' then 'human' else 'assistant' end as handler "
        "from conversations c "
        f"where {_where_sql(filter_sql=filter_sql)} "
        # Ordered by the stamp the row actually shows. Nulls last puts a
        # conversation with nothing said in it at the bottom, which is where
        # an empty thread belongs.
        "order by last_activity_at desc nulls last, c.created_at desc "
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
        "  count(*) filter (where c.status = 'human') as human "
        f"from conversations c where {where}"
    )


async def list_conversations(
    *,
    tenant_id: str,
    status_filter: str | None,
    limit: int,
    offset: int,
    queue_filter: Literal["all", "needs_you", "unread", "human"] = "all",
    q: str | None = None,
    role: str = "tenant_admin",
) -> dict[str, Any]:
    """One queue page plus the server total and the per-tab counts, all read
    inside a single tenant context."""
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
            "human": int(counts["human"]),
        },
    }


async def get_conversation(
    *, tenant_id: str, conversation_id: str, role: str = "tenant_admin"
) -> dict[str, Any] | None:
    """The conversation shell + messages + tool calls + per-message cost; None
    when the conversation does not belong to this tenant."""
    async with db.tenant_context(tenant_id, role) as conn:
        conversation = await conn.fetchrow(
            "select id, customer_ref, customer_email, channel, status, created_at "
            "from conversations "
            "where tenant_id = $1 and id = $2",
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
