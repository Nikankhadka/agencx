"""O-2: the unauthenticated login-in-chat endpoints.

``POST /api/auth/login-code`` sends a code to an email; ``POST
/api/auth/verify-code`` exchanges a code for a session. Both are pre-auth, so
neither carries a bearer dependency - tenant scope is established only after
verification.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field, field_validator

from app.features.auth import controller
from app.services import email as email_service
from app.services import email_address
from app.shared.config import get_settings

router = APIRouter(prefix="/api/auth", tags=["auth"])

# What the owner types is conversational, so the request body accepts free text
# and app.services.email_address is the authority on whether it holds an
# address. A Pydantic validator here would answer a typo with a 422 validation
# dump; the thread needs one calm line instead.
_EMAIL_PROBLEM_COPY = {
    "missing": "I could not find an email address in that. What is the best one to reach you on?",
    "malformed": "That email does not look quite right. Mind checking it?",
}


class LoginCodeRequest(BaseModel):
    """Raw typed text, not a validated address - see ``_resolve_email``."""

    email: str = Field(min_length=1, max_length=320)


def _resolve_email(raw: str) -> str:
    """Normalize typed text to an address, or refuse it conversationally."""
    check = email_address.extract(raw)
    if check.address is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_EMAIL_PROBLEM_COPY[check.problem or "malformed"],
        )
    return check.address


class VerifyCodeRequest(BaseModel):
    email: str = Field(min_length=1, max_length=320)
    code: str = Field(min_length=6, max_length=6)

    @field_validator("code")
    @classmethod
    def _digits(cls, value: str) -> str:
        if not value.isdigit():
            raise ValueError("code must be six digits")
        return value


class LoginCodeResponse(BaseModel):
    """The address the code was actually sent to, after normalization.

    The owner may have typed a sentence, or odd casing; echoing the resolved
    address back is what lets the thread say where to look for the code without
    the client having to re-derive it (and risk disagreeing with the server).
    """

    email: str


class VerifyCodeResponse(BaseModel):
    access_token: str
    user_id: str
    tenant_id: str


@router.post("/login-code", status_code=status.HTTP_202_ACCEPTED)
async def login_code(body: LoginCodeRequest) -> LoginCodeResponse:
    # Deliberately returns 202 for every syntactically valid email, whether or
    # not an account exists - no account-existence leak (US-2). Only unreadable
    # text is refused, and that refusal says nothing about any account.
    email = _resolve_email(body.email)
    await controller.send_login_code(email=email)
    return LoginCodeResponse(email=email)


@router.post("/verify-code", response_model=VerifyCodeResponse)
async def verify_code(body: VerifyCodeRequest) -> VerifyCodeResponse:
    if not body.code.isdigit():
        raise HTTPException(status_code=400, detail="code must be six digits")
    # Normalized the same way as on issue, so the two agree on one key.
    result = await controller.verify_login_code(email=_resolve_email(body.email), code=body.code)
    return VerifyCodeResponse(**result)


@router.get("/dev-login-code")
async def dev_login_code(email: str) -> dict[str, str]:
    """Local-dev only: return the last issued code for ``email``.

    Backs the demo's captured-code path and the E2E login-in-chat flow. Gated to
    the local environment so a real deployment can never expose codes.
    """
    if get_settings().environment != "local":
        raise HTTPException(status_code=404, detail="not found")
    code = email_service.last_issued_code(_resolve_email(email))
    if code is None:
        raise HTTPException(status_code=404, detail="no code issued for this email")
    return {"code": code}
