"""Chat persistence: conversation/message rows, tenant and budget resolution,
and turn persistence (assistant message, tool_calls, cost_logs).

Moved out of api/chat.py. The ticket-level rules stay in the handler docs:
nothing is customer-visible until Inspection clears a draft, escalations are
terminal, and step caps/budget stops hand off gracefully instead of erroring.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from uuid import UUID

from app.observability.cost import TokenUsage, record_costs
from app.shared import config, db
from app.shared.limits import TenantLimits, tenant_over_budget


async def resolve_active_tenant(slug: str) -> UUID:
    """T-005: public tenant lookup - no auth, scope comes from the slug.
    Raises ValueError when the slug is unknown or not active."""
    pool = db.get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("select id, status from resolve_tenant_slug($1)", slug)
    if row is None or row["status"] != "active":
        raise ValueError("unknown tenant slug")
    return UUID(str(row["id"]))


async def resolve_conversation(
    *,
    tenant_id: UUID,
    conversation_id: UUID | None,
    message: str,
) -> tuple[UUID, bool, TenantLimits, bool]:
    """Open or fetch the conversation, persist the customer message, and
    resolve this tenant's limits and remaining daily budget - all inside one
    customer-scoped transaction. Raises ValueError when the conversation id
    belongs to someone else. Returns
    (conversation_id, already_escalated, limits, over_budget)."""
    async with db.tenant_context(tenant_id, "customer") as conn:
        if conversation_id is not None:
            row = await conn.fetchrow(
                "select status from conversations where id = $1 and tenant_id = $2",
                conversation_id,
                tenant_id,
            )
            if row is None:
                raise ValueError("conversation not found")
            already_escalated = row["status"] == "escalated"
        else:
            conversation_id = await conn.fetchval(
                "insert into conversations (tenant_id) values ($1) returning id", tenant_id
            )
            already_escalated = False
        await conn.execute(
            "insert into messages (tenant_id, conversation_id, role, content) "
            "values ($1, $2, 'customer', $3)",
            tenant_id,
            conversation_id,
            message,
        )
        # T-028: resolve this tenant's caps and check the daily budget before
        # any LLM call. Both reads happen inside the customer context so RLS
        # scopes them to this tenant.
        config_row = await conn.fetchrow(
            "select config from tenant_config where tenant_id = $1", tenant_id
        )
        limits = TenantLimits.resolve(
            json.loads(config_row["config"]) if config_row and config_row["config"] else {},
            config.get_settings(),
        )
        over_budget = await tenant_over_budget(conn, tenant_id, limits)
    return conversation_id, already_escalated, limits, over_budget


async def record_limit_escalation(
    *, tenant_id: UUID, conversation_id: UUID, reason: str, message: str
) -> None:
    """T-028: a tenant hit a cap - record the escalation (deduped by 0011's
    partial unique index) and persist the graceful handoff as the assistant
    message. No graph runs.

    C-5 left this the *only* writer of ``conversations.status = 'escalated'``.
    A cap is a hard stop by design: the chat really does end, the composer
    locks, and that is the behaviour being paid for. Every agent-side handoff
    now keeps the conversation open instead."""
    async with db.tenant_context(tenant_id, "customer") as conn:
        await conn.execute(
            "insert into escalations (tenant_id, conversation_id, reason) values ($1, $2, $3) "
            "on conflict (tenant_id, conversation_id) where status = 'open' do nothing",
            tenant_id,
            conversation_id,
            reason,
        )
        await conn.execute(
            "update conversations set status = 'escalated' "
            "where id = $1 and tenant_id = $2 and status <> 'escalated'",
            conversation_id,
            tenant_id,
        )
        await conn.execute(
            "insert into messages (tenant_id, conversation_id, role, content, metadata) "
            "values ($1, $2, 'assistant', $3, $4)",
            tenant_id,
            conversation_id,
            message,
            json.dumps({"limit_escalation": reason}),
        )


async def record_turn_costs(
    *, tenant_id: UUID, conversation_id: UUID, usages: list[TokenUsage]
) -> None:
    async with db.tenant_context(tenant_id, "customer") as conn:
        await record_costs(conn, tenant_id, conversation_id, usages)


async def persist_assistant_turn(
    *,
    tenant_id: UUID,
    conversation_id: UUID,
    full_text: str,
    verdicts: dict[str, object],
    tool_calls: list[dict[str, object]],
    usages: list[TokenUsage],
) -> None:
    """Persist the approved assistant message, its tool-call trace rows, and
    per-turn token costs in one transaction."""
    async with db.tenant_context(tenant_id, "customer") as conn:
        message_id = await conn.fetchval(
            "insert into messages (tenant_id, conversation_id, role, content, metadata) "
            "values ($1, $2, 'assistant', $3, $4) returning id",
            tenant_id,
            conversation_id,
            full_text,
            json.dumps({"inspection": verdicts} if verdicts else {}),
        )
        # T-030: tool_calls rows (the Surface-2 TraceTree) and cost_logs rows
        # (per-turn token accounting, backing the T-028 daily budget).
        for call in tool_calls:
            await conn.execute(
                "insert into tool_calls "
                "(tenant_id, message_id, tool_name, arguments, result, success, latency_ms) "
                "values ($1, $2, $3, $4, $5, $6, $7)",
                tenant_id,
                message_id,
                str(call.get("name", "")),
                json.dumps(call.get("arguments", {})),
                json.dumps(call.get("result")),
                bool(call.get("success", True)),
                call.get("latency_ms"),
            )
        await record_costs(conn, tenant_id, conversation_id, usages)


async def recent_messages(
    *, tenant_id: UUID, conversation_id: UUID, limit: int
) -> list[dict[str, str]]:
    """The tail of a conversation, oldest first, as plain role/content dicts.

    The agent's view of the thread (P-3). Ordered newest-first in SQL so the
    limit keeps the *recent* messages, then reversed for the prompt, where
    chronological order is what the model needs.
    """
    async with db.tenant_context(tenant_id, "customer") as conn:
        rows = await conn.fetch(
            "select role, content from messages "
            "where tenant_id = $1 and conversation_id = $2 "
            "and role in ('customer', 'assistant', 'human_agent') "
            "order by created_at desc, id desc "
            "limit $3",
            tenant_id,
            conversation_id,
            limit,
        )
    return [{"role": row["role"], "content": row["content"]} for row in reversed(rows)]


async def list_messages(
    *,
    tenant_id: UUID,
    conversation_id: UUID,
    after: datetime | None,
    limit: int,
) -> list[dict[str, Any]]:
    """T-031: unauthenticated transcript poll for the customer surface. Trust
    model matches POST /api/chat's conversation_id: knowing the UUID is the
    capability. Raises ValueError when the conversation is not this tenant's."""
    async with db.tenant_context(tenant_id, "customer") as conn:
        exists = await conn.fetchval(
            "select 1 from conversations where tenant_id = $1 and id = $2",
            tenant_id,
            conversation_id,
        )
        if exists is None:
            raise ValueError("conversation not found")
        rows = await conn.fetch(
            "select id, role, content, created_at from messages "
            "where tenant_id = $1 and conversation_id = $2 "
            "and role in ('customer', 'assistant', 'human_agent') "
            "and ($3::timestamptz is null or created_at > $3) "
            "order by created_at asc "
            "limit $4",
            tenant_id,
            conversation_id,
            after,
            limit,
        )
    return [dict(row) for row in rows]
