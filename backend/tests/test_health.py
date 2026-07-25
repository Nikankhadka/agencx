from collections.abc import AsyncIterator

import httpx
import pytest
import pytest_asyncio

from app.core import db
from app.main import app
from tests.conftest import _app_dsn_for


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest_asyncio.fixture
async def db_client(migrated_db: str) -> AsyncIterator[httpx.AsyncClient]:
    await db.create_pool(dsn=_app_dsn_for(migrated_db), min_size=1, max_size=4)
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac
    finally:
        await db.close_pool()


@pytest.mark.db
@pytest.mark.anyio
async def test_health_ready_when_db_reachable(db_client: httpx.AsyncClient) -> None:
    response = await db_client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.anyio
async def test_health_unavailable_when_db_down() -> None:
    # No pool created: the readiness probe must report 503 so the ALB pulls the
    # instance from rotation instead of routing traffic it can't serve.
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 503
    assert response.json() == {"status": "unavailable"}


@pytest.mark.anyio
@pytest.mark.parametrize(
    "origin",
    [
        "http://localhost:3000",
        "http://bytefix.localhost:3000",
        "http://admin.localhost:3000",
        "https://bytefix.wren.app",
        "https://app.wren.app",
    ],
)
async def test_cors_allows_frontend_origins(origin: str) -> None:
    """T-011: frontend and backend are always different origins (every
    tenant gets its own subdomain) - a browser fetch from any of them must
    not be silently blocked by a missing CORS header."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.options(
            "/api/chat",
            headers={"Origin": origin, "Access-Control-Request-Method": "POST"},
        )
    assert response.headers.get("access-control-allow-origin") == origin


@pytest.mark.anyio
async def test_cors_rejects_unrelated_origins() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.options(
            "/api/chat",
            headers={"Origin": "https://evil.example.com", "Access-Control-Request-Method": "POST"},
        )
    assert "access-control-allow-origin" not in response.headers
