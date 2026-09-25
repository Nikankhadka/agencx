"""T-022: per-IP abuse control on the public routes.

``POST /api/chat`` and its transcript poll carry no auth by design (the customer
surface has no login), and every chat hit is an LLM turn plus DB writes. The
per-tenant daily budget in ``limits.py`` bounds *spend*; this bounds *noise* from
one address so a single script cannot burn that budget or fill ``messages``.

One middleware rather than a per-route dependency: a dependency is opt-in, so the
next public route ships unprotected, and it cannot cover ``/docs``. The
middleware sits innermost (main.py), so a 429 still gets an ``X-Request-ID``, an
access log line and CORS headers, and it rejects before a route writes any row.

The client address is read from ONE configurable header, default
``x-vercel-forwarded-for``, which Vercel's edge sets and overwrites. The leftmost
``x-forwarded-for`` entry is client-controlled, so it is never trusted. When the
header is absent (local dev, tests, a direct container probe) the request is NOT
limited: falling back to the socket peer would put the whole internet behind one
counter, and rejecting would break ``make demo`` and the e2e suite.

ponytail: state is a per-process dict, so the effective limit is ``limit x
container count`` and it resets on every cold start; a fixed window allows a 2x
burst across a boundary; and it is a noise limiter, not a spend limiter (a botnet
of IPs each under the limit sails through - see D32). Upgrade path: Vercel WAF
rate-limit rules at the edge, which none of this then needs to replace.
"""

from __future__ import annotations

import logging
import math
import time
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.shared.config import Settings, get_settings
from app.shared.errors import problem_response

logger = logging.getLogger("app.ratelimit")

WINDOW_S = 60.0
# Bound on tracked (bucket, ip) pairs. At the bound, new addresses are allowed
# unrecorded rather than rejected, so a wide scan degrades the limiter for new
# IPs instead of turning it into an outage for real customers.
MAX_TRACKED_KEYS = 10_000
# The bound's expired-entry sweep is O(n); at most once per this many seconds so
# a stream of new addresses cannot make every request pay it.
_SWEEP_MIN_INTERVAL_S = 5.0

CHAT = "chat"
POLL = "poll"
PUBLIC_READ = "public_read"
DEFAULT = "default"

# (bucket, client ip) -> (window start, hits in window), both on the monotonic clock.
_windows: dict[tuple[str, str], tuple[float, int]] = {}
_last_sweep = 0.0
_last_full_warning = -WINDOW_S
_warned_no_header = False


def clear_rate_limits() -> None:
    """Test hook - forget every counter and warning so tests start from zero."""
    global _last_sweep, _last_full_warning, _warned_no_header
    _windows.clear()
    _last_sweep = 0.0
    _last_full_warning = -WINDOW_S
    _warned_no_header = False


def classify(method: str, path: str) -> str | None:
    """The bucket a request counts against, or ``None`` when it is exempt.

    Pure on ``(method, path)`` so it needs no ``Request`` to test."""
    if path == "/health":  # keep-warm.yml and Vercel probe it
        return None
    if method == "POST" and path == "/api/chat":
        return CHAT
    if method == "GET" and path.startswith("/api/chat/") and path.endswith("/messages"):
        return POLL
    if method == "GET" and path.startswith("/api/public/"):
        return PUBLIC_READ
    return DEFAULT


def limit_for(settings: Settings, bucket: str) -> int:
    """Requests allowed per window for a bucket; 0 means unlimited."""
    return {
        CHAT: settings.rate_limit_chat_per_min,
        POLL: settings.rate_limit_poll_per_min,
        PUBLIC_READ: settings.rate_limit_public_read_per_min,
        DEFAULT: settings.rate_limit_default_per_min,
    }[bucket]


def client_ip(header_value: str | None) -> str | None:
    """First entry of the trusted proxy header (it arrives comma-joined), or
    ``None`` when the header is missing or blank."""
    if not header_value:
        return None
    return header_value.split(",")[0].strip() or None


def check(bucket: str, ip: str, limit: int, now: float | None = None) -> int:
    """Count one request. Returns 0 when it is allowed, else the whole seconds
    until the caller's window resets."""
    global _last_sweep, _last_full_warning
    if limit <= 0:
        return 0
    now = time.monotonic() if now is None else now
    key = (bucket, ip)
    entry = _windows.get(key)
    if entry is None or now - entry[0] >= WINDOW_S:
        if entry is None and len(_windows) >= MAX_TRACKED_KEYS:
            if now - _last_sweep >= _SWEEP_MIN_INTERVAL_S:
                _last_sweep = now
                for stale in [k for k, (start, _) in _windows.items() if now - start >= WINDOW_S]:
                    del _windows[stale]
            if len(_windows) >= MAX_TRACKED_KEYS:
                if now - _last_full_warning >= WINDOW_S:
                    _last_full_warning = now
                    logger.warning(
                        "rate limiter is tracking %d addresses; new ones are unlimited "
                        "until entries expire",
                        MAX_TRACKED_KEYS,
                    )
                return 0
        _windows[key] = (now, 1)
        return 0
    start, count = entry
    if count >= limit:
        return max(1, math.ceil(start + WINDOW_S - now))
    _windows[key] = (start, count + 1)
    return 0


def _warn_no_header(settings: Settings) -> None:
    """A deployed environment that never sees the trusted header is not limited
    at all - say so once instead of failing open silently."""
    global _warned_no_header
    if settings.environment.lower() == "production" and not _warned_no_header:
        _warned_no_header = True
        logger.warning(
            "rate limiting is inactive: no %r header on a production request",
            settings.rate_limit_trusted_ip_header,
        )


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        settings = get_settings()
        bucket = classify(request.method, request.url.path)
        if settings.rate_limit_enabled and bucket is not None:
            ip = client_ip(request.headers.get(settings.rate_limit_trusted_ip_header))
            if ip is None:
                _warn_no_header(settings)
            else:
                retry_after = check(bucket, ip, limit_for(settings, bucket))
                if retry_after:
                    return problem_response(request, 429, headers={"retry-after": str(retry_after)})
        return await call_next(request)
