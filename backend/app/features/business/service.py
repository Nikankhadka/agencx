"""E-6: persistence for the Booking page - the links and the cover photo."""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from app.ingestion.pipeline import ingest_catalog_items
from app.llm.embedder import Embedder
from app.shared import db

# The four places a small business is already found. Fixed, because the
# prototype's row is four tiles - an open-ended list is a different screen.
LINK_KEYS = ("website", "google", "facebook", "instagram")

COVER_KIND = "cover"


async def read_links(*, tenant_id: UUID) -> dict[str, str]:
    """The saved links, keyed by platform. Absent keys mean "not added yet"."""
    async with db.tenant_context(tenant_id, "tenant_admin") as conn:
        raw = await conn.fetchval("select brand from tenant_config where tenant_id = $1", tenant_id)
    brand = json.loads(raw) if isinstance(raw, str) else (raw or {})
    links = brand.get("links") if isinstance(brand, dict) else None
    if not isinstance(links, dict):
        return {}
    return {key: str(links[key]) for key in LINK_KEYS if links.get(key)}


async def write_links(*, tenant_id: UUID, links: dict[str, str]) -> dict[str, str]:
    """Replace the links object. An empty string removes one.

    Written into ``brand`` rather than a table of its own: four short strings
    that every surface reading the tenant already fetches, and `brand` is the
    column the public tenant lookup returns, which is where the customer-facing
    page will read them from next.
    """
    kept = {key: value.strip() for key, value in links.items() if key in LINK_KEYS}
    kept = {key: value for key, value in kept.items() if value}
    async with db.tenant_context(tenant_id, "tenant_admin") as conn:
        await conn.execute(
            "update tenant_config set brand = jsonb_set(brand, '{links}', $2::jsonb, true) "
            "where tenant_id = $1",
            tenant_id,
            json.dumps(kept),
        )
    return kept


async def write_cover(*, tenant_id: UUID, mime: str, data: bytes) -> None:
    async with db.tenant_context(tenant_id, "tenant_admin") as conn:
        updated = await conn.execute(
            "update tenant_assets set mime = $3, bytes = $4, updated_at = now() "
            "where tenant_id = $1 and kind = $2",
            tenant_id,
            COVER_KIND,
            mime,
            data,
        )
        if updated == "UPDATE 0":
            await conn.execute(
                "insert into tenant_assets (tenant_id, kind, mime, bytes) values ($1, $2, $3, $4) "
                "on conflict do nothing",
                tenant_id,
                COVER_KIND,
                mime,
                data,
            )


async def read_cover(*, tenant_id: UUID) -> tuple[str, bytes, Any] | None:
    async with db.tenant_context(tenant_id, "tenant_admin") as conn:
        row = await conn.fetchrow(
            "select mime, bytes, updated_at from tenant_assets where tenant_id = $1 and kind = $2",
            tenant_id,
            COVER_KIND,
        )
    if row is None:
        return None
    return row["mime"], bytes(row["bytes"]), row["updated_at"]


async def has_cover(*, tenant_id: UUID) -> bool:
    async with db.tenant_context(tenant_id, "tenant_admin") as conn:
        return bool(
            await conn.fetchval(
                "select 1 from tenant_assets where tenant_id = $1 and kind = $2",
                tenant_id,
                COVER_KIND,
            )
        )


async def delete_cover(*, tenant_id: UUID) -> None:
    async with db.tenant_context(tenant_id, "tenant_admin") as conn:
        await conn.execute(
            "delete from tenant_assets where tenant_id = $1 and kind = $2",
            tenant_id,
            COVER_KIND,
        )


async def list_offers(*, tenant_id: UUID, active_only: bool = False) -> list[dict[str, Any]]:
    """Return the catalog rows that the business chooses to publish as offers.

    Catalog remains the source of truth because agents and deterministic quotes
    already use it. The storefront intentionally omits price fields: pricing is
    an opt-in product concern, while this page describes what the business does.
    """
    active_filter = "and active" if active_only else ""
    async with db.tenant_context(tenant_id, "tenant_admin") as conn:
        rows = await conn.fetch(
            "select id, name, description, active, position from catalog_items "
            f"where tenant_id = $1 {active_filter} order by position, created_at, id",  # noqa: S608
            tenant_id,
        )
    return [dict(row) for row in rows]


