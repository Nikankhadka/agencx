"""Pricing persistence: pricing_rules + read-only catalog queries.

Moved from api/pricing.py. Currency conversion happens ONLY at the API
boundary - clients send decimal dollar strings, this module converts to
integer cents server-side (never trusting a client-supplied cents value
directly). This is the deterministic-pricing hard rule applied to
admin-authored config: an admin is the source of the number, arithmetic on it
still never happens inside an LLM call, and here not even inside the client.

Editing a rule's amount only affects quotes computed AFTER the edit - a
`sent` quote's line_items/totals are already persisted verbatim and the
quotes_immutable trigger (T-002/T-016) physically prevents them from ever
changing.
"""

from __future__ import annotations

import asyncpg

from app.shared import db


async def list_rules(*, tenant_id: str) -> list[dict[str, object]]:
    async with db.tenant_context(tenant_id, "tenant_admin") as conn:
        rows = await conn.fetch(
            "select id, code, label, unit_amount_cents, unit, active, updated_at "
            "from pricing_rules where tenant_id = $1 order by code",
            tenant_id,
        )
    return [dict(row) for row in rows]


async def update_rule(
    *, tenant_id: str, rule_id: str, updates: dict[str, object]
) -> dict[str, object] | None:
    """Apply the whitelisted column updates; None when the rule is not this
    tenant's. Raises asyncpg.UniqueViolationError (409 at the boundary) when a
    code collides. The set-clause keys come from the controller's fixed
    whitelist - never client-supplied column names."""
    set_clause = ", ".join(f"{key} = ${i + 3}" for i, key in enumerate(updates))
    async with db.tenant_context(tenant_id, "tenant_admin") as conn:
        try:
            row = await conn.fetchrow(
                f"update pricing_rules set {set_clause} "  # noqa: S608 - keys are our own fixed whitelist
                "where tenant_id = $1 and id = $2 "
                "returning id, code, label, unit_amount_cents, unit, active, updated_at",
                tenant_id,
                rule_id,
                *updates.values(),
            )
        except asyncpg.UniqueViolationError:
            raise
    return dict(row) if row is not None else None


async def list_catalog(*, tenant_id: str) -> list[dict[str, object]]:
    async with db.tenant_context(tenant_id, "tenant_admin") as conn:
        rows = await conn.fetch(
            "select id, name, description, price_cents, active, updated_at "
            "from offerings where tenant_id = $1 order by name",
            tenant_id,
        )
    return [dict(row) for row in rows]
