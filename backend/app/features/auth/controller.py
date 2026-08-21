"""O-2: login-in-chat orchestration.

Sends and verifies the 6-digit email code, then turns a verified code into a
real session. Deterministic throughout - no model is involved. The tenant
provisioning on first login (a provisional slug/name from the email, finalized
at go-live by O-1) keeps the existing ``require_tenant_admin`` auth and
onboarding persistence unchanged.
"""

from __future__ import annotations

import re
import secrets
from typing import Any

from fastapi import HTTPException, status

from app.features.tenants import service as tenants_service
from app.services import auth_codes, identity
from app.services import email as email_service
from app.shared import db
from app.shared.config import get_settings

_COPY = {
    "invalid": "That code didn't work. Try again, or resend.",
    "expired": "That code expired. Request a new one.",
    "too_many": "Too many tries. Request a new code.",
}

_SLUGIFY_RE = re.compile(r"[^a-z0-9]+")


def _slugify(text: str) -> str:
    slug = _SLUGIFY_RE.sub("-", text.lower()).strip("-")
    return slug or "biz"


def _provisional_slug(email: str) -> str:
    local = email.split("@", 1)[0]
    suffix = "".join(secrets.choice("abcdefghijklmnopqrstuvwxyz0123456789") for _ in range(4))
    return f"{_slugify(local)[:30]}-{suffix}"


async def _find_tenant_for_user(user_id: str) -> str | None:
    pool = db.get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("select tenant_id from resolve_user_tenant($1)", user_id)
    return str(row["tenant_id"]) if row is not None else None


async def send_login_code(email: str) -> None:
    code = await auth_codes.issue_code(email=email)
    provider = email_service.get_email_provider()
    await provider.send_login_code(email=email, code=code)


async def verify_login_code(email: str, code: str) -> dict[str, Any]:
    try:
        await auth_codes.verify_code(email=email, code=code)
    except auth_codes.CodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=_COPY[exc.kind]
        ) from exc

    user_id = await identity.ensure_auth_user(email)
    tenant_id = await _find_tenant_for_user(user_id)
    if tenant_id is None:
        # First login: provision a provisional tenant so the interview (O-1)
        # can run under the existing tenant-admin auth. The real name/slug are
        # written over these at go-live.
        tenant_id = await tenants_service.create_tenant(
            user_id=user_id,
            slug=_provisional_slug(email),
            name=email.split("@", 1)[0],
        )

    secret = get_settings().supabase_jwt_secret
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="auth misconfigured",
        )
    access_token = identity.mint_session(user_id=user_id, email=email, secret=secret)
    return {"access_token": access_token, "user_id": user_id, "tenant_id": tenant_id}
