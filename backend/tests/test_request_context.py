"""Request correlation + structured 500 (app/observability/logging.py).

An unhandled error must not leak a stack trace to the caller; it must return a
structured 500 carrying a correlation id, and every response must echo an
X-Request-ID for support correlation.
"""

from __future__ import annotations

import httpx
import pytest
from fastapi import FastAPI

from app.observability.logging import REQUEST_ID_HEADER, RequestContextMiddleware


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def _app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(RequestContextMiddleware)

    @app.get("/ok")
    async def ok() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/boom")
    async def boom() -> dict[str, str]:
        raise RuntimeError("kaboom")

    return app


async def _client(app: FastAPI) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


@pytest.mark.anyio
async def test_unhandled_error_becomes_structured_500() -> None:
    async with await _client(_app()) as client:
        response = await client.get("/boom")
    assert response.status_code == 500
    body = response.json()
    assert body["detail"] == "An unexpected server error occurred."
    assert body["code"] == "internal_error"
    # The id in the body matches the one echoed in the header.
    assert body["request_id"] == response.headers[REQUEST_ID_HEADER]
    # No stack trace leaked to the caller.
    assert "kaboom" not in response.text


@pytest.mark.anyio
async def test_incoming_request_id_is_echoed() -> None:
    async with await _client(_app()) as client:
        response = await client.get("/ok", headers={REQUEST_ID_HEADER: "trace-123"})
    assert response.headers[REQUEST_ID_HEADER] == "trace-123"


@pytest.mark.anyio
async def test_request_id_is_generated_when_absent() -> None:
    async with await _client(_app()) as client:
        response = await client.get("/ok")
    assert response.headers.get(REQUEST_ID_HEADER)
