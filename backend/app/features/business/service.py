"""E-6: persistence for the Booking page - the links and the cover photo."""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

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
