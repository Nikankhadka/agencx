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

from typing import Any

from app.shared import db


async def list_conversations(
    *, tenant_id: str, status_filter: str | None, limit: int, offset: int
) -> list[dict[str, Any]]:
    async with db.tenant_context(tenant_id, "tenant_admin") as conn:
        # C-6 adds the three things the owner's Chats list reads at a glance:
        # whether a human is wanted (an open escalation), what it is about
        # (that escalation's summary), and the last thing said. All three are
        # correlated subqueries against the row being listed rather than a join
        # + group-by, which keeps one row per conversation without the list
        # having to de-duplicate anything.
        rows = await conn.fetch(
            "select c.id, c.customer_ref, c.status, c.created_at, "
            "  (select count(*) from messages m "
            "   where m.tenant_id = $1 and m.conversation_id = c.id and m.role <> 'system') "
            "   as message_count, "
            "  (select e.summary from escalations e "
            "   where e.tenant_id = $1 and e.conversation_id = c.id and e.status <> 'resolved' "
            "   order by e.created_at desc limit 1) as pending_summary, "
            "  exists (select 1 from escalations e "
            "   where e.tenant_id = $1 and e.conversation_id = c.id and e.status <> 'resolved') "
            "   as needs_attention, "
            "  (select m.content from messages m "
            "   where m.tenant_id = $1 and m.conversation_id = c.id and m.role <> 'system' "
            "   order by m.created_at desc, m.id desc limit 1) as last_message, "
            "  (select m.created_at from messages m "
            "   where m.tenant_id = $1 and m.conversation_id = c.id "
            "   order by m.created_at desc, m.id desc limit 1) as last_activity_at "
            "from conversations c "
            "where c.tenant_id = $1 and ($2::text is null or c.status = $2) "
            # Ordered by the stamp the row actually shows. Nulls last puts a
            # conversation with nothing said in it at the bottom, which is
            # where an empty thread belongs.
            "order by last_activity_at desc nulls last, c.created_at desc "
            "limit $3 offset $4",
            tenant_id,
            status_filter,
            limit,
            offset,
        )
    return [dict(row) for row in rows]


async def get_conversation(*, tenant_id: str, conversation_id: str) -> dict[str, Any] | None:
    """The conversation shell + messages + tool calls + per-message cost; None
    when the conversation does not belong to this tenant."""
    async with db.tenant_context(tenant_id, "tenant_admin") as conn:
        conversation = await conn.fetchrow(
            "select id, customer_ref, channel, status, created_at from conversations "
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
