"""One-off migration of legacy Postgres covers into Cloudinary.

Run with the rotated Cloudinary variables configured in the backend environment:
``python -m scripts.migrate_tenant_covers``. The source rows stay intact so the
legacy proxy remains a rollback path until the migration is verified.
"""

from __future__ import annotations

import asyncio

import asyncpg

from app.features.business.media import Cloudinary
from app.shared.config import get_settings


async def migrate() -> int:
    settings = get_settings()
    cloudinary = Cloudinary(settings)
    if not cloudinary.is_configured:
        raise RuntimeError("Cloudinary is not configured")
    conn = await asyncpg.connect(settings.database_url)
    try:
        rows = await conn.fetch(
            "select tenant_id, mime, bytes from tenant_assets "
            "where kind = 'cover' order by tenant_id"
        )
        for row in rows:
            uploaded = await cloudinary.upload(
                data=bytes(row["bytes"]),
                resource_type="image",
                folder=f"tenants/{row['tenant_id']}/cover",
                filename="legacy-cover",
            )
            await conn.execute(
                "insert into tenant_media "
                "(tenant_id, role, type, provider, url, public_id, poster_url) "
                "values ($1, 'cover', $2, $3, $4, $5, $6) "
                "on conflict (tenant_id) where role = 'cover' do update set "
                "type=excluded.type, provider=excluded.provider, url=excluded.url, "
                "public_id=excluded.public_id, poster_url=excluded.poster_url, updated_at=now()",
                row["tenant_id"],
                uploaded.type,
                uploaded.provider,
                uploaded.url,
                uploaded.public_id,
                uploaded.poster_url,
            )
        tenant_ids = [row["tenant_id"] for row in rows]
        destination_count = (
            await conn.fetchval(
                "select count(*) from tenant_media where role = 'cover' "
                "and tenant_id = any($1::uuid[])",
                tenant_ids,
            )
            if tenant_ids
            else 0
        )
        if destination_count != len(rows):
            raise RuntimeError(
                "cover migration count mismatch: "
                f"source={len(rows)} destination={destination_count}"
            )
        print(f"migrated {len(rows)} legacy cover(s)")
        return len(rows)
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(migrate())
