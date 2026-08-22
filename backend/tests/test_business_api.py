"""E-6: the Booking page API - one read for the screen, links, and the cover."""

from __future__ import annotations

import time
import uuid
from collections.abc import AsyncIterator, Iterator
from typing import Any

import httpx
import jwt
import pytest
import pytest_asyncio

from app.llm.dependency import get_embedder_dependency
from app.main import app
from app.shared import db
from app.shared.config import get_settings
from tests.conftest import _app_dsn_for
from tests.fakes import ZeroEmbedder

pytestmark = pytest.mark.db

TEST_JWT_SECRET = "test-only-supabase-jwt-secret-do-not-use-in-prod"  # noqa: S105

# A one-pixel PNG - a real image header, so the mime check is exercised against
# something a browser would actually produce.
PNG_1PX = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
    "890000000a49444154789c6360000002000100" + "05" * 8
)


@pytest.fixture(autouse=True)
def _supabase_jwt_secret_env() -> Iterator[None]:
    import os

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
    await db.create_pool(dsn=_app_dsn_for(migrated_db), min_size=1, max_size=4)
    app.dependency_overrides[get_embedder_dependency] = ZeroEmbedder
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac
    finally:
        app.dependency_overrides.pop(get_embedder_dependency, None)
        await db.close_pool()


def _make_token(user_id: uuid.UUID) -> str:
    now = int(time.time())
    return jwt.encode(
        {"sub": str(user_id), "aud": "authenticated", "iat": now, "exp": now + 3600},
        TEST_JWT_SECRET,
        algorithm="HS256",
    )


async def _signup(client: httpx.AsyncClient) -> tuple[dict[str, str], uuid.UUID]:
    token = _make_token(uuid.uuid4())
    response = await client.post(
        "/api/tenants",
        json={"slug": f"biz-{uuid.uuid4().hex[:8]}", "name": "Business Test Co"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201, response.text
    return {"Authorization": f"Bearer {token}"}, uuid.UUID(response.json()["tenant_id"])


async def test_page_reads_as_the_screen_renders(client: httpx.AsyncClient) -> None:
    headers, _ = await _signup(client)
    response = await client.get("/api/business/page", headers=headers)
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    # A business that has said nothing yet still gets a coherent page: its name,
    # and every other part empty rather than absent.
    assert body["name"] == "Business Test Co"
    assert body["tagline"] is None
    assert body["services"] == []
    assert body["links"] == {}
    assert body["has_cover"] is False
    assert body["slug"].startswith("biz-")


async def test_links_round_trip_and_merge(client: httpx.AsyncClient) -> None:
    headers, _ = await _signup(client)
    saved = await client.patch(
        "/api/business/links",
        json={"links": {"instagram": "https://instagram.com/sababa"}},
        headers=headers,
    )
    assert saved.status_code == 200, saved.text
    assert saved.json() == {"instagram": "https://instagram.com/sababa"}

    # A second write adds a slot without clearing the first.
    saved = await client.patch(
        "/api/business/links",
        json={"links": {"facebook": "https://facebook.com/sababa"}},
        headers=headers,
    )
    assert saved.json() == {
        "instagram": "https://instagram.com/sababa",
        "facebook": "https://facebook.com/sababa",
    }
    page = await client.get("/api/business/page", headers=headers)
    assert page.json()["links"]["facebook"] == "https://facebook.com/sababa"


async def test_an_empty_link_clears_that_slot(client: httpx.AsyncClient) -> None:
    headers, _ = await _signup(client)
    await client.patch(
        "/api/business/links", json={"links": {"google": "https://g.example"}}, headers=headers
    )
    cleared = await client.patch(
        "/api/business/links", json={"links": {"google": ""}}, headers=headers
    )
    assert cleared.json() == {}


@pytest.mark.parametrize(
    "url",
    ["javascript:alert(1)", "data:text/html,<script>", "not a url", "ftp://example.com"],
)
async def test_a_link_must_be_a_real_web_address(client: httpx.AsyncClient, url: str) -> None:
    """These render as links a customer clicks, so the scheme allowlist is the
    guard against one arriving through the owner's own settings."""
    headers, _ = await _signup(client)
    response = await client.patch(
        "/api/business/links", json={"links": {"website": url}}, headers=headers
    )
    assert response.status_code == 422, response.text


async def test_an_unknown_link_slot_is_refused(client: httpx.AsyncClient) -> None:
    headers, _ = await _signup(client)
    response = await client.patch(
        "/api/business/links", json={"links": {"tiktok": "https://tiktok.com/@x"}}, headers=headers
    )
    assert response.status_code == 422


async def test_cover_round_trips(client: httpx.AsyncClient) -> None:
    headers, _ = await _signup(client)
    assert (await client.get("/api/business/cover", headers=headers)).status_code == 404

    put = await client.put(
        "/api/business/cover",
        files={"file": ("cover.png", PNG_1PX, "image/png")},
        headers=headers,
    )
    assert put.status_code == 204, put.text

    got = await client.get("/api/business/cover", headers=headers)
    assert got.status_code == 200
    assert got.content == PNG_1PX
    assert got.headers["content-type"].startswith("image/png")
    assert got.headers["etag"]
    assert "private" in got.headers["cache-control"]

    assert (await client.get("/api/business/page", headers=headers)).json()["has_cover"] is True

    assert (await client.delete("/api/business/cover", headers=headers)).status_code == 204
    assert (await client.get("/api/business/cover", headers=headers)).status_code == 404


async def test_a_second_upload_replaces_the_first(client: httpx.AsyncClient) -> None:
    headers, _ = await _signup(client)
    await client.put(
        "/api/business/cover", files={"file": ("a.png", PNG_1PX, "image/png")}, headers=headers
    )
    await client.put(
        "/api/business/cover",
        files={"file": ("b.jpg", b"\xff\xd8\xff-second", "image/jpeg")},
        headers=headers,
    )
    got = await client.get("/api/business/cover", headers=headers)
    assert got.content == b"\xff\xd8\xff-second"
    assert got.headers["content-type"].startswith("image/jpeg")


async def test_a_non_image_cover_is_refused(client: httpx.AsyncClient) -> None:
    headers, _ = await _signup(client)
    response = await client.put(
        "/api/business/cover",
        files={"file": ("menu.pdf", b"%PDF-1.4", "application/pdf")},
        headers=headers,
    )
    assert response.status_code == 415


async def test_an_oversized_cover_is_refused(client: httpx.AsyncClient) -> None:
    """The cap is what a Postgres row should carry. The client resizes before
    sending; this is the backstop for a client that does not."""
    headers, _ = await _signup(client)
    response = await client.put(
        "/api/business/cover",
        files={"file": ("big.png", b"\x89PNG" + b"\x00" * (2 * 1024 * 1024), "image/png")},
        headers=headers,
    )
    assert response.status_code == 413


async def test_the_page_needs_a_session(client: httpx.AsyncClient) -> None:
    for method, path in (
        ("get", "/api/business/page"),
        ("get", "/api/business/cover"),
        ("delete", "/api/business/cover"),
    ):
        response = await getattr(client, method)(path)
        assert response.status_code == 401, f"{method} {path}"
