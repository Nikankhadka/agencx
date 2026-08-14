"""T-056: URL ingestion - fetch/extract unit tests plus service/API ingestion.

Split into unit tests (extract_main_text/extract_title/fetch_page, no Postgres)
and db-marked tests (service.upload_url + POST /api/knowledge/urls) following the
test_knowledge_api.py client-fixture pattern. The fetch step is monkeypatched to
serve a canned page so the tests exercise the real extract/chunk/embed path
without network I/O. No vertical-specific strings anywhere in this module.
"""

from __future__ import annotations

import json
import time
import uuid
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import asyncpg
import httpx
import jwt
import pytest
import pytest_asyncio

from app.features.knowledge import service
from app.ingestion.url import extract_main_text, extract_title, fetch_page
from app.llm.dependency import get_embedder_dependency
from app.main import app
from app.shared import db
from app.shared.config import get_settings
from tests.conftest import _app_dsn_for
from tests.fakes import EMBEDDING_DIM, ZeroEmbedder

TEST_JWT_SECRET = "test-only-supabase-jwt-secret-do-not-use-in-prod"  # noqa: S105

_CANNED_HTML = (
    b"<html><head><title>  Acme Hours  </title>"
    b"<script>alert('x')</script><style>nav{color:red}</style></head>"
    b"<body><nav>Menu</nav><header>logo</header>"
    b"<main><p>We are open weekdays 9 to 5.</p></main>"
    b"<footer>goodbye</footer></body></html>"
)


# --- unit: extraction --------------------------------------------------------


def test_extract_main_text_strips_chrome_and_keeps_body() -> None:
    text = extract_main_text(_CANNED_HTML)
    assert "We are open weekdays 9 to 5." in text
    assert "Menu" not in text
    assert "logo" not in text
    assert "goodbye" not in text
    assert "alert('x')" not in text
    assert "color:red" not in text


def test_extract_main_text_empty_when_no_body_content() -> None:
    assert extract_main_text(b"<html><body><nav>only nav</nav></body></html>") == ""


def test_extract_main_text_empty_for_short_or_blank_html() -> None:
    assert extract_main_text(b"") == ""
    assert extract_main_text(b"<html></html>") == ""


def test_extract_title_returns_stripped_title() -> None:
    assert extract_title(_CANNED_HTML) == "Acme Hours"


def test_extract_title_missing_returns_empty() -> None:
    assert extract_title(b"<html><body>hi</body></html>") == ""


# --- unit: fetch -------------------------------------------------------------


async def test_fetch_page_rejects_non_http_scheme() -> None:
    with pytest.raises(ValueError, match="scheme"):
        await fetch_page("ftp://example.com/x")


async def test_fetch_page_rejects_oversized_body() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"x" * (2 * 1024 * 1024 + 1))

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ValueError, match="2MB"):
            await fetch_page("http://example.com/big", client=client)


async def test_fetch_page_returns_body() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"<html>hi</html>")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        assert await fetch_page("http://example.com/", client=client) == b"<html>hi</html>"


# --- db: fixtures + helpers --------------------------------------------------


@pytest_asyncio.fixture
async def pool(migrated_db: str) -> AsyncIterator[None]:
    await db.create_pool(dsn=_app_dsn_for(migrated_db), min_size=1, max_size=4)
    try:
        yield
    finally:
        await db.close_pool()


@pytest.fixture
def uploads_tmp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("UPLOADS_DIR", str(tmp_path))
    get_settings.cache_clear()
    return tmp_path


def _make_token(user_id: uuid.UUID) -> str:
    now = int(time.time())
    payload = {"sub": str(user_id), "aud": "authenticated", "iat": now, "exp": now + 3600}
    return jwt.encode(payload, TEST_JWT_SECRET, algorithm="HS256")


