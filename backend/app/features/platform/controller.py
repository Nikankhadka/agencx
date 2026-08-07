"""Platform-owner handlers: orchestrate the platform service into HTTP results.

Handler logic that moved out of api/platform.py - every query runs without a
tenant scope (platform_admin RLS), so these are thin: call the service, map
errors to statuses, log audited actions. Routers + schemas live in api.py.
"""

from __future__ import annotations

import logging
from typing import Any

import asyncpg
from fastapi import HTTPException, status

from app.features.platform import service
from app.features.tenants.service import invalidate_slug_cache

logger = logging.getLogger(__name__)


async def ping() -> dict[str, bool]:
    return {"ok": True}


async def metrics() -> dict[str, Any]:
    return await service.metrics()


async def list_tenants() -> list[dict[str, Any]]:
    return await service.list_tenants()


async def check_slug_availability(slug: str) -> bool:
    return await service.slug_available(slug)


async def provision(*, actor_user_id: str, slug: str, name: str) -> dict[str, Any]:
    try:
        tenant_id = await service.provision(slug=slug, name=name)
    except asyncpg.UniqueViolationError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="slug already taken"
        ) from exc

    logger.info(
        "audited platform action: tenant_provisioned",
        extra={
            "action": "tenant_provisioned",
            "actor_user_id": actor_user_id,
            "tenant_id": tenant_id,
            "slug": slug,
            "role": "platform_admin",
        },
    )
    return {"id": tenant_id, "slug": slug, "name": name, "status": "provisioning"}


async def update_status(
    *, actor_user_id: str, tenant_id: str, new_status: str
) -> dict[str, Any] | None:
    row = await service.update_status(tenant_id, new_status)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="tenant not found")

    # The customer surface caches positive slug resolutions for 60s
    # (tenants/service.py) - a suspend/reactivate from this surface must be
    # visible immediately, so invalidate the one slug that changed.
    invalidate_slug_cache(row["slug"])

    logger.info(
        "audited platform action: tenant_status_changed",
        extra={
            "action": "tenant_status_changed",
            "actor_user_id": actor_user_id,
            "tenant_id": str(tenant_id),
            "new_status": new_status,
            "role": "platform_admin",
        },
    )
    return row
