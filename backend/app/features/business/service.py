"""E-6: persistence for the Booking page - the links and the cover photo."""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from app.ingestion.pipeline import ingest_offerings
from app.llm.embedder import Embedder
from app.shared import db

# The four places a small business is already found. Fixed, because the
# prototype's row is four tiles - an open-ended list is a different screen.
LINK_KEYS = ("website", "google", "facebook", "instagram")

COVER_KIND = "cover"


async def list_offerings(*, tenant_id: UUID, active_only: bool = False) -> list[dict[str, Any]]:
    """The owner's structured offerings, in the order they appear on the page.

    ``position`` is the owner's own ordering; ``created_at`` then ``id`` break
    ties so a list that has never been reordered still reads oldest-first
    rather than arbitrarily.
    """
    active_filter = "and active" if active_only else ""
    async with db.tenant_context(tenant_id, "tenant_admin") as conn:
        rows = await conn.fetch(
            "select id, name, description, price_cents, active, position from offerings "
            f"where tenant_id = $1 {active_filter} order by position, created_at, id",  # noqa: S608
            tenant_id,
        )
    return [dict(row) for row in rows]


async def create_offering(
    *,
    tenant_id: UUID,
    name: str,
    description: str,
    price_cents: int | None,
    embedder: Embedder,
) -> dict[str, Any]:
    """Create one offering at the end of the list, then rebuild its projection."""
    async with db.tenant_context(tenant_id, "tenant_admin") as conn:
        row = await conn.fetchrow(
            "insert into offerings (tenant_id, name, description, price_cents, position) "
            "values ($1, $2, $3, $4, coalesce((select max(position) + 1 from offerings "
            "where tenant_id = $1), 0)) "
            "returning id, name, description, price_cents, active, position",
            tenant_id,
            name,
            description,
            price_cents,
        )
        assert row is not None
        await ingest_offerings(conn, tenant_id=tenant_id, embedder=embedder)
    return dict(row)


async def update_offering(
    *,
    tenant_id: UUID,
    offering_id: UUID,
    updates: dict[str, Any],
    embedder: Embedder,
) -> dict[str, Any] | None:
    """Update an offering owned by this tenant and rebuild its projection.

    ``updates`` keys are column names from the API layer's fixed allowlist, not
    caller-supplied strings - the interpolation below is safe for that reason
    and for no other. It is never empty: the route refuses an empty patch with
    a 422 before reaching here.
    """
    columns = tuple(updates)
    assignments = ", ".join(f"{column} = ${index}" for index, column in enumerate(columns, start=3))
    async with db.tenant_context(tenant_id, "tenant_admin") as conn:
        row = await conn.fetchrow(
            f"update offerings set {assignments} "  # noqa: S608 - fixed API allowlist
            "where tenant_id = $1 and id = $2 "
            "returning id, name, description, price_cents, active, position",
            tenant_id,
            offering_id,
            *(updates[column] for column in columns),
        )
        if row is not None:
            await ingest_offerings(conn, tenant_id=tenant_id, embedder=embedder)
    return dict(row) if row is not None else None


