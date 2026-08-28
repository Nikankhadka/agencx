"""Tenant service layer: SQL, the RLS-scoped tenant writes, and slug resolution.

Moved from api/tenants.py + api/public.py: tenant creation (service-role write
transaction), the authed "me" read, and the unauthenticated slug lookup with its
in-process cache (``resolve_tenant_slug`` / migration 0003, the sole resolver
bypass). Slug resolution is shared across features - chat/conversations use
``resolve_active_tenant`` and platform invalidates the public cache through
``invalidate_slug_cache``.
"""

from __future__ import annotations

import json
import time
from typing import Any
from uuid import uuid4

import asyncpg

from app.shared import db

_CACHE_TTL_SECONDS = 60.0


class TenantAlreadyExistsError(RuntimeError):
    """The user already belongs to a tenant, or the tenant's slug is taken."""


class UserAlreadyHasTenantError(TenantAlreadyExistsError):
    """The user already belongs to a tenant."""


class TenantSlugTakenError(TenantAlreadyExistsError):
    """The requested tenant slug is already in use."""


class TenantNotFoundError(RuntimeError):
    """The slug (or tenant) does not exist."""


async def create_tenant(*, user_id: str, slug: str, name: str) -> str:
    """Provision a tenant + config + owner in one service-role transaction.

    Returns the generated tenant id. Raises ``TenantAlreadyExistsError`` when
    the user already has a tenant or the slug is taken. Mirrors the DDL check
    on ``tenants.slug`` (database.md section 3) - the caller validates the slug
    shape at the API boundary.

    - A user already belonging to a tenant is rejected before the write
      transaction opens: the service role's Shape C policy is INSERT-only, so
      this membership check must be its own pre-context read (0009's resolver).
    - The id is generated here, not via the column default + RETURNING:
      Postgres enforces a table's SELECT policies on RETURNING even for INSERT,
      and Shape C grants the service role INSERT only (database.md section 2.3)
      - it has no SELECT policy on tenants, so `insert ... returning id` would
      itself raise "new row violates row-level security policy". Supplying the
      id up front sidesteps that read.
    """
    pool = db.get_pool()
    async with pool.acquire() as conn:
        existing = await conn.fetchrow("select tenant_id from resolve_user_tenant($1)", user_id)
    if existing is not None:
        raise UserAlreadyHasTenantError("user already has a tenant")

    tenant_id = str(uuid4())
    try:
        async with db.tenant_context(None, "service") as conn:
            await conn.execute(
                "insert into tenants (id, slug, name, status) values ($1, $2, $3, 'active')",
                tenant_id,
                slug,
                name,
            )
            await conn.execute("insert into tenant_config (tenant_id) values ($1)", tenant_id)
            await conn.execute(
                "insert into users (id, tenant_id, role) values ($1, $2, 'owner')",
                user_id,
                tenant_id,
            )
    except asyncpg.UniqueViolationError as exc:
        # users_pkey means a same-user double-submit raced past the pre-check;
        # anything else is the tenants slug uniqueness.
        error = (
            UserAlreadyHasTenantError("user already has a tenant")
            if exc.constraint_name == "users_pkey"
            else TenantSlugTakenError("slug already taken")
        )
        raise error from exc
    return tenant_id


async def find_tenant_for_user(user_id: str) -> str | None:
    """The caller's tenant id via ``resolve_user_tenant`` (0009), or ``None``
    if they have none yet. Same pre-context resolver pattern ``create_tenant``
    uses for its own membership check above - the one legitimate way to read
    this before a ``tenant_context`` exists. Used by the provisioning shape of
    ``POST /api/tenants`` (login-in-chat) to decide create-vs-return.
    """
    pool = db.get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("select tenant_id from resolve_user_tenant($1)", user_id)
    return str(row["tenant_id"]) if row is not None else None


async def get_tenant(tenant_id: str) -> dict[str, Any] | None:
    """The slug/name/brand triple for the caller's own tenant (Surface-2 header)."""
    async with db.tenant_context(tenant_id, "tenant_admin") as conn:
        row = await conn.fetchrow(
            "select t.slug, t.name, tc.brand from tenants t"
            " left join tenant_config tc on tc.tenant_id = t.id where t.id = $1",
            tenant_id,
        )
    if row is None:
        return None
    result = dict(row)
    raw = result.pop("brand", None)
    if raw is None:
        result["brand"] = {}
    else:
        parsed = json.loads(raw)
        result["brand"] = parsed if isinstance(parsed, dict) else {}
    return result


async def resolve_active_tenant(slug: str) -> str:
    """Active-tenant id for an unauthenticated surface (chat, transcripts).

    Raises ``TenantNotFoundError`` for an unknown or non-active slug. The
    customer surface has no login - tenant scope comes entirely from the slug,
    resolved the same way the public endpoint does (resolve_tenant_slug, 0003).
    """
    pool = db.get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("select id, status from resolve_tenant_slug($1)", slug)
    if row is None or row["status"] != "active":
        raise TenantNotFoundError(slug)
    return str(row["id"])


# --- public tenant resolution + cache (formerly api/public.py) ----------------

_cache: dict[str, tuple[float, dict[str, Any]]] = {}


def invalidate_slug_cache(slug: str) -> None:
    """Drop a cached resolution so the next customer-surface request re-reads
    the database. Called by platform after a status change (suspend/
    reactivate) - without this, a recently-resolved slug would keep serving
    its pre-change status for up to _CACHE_TTL_SECONDS."""
    _cache.pop(slug, None)


async def _customer_config(tenant_id: str) -> dict[str, Any]:
    """The tenant-configured customer-surface bits (greeting, starter
    questions) - read under the customer tenant context, never through the
    resolver bypass. Missing/unset config is an empty dict, never an error."""
    async with db.tenant_context(tenant_id, "customer") as conn:
        raw = await conn.fetchval(
            "select config -> 'customer' from tenant_config where tenant_id = $1",
            tenant_id,
        )
    if raw is None:
        return {}
    # asyncpg returns jsonb as raw text without an explicit codec registered.
    parsed = json.loads(raw)
    return parsed if isinstance(parsed, dict) else {}


async def resolve_slug(slug: str) -> dict[str, Any] | None:
    """Resolve a slug -> public tenant payload (id, name, status, brand,
    customer config). Positive results are cached in-process for 60s per slug; a
    negative result is never cached, so a slug becoming valid via signup is
    visible immediately rather than waiting out a stale 404."""
    now = time.monotonic()
    cached = _cache.get(slug)
    if cached is not None and cached[0] > now:
        return cached[1]

    pool = db.get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "select id, name, status, brand from resolve_tenant_slug($1)", slug
        )
    if row is None:
        _cache.pop(slug, None)
        return None

    # asyncpg returns jsonb as raw text without an explicit codec registered.
    result = {
        "id": row["id"],
        "name": row["name"],
        "status": row["status"],
        "brand": json.loads(row["brand"]),
        "customer": await _customer_config(row["id"]),
    }
    _cache[slug] = (now + _CACHE_TTL_SECONDS, result)
    return result
