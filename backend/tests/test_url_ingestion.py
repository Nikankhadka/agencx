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
from app.ingestion import url as url_ingestion
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


class _FakeNetworkStream:
    def __init__(self, address: str | None = "93.184.216.34") -> None:
        self.address = address
        self.closed = False

    def get_extra_info(self, name: str) -> tuple[str, int] | None:
        return (self.address, 80) if self.address and name in {"server_addr", "peername"} else None

    async def aclose(self) -> None:
        self.closed = True


class _ChunkStream(httpx.AsyncByteStream):
    def __init__(self) -> None:
        self.closed = False

    async def __aiter__(self) -> AsyncIterator[bytes]:
        yield b"x" * (1024 * 1024)
        yield b"x" * (1024 * 1024)
        yield b"x"

    async def aclose(self) -> None:
        self.closed = True


def _test_resolver(host: str, port: int) -> list[str]:
    return ["93.184.216.34"]


def _html_response(
    body: bytes, *, address: str | None = "93.184.216.34", content_type: str = "text/html"
) -> httpx.Response:
    return httpx.Response(
        200,
        headers={"content-type": content_type},
        content=body,
        extensions={"network_stream": _FakeNetworkStream(address)},
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
        return httpx.Response(
            200,
            headers={"content-type": "text/html"},
            content=b"x" * (2 * 1024 * 1024 + 1),
            extensions={"network_stream": _FakeNetworkStream()},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ValueError, match="2MB"):
            await fetch_page("http://example.com/big", client=client, resolver=_test_resolver)


async def test_fetch_page_rejects_non_2xx() -> None:
    """O-3: a 404 page is a failure, not content. Ingesting the error page would
    teach the assistant the site's 'page not found' copy."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            404,
            content=b"<html><body>Page not found</body></html>",
            extensions={"network_stream": _FakeNetworkStream()},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ValueError, match="could not read this URL"):
            await fetch_page("http://example.com/gone", client=client, resolver=_test_resolver)


async def test_fetch_page_wraps_transport_errors() -> None:
    """O-3: an unreachable host surfaces as ValueError like every other fetch
    failure, so both callers degrade instead of raising a 500 at the owner."""

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("nope", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ValueError, match="could not read this URL"):
            await fetch_page("http://nope.invalid/", client=client)


async def test_fetch_page_returns_body() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _html_response(b"<html>hi</html>")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        assert (
            await fetch_page("http://example.com/", client=client, resolver=_test_resolver)
            == b"<html>hi</html>"
        )


# --- O-7: the fetch looks like a browser, and says why it failed -------------


async def test_fetch_page_sends_browser_headers() -> None:
    """O-7: httpx's default ``python-httpx/x.y`` user agent is answered with a
    403 by a good share of real business sites. A shop owner pasting their own
    link is not a bot, and the request should not announce itself as one."""
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(request.headers)
        return _html_response(b"<html>hi</html>")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        await fetch_page("http://example.com/", client=client, resolver=_test_resolver)

    assert "python-httpx" not in seen["user-agent"]
    assert "Mozilla/5.0" in seen["user-agent"]
    assert "text/html" in seen["accept"]
    assert seen["accept-language"].startswith("en")


async def test_fetch_page_names_the_http_status() -> None:
    """O-7: 403 (bot protection), 404 (wrong link) and 503 (their outage) are
    three different problems. The owner sees one calm line either way, so the
    only place the difference can survive is this message, which is logged."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            403,
            content=b"<html><body>Forbidden</body></html>",
            extensions={"network_stream": _FakeNetworkStream()},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ValueError, match=r"HTTP 403"):
            await fetch_page("http://example.com/blocked", client=client, resolver=_test_resolver)


