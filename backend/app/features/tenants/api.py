"""T-004: tenant signup and the authed tenant-admin "me" probe.

``POST /api/tenants`` is the one legitimate caller of ``app.role = 'service'``
(database.md section 2.3, Shape C): the frontend signs a user up with Supabase
first, then calls this endpoint with that user's access token to provision the
tenant/tenant_config/users rows in a single transaction. Handlers live in
controller.py, persistence in service.py.
"""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field, field_validator

from app.features.tenants import controller
from app.features.tenants.slug import validate_slug
from app.shared import auth

router = APIRouter(prefix="/api/tenants", tags=["tenants"])


class TenantSignupRequest(BaseModel):
    slug: str = Field(min_length=3, max_length=40)
    name: str = Field(min_length=1, max_length=120)

    _check_slug = field_validator("slug")(validate_slug)


class TenantSignupResponse(BaseModel):
    tenant_id: UUID
    slug: str


class TenantMeResponse(BaseModel):
    tenant_id: UUID
    slug: str
    name: str
    brand: dict[str, Any] = Field(default_factory=dict)


@router.post("", response_model=TenantSignupResponse, status_code=status.HTTP_201_CREATED)
async def signup(
    body: TenantSignupRequest,
    user_id: Annotated[UUID, Depends(auth.authenticate)],
) -> TenantSignupResponse:
    result = await controller.signup(user_id=str(user_id), slug=body.slug, name=body.name)
    return TenantSignupResponse(tenant_id=UUID(result["tenant_id"]), slug=result["slug"])


@router.get("/me", response_model=TenantMeResponse)
async def me(
    admin: Annotated[auth.AuthedTenantAdmin, Depends(auth.require_tenant_admin)],
) -> TenantMeResponse:
    result = await controller.me(tenant_id=str(admin.tenant_id))
    return TenantMeResponse(
        tenant_id=UUID(result["tenant_id"]),
        slug=result["slug"],
        name=result["name"],
        brand=result["brand"],
    )
