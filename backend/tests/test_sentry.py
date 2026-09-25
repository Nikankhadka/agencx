"""T-024: backend error tracking (app/observability/sentry.py).

Two halves. The init contract (off without a DSN, one production warning, the
PII-safe kwargs) is checked against a recorder standing in for ``sentry_sdk.init``.
The privacy claim is checked for real: the SDK is started with a transport that
keeps events in memory, a stub app wired with the real ``RequestContextMiddleware``
raises inside a handler that holds customer text in a local variable, and the
captured event is searched for that text.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from typing import Any

import httpx
import pytest
import sentry_sdk
from fastapi import FastAPI, Request
from sentry_sdk.envelope import Envelope
from sentry_sdk.transport import Transport

from app.observability import sentry
from app.observability.logging import TRANSCRIPT_LOGGER_NAME, RequestContextMiddleware
from app.shared.config import Settings

DSN = "https://publickey@o0.ingest.example.invalid/1"
SECRET = "MY-NAME-IS-JANE-CALL-0400-000-000"
BEARER = "Bearer eyJ-super-secret-token"


@pytest.fixture(autouse=True)
def _fresh_sentry() -> Iterator[None]:
    sentry._warned_unset = False
    yield
    # Integration patching is global and cannot be undone, but it is inert with no
    # active client; replacing the client with a disabled one keeps later tests clean.
    sentry_sdk.init()


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def _settings(**overrides: object) -> Settings:
    return Settings(**overrides)  # type: ignore[arg-type]


class _Recorder:
    """Stands in for ``sentry_sdk.init`` so no client is ever created."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def __call__(self, **kwargs: Any) -> None:
        self.calls.append(kwargs)


# --- init contract ---------------------------------------------------------------


def test_no_dsn_creates_no_client(monkeypatch: pytest.MonkeyPatch) -> None:
    recorder = _Recorder()
    monkeypatch.setattr(sentry_sdk, "init", recorder)
    assert sentry.init_sentry(_settings(sentry_dsn="")) is False
    assert recorder.calls == []


