"""Public storefront data and image bytes for an active business page."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel, Field

from app.features.business import service
from app.features.tenants import service as tenant_service

router = APIRouter(prefix="/api/public", tags=["public"])


class PublicOffer(BaseModel):
    id: UUID
    name: str
    description: str


class PublicReview(BaseModel):
    quote: str
    author: str
    source: str = ""
    rating: int = Field(ge=1, le=5)


class StorefrontResponse(BaseModel):
    name: str
    tagline: str | None
    about: str
    links: dict[str, str]
    offers: list[PublicOffer]
    reviews: list[PublicReview]
    has_cover: bool


async def _tenant_id(slug: str) -> str:
    try:
        return await tenant_service.resolve_active_tenant(slug)
    except tenant_service.TenantNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="unknown tenant slug"
        ) from exc


@router.get("/tenant/{slug}/storefront", response_model=StorefrontResponse)
async def storefront(slug: str) -> StorefrontResponse:
    tenant_id = await _tenant_id(slug)
    return StorefrontResponse(**await service.read_public_storefront(tenant_id=tenant_id))


@router.get("/tenant/{slug}/cover")
async def cover(slug: str) -> Response:
    found = await service.read_public_cover(tenant_id=await _tenant_id(slug))
    if found is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="storefront image not found"
        )
    mime, data, updated_at = found
    return Response(
        content=data,
        media_type=mime,
        headers={
            "Cache-Control": "public, max-age=3600",
            "ETag": f'\"{updated_at.timestamp()}\"',
        },
    )
