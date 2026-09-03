"""T-004/T-033: the platform-owner surface (admin.wren.app).

Deliberately minimal per frontend.md 7.3: one tenants table with aggregate
metrics and suspend/reactivate - "nothing else at core
scope". Handlers live in controller.py, persistence in service.py.

Tenant creation remains owner-driven through the self-onboarding surface.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, field_validator

from app.features.platform import controller
from app.shared import auth

router = APIRouter(prefix="/api/platform", tags=["platform"])

_VALID_STATUSES = frozenset({"provisioning", "active", "suspended"})


class TenantSummary(BaseModel):
    id: UUID
    slug: str
    name: str
    status: str
    created_at: datetime
    conversation_count: int
    cost_usd: float


class PlatformMetrics(BaseModel):
    tenant_count: int
    total_cost_usd: float


class UpdateTenantStatusRequest(BaseModel):
    status: str

    @field_validator("status")
    @classmethod
    def _valid_status(cls, value: str) -> str:
        if value not in _VALID_STATUSES:
            raise ValueError(f"status must be one of {sorted(_VALID_STATUSES)}")
        return value


@router.get("/ping")
async def ping(
    _admin: Annotated[auth.AuthedPlatformAdmin, Depends(auth.require_platform_admin)],
) -> dict[str, bool]:
    return await controller.ping()


@router.get("/metrics", response_model=PlatformMetrics)
async def get_metrics(
    _admin: Annotated[auth.AuthedPlatformAdmin, Depends(auth.require_platform_admin)],
) -> PlatformMetrics:
    return PlatformMetrics(**await controller.metrics())


@router.get("/tenants", response_model=list[TenantSummary])
async def list_tenants(
    _admin: Annotated[auth.AuthedPlatformAdmin, Depends(auth.require_platform_admin)],
) -> list[TenantSummary]:
    return [TenantSummary(**row) for row in await controller.list_tenants()]


@router.patch("/tenants/{tenant_id}", response_model=TenantSummary)
async def update_tenant_status(
    tenant_id: UUID,
    body: UpdateTenantStatusRequest,
    admin: Annotated[auth.AuthedPlatformAdmin, Depends(auth.require_platform_admin)],
) -> TenantSummary:
    row = await controller.update_status(
        actor_user_id=str(admin.user_id), tenant_id=str(tenant_id), new_status=body.status
    )
    assert row is not None
    return TenantSummary(**row)