async def deactivate_offering(*, tenant_id: UUID, offering_id: UUID, embedder: Embedder) -> bool:
    """Retire an offering by clearing ``active`` rather than deleting the row.

    The row is what a past quote or order refers to by id, so deleting it would
    strand that history; ``active`` exists on the table for exactly this, and
    every reader (the projection, the storefront, the booking page) already
    filters on it. Keeping the row also keeps its ``updated_at``, which is what
    ``knowledge_version`` reads - a hard delete would leave nothing behind for
    the cache to notice.
    """
    return (
        await update_offering(
            tenant_id=tenant_id,
            offering_id=offering_id,
            updates={"active": False},
            embedder=embedder,
        )
        is not None
    )


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
    """Store this tenant's cover, replacing any it already has.

    One statement, so two uploads racing (a double-tapped picker, a retried
    request) resolve to one winner rather than one of them being dropped on the
    primary key while the owner is told it succeeded.
    """
    async with db.tenant_context(tenant_id, "tenant_admin") as conn:
        await conn.execute(
            "insert into tenant_assets (tenant_id, kind, mime, bytes) values ($1, $2, $3, $4) "
            "on conflict (tenant_id, kind) do update set mime = excluded.mime, "
            "bytes = excluded.bytes, updated_at = now()",
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


async def write_storefront(*, tenant_id: UUID, about: str | None = None) -> dict[str, Any]:
    """Merge editable storefront sections into the brand configuration.

    These are small presentation fields, not knowledge. Keeping them together
    makes the owner page a direct representation of the public page without a
    separate page-builder schema or drag-and-drop system.
    """
    patch: dict[str, Any] = {}
    if about is not None:
        patch["about"] = about
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
        return {"about": ""}
    about = parsed.get("about")
    return {
        "about": about.strip() if isinstance(about, str) else "",
    }


def resolve_profile(config: dict[str, Any]) -> dict[str, Any]:
    """The business profile as any presentation surface must read it.

    ``config->profile`` is what confirm writes; ``config->onboarding.draft`` is
    what an interview still in flight has. One resolution order, in one place,
    so the owner's preview and the customer's page cannot read different halves
    of the pair and disagree about the same business.
    """
    profile = config.get("profile") or (config.get("onboarding") or {}).get("draft") or {}
    return profile if isinstance(profile, dict) else {}


def profile_tagline(profile: dict[str, Any]) -> str | None:
    """The prototype's one-line subtitle: what the business does, then when it
    is open. Either half may be missing - a business that never answered the
    hours beat gets the shorter sentence rather than a dangling separator."""
    kept = [part for key in ("services", "hours") if (part := str(profile.get(key, "")).strip())]
    return " · ".join(kept) if kept else None


def display_name(
    *, brand: dict[str, Any], business_name: Any, profile: dict[str, Any], fallback: Any
) -> str:
    """What to call this business, most specific source first: the brand
    override, the name captured at go-live, the profile, then the tenant's
    signup name - which always exists, so this always returns something."""
    return str(
        (brand.get("display_name") if isinstance(brand, dict) else None)
        or business_name
        or str(profile.get("business_name", "")).strip()
        or fallback
    )


async def read_profile_for_display(*, tenant_id: UUID) -> dict[str, Any]:
    """``resolve_profile`` against the owner's own tenant_config."""
    async with db.tenant_context(tenant_id, "tenant_admin") as conn:
        raw = await conn.fetchval(
            "select config from tenant_config where tenant_id = $1", tenant_id
        )
    config = json.loads(raw) if isinstance(raw, str) else (raw or {})
    return resolve_profile(config if isinstance(config, dict) else {})


async def read_public_storefront(*, tenant_id: UUID) -> dict[str, Any]:
    """Read only the public presentation fields under the customer context."""
    async with db.tenant_context(tenant_id, "customer") as conn:
        tenant = await conn.fetchrow(
            "select t.name, t.business_name, tc.brand, tc.config "
            "from tenants t join tenant_config tc on tc.tenant_id = t.id where t.id = $1",
            tenant_id,
        )
        offerings = await conn.fetch(
            "select id, name, description, price_cents from offerings "
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
    profile = resolve_profile(config)
    storefront = brand.get("storefront") if isinstance(brand.get("storefront"), dict) else {}
    return {
        "name": display_name(
            brand=brand,
            business_name=tenant["business_name"],
            profile=profile,
            fallback=tenant["name"],
        ),
        "tagline": profile_tagline(profile),
        "about": storefront.get("about", "") if isinstance(storefront, dict) else "",
        "links": {
            key: value
            for key, value in (brand.get("links") or {}).items()
            if key in LINK_KEYS and isinstance(value, str) and value
        },
        "offerings": [dict(row) for row in offerings],
        "has_cover": bool(cover),
    }


async def read_public_cover(*, tenant_id: UUID) -> tuple[str, bytes, Any] | None:
    async with db.tenant_context(tenant_id, "customer") as conn:
        row = await conn.fetchrow(
            "select mime, bytes, updated_at from tenant_assets where tenant_id = $1 and kind = $2",
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
