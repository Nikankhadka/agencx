"""E-6: the Business page's read model - one call for everything on the screen."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.features.business import service
from app.features.onboarding import service as onboarding_service
from app.features.tenants import service as tenant_service


def _describe(profile: dict[str, Any]) -> str | None:
    """The prototype's one-line subtitle: what the business does, then when it
    is open. Either half may be missing - a business that never answered the
    hours beat gets the shorter sentence rather than a dangling separator."""
    parts = [str(profile.get(key, "")).strip() for key in ("services", "hours")]
    kept = [part for part in parts if part]
    return " · ".join(kept) if kept else None


async def booking_page(*, tenant_id: UUID) -> dict[str, Any]:
    """Everything the Business page renders, in one read.

    Replaces the two ad-hoc calls the screen used to make (`/api/tenants/me`
    plus `/api/onboarding/state`, the second of which returns an interview
    transcript to render a business name). The shape here is the page.

    Offerings are deliberately absent: M-4 gave them their own screen
    (`/business/offerings`) and the owner sees them as a customer does through
    the storefront preview link, so carrying a second read-only copy here would
    be a list nothing renders.
    """
    tenant = await tenant_service.get_tenant(str(tenant_id))
    if tenant is None:
        raise LookupError("tenant not found")
    record = await onboarding_service.load_record(tenant_id=tenant_id)
    profile: dict[str, Any] = (record or {}).get("draft") or {}
    brand = tenant.get("brand") or {}

    return {
        "slug": tenant["slug"],
        "name": (
            (brand.get("display_name") if isinstance(brand, dict) else None)
            or tenant.get("business_name")
            or str(profile.get("business_name", "")).strip()
            or tenant["name"]
        ),
        "tagline": _describe(profile),
        "links": await service.read_links(tenant_id=tenant_id),
        "has_cover": await service.has_cover(tenant_id=tenant_id),
    }


async def storefront_sections(*, tenant_id: UUID) -> dict[str, Any]:
    return await service.read_storefront_sections(tenant_id=tenant_id)
