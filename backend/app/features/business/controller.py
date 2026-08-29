"""E-6: the Business page's read model - one call for everything on the screen."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.features.business import service
from app.features.tenants import service as tenant_service


async def booking_page(*, tenant_id: UUID) -> dict[str, Any]:
    """Everything the Business page renders, in one read.

    Replaces the two ad-hoc calls the screen used to make (`/api/tenants/me`
    plus `/api/onboarding/state`, the second of which returns an interview
    transcript to render a business name). The shape here is the page.

    Offerings are deliberately absent: M-4 gave them their own screen
    (`/business/offerings`) and the owner sees them as a customer does through
    the storefront preview link, so carrying a second read-only copy here would
    be a list nothing renders.

    Name and tagline come from the same helpers the public storefront uses, off
    the same resolved profile: this screen calls itself a preview of what
    customers see, and two derivations would eventually make it a lie.
    """
    tenant = await tenant_service.get_tenant(str(tenant_id))
    if tenant is None:
        raise LookupError("tenant not found")
    profile = await service.read_profile_for_display(tenant_id=tenant_id)
    brand = tenant.get("brand") or {}

    return {
        "slug": tenant["slug"],
        "name": service.display_name(
            brand=brand,
            business_name=tenant.get("business_name"),
            profile=profile,
            fallback=tenant["name"],
        ),
        "tagline": service.profile_tagline(profile),
        "links": await service.read_links(tenant_id=tenant_id),
        "has_cover": await service.has_cover(tenant_id=tenant_id),
        "offerings": (await service.list_offerings(tenant_id=tenant_id, active_only=True))[:3],
    }


async def storefront_sections(*, tenant_id: UUID) -> dict[str, Any]:
    return await service.read_storefront_sections(tenant_id=tenant_id)
