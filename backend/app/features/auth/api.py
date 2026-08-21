"""O-2: the unauthenticated login-in-chat endpoints.

``POST /api/auth/login-code`` sends a code to an email; ``POST
/api/auth/verify-code`` exchanges a code for a session. Both are pre-auth, so
neither carries a bearer dependency - tenant scope is established only after
verification.
"""

from __future__ import annotations

import re

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field, field_validator

from app.features.auth import controller
from app.services import email as email_service
from app.shared.config import get_settings

router = APIRouter(prefix="/api/auth", tags=["auth"])

# A deliberately loose email shape - enough to reject obvious junk without
# depending on email-validator. The frontend gates send on the same shape.
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class LoginCodeRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)

    @field_validator("email")
    @classmethod
    def _valid_email(cls, value: str) -> str:
        if not _EMAIL_RE.fullmatch(value):
            raise ValueError("enter a valid email address")
        return value


class VerifyCodeRequest(BaseModel):
    email: str
    code: str = Field(min_length=6, max_length=6)

    @field_validator("code")
    @classmethod
    def _digits(cls, value: str) -> str:
        if not value.isdigit():
            raise ValueError("code must be six digits")
        return value


class VerifyCodeResponse(BaseModel):
    access_token: str
    user_id: str
    tenant_id: str


@router.post("/login-code", status_code=status.HTTP_202_ACCEPTED)
async def login_code(body: LoginCodeRequest) -> None:
    # Deliberately returns 202 for every syntactically valid email, whether or
    # not an account exists - no account-existence leak (US-2).
    await controller.send_login_code(email=body.email)


@router.post("/verify-code", response_model=VerifyCodeResponse)
async def verify_code(body: VerifyCodeRequest) -> VerifyCodeResponse:
    if not body.code.isdigit():
        raise HTTPException(status_code=400, detail="code must be six digits")
    result = await controller.verify_login_code(email=body.email, code=body.code)
    return VerifyCodeResponse(**result)


@router.get("/dev-login-code")
async def dev_login_code(email: str) -> dict[str, str]:
    """Local-dev only: return the last issued code for ``email``.

    Backs the demo's captured-code path and the E2E login-in-chat flow. Gated to
    the local environment so a real deployment can never expose codes.
    """
    if get_settings().environment != "local":
        raise HTTPException(status_code=404, detail="not found")
    code = email_service.last_issued_code(email)
    if code is None:
        raise HTTPException(status_code=404, detail="no code issued for this email")
    return {"code": code}
