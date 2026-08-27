"""T-004: Supabase auth + tenant-context middleware, exercised at the API level.

Uses httpx's ``ASGITransport`` against the real app (no lifespan - the app pool is
created/closed by the ``client`` fixture below, pointed at ``wren_test`` via the
wren_app-role DSN from ``tests.conftest._app_dsn_for``, matching test_rls.py's
pattern). HS256 JWTs are minted locally with a fixed test secret injected into
``Settings`` before any code path can call the lru_cached ``get_settings()`` with
the real (empty, in ``.env``) one. ES256 tokens are minted with a throwaway EC
keypair and verified against a stubbed JWKS endpoint - see the "ES256 / JWKS"
section - exercising the path hosted Supabase projects actually use
(shared/auth.py's ``_decode_claims``).
"""

from __future__ import annotations

import os
import time
import uuid
from collections.abc import AsyncIterator, Iterator
from typing import Any

import asyncpg
import httpx
import jwt
import pytest
import pytest_asyncio
from cryptography.hazmat.primitives.asymmetric import ec
from jwt.algorithms import ECAlgorithm

from app.main import app
from app.shared import auth, db
from app.shared.config import get_settings
from tests.conftest import _app_dsn_for

pytestmark = pytest.mark.db

TEST_JWT_SECRET = "test-only-supabase-jwt-secret-do-not-use-in-prod"  # noqa: S105


@pytest.fixture(autouse=True)
def _supabase_jwt_secret_env() -> Iterator[None]:
    """Force a known SUPABASE_JWT_SECRET for every test in this module.

    ``get_settings`` is ``lru_cache``d process-wide, so setting the env var alone
    is not enough if some earlier test already triggered a cache hit with the
    real (empty) value from .env - clearing the cache here, before and after,
    makes this robust to test ordering.
    """
    original = os.environ.get("SUPABASE_JWT_SECRET")
    os.environ["SUPABASE_JWT_SECRET"] = TEST_JWT_SECRET
    get_settings.cache_clear()
    yield
    if original is None:
        os.environ.pop("SUPABASE_JWT_SECRET", None)
    else:
        os.environ["SUPABASE_JWT_SECRET"] = original
    get_settings.cache_clear()


@pytest_asyncio.fixture
async def client(migrated_db: str) -> AsyncIterator[httpx.AsyncClient]:
    """A wren_app pool pointed at wren_test, plus an httpx client for the real app.

    ``ASGITransport`` does not send ASGI lifespan events, so ``app``'s lifespan
    (app/main.py) never runs here and never double-creates the pool this fixture
    owns; it is closed unconditionally in the finally block.
    """
    await db.create_pool(dsn=_app_dsn_for(migrated_db), min_size=1, max_size=4)
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac
    finally:
        await db.close_pool()


def _make_token(
    user_id: uuid.UUID,
    *,
    secret: str = TEST_JWT_SECRET,
    audience: str = "authenticated",
    expires_in: int = 3600,
    email: str | None = None,
) -> str:
    now = int(time.time())
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "aud": audience,
        "iat": now,
        "exp": now + expires_in,
    }
    if email is not None:
        payload["email"] = email
    return jwt.encode(payload, secret, algorithm="HS256")


async def _signup(client: httpx.AsyncClient, *, token: str, slug: str, name: str) -> httpx.Response:
    """The explicit-body shape: a caller (seed scripts) choosing its own slug/name."""
    return await client.post(
        "/api/tenants",
        json={"slug": slug, "name": name},
        headers={"Authorization": f"Bearer {token}"},
    )


async def _provision(client: httpx.AsyncClient, *, token: str) -> httpx.Response:
    """The empty-body shape: login-in-chat's "give me my tenant" call."""
    return await client.post("/api/tenants", json={}, headers={"Authorization": f"Bearer {token}"})