async def create_offer(*, tenant_id: UUID, name: str, description: str) -> dict[str, Any]:
    async with db.tenant_context(tenant_id, "tenant_admin") as conn:
        row = await conn.fetchrow(
            "insert into catalog_items (tenant_id, name, description, position) "
            "values ($1, $2, $3, coalesce((select max(position) + 1 from catalog_items "
            "where tenant_id = $1), 0)) "
            "returning id, name, description, active, position",
            tenant_id,
            name,
            description,
        )
    assert row is not None
    return dict(row)


async def update_offer(
    *, tenant_id: UUID, offer_id: UUID, updates: dict[str, Any]
) -> dict[str, Any] | None:
    if not updates:
        rows = await list_offers(tenant_id=tenant_id)
        return next((row for row in rows if row["id"] == offer_id), None)
    columns = tuple(updates)
    assignments = ", ".join(f"{column} = ${index}" for index, column in enumerate(columns, start=3))
    async with db.tenant_context(tenant_id, "tenant_admin") as conn:
        row = await conn.fetchrow(
            f"update catalog_items set {assignments} "  # noqa: S608 - fixed API whitelist
            "where tenant_id = $1 and id = $2 "
            "returning id, name, description, active, position",
            tenant_id,
            offer_id,
            *(updates[column] for column in columns),
        )
    return dict(row) if row is not None else None


async def deactivate_offer(*, tenant_id: UUID, offer_id: UUID) -> bool:
    return (
        await update_offer(tenant_id=tenant_id, offer_id=offer_id, updates={"active": False})
        is not None
    )


async def refresh_offers(*, tenant_id: UUID, embedder: Embedder) -> None:
    """Rebuild the catalog projection after an owner changes an offer."""
    async with db.tenant_context(tenant_id, "tenant_admin") as conn:
        await ingest_catalog_items(conn, tenant_id=tenant_id, embedder=embedder)


