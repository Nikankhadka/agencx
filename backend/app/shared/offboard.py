"""Operator offboarding: delete one tenant and everything it owns, with a receipt.

This is how an erasure request or a cancelled tenant is closed (privacy page,
T-032; request process and SLA in ``docs/agencx/deploy.md``, ADR D35). It is a
script, not a button: deleting a business is rare, irreversible, and the one
place a customer's quotes are allowed to go (the app role cannot delete them,
migration 0006; the owner connection here can, and cascades do).

Order is external first, so a failure leaves orphans that a re-run finishes
instead of an unreachable tenant with live files:

1. Cloudinary media (one destroy call per ``tenant_media`` row)
2. Supabase Storage everything under ``{tenant_id}/``
3. GoTrue: every ``users`` row's login
4. Postgres: ``delete from tenants`` (every tenant table cascades)

Steps 1 to 3 run before step 4 and each treats "already gone" as success, so a
failure in any of them exits non-zero with Postgres untouched and the same
command safe to run again. Credentials for the steps a tenant actually needs
are checked before anything is deleted, in the dry run too, so a dry run that
passes is a run that can finish.

Dry run is the default and prints the same receipt with nothing deleted.
``--apply`` deletes and requires ``--confirm SLUG`` to repeat the slug. The
receipt is JSON on stdout (status lines go to stderr) and holds only the slug,
opaque ids and counts, so it is safe to keep as the deletion-log entry.

CLI: ``uv run python -m app.shared.offboard --slug SLUG [--apply --confirm SLUG]``
(``make offboard`` / ``make offboard-apply``).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from uuid import UUID

import asyncpg
import httpx

from app.features.business.media import Cloudinary
from app.shared.config import Settings, get_settings
from app.shared.export import TENANT_TABLES
from app.shared.storage import Storage, get_storage

DeleteAuthUser = Callable[[UUID], Awaitable[None]]


class OffboardError(RuntimeError):
    """A step failed before Postgres was touched; the command is safe to re-run."""


@dataclass
class Receipt:
    slug: str
    tenant_id: str
    applied: bool
    at: str
    rows: dict[str, int]
    cloudinary_public_ids: list[str]
    storage_backend: str
    storage_prefix: str
    auth_user_ids: list[str]


def gotrue_deleter(settings: Settings) -> DeleteAuthUser:
    """``DELETE /auth/v1/admin/users/{id}`` with the service role key."""
    key = settings.supabase_service_role_key
    headers = {"Authorization": f"Bearer {key}", "apikey": key}
    base = settings.supabase_url.rstrip("/")

    async def delete(user_id: UUID) -> None:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.delete(f"{base}/auth/v1/admin/users/{user_id}", headers=headers)
        if resp.status_code != 404:  # 404: already gone, a re-run after a partial failure
            resp.raise_for_status()

    return delete


def _preflight(settings: Settings, *, media: int, users: int, cloudinary: Cloudinary) -> None:
    """Refuse to start a run that would stall halfway on a missing credential."""
    if media and not cloudinary.is_configured:
        raise OffboardError(
            f"the tenant has {media} Cloudinary asset(s) but CLOUDINARY_CLOUD_NAME, "
            "CLOUDINARY_API_KEY and CLOUDINARY_API_SECRET are not all set"
        )
    if users and not (settings.supabase_url and settings.supabase_service_role_key):
        raise OffboardError(
            f"the tenant has {users} login(s) but SUPABASE_URL and "
            "SUPABASE_SERVICE_ROLE_KEY are not both set"
        )


async def offboard_tenant(
    slug: str,
    *,
    apply: bool = False,
    dsn: str | None = None,
    settings: Settings | None = None,
    cloudinary: Cloudinary | None = None,
    storage: Storage | None = None,
    delete_auth_user: DeleteAuthUser | None = None,
) -> Receipt:
    """Offboard ``slug``. Writes nothing unless ``apply``. Collaborators are injectable."""
    settings = settings or get_settings()
    cloudinary = cloudinary or Cloudinary(settings)
    storage = storage or get_storage()
    conn = await asyncpg.connect(dsn or settings.database_url)
    try:
        tenant = await conn.fetchrow("select id from tenants where slug = $1", slug)
        if tenant is None:
            raise LookupError(f"no tenant with slug {slug!r}")
        tenant_id: UUID = tenant["id"]

        rows: dict[str, int] = {}
        for table in TENANT_TABLES:
            rows[table] = await conn.fetchval(
                f"select count(*) from {table} where tenant_id = $1",  # noqa: S608
                tenant_id,
            )
        media = await conn.fetch(
            "select public_id, type from tenant_media "
            "where tenant_id = $1 and provider = 'cloudinary' and public_id is not null",
            tenant_id,
        )
        logins = await conn.fetch("select id from users where tenant_id = $1", tenant_id)
        user_ids: list[UUID] = [r["id"] for r in logins]
        receipt = Receipt(
            slug=slug,
            tenant_id=str(tenant_id),
            applied=apply,
            at=datetime.now(UTC).isoformat(),
            rows=rows,
            cloudinary_public_ids=[str(m["public_id"]) for m in media],
            storage_backend=type(storage).__name__,
            storage_prefix=f"{tenant_id}/",
            auth_user_ids=[str(u) for u in user_ids],
        )
        _preflight(settings, media=len(media), users=len(user_ids), cloudinary=cloudinary)
        if not apply:
            return receipt

        try:
            for m in media:
                await cloudinary.delete(public_id=str(m["public_id"]), resource_type=str(m["type"]))
            await storage.delete_prefix(receipt.storage_prefix)
            if user_ids:
                delete = delete_auth_user or gotrue_deleter(settings)
                for user_id in user_ids:
                    await delete(user_id)
        except Exception as exc:  # any failure here must stop before Postgres is touched
            raise OffboardError(f"{type(exc).__name__}: {exc}") from exc

        await conn.execute("delete from tenants where id = $1", tenant_id)
        return receipt
    finally:
        await conn.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Delete one tenant and everything it owns.")
    parser.add_argument("--slug", required=True, help="the tenant to offboard")
    parser.add_argument("--apply", action="store_true", help="delete; the default is a dry run")
    parser.add_argument("--confirm", help="the slug again; required with --apply")
    args = parser.parse_args(argv)
    if args.apply and args.confirm != args.slug:
        parser.error("--apply needs --confirm with the same slug, to prove the right tenant")
    try:
        receipt = asyncio.run(offboard_tenant(args.slug, apply=args.apply))
    except LookupError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except OffboardError as exc:
        print(
            f"error: {exc}\nNothing was deleted from Postgres. Fix the cause and run it again; "
            "objects already removed are skipped.",
            file=sys.stderr,
        )
        return 1
    print(json.dumps(asdict(receipt), indent=2))
    print(
        "Deleted. Keep the receipt above as the deletion-log entry."
        if args.apply
        else "DRY RUN: nothing was deleted. Re-run with --apply --confirm SLUG to delete.",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
