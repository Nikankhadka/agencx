"""T-004: tenant provisioning and the authed tenant-admin "me" probe.

``POST /api/tenants`` is the one legitimate caller of ``app.role = 'service'``
(database.md section 2.3, Shape C). Two shapes share it: an explicit
``slug``/``name`` body (the seed scripts' signup path - provisions and 409s if
the user already has a tenant or the slug is taken), and an empty body
(login-in-chat's first-login call, made on every sign-in - provisions a
provisional tenant on the first call, returns the existing one on every call
after). Handlers live in controller.py, persistence in service.py.
"""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel, Field, field_validator

from app.features.tenants import controller
from app.features.tenants.slug import validate_slug
from app.shared import auth

router = APIRouter(prefix="/api/tenants", tags=["tenants"])


class TenantSignupRequest(BaseModel):
    """Both fields absent is the login-in-chat provisioning shape - see the
    module docstring and ``controller.signup``."""

    slug: str | None = Field(default=None, min_length=3, max_length=40)
    name: str | None = Field(default=None, min_length=1, max_length=120)

    @field_validator("slug")
    @classmethod
    def _check_slug(cls, value: str | None) -> str | None:
        return value if value is None else validate_slug(value)


class TenantSignupResponse(BaseModel):
    tenant_id: UUID
    slug: str


class TenantMeResponse(BaseModel):
    tenant_id: UUID
    slug: str
    name: str
    brand: dict[str, Any] = Field(default_factory=dict)


@router.post("", response_model=TenantSignupResponse)
async def signup(
    body: TenantSignupRequest,
    response: Response,
    caller: Annotated[auth.AuthedUser, Depends(auth.authenticate_with_email)],
) -> TenantSignupResponse:
    result = await controller.signup(
        user_id=str(caller.user_id), email=caller.email, slug=body.slug, name=body.name
    )
    response.status_code = status.HTTP_201_CREATED if result["created"] else status.HTTP_200_OK
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