async def _insert_platform_admin(conn: asyncpg.Connection[Any], user_id: uuid.UUID) -> None:
    """Bootstrap a platform_admins row per database.md's bootstrap note: platform_admins
    is FORCE RLS'd platform-admin-only, so even the migrating connection needs the
    app.role setting to satisfy the policy's with-check."""
    async with conn.transaction():
        await conn.execute("select set_config('app.role', 'platform_admin', true)")
        await conn.execute("insert into platform_admins (user_id) values ($1)", user_id)


# --- signup (explicit slug/name) ------------------------------------------------


async def test_signup_happy_path_creates_all_three_rows(
    client: httpx.AsyncClient, superuser_conn: asyncpg.Connection[Any]
) -> None:
    user_id = uuid.uuid4()
    token = _make_token(user_id)
    slug = f"signup-{uuid.uuid4().hex[:8]}"

    response = await _signup(client, token=token, slug=slug, name="Signup Co")
    assert response.status_code == 201
    body = response.json()
    assert body["slug"] == slug
    tenant_id = uuid.UUID(body["tenant_id"])

    tenant_row = await superuser_conn.fetchrow(
        "select slug, name, status from tenants where id = $1", tenant_id
    )
    assert tenant_row is not None
    assert tenant_row["slug"] == slug
    assert tenant_row["status"] == "active"

    config_row = await superuser_conn.fetchrow(
        "select tenant_id from tenant_config where tenant_id = $1", tenant_id
    )
    assert config_row is not None

    user_row = await superuser_conn.fetchrow(
        "select tenant_id, role from users where id = $1", user_id
    )
    assert user_row is not None
    assert user_row["tenant_id"] == tenant_id
    assert user_row["role"] == "owner"


async def test_signup_duplicate_slug_is_conflict(client: httpx.AsyncClient) -> None:
    slug = f"dup-slug-{uuid.uuid4().hex[:8]}"
    first = await _signup(client, token=_make_token(uuid.uuid4()), slug=slug, name="First")
    assert first.status_code == 201

    second = await _signup(client, token=_make_token(uuid.uuid4()), slug=slug, name="Second")
    assert second.status_code == 409


async def test_signup_same_user_twice_is_conflict(client: httpx.AsyncClient) -> None:
    token = _make_token(uuid.uuid4())
    first = await _signup(client, token=token, slug=f"once-{uuid.uuid4().hex[:8]}", name="Once")
    assert first.status_code == 201

    second = await _signup(client, token=token, slug=f"twice-{uuid.uuid4().hex[:8]}", name="Twice")
    assert second.status_code == 409


@pytest.mark.parametrize("bad_slug", ["ab", "Has-Upper", "-leading-dash", "has_underscore"])
async def test_signup_bad_slug_is_unprocessable(client: httpx.AsyncClient, bad_slug: str) -> None:
    response = await _signup(
        client, token=_make_token(uuid.uuid4()), slug=bad_slug, name="Bad Slug Co"
    )
    assert response.status_code == 422


async def test_signup_no_token_is_unauthorized(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/api/tenants", json={"slug": f"notoken-{uuid.uuid4().hex[:8]}", "name": "No Token"}
    )
    assert response.status_code == 401


async def test_signup_garbage_token_is_unauthorized(client: httpx.AsyncClient) -> None:
    response = await _signup(
        client, token="not-a-real-jwt", slug=f"garbage-{uuid.uuid4().hex[:8]}", name="Garbage"
    )
    assert response.status_code == 401


async def test_signup_expired_token_is_unauthorized(client: httpx.AsyncClient) -> None:
    token = _make_token(uuid.uuid4(), expires_in=-3600)
    response = await _signup(
        client, token=token, slug=f"expired-{uuid.uuid4().hex[:8]}", name="Expired"
    )
    assert response.status_code == 401


