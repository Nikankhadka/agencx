"""One safe JSON error shape for every HTTP failure."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict
from starlette.requests import Request
from starlette.status import HTTP_401_UNAUTHORIZED


class ProblemError(BaseModel):
    pointer: str
    code: str
    detail: str


class ProblemDetails(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str = "about:blank"
    title: str
    status: int
    detail: str
    instance: str
    code: str
    request_id: str
    errors: list[ProblemError] | None = None


_TITLES = {
    400: "Bad Request",
    401: "Unauthorized",
    403: "Forbidden",
    404: "Not Found",
    405: "Method Not Allowed",
    409: "Conflict",
    413: "Content Too Large",
    415: "Unsupported Media Type",
    422: "Unprocessable Content",
    429: "Too Many Requests",
    500: "Internal Server Error",
    502: "Bad Gateway",
    503: "Service Unavailable",
    504: "Gateway Timeout",
}

_CODES = {
    400: "bad_request",
    401: "unauthenticated",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    413: "content_too_large",
    415: "unsupported_media_type",
    422: "validation_failed",
    429: "rate_limited",
    500: "internal_error",
    502: "upstream_failure",
    503: "service_unavailable",
    504: "gateway_timeout",
}

_SAFE_DETAILS = {
    400: "The request could not be understood.",
    401: "Authentication is required.",
    403: "You do not have permission to perform this action.",
    404: "The requested resource was not found.",
    405: "The request method is not allowed for this resource.",
    409: "The request conflicts with the current resource state.",
    413: "The submitted content is too large.",
    415: "The submitted media type is not supported.",
    422: "One or more fields are invalid.",
    429: "Too many requests. Please try again later.",
    500: "An unexpected server error occurred.",
    502: "An upstream service failed to respond.",
    503: "The service is temporarily unavailable.",
    504: "An upstream service timed out.",
}


def request_id(request: Request) -> str:
    value = getattr(request.state, "request_id", None)
    return value if isinstance(value, str) else "unknown"


def _pointer(loc: Iterable[Any]) -> str:
    parts = list(loc)
    if parts and parts[0] in {"body", "query", "path", "header", "cookie"}:
        parts = parts[1:]
    escaped = [str(part).replace("~", "~0").replace("/", "~1") for part in parts]
    return "/" + "/".join(escaped) if escaped else ""


def validation_problem(request: Request, exc: RequestValidationError) -> JSONResponse:
    malformed = any(
        error.get("type") in {"json_invalid", "model_attributes_type"}
        # `loc` is indexed, not unpacked: an empty one would make this handler
        # itself raise, turning a 400 into a 500 on the way out.
        and tuple(error.get("loc", ()))[:1] == ("body",)
        for error in exc.errors()
    )
    status = 400 if malformed else 422
    code = "malformed_request" if malformed else "validation_failed"
    errors = [
        ProblemError(
            pointer=_pointer(error.get("loc", ())),
            code=str(error.get("type", "invalid")),
            detail=str(error.get("msg", "Field is invalid.")),
        )
        for error in exc.errors()
    ]
    return problem_response(request, status, code=code, errors=errors)


def problem_response(
    request: Request,
    status: int,
    *,
    code: str | None = None,
    detail: str | None = None,
    errors: list[ProblemError] | None = None,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    request_ref = request_id(request)
    payload = ProblemDetails(
        title=_TITLES.get(status, "Request Error"),
        status=status,
        detail=detail or _SAFE_DETAILS.get(status, "The request could not be completed."),
        instance=f"urn:agencx:request:{request_ref}",
        code=code or _CODES.get(status, "request_failed"),
        request_id=request_ref,
        errors=errors,
    )
    response_headers = {"content-type": "application/problem+json"}
    if headers:
        response_headers.update(headers)
    if status == HTTP_401_UNAUTHORIZED:
        response_headers.setdefault("www-authenticate", "Bearer")
    if status == 429:
        response_headers.setdefault("retry-after", "60")
    return JSONResponse(
        status_code=status,
        content=payload.model_dump(exclude_none=True),
        headers=response_headers,
    )
