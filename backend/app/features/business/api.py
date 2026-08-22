"""E-6: the Booking page - the business as a customer finds it.

One read for the whole screen, a write for the four links, and the cover photo
in and out. The Services rows are derived in ``offerings.py``, where the money
rule is held by construction: no model runs on this path, and a price is a
verbatim slice of the owner's own line.
"""

from __future__ import annotations

from typing import Annotated
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from pydantic import BaseModel, Field, field_validator

from app.features.business import controller, service
from app.shared import auth

router = APIRouter(prefix="/api/business", tags=["business"])

# One cover photo, resized client-side before it is sent. The cap is what a row
# should carry, not what an image could be.
MAX_COVER_BYTES = 2 * 1024 * 1024
ALLOWED_COVER_MIME = ("image/jpeg", "image/png", "image/webp")


class Offering(BaseModel):
    name: str
    price: str | None


class BookingPageResponse(BaseModel):
    slug: str
    name: str
    tagline: str | None
    services: list[Offering]
    links: dict[str, str]
    has_cover: bool


class LinksUpdate(BaseModel):
    """The four link slots. An empty string clears one; an absent key leaves it."""

    links: dict[str, str] = Field(default_factory=dict)

    @field_validator("links")
    @classmethod
    def _validate(cls, value: dict[str, str]) -> dict[str, str]:
        for key, url in value.items():
            if key not in service.LINK_KEYS:
                raise ValueError(f"unknown link {key!r}")
            if not url.strip():
                continue
            parsed = urlparse(url.strip())
            # These addresses are rendered as links a customer clicks, so the
            # scheme allowlist is the guard against a javascript: or data: URL
            # arriving through the owner's own settings.
            if parsed.scheme.lower() not in ("http", "https") or not parsed.netloc:
                raise ValueError(f"{key} must be an absolute http:// or https:// URL")
        return value


@router.get("/page", response_model=BookingPageResponse)
async def get_booking_page(
    admin: Annotated[auth.AuthedTenantAdmin, Depends(auth.require_tenant_admin)],
) -> BookingPageResponse:
    try:
        return BookingPageResponse(**await controller.booking_page(tenant_id=admin.tenant_id))
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="tenant not found"
        ) from exc


@router.patch("/links", response_model=dict[str, str])
async def patch_links(
    body: LinksUpdate,
    admin: Annotated[auth.AuthedTenantAdmin, Depends(auth.require_tenant_admin)],
) -> dict[str, str]:
    current = await service.read_links(tenant_id=admin.tenant_id)
    current.update(body.links)
    return await service.write_links(tenant_id=admin.tenant_id, links=current)


@router.put("/cover", status_code=status.HTTP_204_NO_CONTENT)
async def put_cover(
    admin: Annotated[auth.AuthedTenantAdmin, Depends(auth.require_tenant_admin)],
    file: Annotated[UploadFile, File()],
) -> Response:
    data = await file.read()
    mime = (file.content_type or "").split(";")[0].strip().lower()
    if mime not in ALLOWED_COVER_MIME:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="the cover photo must be a JPEG, PNG or WebP image",
        )
    if len(data) > MAX_COVER_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"the cover photo must be under {MAX_COVER_BYTES // (1024 * 1024)}MB",
        )
    if not data:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="the file is empty"
        )
    await service.write_cover(tenant_id=admin.tenant_id, mime=mime, data=data)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/cover")
async def get_cover(
    admin: Annotated[auth.AuthedTenantAdmin, Depends(auth.require_tenant_admin)],
) -> Response:
    found = await service.read_cover(tenant_id=admin.tenant_id)
    if found is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="no cover photo")
    mime, data, updated_at = found
    return Response(
        content=data,
        media_type=mime,
        headers={
            # Private: this is one tenant's own image behind their own session.
            # The mtime ETag is what stops the browser refetching it on every
            # visit to the page while still showing a new one immediately.
            "Cache-Control": "private, max-age=0, must-revalidate",
            "ETag": f'"{updated_at.timestamp()}"',
        },
    )


@router.delete("/cover", status_code=status.HTTP_204_NO_CONTENT)
async def delete_cover(
    admin: Annotated[auth.AuthedTenantAdmin, Depends(auth.require_tenant_admin)],
) -> Response:
    await service.delete_cover(tenant_id=admin.tenant_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
