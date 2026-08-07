"""Platform-owner SQL: metrics, tenant listing, provisioning, status changes.

Moved from api/platform.py. Every query runs under
``tenant_context(None, "platform_admin")`` (no single-tenant scope - the whole
point of this surface is reading across tenants) through the
``platform_admin_all`` RLS policy on both ``tenants`` and ``tenant_config``
(migration 0013 widened the latter from read-only - provisioning needs to
insert a config row, database.md section 3), never the resolver-function
bypass pattern public/auth use for pre-auth reads.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from app.shared import db

PROVISION_NOTE = (
    "Tenant shell created with no owner yet - the self-serve signup flow can't "
    "currently attach an owner to a pre-provisioned tenant (a known, flagged "
    "gap; see .agents/memory.md T-033). Provisioned tenants stay in "
    "status='provisioning' until a founder decision on the claim mechanism."
)


async def metrics() -> dict[str, int | float]:
    """Aggregate tenant count + total cost across all tenants."""
    async with db.tenant_context(None, "platform_admin") as conn:
        row = await conn.fetchrow(
            "select (select count(*) from tenants) as tenant_count, "
            "  (select coalesce(sum(cost_usd), 0) from cost_logs) as total_cost_usd"
        )
    assert row is not None
    return {"tenant_count": row["tenant_count"], "total_cost_usd": float(row["total_cost_usd"])}


async def list_tenants() -> list[dict[str, Any]]:
    """All tenants with conversation/cost aggregates, newest first."""
    async with db.tenant_context(None, "platform_admin") as conn:
        rows = await conn.fetch(
            "select t.id, t.slug, t.name, t.status, t.created_at, "
            "  (select count(*) from conversations c where c.tenant_id = t.id) "
            "    as conversation_count, "
            "  (select coalesce(sum(cl.cost_usd), 0) from cost_logs cl "
            "    where cl.tenant_id = t.id) as cost_usd "
            "from tenants t "
            "order by t.created_at desc"
        )
    return [{**dict(row), **{"cost_usd": float(row["cost_usd"])}} for row in rows]


async def slug_available(slug: str) -> bool:
    async with db.tenant_context(None, "platform_admin") as conn:
        exists = await conn.fetchval("select 1 from tenants where slug = $1", slug)
    return exists is None


async def provision(*, slug: str, name: str) -> str:
    """Insert the 'provisioning' tenant shell + config row, returning the
    generated tenant id. Raises an asyncpg UniqueViolationError (mapped to a
    409 by the controller) when the slug is taken."""
    tenant_id = str(uuid4())
    async with db.tenant_context(None, "platform_admin") as conn:
        await conn.execute(
            "insert into tenants (id, slug, name, status) values ($1, $2, $3, 'provisioning')",
            tenant_id,
            slug,
            name,
        )
        await conn.execute("insert into tenant_config (tenant_id) values ($1)", tenant_id)
    return tenant_id


async def update_status(tenant_id: str, status_value: str) -> dict[str, str] | None:
    """Flip a tenant's status; returns the updated slug/name rows or None when
    the tenant does not exist."""
    async with db.tenant_context(None, "platform_admin") as conn:
        row = await conn.fetchrow(
            "update tenants set status = $1 where id = $2 "
            "returning id, slug, name, status, created_at",
            status_value,
            tenant_id,
        )
        if row is None:
            return None
        counts = await conn.fetchrow(
            "select "
            "  (select count(*) from conversations c "
            "     where c.tenant_id = $1) as conversation_count, "
            "  (select coalesce(sum(cl.cost_usd), 0) from cost_logs cl "
            "     where cl.tenant_id = $1) as cost_usd",
            tenant_id,
        )
    assert counts is not None
    return dict({**dict(row), **dict(counts), "cost_usd": float(counts["cost_usd"])})