@pytest.mark.parametrize(
    "address",
    [
        "10.0.0.1",
        "172.16.0.1",
        "192.168.1.1",
        "127.0.0.1",
        "169.254.1.1",
        "224.0.0.1",
        "192.0.2.1",
        "198.18.0.1",
        "100.64.0.1",
        "0.0.0.0",
        "::",
        "::1",
        "fc00::1",
        "fe80::1",
        "ff02::1",
        "2001:db8::1",
    ],
)
async def test_fetch_page_rejects_blocked_literal_addresses(address: str) -> None:
    with pytest.raises(ValueError, match="blocked network"):
        await fetch_page(f"http://[{address}]/" if ":" in address else f"http://{address}/")


@pytest.mark.parametrize("address", ["10.0.0.1", "127.0.0.1", "169.254.169.254", "::1"])
async def test_fetch_page_rejects_blocked_resolved_addresses(address: str) -> None:
    def resolver(host: str, port: int) -> list[str]:
        return [address]

    with pytest.raises(ValueError, match="blocked network"):
        await fetch_page("http://untrusted.example/", resolver=resolver)


async def test_fetch_page_rejects_numeric_loopback_and_mixed_dns() -> None:
    def loopback(host: str, port: int) -> list[str]:
        return ["127.0.0.1"]

    for numeric_host in ("2130706433", "0x7f000001", "0177.0.0.1"):
        with pytest.raises(ValueError, match="blocked network"):
            await fetch_page(f"http://{numeric_host}/", resolver=loopback)

    with pytest.raises(ValueError, match="blocked network"):
        await fetch_page(
            "http://mixed.example/", resolver=lambda h, p: ["93.184.216.34", "10.0.0.1"]
        )


@pytest.mark.parametrize(
    "url,match",
    [("http://user:pass@example.com/", "credentials"), ("http://example.com:8080/", "port")],
)
async def test_fetch_page_rejects_credentials_and_disallowed_ports(url: str, match: str) -> None:
    with pytest.raises(ValueError, match=match):
        await fetch_page(url, resolver=_test_resolver)


@pytest.mark.parametrize(
    "url",
    [
        "http://example.com/",
        "http://example.com:443/",
        "https://example.com/",
        "https://example.com:80/",
    ],
)
async def test_fetch_page_preserves_bound_port_and_host(url: str) -> None:
    seen: dict[str, str | int | None] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["port"] = request.url.port
        seen["host"] = request.headers["host"]
        seen["sni"] = request.extensions.get("sni_hostname")
        return _html_response(b"ok")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        assert await fetch_page(url, client=client, resolver=_test_resolver) == b"ok"
    authority = url.split("//", 1)[1].split("/", 1)[0]
    expected_port = (
        int(authority.rsplit(":", 1)[1])
        if ":" in authority
        else (443 if url.startswith("https") else 80)
    )
    assert (seen["port"] or (443 if url.startswith("https") else 80)) == expected_port
    assert seen["host"] == url.split("//", 1)[1].split("/", 1)[0]
    if url.startswith("https"):
        assert seen["sni"] == "example.com"


async def test_fetch_page_accepts_public_ipv6_with_matching_peer() -> None:
    address = "2001:4860:4860::8888"

    def resolver(host: str, port: int) -> list[str]:
        return [address]

    def handler(request: httpx.Request) -> httpx.Response:
        return _html_response(b"ok", address=address)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        assert await fetch_page("https://ipv6.example/", client=client, resolver=resolver) == b"ok"


async def test_fetch_page_follows_only_validated_redirects_and_caps_depth() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.headers["host"])
        if len(calls) == 1:
            return httpx.Response(
                302,
                headers={"location": "/next"},
                extensions={"network_stream": _FakeNetworkStream()},
            )
        return _html_response(b"ok")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        assert (
            await fetch_page("http://example.com/", client=client, resolver=_test_resolver) == b"ok"
        )
    assert calls == ["example.com", "example.com"]

    def looping(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            302, headers={"location": "/again"}, extensions={"network_stream": _FakeNetworkStream()}
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(looping)) as client:
        with pytest.raises(ValueError, match="too many redirects"):
            await fetch_page("http://example.com/", client=client, resolver=_test_resolver)