async def write_storefront(
    *, tenant_id: UUID, about: str | None = None, reviews: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    """Merge editable storefront sections into the brand configuration.

    These are small presentation fields, not knowledge. Keeping them together
    makes the owner page a direct representation of the public page without a
    separate page-builder schema or drag-and-drop system.
    """
    patch: dict[str, Any] = {}
    if about is not None:
        patch["about"] = about
    if reviews is not None:
        patch["reviews"] = reviews
    async with db.tenant_context(tenant_id, "tenant_admin") as conn:
        await conn.execute(
            "update tenant_config set brand = jsonb_set(brand, '{storefront}', "
            "coalesce(brand->'storefront', '{}'::jsonb) || $2::jsonb, true), updated_at = now() "
            "where tenant_id = $1",
            tenant_id,
            json.dumps(patch),
        )
    return await read_storefront_sections(tenant_id=tenant_id)


async def read_storefront_sections(*, tenant_id: UUID) -> dict[str, Any]:
    async with db.tenant_context(tenant_id, "tenant_admin") as conn:
        raw = await conn.fetchval(
            "select brand -> 'storefront' from tenant_config where tenant_id = $1", tenant_id
        )
    parsed = json.loads(raw) if isinstance(raw, str) else (raw or {})
    if not isinstance(parsed, dict):
        return {"about": "", "reviews": []}
    about = parsed.get("about")
    reviews = parsed.get("reviews")
    return {
        "about": about.strip() if isinstance(about, str) else "",
        "reviews": reviews if isinstance(reviews, list) else [],
    }


async def read_public_storefront(*, tenant_id: UUID) -> dict[str, Any]:
    """Read only the public presentation fields under the customer context."""
    async with db.tenant_context(tenant_id, "customer") as conn:
        tenant = await conn.fetchrow(
            "select t.name, t.business_name, tc.brand, tc.config "
            "from tenants t join tenant_config tc on tc.tenant_id = t.id where t.id = $1",
            tenant_id,
        )
        offers = await conn.fetch(
            "select id, name, description from catalog_items "
            "where tenant_id = $1 and active order by position, created_at, id",
            tenant_id,
        )
        cover = await conn.fetchval(
            "select 1 from tenant_assets where tenant_id = $1 and kind = $2",
            tenant_id,
            COVER_KIND,
        )
    if tenant is None:
        raise LookupError("tenant not found")
    brand_raw = tenant["brand"]
    config_raw = tenant["config"]
    brand = json.loads(brand_raw) if isinstance(brand_raw, str) else (brand_raw or {})
    config = json.loads(config_raw) if isinstance(config_raw, str) else (config_raw or {})
    if not isinstance(brand, dict):
        brand = {}
    if not isinstance(config, dict):
        config = {}
    profile = config.get("profile") or (config.get("onboarding") or {}).get("draft") or {}
    storefront = brand.get("storefront") if isinstance(brand.get("storefront"), dict) else {}
    display_name = (
        brand.get("display_name")
        or tenant["business_name"]
        or (profile.get("business_name") if isinstance(profile, dict) else None)
        or tenant["name"]
    )
    services = profile.get("services") if isinstance(profile, dict) else None
    hours = profile.get("hours") if isinstance(profile, dict) else None
    tagline = " · ".join(
        str(value).strip() for value in (services, hours) if str(value or "").strip()
    )
    raw_reviews = storefront.get("reviews") if isinstance(storefront, dict) else []
    reviews = raw_reviews if isinstance(raw_reviews, list) else []
    return {
        "name": str(display_name),
        "tagline": tagline or None,
        "about": storefront.get("about", "") if isinstance(storefront, dict) else "",
        "links": {
            key: value
            for key, value in (brand.get("links") or {}).items()
            if key in LINK_KEYS and isinstance(value, str) and value
        },
        "offers": [dict(row) for row in offers],
        "reviews": reviews,
        "has_cover": bool(cover),
    }


async def read_public_cover(*, tenant_id: UUID) -> tuple[str, bytes, Any] | None:
    async with db.tenant_context(tenant_id, "customer") as conn:
        row = await conn.fetchrow(
            "select mime, bytes, updated_at from tenant_assets "
            "where tenant_id = $1 and kind = $2",
            tenant_id,
            COVER_KIND,
        )
    if row is None:
        return None
    return row["mime"], bytes(row["bytes"]), row["updated_at"]


# O-9: the slice of the profile an owner can correct after go-live. The rest of
# the profile is written once, at confirm, and stays frozen - the ticket says
# why, and a settings tree that edits all of it is not being built.
PROFILE_FIELDS = ("abn", "gst")


async def read_profile(*, tenant_id: UUID) -> dict[str, str]:
    """The editable profile fields, empty string where nothing was captured.

    Reads `config->profile` (what confirm writes) and falls back per field to
    `config->onboarding.draft` (what an interview in flight has), so a value is
    shown whichever half of the pair holds it.
    """
    async with db.tenant_context(tenant_id, "tenant_admin") as conn:
        raw = await conn.fetchval(
            "select config from tenant_config where tenant_id = $1", tenant_id
        )
    config = json.loads(raw) if isinstance(raw, str) else (raw or {})
    profile = config.get("profile") or {}
    draft = (config.get("onboarding") or {}).get("draft") or {}
    return {key: str(profile.get(key) or draft.get(key) or "") for key in PROFILE_FIELDS}


async def write_profile(*, tenant_id: UUID, fields: dict[str, str]) -> dict[str, str]:
    """Merge `fields` into both places the profile is kept.

    `config->profile` is what confirm writes and what the E-5 spec names;
    `config->onboarding.draft` is what the Booking page reads. They are already
    allowed to diverge - this does not add a second way for them to, so one
    statement moves both. Each object is rebuilt from itself with `||` so a
    tenant missing either key gains it rather than silently keeping the old
    value.
    """
    patch = json.dumps({key: value for key, value in fields.items() if key in PROFILE_FIELDS})
    async with db.tenant_context(tenant_id, "tenant_admin") as conn:
        await conn.execute(
            "update tenant_config set config = jsonb_set("
            "  jsonb_set(config, '{profile}', "
            "    coalesce(config->'profile', '{}'::jsonb) || $2::jsonb, true), "
            "  '{onboarding}', "
            "    coalesce(config->'onboarding', '{}'::jsonb) || jsonb_build_object('draft', "
            "      coalesce(config->'onboarding'->'draft', '{}'::jsonb) || $2::jsonb), true"
            "), updated_at = now() where tenant_id = $1",
            tenant_id,
            patch,
        )
    return await read_profile(tenant_id=tenant_id)
