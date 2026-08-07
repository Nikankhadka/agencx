"""T-004: tenant signup and the authed tenant-admin "me" probe.

``POST /api/tenants`` is the one legitimate caller of ``app.role = 'service'``
(database.md section 2.3, Shape C): the frontend signs a user up with Supabase
first, then calls this endpoint with that user's access token to provision the
tenant/tenant_config/users rows in a single transaction. Handlers live in
controller.py, persistence in service.py.
"""

from __future__ import annotations

import re
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field, field_validator

from app.features.tenants import controller
from app.shared import auth

router = APIRouter(prefix="/api/tenants", tags=["tenants"])

# Mirrors the DDL check on tenants.slug (database.md section 3) exactly, so a
# bad slug is rejected at the API layer (422) before it can reach the insert.
_SLUG_RE = re.compile(r"^[a-z0-9](-?[a-z0-9])*$")


class TenantSignupRequest(BaseModel):
    slug: str = Field(min_length=3, max_length=40)
    name: str = Field(min_length=1, max_length=120)

    @field_validator("slug")
    @classmethod
    def _valid_slug(cls, value: str) -> str:
        if not _SLUG_RE.fullmatch(value):
            raise ValueError("slug must match ^[a-z0-9](-?[a-z0-9])*$")
        return value


class TenantSignupResponse(BaseModel):
    tenant_id: UUID
    slug: str


class TenantMeResponse(BaseModel):
    tenant_id: UUID
    slug: str
    name: str


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
    )
