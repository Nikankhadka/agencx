"""Public storefront data and image bytes for an active business page."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Response, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from app.features.business import service
from app.features.business.media import OfferingMedia
from app.features.tenants import service as tenant_service

router = APIRouter(prefix="/api/public", tags=["public"])


class PublicOffering(BaseModel):
    """One offering as a customer sees it.

    ``price_cents`` is the owner's own typed figure, passed through untouched -
    the page formats it, nothing computes it. Null means the owner published no
    price, and the page shows none rather than inventing one.
    """

    id: UUID
    name: str
    description: str
    price_cents: int | None
    category: str | None = None
    media: OfferingMedia | None = None


class StorefrontResponse(BaseModel):
    name: str
    tagline: str | None
    links: dict[str, str]
    offerings: list[PublicOffering]
    has_cover: bool
    cover_url: str | None = None


async def _tenant_id(slug: str) -> UUID:
    """The active tenant behind a public slug, as a UUID.

    ``resolve_active_tenant`` hands back a string because the chat surface only
    ever passes it on; the reads below bind it as a query parameter against
    uuid columns, which asyncpg will not coerce, so it is converted here rather
    than at each call site.
    """
    try:
        return UUID(await tenant_service.resolve_active_tenant(slug))
    except tenant_service.TenantNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="unknown tenant slug"
        ) from exc


@router.get(
    "/tenant/{slug}/storefront",
    response_model=StorefrontResponse,
)
async def storefront(slug: str) -> StorefrontResponse:
    tenant_id = await _tenant_id(slug)
    return StorefrontResponse(**await service.read_public_storefront(tenant_id=tenant_id))


@router.get("/tenant/{slug}/cover")
async def cover(slug: str) -> Response:
    tenant_id = await _tenant_id(slug)
    cloud_url = await service.read_cover_url(tenant_id=tenant_id, role=service.COVER_KIND)
    if cloud_url:
        return RedirectResponse(cloud_url)
    found = await service.read_public_cover(tenant_id=tenant_id)
    if found is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="storefront image not found"
        )
    mime, data, updated_at = found
    return Response(
        content=data,
        media_type=mime,
        headers={
            # Public: the same bytes for every customer on this page. Short
            # freshness, then a conditional GET against the mtime ETag - an
            # owner who replaces their cover sees the new one on the next
            # minute rather than the next hour, and an unchanged cover still
            # costs a 304 rather than the image.
            "Cache-Control": "public, max-age=60, must-revalidate",
            "ETag": f'"{updated_at.timestamp()}"',
        },
    )
