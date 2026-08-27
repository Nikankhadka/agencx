"""Tenant handlers: request orchestration for the tenants + public routers.

The HTTP-facing logic that moved out of api/tenants.py and api/public.py:
turning service results into responses and service errors into HTTP statuses.
Routers and their request/response schemas live in api.py / public_api.py.
"""

from __future__ import annotations

import asyncio
import logging
import re
import secrets
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status

from app.features.tenants import service
from app.services import context_package

logger = logging.getLogger(__name__)

_preload_tasks: set[asyncio.Task[None]] = set()

_SLUGIFY_RE = re.compile(r"[^a-z0-9]+")


def _slugify(text: str) -> str:
    slug = _SLUGIFY_RE.sub("-", text.lower()).strip("-")
    return slug or "biz"


def _provisional_slug(email: str | None) -> str:
    """A first-login tenant's throwaway slug: readable, unique, never
    real - the onboarding interview (O-1) overwrites it. Named after the
    owner's email when there is one (there always is one for an OTP login;
    the fallback only guards a token with no email claim)."""
    local = (email or "biz").split("@", 1)[0]
    suffix = "".join(secrets.choice("abcdefghijklmnopqrstuvwxyz0123456789") for _ in range(4))
    return f"{_slugify(local)[:30]}-{suffix}"


def _provisional_name(email: str | None) -> str:
    return (email or "New business").split("@", 1)[0]


async def _existing_tenant_result(tenant_id: str) -> dict[str, Any]:
    row = await service.get_tenant(tenant_id)
    if row is None:
        # Should not happen (FK guarantees the tenant row exists) - fail
        # closed exactly like `me()` below does for the same case.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="tenant not found")
    return {"tenant_id": tenant_id, "slug": row["slug"], "created": False}


async def signup(
    *, user_id: str, email: str | None, slug: str | None, name: str | None
) -> dict[str, Any]:
    """POST /api/tenants - provision a tenant for an authenticated user, or
    hand back the one they already have.

    Two shapes share this endpoint:

    - Explicit (``slug``/``name`` given): the seed scripts' signup path. 409s
      if the user already has a tenant or the slug is taken - the same
      behavior this endpoint always had.
    - Provisioning (both absent): login-in-chat's call, made on every
      sign-in. Returns the caller's existing tenant (``created=False``) when
      they have one; otherwise creates one named after their email
      (``created=True``) - the onboarding interview (O-1) overwrites the real
      name/slug later.

    Every create is logged as an audited service action (actor user id +
    action), per T-004.
    """
    provisioning = slug is None and name is None

    if provisioning:
        existing_id = await service.find_tenant_for_user(user_id)
        if existing_id is not None:
            return await _existing_tenant_result(existing_id)
        slug = _provisional_slug(email)
        name = _provisional_name(email)
    elif slug is None or name is None:
        # Neither shape: a body with one of the two fields but not the other.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="slug and name must both be given, or both omitted",
        )

    try:
        tenant_id = await service.create_tenant(user_id=user_id, slug=slug, name=name)
    except service.TenantAlreadyExistsError as exc:
        if not provisioning:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
        # A concurrent double-login raced the pre-check (users_pkey) - not a
        # real conflict from this caller's perspective, just "give me my
        # tenant" arriving twice at once. The row exists now; fetch it.
        existing_id = await service.find_tenant_for_user(user_id)
        if existing_id is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="tenant provisioning failed unexpectedly",
            ) from exc
        return await _existing_tenant_result(existing_id)

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
    return {"tenant_id": tenant_id, "slug": slug, "created": True}


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
