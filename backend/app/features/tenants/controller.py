"""Tenant handlers: request orchestration for the tenants + public routers.

The HTTP-facing logic that moved out of api/tenants.py and api/public.py:
turning service results into responses and service errors into HTTP statuses.
Routers and their request/response schemas live in api.py / public_api.py.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status

from app.features.tenants import service
from app.services import context_package

logger = logging.getLogger(__name__)

_preload_tasks: set[asyncio.Task[None]] = set()


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

    P-3: this is the request the customer page makes as it loads, which makes it
    the moment the chat opens - so it also warms the tenant's context package.
    The assembly runs behind the response (nothing awaits it) because a page
    load must never wait on it, and a failure costs a cold first message, not an
    error.
    """
    result = await service.resolve_slug(slug)
    if result is not None and result["status"] == "active":
        _preload_package(result["id"])
    return result


def _preload_package(tenant_id: UUID) -> None:
    task = asyncio.create_task(context_package.prime(tenant_id))
    # asyncio only holds a weak reference to a running task, so a fire-and-forget
    # task can be garbage collected mid-flight; keeping it in a set until it is
    # done is the documented way to stop that.
    _preload_tasks.add(task)
    task.add_done_callback(_preload_tasks.discard)
