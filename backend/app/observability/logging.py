"""Structured JSON logging + per-request correlation.

Before this the app logged almost nothing (only auth had a logger) and had no
request id, so a provider failure that didn't happen to hit the budget/timeout
paths was invisible in CloudWatch. This module gives every log line a JSON
shape and a ``request_id``, and the middleware here emits one access line per
request and tags any log emitted during that request with its id.

Correlation channel: the id is stashed both on ``request.state.request_id``
(read by the global exception handler, which runs above this middleware after
its context resets) and on a contextvar (so any ``logger`` call deep in the
stack carries the id automatically).
"""

from __future__ import annotations

import json
import logging
import re
import time
from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.shared.errors import problem_response

REQUEST_ID_HEADER = "X-Request-ID"
_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{1,96}$")

# A dedicated logger whose handler emits plain, human-readable lines (not the
# JSON shape every other record gets). Used for the conversational transcript
# so a human can follow a demo live instead of parsing JSON blobs.
TRANSCRIPT_LOGGER_NAME = "app.transcript"

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)

# The attributes every LogRecord carries; anything else on a record came from a
# caller's ``extra=`` and is worth emitting as a structured field.
_STANDARD_RECORD_ATTRS = frozenset(logging.makeLogRecord({}).__dict__) | {
    "message",
    "asctime",
    "taskName",
}


class JsonFormatter(logging.Formatter):
    """Renders a log record as a single-line JSON object, folding in the
    current request id and any ``extra=`` fields the caller passed."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created)),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        request_id = request_id_var.get()
        if request_id is not None:
            payload["request_id"] = request_id
        for key, value in record.__dict__.items():
            if key not in _STANDARD_RECORD_ATTRS and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


class PlainFormatter(logging.Formatter):
    """Renders a record as a single human-readable line (timestamp + message)
    rather than JSON - for the conversational transcript a person reads live."""

    def format(self, record: logging.LogRecord) -> str:
        ts = time.strftime("%H:%M:%S", time.gmtime(record.created))
        return f"{ts} {record.getMessage()}"


def configure_logging(level: str = "INFO") -> None:
    """Install the JSON formatter on the root logger's stdout handler. Idempotent
    - safe to call once at startup even if a handler already exists."""
    root = logging.getLogger()
    root.setLevel(level.upper())
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    # Replace any pre-existing handlers so uvicorn's default plain formatter
    # doesn't double-log alongside ours.
    root.handlers = [handler]
    # uvicorn installs its own handlers on these; clear them so their records
    # propagate to the root JSON handler instead of printing twice.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logging.getLogger(name).handlers = []
    # The transcript logger prints plain lines and does not propagate, so its
    # records never double up as JSON on the root handler.
    transcript = logging.getLogger(TRANSCRIPT_LOGGER_NAME)
    transcript.propagate = False
    transcript.setLevel(level.upper())
    transcript_handler = logging.StreamHandler()
    transcript_handler.setFormatter(PlainFormatter())
    transcript.handlers = [transcript_handler]


logger = logging.getLogger("app.request")


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Assigns each request a correlation id, emits one access log line, and
    turns any unhandled exception into a structured 500 (logged with the id).

    It handles the 500 here rather than via ``@app.exception_handler`` because
    that runs outside CORSMiddleware, so its response would miss CORS headers
    and a browser couldn't read it. This middleware sits inside CORS, so the
    response it returns still gets CORS headers on the way out.
    """

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        supplied_id = request.headers.get(REQUEST_ID_HEADER, "")
        request_id = supplied_id if _REQUEST_ID_RE.fullmatch(supplied_id) else uuid4().hex
        request.state.request_id = request_id
        token = request_id_var.set(request_id)
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = round((time.perf_counter() - start) * 1000, 1)
            logger.exception(
                "request failed",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "duration_ms": duration_ms,
                },
            )
            response = problem_response(request, 500)
        else:
            # The ALB pings /health constantly; logging every probe would drown
            # the real traffic, so skip the access line for it.
            if request.url.path != "/health":
                duration_ms = round((time.perf_counter() - start) * 1000, 1)
                logger.info(
                    "request",
                    extra={
                        "method": request.method,
                        "path": request.url.path,
                        "status_code": response.status_code,
                        "duration_ms": duration_ms,
                    },
                )
        finally:
            request_id_var.reset(token)
        response.headers[REQUEST_ID_HEADER] = request_id
        return response