async def test_fetch_page_rejects_blocked_redirect_before_following() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(
            302,
            headers={"location": "http://internal.example/"},
            extensions={"network_stream": _FakeNetworkStream()},
        )

    def resolver(host: str, port: int) -> list[str]:
        return ["93.184.216.34"] if host == "example.com" else ["10.0.0.1"]

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ValueError, match="blocked network"):
            await fetch_page("http://example.com/", client=client, resolver=resolver)
    assert calls == 1


async def test_fetch_page_re_resolves_same_host_after_redirect() -> None:
    resolutions = 0
    requests = 0

    def resolver(host: str, port: int) -> list[str]:
        nonlocal resolutions
        resolutions += 1
        return ["93.184.216.34"] if resolutions == 1 else ["10.0.0.1"]

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        return httpx.Response(
            302,
            headers={"location": "/private"},
            extensions={"network_stream": _FakeNetworkStream()},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ValueError, match="blocked network"):
            await fetch_page("http://same.example/", client=client, resolver=resolver)
    assert resolutions == 2
    assert requests == 1


@pytest.mark.parametrize("address", [None, "10.0.0.1", "93.184.216.35", "::ffff:93.184.216.34"])
async def test_fetch_page_checks_and_closes_connected_peer(address: str | None) -> None:
    stream = _FakeNetworkStream(address)
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if address == "::ffff:93.184.216.34":
            return httpx.Response(
                200,
                headers={"content-type": "text/html"},
                content=b"ok",
                extensions={"network_stream": stream},
            )
        return httpx.Response(
            302,
            headers={"location": "/next"},
            extensions={"network_stream": stream},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        if address == "::ffff:93.184.216.34":
            assert (
                await fetch_page("http://example.com/", client=client, resolver=_test_resolver)
                == b"ok"
            )
        else:
            with pytest.raises(ValueError, match="network peer"):
                await fetch_page("http://example.com/", client=client, resolver=_test_resolver)
            assert calls == 1


@pytest.mark.parametrize("content_type", ["", "application/json", "text/plain"])
async def test_fetch_page_requires_html_media_type(content_type: str) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        headers = {"content-type": content_type} if content_type else {}
        return httpx.Response(
            200, headers=headers, content=b"x", extensions={"network_stream": _FakeNetworkStream()}
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ValueError, match="HTML"):
            await fetch_page("http://example.com/", client=client, resolver=_test_resolver)


async def test_fetch_page_accepts_html_parameters_and_xhtml() -> None:
    for media_type in ("text/html; charset=utf-8", "application/xhtml+xml; charset=utf-8"):
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda request, media_type=media_type: _html_response(
                    b"ok", content_type=media_type
                )
            )
        ) as client:
            assert (
                await fetch_page("http://example.com/", client=client, resolver=_test_resolver)
                == b"ok"
            )


async def test_fetch_page_rejects_declared_and_streamed_oversize() -> None:
    def declared(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": "text/html", "content-length": str(2 * 1024 * 1024 + 1)},
            content=b"x",
            extensions={"network_stream": _FakeNetworkStream()},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(declared)) as client:
        with pytest.raises(ValueError, match="2MB"):
            await fetch_page("http://example.com/", client=client, resolver=_test_resolver)

    stream = _ChunkStream()

    def streamed(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": "text/html"},
            stream=stream,
            extensions={"network_stream": _FakeNetworkStream()},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(streamed)) as client:
        with pytest.raises(ValueError, match="2MB"):
            await fetch_page("http://example.com/", client=client, resolver=_test_resolver)
    assert stream.closed


async def test_fetch_page_wraps_transport_and_overall_timeouts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def transport_timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timeout", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(transport_timeout)) as client:
        with pytest.raises(ValueError, match="could not read"):
            await fetch_page("http://example.com/", client=client, resolver=_test_resolver)

    def slow_resolver(host: str, port: int) -> list[str]:
        import time as _time

        _time.sleep(0.05)
        return ["93.184.216.34"]

    monkeypatch.setattr(url_ingestion, "_OPERATION_TIMEOUT_S", 0.001)
    with pytest.raises(ValueError, match="timeout"):
        await fetch_page("http://slow.example/", resolver=slow_resolver)


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
