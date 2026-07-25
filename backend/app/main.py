from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from starlette.middleware.cors import CORSMiddleware

from app.api import (
    chat,
    conversations,
    dashboards,
    escalations,
    knowledge,
    onboarding,
    platform,
    pricing,
    public,
    tenants,
)
from app.core import db
from app.core.config import get_settings
from app.core.startup import check_startup_config
from app.observability.logging import RequestContextMiddleware, configure_logging
from app.retrieval.dependency import close_reranker

# The frontend and backend are always different origins - three tenant-facing
# subdomains in dev (localhost:3000) and prod ({slug|admin|app}.wren.app), none
# of them known in advance since every tenant gets its own subdomain. No
# cookies are used (bearer tokens only), so allow_credentials stays False.
_ALLOWED_ORIGIN_REGEX = r"^https?://([a-z0-9-]+\.)?(localhost|wren\.app)(:\d+)?$"

logger = logging.getLogger("app.main")


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Create the wren_app pool on startup, close it on shutdown.

    Guarded against double-create: tests that already created a pool pointed at
    wren_test (backend/tests/conftest.py) drive the app without running this
    lifespan (httpx's ASGITransport does not send lifespan events on its own),
    but the guard keeps this safe even if that ever changes.
    """
    settings = get_settings()
    configure_logging(settings.log_level)
    # Fail loudly now rather than 500ing on the first authed request if a real
    # deployment booted with placeholder/empty secrets.
    check_startup_config(settings)
    created_here = False
    try:
        db.get_pool()
    except RuntimeError:
        await db.create_pool()
        created_here = True
    try:
        yield
    finally:
        await close_reranker()
        if created_here:
            await db.close_pool()


app = FastAPI(title="Wren", version="0.1.0", lifespan=lifespan)
# Order matters: add_middleware prepends, so the LAST added is outermost. CORS
# must be outermost so its headers land on every response - including the
# structured 500 that RequestContextMiddleware (inner) produces for an
# unhandled error.
app.add_middleware(RequestContextMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=_ALLOWED_ORIGIN_REGEX,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(tenants.router)
app.include_router(platform.router)
app.include_router(public.router)
app.include_router(onboarding.router)
app.include_router(knowledge.router)
app.include_router(chat.router)
app.include_router(conversations.router)
app.include_router(escalations.router)
app.include_router(pricing.router)
app.include_router(dashboards.router)


@app.get("/health")
async def health() -> JSONResponse:
    """Readiness probe (the ALB target-group health check). Pings the DB so an
    instance that can't reach Postgres is pulled from rotation instead of
    serving 500s."""
    try:
        pool = db.get_pool()
        async with pool.acquire() as conn:
            await conn.execute("select 1")
    except Exception:
        logger.exception("health check failed: database unreachable")
        return JSONResponse(status_code=503, content={"status": "unavailable"})
    return JSONResponse(status_code=200, content={"status": "ok"})
