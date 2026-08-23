"""T-004/T-033: the platform-owner surface (admin.wren.app).

Deliberately minimal per frontend.md 7.3: one tenants table with aggregate
metrics, a provision flow, and suspend/reactivate - "nothing else at core
scope". Handlers live in controller.py, persistence in service.py.

KNOWN GAP (flagged, not solved here - see .agents/memory.md T-033): a
platform-admin-provisioned tenant has no owner (no ``users`` row) because
creating a Supabase auth user server-side needs Admin API credentials this
project doesn't have yet (no hosted Supabase project - same gap as T-004/T-006).
Provisioned tenants land in status='provisioning' until a founder decision on
the claim mechanism.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field, field_validator

from app.features.platform import controller
from app.features.platform.service import PROVISION_NOTE
from app.features.tenants.slug import validate_slug
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


class ProvisionTenantRequest(BaseModel):
    slug: str = Field(min_length=3, max_length=40)
    name: str = Field(min_length=1, max_length=120)

    _check_slug = field_validator("slug")(validate_slug)


class ProvisionTenantResponse(BaseModel):
    id: UUID
    slug: str
    name: str
    status: str
    note: str


class SlugAvailabilityResponse(BaseModel):
    available: bool


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


@router.get("/tenants/slug-availability", response_model=SlugAvailabilityResponse)
async def check_slug_availability(
    _admin: Annotated[auth.AuthedPlatformAdmin, Depends(auth.require_platform_admin)],
    slug: Annotated[str, Query(min_length=1, max_length=40)],
) -> SlugAvailabilityResponse:
    return SlugAvailabilityResponse(available=await controller.check_slug_availability(slug))


@router.post(
    "/tenants", response_model=ProvisionTenantResponse, status_code=status.HTTP_201_CREATED
)
async def provision_tenant(
    body: ProvisionTenantRequest,
    admin: Annotated[auth.AuthedPlatformAdmin, Depends(auth.require_platform_admin)],
) -> ProvisionTenantResponse:
    result = await controller.provision(
        actor_user_id=str(admin.user_id), slug=body.slug, name=body.name
    )
    return ProvisionTenantResponse(**result, note=PROVISION_NOTE)


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
