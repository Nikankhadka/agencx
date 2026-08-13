"""Tenant handlers: request orchestration for the tenants + public routers.

The HTTP-facing logic that moved out of api/tenants.py and api/public.py:
turning service results into responses and service errors into HTTP statuses.
Routers and their request/response schemas live in api.py / public_api.py.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import HTTPException, status

from app.features.tenants import service

logger = logging.getLogger(__name__)


async def signup(*, user_id: str, slug: str, name: str) -> dict[str, str]:
    """POST /api/tenants - provision a tenant for an authenticated user.

    The one legitimate caller of ``app.role = 'service'``: the frontend signs a
    user up with Supabase first, then calls this endpoint with that user's
    access token. Every call is logged as an audited service action (actor user
    id + action), per T-004.
    """
    try:
        tenant_id = await service.create_tenant(user_id=user_id, slug=slug, name=name)
    except service.TenantAlreadyExistsError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    logger.info(
        "audited service action: tenant_signup",
        extra={
            "action": "tenant_signup",
            "actor_user_id": user_id,
            "tenant_id": tenant_id,
            "slug": slug,
            "role": "service",
        },
    )
    return {"tenant_id": tenant_id, "slug": slug}


async def me(*, tenant_id: str) -> dict[str, Any]:
    """GET /api/tenants/me - the authed tenant-admin's own slug + name + brand."""
    row = await service.get_tenant(tenant_id)
    if row is None:
        # Should not happen for a resolved tenant_admin (FK guarantees the
        # tenant row exists), but fail closed rather than return a null body.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="tenant not found")
    return {"tenant_id": tenant_id, "slug": row["slug"], "name": row["name"], "brand": row["brand"]}


async def resolve_public(slug: str) -> dict[str, Any] | None:
    """GET /api/public/tenant/{slug} - the pre-auth customer-surface lookup.

    Unknown slugs are None (the caller turns it into a 404); known slugs come
    back with their status (including ``suspended``) so the frontend renders
    the right customer-surface state rather than treating a suspended tenant
    as an error.
    """
    return await service.resolve_slug(slug)
