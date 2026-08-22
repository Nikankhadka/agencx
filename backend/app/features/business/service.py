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