@pytest_asyncio.fixture
async def client(
    migrated_db: str, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[httpx.AsyncClient]:
    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    get_settings.cache_clear()
    await db.create_pool(dsn=_app_dsn_for(migrated_db), min_size=1, max_size=4)
    app.dependency_overrides[get_embedder_dependency] = ZeroEmbedder
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac
    finally:
        app.dependency_overrides.pop(get_embedder_dependency, None)
        await db.close_pool()


async def _signup_tenant_admin(client: httpx.AsyncClient) -> str:
    user_id = uuid.uuid4()
    token = _make_token(user_id)
    slug = f"url-{uuid.uuid4().hex[:8]}"
    response = await client.post(
        "/api/tenants",
        json={"slug": slug, "name": "URL Test Co"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    return token


async def _make_tenant(superuser_conn: asyncpg.Connection[Any]) -> uuid.UUID:
    return uuid.UUID(
        str(
            await superuser_conn.fetchval(
                "insert into tenants (slug, name) values ($1, $2) returning id",
                f"url-{uuid.uuid4().hex[:8]}",
                "URL Test Co",
            )
        )
    )


def _patch_fetch(monkeypatch: pytest.MonkeyPatch, html: bytes) -> None:
    async def fake_fetch(url: str, *, client: httpx.AsyncClient | None = None) -> bytes:
        return html

    monkeypatch.setattr("app.features.knowledge.service.fetch_page", fake_fetch)


# --- db: service-level -------------------------------------------------------


@pytest.mark.db
async def test_upload_url_ingests_chunks_and_dedupes(
    pool: None,
    uploads_tmp: Path,
    superuser_conn: asyncpg.Connection[Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tenant_id = await _make_tenant(superuser_conn)
    _patch_fetch(monkeypatch, _CANNED_HTML)

    document_id = uuid.uuid4()
    row = await service.upload_url(
        tenant_id=tenant_id,
        document_id=document_id,
        url="https://example.com/hours",
        embedder=ZeroEmbedder(),
    )
    assert row is not None
    assert row["doc_type"] == "website"
    assert row["status"] == "ready"
    assert row["filename"] == "https://example.com/hours"
    assert row["error"] is None

    chunk = await superuser_conn.fetchrow(
        "select content, embedding, metadata from knowledge_chunks where document_id = $1",
        document_id,
    )
    assert chunk is not None
    assert "open weekdays" in chunk["content"]
    assert chunk["embedding"].dimensions() == EMBEDDING_DIM
    assert json.loads(chunk["metadata"])["source"] == "Acme Hours"

    # the extracted text landed on disk as {document_id}.txt
    disk = uploads_tmp / str(tenant_id) / f"{document_id}.txt"
    assert disk.read_bytes() == b"We are open weekdays 9 to 5."

    # re-pasting the same URL is idempotent: same document, no new chunks.
    again = await service.upload_url(
        tenant_id=tenant_id,
        document_id=uuid.uuid4(),
        url="https://example.com/hours",
        embedder=ZeroEmbedder(),
    )
    assert again is not None and again["id"] == row["id"]
    count = await superuser_conn.fetchval(
        "select count(*) from knowledge_chunks where document_id = $1", document_id
    )
    assert count == 1


@pytest.mark.db
async def test_upload_url_without_extractable_text_raises(
    pool: None,
    uploads_tmp: Path,
    superuser_conn: asyncpg.Connection[Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tenant_id = await _make_tenant(superuser_conn)
    _patch_fetch(monkeypatch, b"<html><body><nav>menu only</nav></body></html>")

    with pytest.raises(ValueError, match="no extractable content"):
        await service.upload_url(
            tenant_id=tenant_id,
            document_id=uuid.uuid4(),
            url="https://example.com/empty",
            embedder=ZeroEmbedder(),
        )


# --- db: API-level -----------------------------------------------------------


@pytest.mark.db
async def test_ingest_url_endpoint_returns_ready_website_doc(
    client: httpx.AsyncClient,
    uploads_tmp: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token = await _signup_tenant_admin(client)
    _patch_fetch(monkeypatch, _CANNED_HTML)

    response = await client.post(
        "/api/knowledge/urls",
        json={"url": "https://example.com/hours"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["doc_type"] == "website"
    assert body["status"] == "ready"
    assert body["filename"] == "https://example.com/hours"


@pytest.mark.db
async def test_ingest_url_rejects_non_http_scheme(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    token = await _signup_tenant_admin(client)
    response = await client.post(
        "/api/knowledge/urls",
        json={"url": "ftp://example.com/x"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422


@pytest.mark.db
async def test_ingest_url_requires_auth(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    response = await client.post("/api/knowledge/urls", json={"url": "https://example.com/"})
    assert response.status_code == 401
