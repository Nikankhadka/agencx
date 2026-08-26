"""O-2: identity - ensure the Supabase auth user exists and mint a session token.

Sessions are ours, not GoTrue's: we sign them HS256 with ``SUPABASE_JWT_SECRET``
and ``verify_token`` (app/shared/auth.py) verifies them with the same key, so no
GoTrue session table is involved in the backend bearer flow. That secret is
therefore just this app's session-signing key - on a hosted project that signs
sessions asymmetrically (ES256) it need not match anything Supabase holds.

``ensure_auth_user`` keeps the auth user real: it find-or-creates the
``auth.users`` row through GoTrue's Admin API (the same path the demo seed uses),
so ``users.id = auth.users.id`` holds for every login. In production the same
call runs against the hosted Supabase admin API (env-config'd); the local demo
points it at the GoTrue auth-proxy.
"""

from __future__ import annotations

import time

import httpx
import jwt

from app.shared.config import Settings, get_settings

# Same far-future shape as the role keys in seeds/supabase_keys.py: a service
# token presented to GoTrue's Admin API, never to our backend.
_SERVICE_TOKEN_EXPIRES_IN = 10 * 365 * 24 * 60 * 60


def mint_session(*, user_id: str, email: str, secret: str, expires_in: int = 3600) -> str:
    """Mint a Supabase-style user access token (HS256) for ``user_id``.

    Claims match what GoTrue issues: ``sub``, ``email``, ``aud=authenticated``,
    ``role=authenticated``, ``iat``, ``exp``. The backend's ``verify_token``
    validates the same claims GoTrue tokens carry.
    """
    now = int(time.time())
    payload = {
        "sub": user_id,
        "email": email,
        "aud": "authenticated",
        "role": "authenticated",
        "iat": now,
        "exp": now + expires_in,
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def _service_token(secret: str) -> str:
    now = int(time.time())
    payload = {
        "role": "service_role",
        "iss": "supabase",
        "iat": now,
        "exp": now + _SERVICE_TOKEN_EXPIRES_IN,
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def _admin_credential(settings: Settings) -> str:
    """The credential GoTrue's Admin API accepts for this deployment.

    Hosted Supabase projects created since the move to asymmetric (ES256)
    session signing do not validate a token we mint ourselves - there is no
    shared symmetric secret behind their signing key - so the project's real
    ``service_role`` key is the only thing that works. The local auth-proxy is
    the older symmetric world (see seeds/supabase_keys.py) and has no such key,
    so minting stays the fallback and ``make dev`` is unaffected.
    """
    return settings.supabase_service_role_key or _service_token(settings.supabase_jwt_secret)


async def _find_user_by_email(
    client: httpx.AsyncClient, base: str, headers: dict[str, str], email: str
) -> str | None:
    page = 1
    while True:
        resp = await client.get(
            f"{base}/auth/v1/admin/users",
            params={"page": page, "per_page": 1000},
            headers=headers,
        )
        resp.raise_for_status()
        data = resp.json()
        users = data.get("users", []) if isinstance(data, dict) else data
        for user in users:
            if user.get("email") == email and user.get("id"):
                return str(user["id"])
        if isinstance(data, dict):
            if not data.get("has_next") or not users:
                break
        elif not users:
            break
        page += 1
    return None


async def ensure_auth_user(email: str) -> str:
    """Find-or-create the Supabase auth user for ``email``; return its id.

    Raises ``RuntimeError`` when Supabase/GoTrue is not reachable or the auth
    settings are unset (the demo path - run scripts/demo.sh first).
    """
    settings = get_settings()
    base = settings.supabase_url.rstrip("/")
    secret = settings.supabase_jwt_secret
    if not base or not secret:
        raise RuntimeError(
            "SUPABASE_URL and SUPABASE_JWT_SECRET must be set to verify a login "
            "code (run scripts/demo.sh, or inject ensure_auth_user in tests)."
        )
    service = _admin_credential(settings)
    headers = {
        "Authorization": f"Bearer {service}",
        "apikey": service,
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=30) as client:
        existing = await _find_user_by_email(client, base, headers, email)
        if existing is not None:
            return existing
        resp = await client.post(
            f"{base}/auth/v1/admin/users",
            json={"email": email, "email_confirm": True},
            headers=headers,
        )
        if resp.status_code in (200, 201):
            return str(resp.json()["id"])
        existing = await _find_user_by_email(client, base, headers, email)
        if existing is not None:
            return existing
        resp.raise_for_status()
        raise RuntimeError(f"unexpected GoTrue admin create response: {resp.status_code}")