def test_unset_dsn_warns_once_in_production_and_never_locally(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(sentry_sdk, "init", _Recorder())
    with caplog.at_level("WARNING", logger="app.observability.sentry"):
        sentry.init_sentry(_settings(sentry_dsn="", environment="local"))
    assert caplog.records == []

    with caplog.at_level("WARNING", logger="app.observability.sentry"):
        sentry.init_sentry(_settings(sentry_dsn="", environment="production"))
        sentry.init_sentry(_settings(sentry_dsn="", environment="Production"))
    assert len(caplog.records) == 1


def test_a_set_dsn_in_production_does_not_warn(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(sentry_sdk, "init", _Recorder())
    with caplog.at_level("WARNING", logger="app.observability.sentry"):
        assert sentry.init_sentry(_settings(sentry_dsn=DSN, environment="production")) is True
    assert caplog.records == []


def test_init_passes_only_the_pii_safe_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    recorder = _Recorder()
    monkeypatch.setattr(sentry_sdk, "init", recorder)
    monkeypatch.setenv("VERCEL_GIT_COMMIT_SHA", "abc1234")
    sentry.init_sentry(_settings(sentry_dsn=DSN, environment="production"))

    (kwargs,) = recorder.calls
    integrations = kwargs.pop("integrations")
    assert kwargs == {
        "dsn": DSN,
        "environment": "production",
        "release": "abc1234",
        "send_default_pii": False,
        "max_request_body_size": "never",
        "include_local_variables": False,
        "traces_sample_rate": 0.0,
    }
    assert len(integrations) == 1


def test_release_is_none_when_not_on_vercel(monkeypatch: pytest.MonkeyPatch) -> None:
    recorder = _Recorder()
    monkeypatch.setattr(sentry_sdk, "init", recorder)
    monkeypatch.delenv("VERCEL_GIT_COMMIT_SHA", raising=False)
    sentry.init_sentry(_settings(sentry_dsn=DSN))
    assert recorder.calls[0]["release"] is None


# --- what actually leaves the process --------------------------------------------


class _Capture(Transport):
    """Keeps every event in memory instead of posting it."""

    def __init__(self, events: list[dict[str, Any]]) -> None:
        super().__init__()
        self.events = events

    def capture_envelope(self, envelope: Envelope) -> None:
        event = envelope.get_event()
        if event is not None:
            self.events.append(dict(event))


def _start_capturing(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """Run the real ``init_sentry`` but ship events to a list."""
    events: list[dict[str, Any]] = []
    real_init = sentry_sdk.init
    monkeypatch.setattr(
        sentry_sdk,
        "init",
        lambda **kwargs: real_init(**kwargs, transport=_Capture(events)),
    )
    assert sentry.init_sentry(_settings(sentry_dsn=DSN)) is True
    return events


def _app() -> FastAPI:
    """The real 500-swallowing middleware over a handler shaped like the chat route:
    the customer's text sits in locals and in the body when it raises."""
    app = FastAPI()
    app.add_middleware(RequestContextMiddleware)

    @app.post("/api/chat")
    async def chat(request: Request) -> dict[str, str]:
        payload = await request.json()
        message = payload["message"]  # noqa: F841 - the local is the point
        logging.getLogger(TRANSCRIPT_LOGGER_NAME).warning("customer said: %s", message)
        logging.getLogger("app.chat").warning("routing turn")
        raise RuntimeError("chat handler failed")

    @app.get("/logged")
    async def logged() -> dict[str, str]:
        logging.getLogger("app.chat").error("an error log line, not an exception")
        return {"ok": "yes"}

    return app


async def _post_chat(app: FastAPI) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.post(
            "/api/chat",
            json={"message": SECRET},
            headers={"authorization": BEARER, "cookie": "session=cookie-secret"},
        )


@pytest.mark.anyio
async def test_a_swallowed_500_becomes_an_event_without_the_customers_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events = _start_capturing(monkeypatch)
    response = await _post_chat(_app())
    sentry_sdk.flush()

    # The middleware still answers normally...
    assert response.status_code == 500
    assert response.headers["content-type"] == "application/problem+json"
    # ...and the seam in RequestContextMiddleware reported it (exactly once).
    (event,) = events
    assert event["exception"]["values"][0]["type"] == "RuntimeError"
    # Guard against a vacuous pass: the request context IS attached, so the
    # absences below mean something.
    assert event["request"]["method"] == "POST"
    assert event["request"]["url"].endswith("/api/chat")

    blob = json.dumps(event)
    assert SECRET not in blob  # not in the body, not in a frame local, not a breadcrumb
    assert "eyJ-super-secret-token" not in blob
    assert "cookie-secret" not in blob
    assert all(
        "vars" not in frame
        for value in event["exception"]["values"]
        for frame in value["stacktrace"]["frames"]
    )
    # "never" leaves the key but empties it (annotated as removed by config).
    assert event["request"]["data"] == ""
    assert event["request"]["headers"]["authorization"] == "[Filtered]"


@pytest.mark.anyio
async def test_transcript_logger_is_not_a_breadcrumb_but_other_loggers_are(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events = _start_capturing(monkeypatch)
    await _post_chat(_app())
    sentry_sdk.flush()

    (event,) = events
    messages = [crumb.get("message") for crumb in event["breadcrumbs"]["values"]]
    assert "routing turn" in messages  # control: breadcrumbs work at all
    assert not any(SECRET in (message or "") for message in messages)


@pytest.mark.anyio
async def test_error_log_lines_do_not_become_events(monkeypatch: pytest.MonkeyPatch) -> None:
    events = _start_capturing(monkeypatch)
    transport = httpx.ASGITransport(app=_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        assert (await client.get("/logged")).status_code == 200
    sentry_sdk.flush()
    assert events == []


@pytest.mark.anyio
async def test_the_500_path_is_untouched_when_sentry_is_off() -> None:
    # No init: capture_exception() must be a silent no-op, not a crash.
    response = await _post_chat(_app())
    assert response.status_code == 500
    assert response.json()["code"] == "internal_error"
