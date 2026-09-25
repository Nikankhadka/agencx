"""T-022: per-IP abuse control (app/shared/ratelimit.py).

The classifier and the counter are pure, so they are tested directly; the
middleware is exercised over a tiny app wired the way main.py wires it, so the
429 is proven to carry a request id and to land before the route runs.
"""

from __future__ import annotations

from collections.abc import Iterator

import httpx
import pytest
from fastapi import FastAPI
from pydantic import ValidationError

from app.features.chat.api import ChatRequest
from app.main import docs_enabled
from app.observability.logging import REQUEST_ID_HEADER, RequestContextMiddleware
from app.shared import ratelimit
from app.shared.config import Settings
from app.shared.ratelimit import (
    CHAT,
    DEFAULT,
    MAX_TRACKED_KEYS,
    POLL,
    PUBLIC_READ,
    WINDOW_S,
    RateLimitMiddleware,
    check,
    classify,
    clear_rate_limits,
)

TRUSTED = "x-vercel-forwarded-for"


@pytest.fixture(autouse=True)
def _fresh_counters() -> Iterator[None]:
    clear_rate_limits()
    yield
    clear_rate_limits()


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


# --- classify --------------------------------------------------------------------


@pytest.mark.parametrize(
    ("method", "path", "bucket"),
    [
        ("POST", "/api/chat", CHAT),
        ("GET", "/api/chat/6f1c2b9e-0000-4000-8000-000000000000/messages", POLL),
        ("GET", "/api/public/tenant/acme", PUBLIC_READ),
        ("GET", "/api/public/tenant/acme/cover", PUBLIC_READ),
        ("GET", "/api/conversations", DEFAULT),
        ("POST", "/api/knowledge/documents", DEFAULT),
        ("GET", "/docs", DEFAULT),
        ("GET", "/openapi.json", DEFAULT),
        # Only the method-path pairs the plan names are special: a GET on the
        # chat POST route is not a chat turn.
        ("GET", "/api/chat", DEFAULT),
        ("POST", "/api/public/tenant/acme", DEFAULT),
        ("GET", "/health", None),
    ],
)
def test_classify(method: str, path: str, bucket: str | None) -> None:
    assert classify(method, path) == bucket


# --- counter ---------------------------------------------------------------------


def test_allows_up_to_the_limit_then_rejects_with_a_retry_after() -> None:
    assert [check(CHAT, "1.1.1.1", 3, now=100.0) for _ in range(3)] == [0, 0, 0]
    # 10s into the window, 50s remain.
    assert check(CHAT, "1.1.1.1", 3, now=110.0) == 50


def test_window_resets_after_it_elapses() -> None:
    for _ in range(3):
        check(CHAT, "1.1.1.1", 3, now=100.0)
    assert check(CHAT, "1.1.1.1", 3, now=100.0 + WINDOW_S) == 0


def test_addresses_and_buckets_are_counted_separately() -> None:
    for _ in range(3):
        check(CHAT, "1.1.1.1", 3, now=100.0)
    assert check(CHAT, "1.1.1.1", 3, now=100.0) > 0
    assert check(CHAT, "2.2.2.2", 3, now=100.0) == 0
    assert check(POLL, "1.1.1.1", 3, now=100.0) == 0


def test_a_limit_of_zero_means_unlimited() -> None:
    assert all(check(CHAT, "1.1.1.1", 0, now=100.0) == 0 for _ in range(1000))
    assert ratelimit._windows == {}


def test_retry_after_is_never_zero_for_a_rejection() -> None:
    check(CHAT, "1.1.1.1", 1, now=100.0)
    # A hair before the window closes: still rejected, must say at least 1s.
    assert check(CHAT, "1.1.1.1", 1, now=100.0 + WINDOW_S - 0.001) == 1


