"""T-024: error tracking (Sentry).

An unhandled 500 used to exist only as a container log line nobody reads. With
``SENTRY_DSN`` set it also becomes an event. With it unset this module does
nothing - no import-time side effects, no network, no overhead - the same
off-by-default rule ``tracing.py`` applies to Langfuse.

What is deliberately NOT sent, because this app carries a customer's name and
phone number in the chat box:

- request bodies (``max_request_body_size="never"``): a 500 on ``POST /api/chat``
  would otherwise attach the customer's verbatim message;
- frame local variables (``include_local_variables=False``): the SDK default
  captures ``body`` and ``message`` from the chat handler's stack frames, which is
  the same leak by another road;
- default PII (``send_default_pii=False``): cookies, client IP, auth headers;
- the transcript logger, whose whole job is to print message text;
- log-derived events (``event_level=None``): logs stay breadcrumbs, so every
  ``logger.error`` in the app does not become an issue and nothing double-reports;
- traces (``traces_sample_rate=0.0``): Langfuse owns tracing, and spans would burn
  the free error quota.

Errors are reported from two places. Anything the ASGI stack lets through is
seen by the SDK's own integrations; but ``RequestContextMiddleware`` swallows the
exception and returns a 500 response, so the SDK would see only a response and
create no event - that middleware calls ``sentry_sdk.capture_exception()`` itself
(a no-op while uninitialised).

ponytail: the exception message and stack text are still sent, and they can
carry data (a database error quoting a value, a parse error quoting model
output). Upgrade path is a ``before_send`` scrubber, worth writing once real
events show what actually leaks; guessing patterns now would be false comfort.
"""

from __future__ import annotations

import logging
import os

import sentry_sdk
from sentry_sdk.integrations.logging import LoggingIntegration, ignore_logger

from app.observability.logging import TRANSCRIPT_LOGGER_NAME
from app.shared.config import Settings

logger = logging.getLogger("app.observability.sentry")

_warned_unset = False


def _sentry_configured(settings: Settings) -> bool:
    return bool(settings.sentry_dsn)


def init_sentry(settings: Settings) -> bool:
    """Start error reporting when a DSN is set. Returns whether it did."""
    global _warned_unset
    if not _sentry_configured(settings):
        # A production deploy with no DSN has no error tracking at all, and that
        # reads exactly like a healthy one - say so once instead of silently.
        if settings.environment.lower() == "production" and not _warned_unset:
            _warned_unset = True
            logger.warning("error tracking is inactive: SENTRY_DSN is unset in production")
        return False

    ignore_logger(TRANSCRIPT_LOGGER_NAME)
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.environment,
        # Vercel sets this on every deployment; unset locally, which is fine.
        release=os.getenv("VERCEL_GIT_COMMIT_SHA") or None,
        send_default_pii=False,
        max_request_body_size="never",
        include_local_variables=False,
        traces_sample_rate=0.0,
        integrations=[LoggingIntegration(event_level=None)],
    )
    return True
