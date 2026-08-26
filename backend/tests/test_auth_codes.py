"""O-2: login-in-chat - the auth-code lifecycle and the two endpoints.

The code lifecycle (issue/verify: hash, TTL, attempt budget, single-use,
duplicate-email non-leak) is tested at the service layer against wren_test; the
endpoints are exercised through the real app. ``ensure_auth_user`` is
monkeypatched because it talks to GoTrue's Admin API, which tests run without.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator, Iterator
from typing import Any

import httpx
import jwt
import pytest
import pytest_asyncio

from app.main import app
from app.services import auth_codes
from app.shared import db
from app.shared.config import get_settings
from tests.conftest import _app_dsn_for

pytestmark = pytest.mark.db

TEST_JWT_SECRET = "test-only-supabase-jwt-secret-do-not-use-in-prod"  # noqa: S105


@pytest.fixture(autouse=True)
def _supabase_jwt_secret_env() -> Iterator[None]:
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
async def pool(migrated_db: str) -> AsyncIterator[None]:
    await db.create_pool(dsn=_app_dsn_for(migrated_db), min_size=1, max_size=4)
    try:
        yield
    finally:
        await db.close_pool()


@pytest_asyncio.fixture
async def client(migrated_db: str, pool: None) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# --- service layer: the code lifecycle ----------------------------------------


async def test_issue_then_verify_roundtrip(pool: None) -> None:
    email = f"sam-{uuid.uuid4().hex}@example.com"
    code = await auth_codes.issue_code(email=email)
    await auth_codes.verify_code(email=email, code=code)


async def test_code_is_single_use(pool: None) -> None:
    email = f"sam-{uuid.uuid4().hex}@example.com"
    code = await auth_codes.issue_code(email=email)
    await auth_codes.verify_code(email=email, code=code)
    with pytest.raises(auth_codes.CodeError) as exc:
        await auth_codes.verify_code(email=email, code=code)
    assert exc.value.kind == "invalid"


async def test_wrong_code_increments_attempts_then_too_many(pool: None) -> None:
    email = f"sam-{uuid.uuid4().hex}@example.com"
    code = await auth_codes.issue_code(email=email)
    for _ in range(auth_codes.MAX_ATTEMPTS):
        with pytest.raises(auth_codes.CodeError) as exc:
            await auth_codes.verify_code(email=email, code="000000")
        assert exc.value.kind == "invalid"
    # budget exhausted - even the correct code no longer works
    with pytest.raises(auth_codes.CodeError) as exc:
        await auth_codes.verify_code(email=email, code=code)
    assert exc.value.kind == "too_many"


async def test_expired_code(superuser_conn: Any, pool: None) -> None:
    email = f"sam-{uuid.uuid4().hex}@example.com"
    code = await auth_codes.issue_code(email=email)
    await superuser_conn.execute(
        "update auth_codes set expires_at = now() - interval '1 minute' where email = $1",
        email,
    )
    with pytest.raises(auth_codes.CodeError) as exc:
        await auth_codes.verify_code(email=email, code=code)
    assert exc.value.kind == "expired"


async def test_latest_code_wins_on_duplicate_email(pool: None) -> None:
    email = f"sam-{uuid.uuid4().hex}@example.com"
    await auth_codes.issue_code(email=email)
    latest = await auth_codes.issue_code(email=email)
    await auth_codes.verify_code(email=email, code=latest)


async def test_issuance_is_capped_per_address(pool: None) -> None:
    """The route is unauthenticated and, with a relay configured, mails whatever
    address it is handed. The ceiling is what stops it being an open relay."""
    email = f"flood-{uuid.uuid4().hex}@example.com"
    for _ in range(auth_codes.MAX_CODES_PER_WINDOW):
        await auth_codes.issue_code(email=email)

    with pytest.raises(auth_codes.CodeError) as exc:
        await auth_codes.issue_code(email=email)
    assert exc.value.kind == "rate_limited"


async def test_the_cap_is_per_address_not_global(pool: None) -> None:
    """One flooded mailbox must not lock every other owner out of logging in."""
    flooded = f"flood-{uuid.uuid4().hex}@example.com"
    for _ in range(auth_codes.MAX_CODES_PER_WINDOW):
        await auth_codes.issue_code(email=flooded)

    other = f"sam-{uuid.uuid4().hex}@example.com"
    code = await auth_codes.issue_code(email=other)
    await auth_codes.verify_code(email=other, code=code)


# --- endpoints ----------------------------------------------------------------


async def test_login_code_endpoint_accepts_valid_email(client: httpx.AsyncClient) -> None:
    resp = await client.post("/api/auth/login-code", json={"email": "sam@example.com"})
    assert resp.status_code == 202


@pytest.mark.parametrize("bad_email", ["not-an-email", "a@b", "bob@gmial", "bob@.com"])
async def test_login_code_endpoint_answers_unreadable_email_conversationally(
    client: httpx.AsyncClient, bad_email: str
) -> None:
    """A typo gets one calm line, never a 422 validation dump (the thread shows
    ``detail`` verbatim)."""
    resp = await client.post("/api/auth/login-code", json={"email": bad_email})
    assert resp.status_code == 400
    detail = resp.json()["detail"]
    assert isinstance(detail, str) and detail
    assert "@" not in detail  # the refusal never echoes the address back


async def test_login_code_endpoint_answers_429_past_the_cap(client: httpx.AsyncClient) -> None:
    """Every request up to the ceiling is accepted, so a green assertion here
    means the cap actually refused rather than the whole route being broken."""
    email = f"flood-{uuid.uuid4().hex}@example.com"
    for _ in range(auth_codes.MAX_CODES_PER_WINDOW):
        accepted = await client.post("/api/auth/login-code", json={"email": email})
        assert accepted.status_code == 202

    resp = await client.post("/api/auth/login-code", json={"email": email})
    assert resp.status_code == 429
    assert resp.json()["detail"] == "That's a lot of codes for one address. Try again in an hour."


async def test_login_code_endpoint_rejects_empty_body_field(client: httpx.AsyncClient) -> None:
    """An empty field is a malformed request, not a conversational mistake."""
    resp = await client.post("/api/auth/login-code", json={"email": ""})
    assert resp.status_code == 422


async def test_login_code_endpoint_reads_an_email_out_of_prose(
    client: httpx.AsyncClient,
) -> None:
    """The composer is a chat pill, so the owner may answer in a sentence."""
    local = f"sam.{uuid.uuid4().hex}"
    resp = await client.post(
        "/api/auth/login-code", json={"email": f"it's {local}@Example.com, thanks!"}
    )
    assert resp.status_code == 202
    # The code is filed under the normalized address, not the sentence.
    issued = await client.get(f"/api/auth/dev-login-code?email={local}@example.com")
    assert issued.status_code == 200


async def test_issue_and_verify_agree_on_one_normalized_key(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Issuing from one spelling and verifying from another must not desync -
    normalization happens once, at the edge, for both routes."""
    user_id = str(uuid.uuid4())

    async def _fake_ensure_auth_user(email: str) -> str:
        return user_id

    monkeypatch.setattr("app.services.identity.ensure_auth_user", _fake_ensure_auth_user)

    local = f"sam-{uuid.uuid4().hex}"
    await client.post("/api/auth/login-code", json={"email": f"  {local.upper()}@EXAMPLE.com "})
    code = (await client.get(f"/api/auth/dev-login-code?email={local}@example.com")).json()["code"]

    verify = await client.post(
        "/api/auth/verify-code", json={"email": f"mailto:{local}@Example.com.", "code": code}
    )
    assert verify.status_code == 200