def test_bound_allows_new_addresses_unrecorded_but_keeps_limiting_tracked_ones(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(ratelimit, "MAX_TRACKED_KEYS", 3)
    for n in range(3):
        check(CHAT, f"10.0.0.{n}", 1, now=100.0)
    # A fourth address is over the bound: allowed every time, never tracked.
    assert check(CHAT, "10.9.9.9", 1, now=101.0) == 0
    assert check(CHAT, "10.9.9.9", 1, now=101.0) == 0
    assert ("chat", "10.9.9.9") not in ratelimit._windows
    # A tracked address is still enforced.
    assert check(CHAT, "10.0.0.0", 1, now=101.0) > 0


def test_bound_sweeps_expired_entries_before_giving_up(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ratelimit, "MAX_TRACKED_KEYS", 3)
    for n in range(3):
        check(CHAT, f"10.0.0.{n}", 1, now=100.0)
    later = 100.0 + WINDOW_S
    assert check(CHAT, "10.9.9.9", 1, now=later) == 0
    # The sweep made room, so the newcomer IS tracked and now limited.
    assert ("chat", "10.9.9.9") in ratelimit._windows
    assert check(CHAT, "10.9.9.9", 1, now=later) > 0


def test_the_real_bound_is_the_documented_ten_thousand() -> None:
    assert MAX_TRACKED_KEYS == 10_000


# --- middleware ------------------------------------------------------------------


def _app() -> tuple[FastAPI, list[str]]:
    """The middleware stack as main.py builds it, over two stub routes."""
    calls: list[str] = []
    app = FastAPI()
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(RequestContextMiddleware)

    @app.post("/api/chat")
    async def chat() -> dict[str, str]:
        calls.append("chat")
        return {"ok": "yes"}

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app, calls


def _use_settings(monkeypatch: pytest.MonkeyPatch, **overrides: object) -> None:
    settings = Settings(**overrides)  # type: ignore[arg-type]
    monkeypatch.setattr(ratelimit, "get_settings", lambda: settings)


async def _client(app: FastAPI) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


@pytest.mark.anyio
async def test_over_the_limit_is_a_problem_json_429_before_the_route_runs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _use_settings(monkeypatch, rate_limit_chat_per_min=2)
    app, calls = _app()
    async with await _client(app) as client:
        headers = {TRUSTED: "203.0.113.7"}
        first = await client.post("/api/chat", headers=headers)
        second = await client.post("/api/chat", headers=headers)
        third = await client.post("/api/chat", headers=headers)
    assert (first.status_code, second.status_code, third.status_code) == (200, 200, 429)
    assert calls == ["chat", "chat"]  # the third never reached the route
    assert third.headers["content-type"] == "application/problem+json"
    assert 1 <= int(third.headers["retry-after"]) <= 60
    body = third.json()
    assert body["code"] == "rate_limited"
    # Innermost placement: the 429 still carries the correlation id.
    assert body["request_id"] == third.headers[REQUEST_ID_HEADER]


@pytest.mark.anyio
async def test_only_the_first_forwarded_address_is_the_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _use_settings(monkeypatch, rate_limit_chat_per_min=1)
    app, _ = _app()
    async with await _client(app) as client:
        assert (
            await client.post("/api/chat", headers={TRUSTED: "203.0.113.7, 10.0.0.1"})
        ).status_code == 200
        # Same client behind a different proxy hop: still the same key.
        assert (
            await client.post("/api/chat", headers={TRUSTED: "203.0.113.7, 10.9.9.9"})
        ).status_code == 429
        assert (
            await client.post("/api/chat", headers={TRUSTED: "198.51.100.1"})
        ).status_code == 200


@pytest.mark.anyio
async def test_untrusted_forwarded_for_is_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    _use_settings(monkeypatch, rate_limit_chat_per_min=1)
    app, _ = _app()
    async with await _client(app) as client:
        for _ in range(5):
            response = await client.post("/api/chat", headers={"x-forwarded-for": "203.0.113.7"})
            assert response.status_code == 200


@pytest.mark.anyio
async def test_no_trusted_header_means_no_limiting(monkeypatch: pytest.MonkeyPatch) -> None:
    _use_settings(monkeypatch, rate_limit_chat_per_min=1)
    app, calls = _app()
    async with await _client(app) as client:
        for _ in range(5):
            assert (await client.post("/api/chat")).status_code == 200
    assert len(calls) == 5


@pytest.mark.anyio
async def test_missing_header_warns_once_in_production_and_never_locally(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    app, _ = _app()
    _use_settings(monkeypatch, environment="local")
    with caplog.at_level("WARNING", logger="app.ratelimit"):
        async with await _client(app) as client:
            await client.post("/api/chat")
    assert caplog.records == []

    _use_settings(monkeypatch, environment="production")
    with caplog.at_level("WARNING", logger="app.ratelimit"):
        async with await _client(app) as client:
            await client.post("/api/chat")
            await client.post("/api/chat")
    assert len(caplog.records) == 1


@pytest.mark.anyio
async def test_kill_switch_disables_limiting(monkeypatch: pytest.MonkeyPatch) -> None:
    _use_settings(monkeypatch, rate_limit_enabled=False, rate_limit_chat_per_min=1)
    app, _ = _app()
    async with await _client(app) as client:
        for _ in range(5):
            assert (
                await client.post("/api/chat", headers={TRUSTED: "203.0.113.7"})
            ).status_code == 200


@pytest.mark.anyio
async def test_health_is_exempt(monkeypatch: pytest.MonkeyPatch) -> None:
    _use_settings(monkeypatch, rate_limit_default_per_min=1)
    app, _ = _app()
    async with await _client(app) as client:
        for _ in range(5):
            assert (
                await client.get("/health", headers={TRUSTED: "203.0.113.7"})
            ).status_code == 200


# --- docs toggle -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("environment", "enabled"),
    [("local", True), ("ci", True), ("production", False), ("Production", False)],
)
def test_docs_are_off_only_in_production(environment: str, enabled: bool) -> None:
    assert docs_enabled(environment) is enabled


# --- chat message cap ------------------------------------------------------------


def test_chat_message_is_capped_at_2000_characters() -> None:
    assert ChatRequest(slug="acme", message="a" * 2000)
    # FastAPI turns this into the standard 422 before the route (and any row
    # write or LLM call) runs.
    with pytest.raises(ValidationError):
        ChatRequest(slug="acme", message="a" * 2001)