async def test_signup_token_without_exp_is_unauthorized(client: httpx.AsyncClient) -> None:
    # PyJWT only validates exp when the claim is present; verify_token requires it
    # so a token minted without one is never a forever-valid credential.
    payload = {"sub": str(uuid.uuid4()), "aud": "authenticated", "iat": int(time.time())}
    token = jwt.encode(payload, TEST_JWT_SECRET, algorithm="HS256")
    response = await _signup(
        client, token=token, slug=f"noexp-{uuid.uuid4().hex[:8]}", name="No Exp"
    )
    assert response.status_code == 401


async def test_signup_wrong_audience_token_is_unauthorized(client: httpx.AsyncClient) -> None:
    token = _make_token(uuid.uuid4(), audience="not-authenticated")
    response = await _signup(
        client, token=token, slug=f"wrongaud-{uuid.uuid4().hex[:8]}", name="Wrong Audience"
    )
    assert response.status_code == 401


# --- provisioning (login-in-chat's empty-body call) ------------------------------


async def test_provisioning_first_call_creates_a_provisional_tenant(
    client: httpx.AsyncClient,
) -> None:
    token = _make_token(uuid.uuid4(), email="sam@example.com")

    response = await _provision(client, token=token)
    assert response.status_code == 201
    assert response.json()["slug"].startswith("sam-")


async def test_provisioning_second_call_returns_the_same_tenant(
    client: httpx.AsyncClient,
) -> None:
    token = _make_token(uuid.uuid4(), email="pat@example.com")

    first = await _provision(client, token=token)
    assert first.status_code == 201

    second = await _provision(client, token=token)
    assert second.status_code == 200
    assert second.json() == first.json()


async def test_provisioning_with_no_email_claim_falls_back(client: httpx.AsyncClient) -> None:
    """GoTrue always sets `email` for an OTP login - this only guards the token
    never having one at all, so provisioning still succeeds rather than 500ing."""
    token = _make_token(uuid.uuid4())  # no email kwarg

    response = await _provision(client, token=token)
    assert response.status_code == 201
    assert response.json()["slug"].startswith("biz-")


# --- tenant isolation at the API level ------------------------------------------


async def test_tenant_admin_me_is_isolated_per_tenant(client: httpx.AsyncClient) -> None:
    token_a = _make_token(uuid.uuid4())
    token_b = _make_token(uuid.uuid4())
    slug_a = f"me-a-{uuid.uuid4().hex[:8]}"
    slug_b = f"me-b-{uuid.uuid4().hex[:8]}"

    signup_a = await _signup(client, token=token_a, slug=slug_a, name="Tenant A")
    signup_b = await _signup(client, token=token_b, slug=slug_b, name="Tenant B")
    assert signup_a.status_code == 201
    assert signup_b.status_code == 201
    tenant_a_id = signup_a.json()["tenant_id"]
    tenant_b_id = signup_b.json()["tenant_id"]

    me_a = await client.get("/api/tenants/me", headers={"Authorization": f"Bearer {token_a}"})
    assert me_a.status_code == 200
    assert me_a.json() == {
        "tenant_id": tenant_a_id,
        "slug": slug_a,
        "name": "Tenant A",
        "brand": {},
    }
    assert me_a.json()["tenant_id"] != tenant_b_id

    me_b = await client.get("/api/tenants/me", headers={"Authorization": f"Bearer {token_b}"})
    assert me_b.status_code == 200
    assert me_b.json() == {
        "tenant_id": tenant_b_id,
        "slug": slug_b,
        "name": "Tenant B",
        "brand": {},
    }


