"""Escalations persistence: the queue read and the claim/resolve transitions.

Moved from api/escalations.py. Claim/resolve use a conditional UPDATE (``where
status = 'open'``/``status in (...)``) rather than read-then-write, so two
admins racing on the same row can't both "win" a claim - the loser's UPDATE
simply matches zero rows.
"""

from __future__ import annotations

import asyncpg

from app.shared import db

_SELECT_COLUMNS = "id, conversation_id, reason, status, created_at, resolved_at"


async def list_escalations(*, tenant_id: str, limit: int, offset: int) -> list[dict[str, object]]:
    async with db.tenant_context(tenant_id, "tenant_admin") as conn:
        rows = await conn.fetch(
            f"select {_SELECT_COLUMNS} from escalations where tenant_id = $1 "
            "order by created_at desc limit $2 offset $3",
            tenant_id,
            limit,
            offset,
        )
    return [dict(row) for row in rows]


async def claim(*, tenant_id: str, escalation_id: str) -> dict[str, str] | None:
    """Try to claim; the conditional UPDATE returns None when the escalation
    was already moved (the caller then reads the row to tell 404 from 409)."""
    async with db.tenant_context(tenant_id, "tenant_admin") as conn:
        claimed = await conn.fetchrow(
            f"update escalations set status = 'claimed' "
            f"where tenant_id = $1 and id = $2 and status = 'open' "
            f"returning {_SELECT_COLUMNS}",
            tenant_id,
            escalation_id,
        )
        if claimed is not None:
            return dict(claimed)
        existing = await _fetch_one(conn, tenant_id, escalation_id)
    if existing is None:
        return None
    return {"__conflict__": f"escalation is already {existing['status']}, not open"}


async def resolve(
    *, tenant_id: str, escalation_id: str, message: str | None
) -> dict[str, str] | None:
    """Resolve an open/claimed escalation; ``message`` (if given) becomes a
    human_agent message in the transcript. None means the escalation was
    already resolved or missing - the caller distinguishes 404 from 409."""
    async with db.tenant_context(tenant_id, "tenant_admin") as conn:
        resolved = await conn.fetchrow(
            f"update escalations set status = 'resolved', resolved_at = now() "
            f"where tenant_id = $1 and id = $2 and status in ('open', 'claimed') "
            f"returning {_SELECT_COLUMNS}",
            tenant_id,
            escalation_id,
        )
        if resolved is None:
            existing = await _fetch_one(conn, tenant_id, escalation_id)
            if existing is None:
                return None
            return {"conflict": "escalation is already resolved"}

        if message is not None:
            # T-031: a human_agent reply lands in the transcript the same way
            # any other message does - the customer surface picks it up by
            # polling (no push mechanism exists in this codebase; see
            # CustomerChat.tsx's escalated-state poll).
            await conn.execute(
                "insert into messages (tenant_id, conversation_id, role, content) "
                "values ($1, $2, 'human_agent', $3)",
                tenant_id,
                resolved["conversation_id"],
                message,
            )
    return dict(resolved)


async def _fetch_one(
    conn: db.AppConnection, tenant_id: str, escalation_id: str
) -> asyncpg.Record | None:
    return await conn.fetchrow(
        f"select {_SELECT_COLUMNS} from escalations where tenant_id = $1 and id = $2",
        tenant_id,
        escalation_id,
    )
