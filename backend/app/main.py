from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.cors import CORSMiddleware

from app.features.business.api import router as business_router
from app.features.business.public_api import router as business_public_router
from app.features.chat.api import router as chat_router
from app.features.conversations.api import router as conversations_router
from app.features.dashboards.api import router as dashboards_router
from app.features.escalations.api import router as escalations_router
from app.features.knowledge.api import router as knowledge_router
from app.features.onboarding.api import router as onboarding_router
from app.features.platform.api import router as platform_router
from app.features.pricing.api import router as pricing_router
from app.features.tenants.api import router as tenants_router
from app.features.tenants.public_api import router as public_router
from app.llm.dependency import get_embedder_dependency
from app.observability.logging import RequestContextMiddleware, configure_logging
from app.retrieval.dependency import close_reranker, get_reranker_dependency
from app.shared import db
from app.shared.config import get_settings
from app.shared.errors import ProblemDetails, problem_response, validation_problem
from app.shared.startup import check_startup_config

# Local dev only. B-4 deploys the frontend and backend as two services behind
# one Vercel origin (vercel.json routes /api/* and /health to the backend), so
# in production the browser never makes a cross-origin request and no preflight
# happens at all - there is no deployed host to list here. Only the dev stack is
# split across ports (frontend :3000 -> backend :8000), which `localhost`
# covers. No cookies are used (bearer tokens only), so allow_credentials stays
# False.
_ALLOWED_ORIGIN_REGEX = r"^https?://localhost(:\d+)?$"

logger = logging.getLogger("app.main")


class HealthResponse(BaseModel):
    status: str


async def _warm_local_models() -> None:
    """Load the local embedder/reranker models now rather than on the first
    customer message.

    Both are lazily loaded on first use, so before this the first chat of a
    fresh process paid the full sentence-transformers import plus two model
    loads inside the turn. Warming is best-effort: a failure here (e.g. no
    network on a cold HF cache) must not stop the app from booting, since the
    same load would simply be retried on first use.
    """
    for name, component in (
        ("embedder", get_embedder_dependency()),
        ("reranker", get_reranker_dependency()),
    ):
        try:
            await component.warm()
        except Exception:
            logger.warning("could not warm %s; it will load on first use", name, exc_info=True)


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
    await _warm_local_models()
    try:
        yield
    finally:
        await close_reranker()
        if created_here:
            await db.close_pool()


app = FastAPI(title="Agencx", version="0.1.0", lifespan=lifespan)


def _openapi() -> dict[str, object]:
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(title=app.title, version=app.version, routes=app.routes)
    schemas = schema.setdefault("components", {}).setdefault("schemas", {})
    problem_schema = ProblemDetails.model_json_schema(ref_template="#/components/schemas/{model}")
    schemas["ProblemDetails"] = problem_schema
    schemas.update(problem_schema.pop("$defs", {}))
    problem_ref = {"$ref": "#/components/schemas/ProblemDetails"}
    for path in schema.get("paths", {}).values():
        for operation in path.values():
            if not isinstance(operation, dict) or "responses" not in operation:
                continue
            responses = operation["responses"]
            for status_code in tuple(responses):
                if status_code.isdigit() and int(status_code) >= 400:
                    responses[status_code] = {
                        "description": _error_description(status_code),
                        "content": {"application/problem+json": {"schema": problem_ref}},
                    }
            responses["default"] = {
                "description": "Problem details error",
                "content": {"application/problem+json": {"schema": problem_ref}},
            }
    app.openapi_schema = schema
    return schema


def _error_description(status_code: str) -> str:
    # `.get`, not `[...]`: a route declaring a code that is not listed here
    # (402, 410, 451) would otherwise raise straight out of openapi(), which
    # takes down /openapi.json, /docs, and `npm run gen:types` with it.
    return {
        "400": "Malformed request",
        "401": "Unauthenticated",
        "403": "Forbidden",
        "404": "Not found",
        "405": "Method not allowed",
        "409": "Conflict",
        "413": "Content too large",
        "415": "Unsupported media type",
        "422": "Validation failed",
        "429": "Rate limited",
        "500": "Internal server error",
        "502": "Upstream failure",
        "503": "Service unavailable",
        "504": "Gateway timeout",
    }.get(status_code, "Error")


app.openapi = _openapi  # type: ignore[method-assign]


@app.exception_handler(RequestValidationError)
async def request_validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return validation_problem(request, exc)


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    detail: str | None = exc.detail if isinstance(exc.detail, str) else None
    if exc.status_code >= 500:
        detail = None
    return problem_response(request, exc.status_code, detail=detail, headers=exc.headers)


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

app.include_router(tenants_router)
app.include_router(platform_router)
app.include_router(public_router)
app.include_router(business_public_router)
app.include_router(onboarding_router)
app.include_router(knowledge_router)
app.include_router(business_router)
app.include_router(chat_router)
app.include_router(conversations_router)
app.include_router(escalations_router)
app.include_router(pricing_router)
app.include_router(dashboards_router)


@app.get("/health", response_model=HealthResponse)
async def health(request: Request) -> HealthResponse | JSONResponse:
    """Readiness probe (the ALB target-group health check). Pings the DB so an
    instance that can't reach Postgres is pulled from rotation instead of
    serving 500s."""
    try:
        pool = db.get_pool()
        async with pool.acquire() as conn:
            await conn.execute("select 1")
    except Exception:
        logger.exception("health check failed: database unreachable")
        return problem_response(request, 503)
    return HealthResponse(status="ok")