async def test_verify_code_mints_session_for_existing_user(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    user_id = str(uuid.uuid4())
    email = f"sam-{uuid.uuid4().hex}@example.com"

    async def _fake_ensure_auth_user(_email: str) -> str:
        return user_id

    monkeypatch.setattr("app.services.identity.ensure_auth_user", _fake_ensure_auth_user)

    code = await auth_codes.issue_code(email=email)
    resp = await client.post("/api/auth/verify-code", json={"email": email, "code": code})
    assert resp.status_code == 200
    body = resp.json()
    assert body["user_id"] == user_id
    claims = jwt.decode(
        body["access_token"], TEST_JWT_SECRET, algorithms=["HS256"], audience="authenticated"
    )
    assert claims["sub"] == user_id


async def test_verify_code_provisions_tenant_for_new_user(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch, superuser_conn: Any
) -> None:
    user_id = str(uuid.uuid4())
    email = f"new-{uuid.uuid4().hex}@example.com"

    async def _fake_ensure_auth_user(_email: str) -> str:
        return user_id

    monkeypatch.setattr("app.services.identity.ensure_auth_user", _fake_ensure_auth_user)

    code = await auth_codes.issue_code(email=email)
    resp = await client.post("/api/auth/verify-code", json={"email": email, "code": code})
    assert resp.status_code == 200
    tenant_id = uuid.UUID(resp.json()["tenant_id"])

    user_row = await superuser_conn.fetchrow(
        "select tenant_id, role from users where id = $1", user_id
    )
    assert user_row is not None
    assert user_row["tenant_id"] == tenant_id
    assert user_row["role"] == "owner"

    # the minted session is usable: GET /api/tenants/me works with it
    me = await client.get(
        "/api/tenants/me",
        headers={"Authorization": f"Bearer {resp.json()['access_token']}"},
    )
    assert me.status_code == 200


async def test_verify_code_wrong_code_returns_calm_copy(client: httpx.AsyncClient) -> None:
    email = f"sam-{uuid.uuid4().hex}@example.com"
    await auth_codes.issue_code(email=email)
    resp = await client.post("/api/auth/verify-code", json={"email": email, "code": "000000"})
    assert resp.status_code == 400
    assert resp.json()["detail"] == "That code didn't work. Try again, or resend."


async def test_verify_code_no_outstanding_code_returns_calm_copy(
    client: httpx.AsyncClient,
) -> None:
    resp = await client.post(
        "/api/auth/verify-code", json={"email": "nobody@example.com", "code": "123456"}
    )
    assert resp.status_code == 400
    assert resp.json()["detail"] == "That code didn't work. Try again, or resend."


async def test_verify_code_requires_six_digits(client: httpx.AsyncClient) -> None:
    resp = await client.post(
        "/api/auth/verify-code", json={"email": "sam@example.com", "code": "abc"}
    )
    assert resp.status_code == 422


async def test_dev_login_code_returns_the_captured_code(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    email = f"dev-{uuid.uuid4().hex}@example.com"
    user_id = str(uuid.uuid4())

    async def _fake_ensure_auth_user(_email: str) -> str:
        return user_id

    monkeypatch.setattr("app.services.identity.ensure_auth_user", _fake_ensure_auth_user)

    await client.post("/api/auth/login-code", json={"email": email})
    resp = await client.get(f"/api/auth/dev-login-code?email={email}")
    assert resp.status_code == 200
    code = resp.json()["code"]
    assert len(code) == 6 and code.isdigit()

    verify = await client.post("/api/auth/verify-code", json={"email": email, "code": code})
    assert verify.status_code == 200


async def test_dev_login_code_404_for_never_issued_email(client: httpx.AsyncClient) -> None:
    resp = await client.get(f"/api/auth/dev-login-code?email=never-{uuid.uuid4().hex}@example.com")
    assert resp.status_code == 404
