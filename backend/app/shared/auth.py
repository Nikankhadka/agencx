"""T-004: Supabase JWT verification and the tenant/platform-admin auth dependencies.

Local GoTrue signs HS256 with the project's shared secret
(``settings.supabase_jwt_secret``); hosted Supabase projects sign asymmetrically
(ES256, and RS256 on older projects) - there is no shared secret to verify those
against, only the project's published JWKS. ``verify_token`` reads the token's
own `alg` header and picks the matching verification path; both agree on
audience ``authenticated`` and a `sub` that is the Supabase ``auth.users.id``.
This module turns a verified token into one of two authenticated-principal
dataclasses, each backed by a pre-context lookup that runs through the resolver
functions from migration 0009 (``resolve_user_tenant``, ``resolve_platform_admin``)
- the one legitimate way to read `users` / `platform_admins` before any
``tenant_context`` exists, mirroring ``resolve_tenant_slug`` (0003). See
database.md sections 2 and 3.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import lru_cache
from typing import Annotated
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.shared import db
from app.shared.config import get_settings

logger = logging.getLogger(__name__)

# Supabase access tokens always carry this audience; verifying it is part of
# validating the token, not an optional extra.
SUPABASE_AUDIENCE = "authenticated"
SUPABASE_JWT_ALGORITHMS = frozenset({"HS256", "ES256", "RS256"})

_bearer_scheme = HTTPBearer(auto_error=False)


@lru_cache
def _jwks_client(supabase_url: str) -> jwt.PyJWKClient:
    """One cached client per ``SUPABASE_URL`` - it keeps its own key cache and
    handles rotation, so this only ever runs the discovery fetch once per
    process rather than once per request.
    """
    return jwt.PyJWKClient(f"{supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json")


class AuthConfigError(RuntimeError):
    """Raised when SUPABASE_JWT_SECRET is unset or empty.

    Deliberately distinct from an auth failure: an empty secret must never fall
    back to unsigned/"none" verification, and the caller (a misconfigured
    deployment) should see a 500, not a misleading 401.
    """


@dataclass(frozen=True)
class AuthedTenantAdmin:
    user_id: UUID
    tenant_id: UUID


@dataclass(frozen=True)
class AuthedPlatformAdmin:
    user_id: UUID


def _decode_claims(token: str) -> dict[str, object]:
    """Verify a Supabase access token and return its decoded claims.

    Reads the token's own ``alg`` header to pick the verification path: local
    GoTrue signs HS256 with the shared secret; hosted Supabase signs
    asymmetrically (ES256, or RS256 on older projects), which has no shared
    secret to check against, only the project's JWKS. Both paths require the
    same ``aud``/``exp`` shape - only the key material differs.

    Raises ``AuthConfigError`` if HS256 is used and the JWT secret is not
    configured, and ``HTTPException(401)`` for any invalid/expired/wrong-
    audience token or an unreachable JWKS endpoint.
    """
    settings = get_settings()
    try:
        alg = jwt.get_unverified_header(token).get("alg")
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid or expired token"
        ) from exc
    if alg not in SUPABASE_JWT_ALGORITHMS:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="token uses an unsupported algorithm",
        )

    # ``exp`` is only validated by PyJWT when present; require it so a token
    # minted without one can never be accepted as a forever-valid credential.
    # ``aud`` is effectively required by passing ``audience=`` (this is also
    # what rejects the public anon / service_role API keys, which are signed
    # with the same secret but carry no ``aud`` claim). Written out at each
    # call site, not shared via a splatted dict: `jwt.decode`'s keyword types
    # vary per argument, which a single heterogeneous dict can't express.
    try:
        if alg == "HS256":
            secret = settings.supabase_jwt_secret
            if not secret:
                raise AuthConfigError("SUPABASE_JWT_SECRET is not configured")
            payload = jwt.decode(
                token,
                secret,
                algorithms=["HS256"],
                audience=SUPABASE_AUDIENCE,
                options={"require": ["exp"]},
            )
        else:
            if not settings.supabase_url:
                raise AuthConfigError("SUPABASE_URL is not configured")
            signing_key = _jwks_client(settings.supabase_url).get_signing_key_from_jwt(token)
            payload = jwt.decode(
                token,
                signing_key,
                algorithms=[alg],
                audience=SUPABASE_AUDIENCE,
                options={"require": ["exp"]},
            )
    except AuthConfigError:
        raise
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid or expired token"
        ) from exc

    return payload


def _claims_user_id(payload: dict[str, object]) -> UUID:
    sub = payload.get("sub")
    if not sub:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="token missing sub")
    try:
        return UUID(str(sub))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="token sub is not a valid user id"
        ) from exc


def verify_token(token: str) -> UUID:
    """Verify a Supabase access token and return the user id (`sub` claim).

    Raises ``AuthConfigError`` if the relevant key material is not configured,
    and ``HTTPException(401)`` for any invalid/expired/wrong-audience token.
    """
    return _claims_user_id(_decode_claims(token))


async def authenticate(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
) -> UUID:
    """Bare authentication: verify the bearer token, return the user id.

    Used directly by routes that need an authenticated caller but resolve
    tenant/platform membership themselves rather than through one of the
    dependencies below.
    """
    if credentials is None or not credentials.credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing bearer token")
    try:
        return verify_token(credentials.credentials)
    except AuthConfigError as exc:
        logger.error("auth config error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="auth misconfigured"
        ) from exc


@dataclass(frozen=True)
class AuthedUser:
    """An authenticated caller's identity, email included.

    Distinct from the bare ``UUID`` ``authenticate`` returns: only the one
    caller that needs the email (tenant provisioning, to name a first-login
    tenant after its owner) pays for decoding it.
    """

    user_id: UUID
    email: str | None


async def authenticate_with_email(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
) -> AuthedUser:
    """Like ``authenticate``, but returns the token's email claim too."""
    if credentials is None or not credentials.credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing bearer token")
    try:
        payload = _decode_claims(credentials.credentials)
    except AuthConfigError as exc:
        logger.error("auth config error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="auth misconfigured"
        ) from exc
    email = payload.get("email")
    return AuthedUser(user_id=_claims_user_id(payload), email=str(email) if email else None)


async def require_tenant_admin(
    user_id: Annotated[UUID, Depends(authenticate)],
) -> AuthedTenantAdmin:
    """Authenticate, then resolve the caller's ``users`` row -> tenant membership.

    403 when the token is valid but the user has no ``users`` row (never signed
    up / not a member of any tenant).
    """
    pool = db.get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("select tenant_id, role from resolve_user_tenant($1)", user_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="no tenant membership for this user"
        )
    return AuthedTenantAdmin(user_id=user_id, tenant_id=row["tenant_id"])


async def require_platform_admin(
    user_id: Annotated[UUID, Depends(authenticate)],
) -> AuthedPlatformAdmin:
    """Authenticate, then check ``platform_admins`` membership.

    403 when the token is valid but the user has no ``platform_admins`` row.
    """
    pool = db.get_pool()
    async with pool.acquire() as conn:
        is_admin = await conn.fetchval("select resolve_platform_admin($1)", user_id)
    if not is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="not a platform admin")
    return AuthedPlatformAdmin(user_id=user_id)
