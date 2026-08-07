"""T-005: unauthenticated slug -> tenant resolution for the customer surface.

``GET /api/public/tenant/{slug}`` is the one pre-auth read the customer surface
needs before any ``tenant_context`` exists: it goes through ``resolve_tenant_slug``
(resolver, migration 0003), the sole wren_resolver-owned RLS bypass, matching the
pattern ``auth.py`` already uses for ``resolve_user_tenant`` / ``resolve_platform_admin``.
Unknown slugs are 404; known slugs return 200 with their ``status`` (including
``suspended``) so the frontend renders the right customer-surface state rather
than treating a suspended tenant as an error. T-032 adds ``customer``: the
tenant-configured greeting and starter questions the empty-conversation state
renders. Resolution + cache live in service.py; the cache is invalidated by
platform's suspend/reactivate (``invalidate_slug_cache``).
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.features.tenants import controller

router = APIRouter(prefix="/api/public", tags=["public"])


class TenantResolveResponse(BaseModel):
    id: UUID
    name: str
    status: str
    brand: dict[str, Any]
    customer: dict[str, Any]


@router.get("/tenant/{slug}", response_model=TenantResolveResponse)
async def resolve_tenant(slug: str) -> TenantResolveResponse:
    result = await controller.resolve_public(slug)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="unknown tenant slug")
    return TenantResolveResponse(**result)
