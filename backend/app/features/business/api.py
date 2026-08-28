"""E-6: the Booking page - the business as a customer finds it.

One read for the whole screen, a write for the four links, the cover photo in
and out, and (O-9) the two profile fields that stay correctable after go-live.
The Services rows are derived in ``offerings.py``, where the money rule is held
by construction: no model runs on this path, and a price is a verbatim slice of
the owner's own line.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Annotated
from urllib.parse import urlparse
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.features.business import controller, service
from app.llm.dependency import get_embedder_dependency
from app.llm.embedder import Embedder
from app.onboarding.beats import NO_ABN
from app.shared import auth

router = APIRouter(prefix="/api/business", tags=["business"])

# One cover photo, resized client-side before it is sent. The cap is what a row
# should carry, not what an image could be.
MAX_COVER_BYTES = 2 * 1024 * 1024
ALLOWED_COVER_MIME = ("image/jpeg", "image/png", "image/webp")


class BookingOffering(BaseModel):
    name: str
    price: str | None


class BookingPageResponse(BaseModel):
    slug: str
    name: str
    tagline: str | None
    services: list[BookingOffering]
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


_MAX_OFFERING_DOLLARS = Decimal("1000000")


def _offering_price(value: object) -> Decimal | None:
    if value is None:
        return None
    try:
        amount = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError("price is not a valid decimal amount") from exc
    if not amount.is_finite():
        raise ValueError("price must be finite")
    if amount < 0:
        raise ValueError("price must not be negative")
    if amount > _MAX_OFFERING_DOLLARS:
        raise ValueError(f"price must not exceed {_MAX_OFFERING_DOLLARS}")
    if amount != amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP):
        raise ValueError("price must have at most 2 decimal places")
    return amount


def _price_cents(amount: Decimal | None) -> int | None:
    if amount is None:
        return None
    return int((amount * 100).to_integral_value(rounding=ROUND_HALF_UP))


class OfferingResponse(BaseModel):
    id: UUID
    name: str
    description: str
    price_cents: int | None


class OfferingCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    description: str = ""
    price_dollars: Decimal | None = None

    @field_validator("name")
    @classmethod
    def _name(cls, value: str) -> str:
        if not (normalized := value.strip()):
            raise ValueError("name must not be blank")
        return normalized

    @field_validator("description")
    @classmethod
    def _description(cls, value: str) -> str:
        return value.strip()

    @field_validator("price_dollars", mode="before")
    @classmethod
    def _price(cls, value: object) -> Decimal | None:
        return _offering_price(value)


class OfferingUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    description: str | None = None
    price_dollars: Decimal | None = None

    @field_validator("name")
    @classmethod
    def _name(cls, value: str | None) -> str | None:
        if value is not None and not (normalized := value.strip()):
            raise ValueError("name must not be blank")
        return normalized if value is not None else None

    @field_validator("description")
    @classmethod
    def _description(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None

    @field_validator("price_dollars", mode="before")
    @classmethod
    def _price(cls, value: object) -> Decimal | None:
        return _offering_price(value)

    def updates(self) -> dict[str, object]:
        updates: dict[str, object] = {}
        if "name" in self.model_fields_set:
            updates["name"] = self.name
        if "description" in self.model_fields_set:
            updates["description"] = self.description
        if "price_dollars" in self.model_fields_set:
            updates["price_cents"] = _price_cents(self.price_dollars)
        return updates


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


@router.get("/offerings", response_model=list[OfferingResponse])
async def list_offerings(
    admin: Annotated[auth.AuthedTenantAdmin, Depends(auth.require_tenant_admin)],
) -> list[OfferingResponse]:
    rows = await service.list_offerings(tenant_id=admin.tenant_id)
    return [OfferingResponse.model_validate(row) for row in rows]


@router.post("/offerings", response_model=OfferingResponse, status_code=status.HTTP_201_CREATED)
async def post_offering(
    body: OfferingCreate,
    admin: Annotated[auth.AuthedTenantAdmin, Depends(auth.require_tenant_admin)],
    embedder: Annotated[Embedder, Depends(get_embedder_dependency)],
) -> OfferingResponse:
    return OfferingResponse.model_validate(
        await service.create_offering(
            tenant_id=admin.tenant_id,
            name=body.name,
            description=body.description,
            price_cents=_price_cents(body.price_dollars),
            embedder=embedder,
        )
    )


@router.patch("/offerings/{offering_id}", response_model=OfferingResponse)
async def patch_offering(
    offering_id: UUID,
    body: OfferingUpdate,
    admin: Annotated[auth.AuthedTenantAdmin, Depends(auth.require_tenant_admin)],
    embedder: Annotated[Embedder, Depends(get_embedder_dependency)],
) -> OfferingResponse:
    updates = body.updates()
    if not updates:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="no fields to update"
        )
    row = await service.update_offering(
        tenant_id=admin.tenant_id,
        offering_id=offering_id,
        updates=updates,
        embedder=embedder,
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="offering not found")
    return OfferingResponse.model_validate(row)


@router.delete("/offerings/{offering_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_offering(
    offering_id: UUID,
    admin: Annotated[auth.AuthedTenantAdmin, Depends(auth.require_tenant_admin)],
    embedder: Annotated[Embedder, Depends(get_embedder_dependency)],
) -> Response:
    if not await service.delete_offering(
        tenant_id=admin.tenant_id, offering_id=offering_id, embedder=embedder
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="offering not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


class ProfileUpdate(BaseModel):
    """The ABN and its GST answer - the slice of the profile that stays
    correctable after go-live.

    Extra keys are refused rather than ignored: the rest of the profile is
    frozen at confirm, and a request that thought otherwise should hear so.
    """

    model_config = ConfigDict(extra="forbid")

    abn: str | None = None
    gst: str | None = None

    def normalized(self) -> dict[str, str]:
        """The fields as they are stored, or a ValueError an owner can read.

        Not field validators: pydantic prefixes those with "Value error," and
        this message is rendered verbatim under the field the owner is typing
        in.
        """
        fields: dict[str, str] = {}
        if self.abn is not None:
            fields["abn"] = _normalize_abn(self.abn)
        if self.gst is not None:
            gst = self.gst.strip().lower()
            if gst not in ("yes", "no"):
                raise ValueError("GST is either yes or no.")
            fields["gst"] = gst
        return fields


def _normalize_abn(value: str) -> str:
    """Stored as the eleven digits, the way the interview stores them.

    Cleared means "no ABN" - the same stated answer the interview's "No, not
    yet" chip leaves - rather than "never asked", which is what an empty string
    means everywhere else in the draft.
    """
    if not value.strip() or value.strip().lower() == NO_ABN:
        return NO_ABN
    digits = "".join(char for char in value if char.isdigit())
    if len(digits) != 11:
        raise ValueError("An ABN is 11 digits.")
    return digits


@router.get("/profile", response_model=dict[str, str])
async def get_profile(
    admin: Annotated[auth.AuthedTenantAdmin, Depends(auth.require_tenant_admin)],
) -> dict[str, str]:
    return await service.read_profile(tenant_id=admin.tenant_id)


@router.patch("/profile", response_model=dict[str, str])
async def patch_profile(
    body: ProfileUpdate,
    admin: Annotated[auth.AuthedTenantAdmin, Depends(auth.require_tenant_admin)],
) -> dict[str, str]:
    try:
        fields = body.normalized()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    if not fields:
        return await service.read_profile(tenant_id=admin.tenant_id)
    return await service.write_profile(tenant_id=admin.tenant_id, fields=fields)


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