async def test_tenant_admin_me_with_no_users_row_is_forbidden(client: httpx.AsyncClient) -> None:
    token = _make_token(uuid.uuid4())  # never signed up
    response = await client.get("/api/tenants/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403


# --- platform admin --------------------------------------------------------------


async def test_platform_ping_requires_platform_admin(
    client: httpx.AsyncClient, superuser_conn: asyncpg.Connection[Any]
) -> None:
    tenant_user_id = uuid.uuid4()
    tenant_token = _make_token(tenant_user_id)
    signup = await _signup(
        client, token=tenant_token, slug=f"notadmin-{uuid.uuid4().hex[:8]}", name="Not Admin"
    )
    assert signup.status_code == 201

    forbidden = await client.get(
        "/api/platform/ping", headers={"Authorization": f"Bearer {tenant_token}"}
    )
    assert forbidden.status_code == 403

    admin_user_id = uuid.uuid4()
    await _insert_platform_admin(superuser_conn, admin_user_id)
    admin_token = _make_token(admin_user_id)

    ok = await client.get("/api/platform/ping", headers={"Authorization": f"Bearer {admin_token}"})
    assert ok.status_code == 200
    assert ok.json() == {"ok": True}


# --- ES256 / JWKS (hosted Supabase's actual signing shape) -----------------------

_JWKS_SUPABASE_URL = "http://jwks-test.invalid"


def _es256_token(
    user_id: uuid.UUID, *, kid: str, expires_in: int = 3600
) -> tuple[str, dict[str, Any]]:
    """A token signed with a throwaway EC keypair, plus the JWKS document that
    verifies it - the shape hosted Supabase actually ships (progress.md's
    known-gap note: the hosted project signs ES256, and until this module the
    backend could only verify HS256)."""
    private_key = ec.generate_private_key(ec.SECP256R1())
    now = int(time.time())
    payload = {
        "sub": str(user_id),
        "aud": "authenticated",
        "iat": now,
        "exp": now + expires_in,
    }
    token = jwt.encode(payload, private_key, algorithm="ES256", headers={"kid": kid})
    jwk = ECAlgorithm.to_jwk(private_key.public_key(), as_dict=True)
    jwk.update({"kid": kid, "alg": "ES256", "use": "sig"})
    return token, {"keys": [jwk]}


@pytest.fixture
def jwks_supabase_url(monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    """Point SUPABASE_URL at a fake host - only ``_jwks_client``'s stubbed
    ``fetch_data`` (below) ever has to answer for it, nothing makes a real
    request. Same lru_cache-clearing discipline as the JWT-secret fixture."""
    monkeypatch.setenv("SUPABASE_URL", _JWKS_SUPABASE_URL)
    get_settings.cache_clear()
    yield _JWKS_SUPABASE_URL
    get_settings.cache_clear()


def _stub_jwks(monkeypatch: pytest.MonkeyPatch, supabase_url: str, jwks: dict[str, Any]) -> None:
    """Serve ``jwks`` from the JWKS client the app will actually use for
    ``supabase_url`` (``auth._jwks_client`` is process-lifetime lru_cached, so
    this is the same instance ``_decode_claims`` calls) without any real
    network access - ``fetch_data`` is ``PyJWKClient``'s one I/O seam."""
    monkeypatch.setattr(auth._jwks_client(supabase_url), "fetch_data", lambda: jwks)


async def test_es256_token_is_accepted_via_jwks(
    client: httpx.AsyncClient, jwks_supabase_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    kid = f"test-{uuid.uuid4().hex[:8]}"
    token, jwks = _es256_token(uuid.uuid4(), kid=kid)
    _stub_jwks(monkeypatch, jwks_supabase_url, jwks)

    response = await _provision(client, token=token)
    assert response.status_code == 201


async def test_es256_token_with_unknown_kid_is_unauthorized(
    client: httpx.AsyncClient, jwks_supabase_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Signed with a keypair whose public half never makes it into the stubbed
    # JWKS - the same shape as a token signed by a key the project has since
    # rotated away from.
    token, _real_jwks = _es256_token(uuid.uuid4(), kid=f"real-{uuid.uuid4().hex[:8]}")
    _stub_jwks(monkeypatch, jwks_supabase_url, {"keys": []})

    response = await _provision(client, token=token)
    assert response.status_code == 401
