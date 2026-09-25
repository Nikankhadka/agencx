"""T-031 (ADR D35): app.shared.export and app.shared.offboard against real Postgres.

Each scenario seeds its own tenant as the superuser and passes its slug, so other
modules' data never leaks into a count. The external systems (Cloudinary, Supabase
Storage, GoTrue) are stubs that record what they were asked to delete.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

import asyncpg
import httpx
import pytest

from app.features.business.media import Cloudinary
from app.shared.config import Settings
from app.shared.export import TENANT_TABLES, export_tenant
from app.shared.offboard import OffboardError, main, offboard_tenant
from app.shared.storage import LocalStorage

pytestmark = pytest.mark.db

CONFIGURED = Settings(
    cloudinary_cloud_name="cloud",
    cloudinary_api_key="key",
    cloudinary_api_secret="secret",
    supabase_url="http://gotrue.test",
    supabase_service_role_key="service",
)


class World:
    """One fully populated tenant and the ids the assertions need."""

    def __init__(self, tenant_id: uuid.UUID, slug: str, user_id: uuid.UUID) -> None:
        self.tenant_id = tenant_id
        self.slug = slug
        self.user_id = user_id


async def _world(conn: asyncpg.Connection[Any]) -> World:
    slug = f"offboard-{uuid.uuid4().hex[:8]}"
    tenant_id: uuid.UUID = await conn.fetchval(
        "insert into tenants (slug, name) values ($1, 'Offboard Test Co') returning id", slug
    )
    user_id = uuid.uuid4()
    await conn.execute(
        "insert into tenant_config (tenant_id, config) values ($1, $2)",
        tenant_id,
        json.dumps({"onboarding": {"business": "Offboard Test Co"}}),
    )
    await conn.execute("insert into users (id, tenant_id) values ($1, $2)", user_id, tenant_id)
    document_id: uuid.UUID = await conn.fetchval(
        "insert into documents (tenant_id, filename, doc_type, status) "
        "values ($1, 'faq.pdf', 'faq', 'ready') returning id",
        tenant_id,
    )
    await conn.execute(
        "insert into knowledge_chunks (tenant_id, document_id, content, embedding) "
        "values ($1, $2, 'We are open nine to five.', $3::text::vector)",
        tenant_id,
        document_id,
        "[" + ",".join(["0.1"] * 384) + "]",
    )
    await conn.execute(
        "insert into tenant_assets (tenant_id, kind, mime, bytes) "
        "values ($1, 'cover', 'image/png', $2)",
        tenant_id,
        b"\x89PNG-not-a-real-image",
    )
    await conn.execute(
        "insert into tenant_media (tenant_id, role, type, provider, url, public_id) "
        "values ($1, 'cover', 'image', 'cloudinary', 'https://res.cloudinary.com/x.png', 'x-1')",
        tenant_id,
    )
    conversation_id: uuid.UUID = await conn.fetchval(
        "insert into conversations (tenant_id) values ($1) returning id", tenant_id
    )
    await conn.execute(
        "insert into messages (tenant_id, conversation_id, role, content) "
        "values ($1, $2, 'customer', 'my number is 0400 000 000')",
        tenant_id,
        conversation_id,
    )
    await conn.execute(
        "insert into quotes (tenant_id, conversation_id, line_items, subtotal_cents, total_cents) "
        "values ($1, $2, '[]', 1000, 1000)",
        tenant_id,
        conversation_id,
    )
    await conn.execute(
        "insert into cost_logs (tenant_id, conversation_id, model, input_tokens, output_tokens, "
        "cost_usd) values ($1, $2, 'gpt-4o-mini', 10, 5, 0.1)",
        tenant_id,
        conversation_id,
    )
    return World(tenant_id, slug, user_id)


async def _remaining(conn: asyncpg.Connection[Any], tenant_id: uuid.UUID) -> dict[str, int]:
    counts = {
        table: await conn.fetchval(
            f"select count(*) from {table} where tenant_id = $1",  # noqa: S608
            tenant_id,
        )
        for table in TENANT_TABLES
    }
    counts["tenants"] = await conn.fetchval("select count(*) from tenants where id = $1", tenant_id)
    return counts


class RecordingStorage(LocalStorage):
    """Real folder deletion on a temp dir, recording every prefix it was asked for."""

    def __init__(self, root: Path, *, fail_times: int = 0) -> None:
        super().__init__(str(root))
        self.prefixes: list[str] = []
        self._fail_times = fail_times

    async def delete_prefix(self, prefix: str) -> None:
        self.prefixes.append(prefix)
        if self._fail_times:
            self._fail_times -= 1
            raise RuntimeError("storage is down")
        await super().delete_prefix(prefix)


class Recorder:
    """Stands in for Cloudinary's HTTP API, Storage and GoTrue, recording the calls."""

    def __init__(self, *, storage_root: Path, fail_storage_times: int = 0) -> None:
        self.cloudinary_calls: list[str] = []
        self.auth_users: list[uuid.UUID] = []
        self.storage = RecordingStorage(storage_root, fail_times=fail_storage_times)

    def cloudinary(self, settings: Settings = CONFIGURED) -> Cloudinary:
        def handler(request: httpx.Request) -> httpx.Response:
            self.cloudinary_calls.append(str(request.url))
            return httpx.Response(200, json={"result": "ok"})

        return Cloudinary(settings, httpx.AsyncClient(transport=httpx.MockTransport(handler)))

    async def delete_auth_user(self, user_id: uuid.UUID) -> None:
        self.auth_users.append(user_id)


async def test_every_table_with_a_tenant_id_is_covered(
    migrated_db: str, superuser_conn: asyncpg.Connection[Any]
) -> None:
    """A new tenant table must join TENANT_TABLES, or it escapes export and the receipt."""
    rows = await superuser_conn.fetch(
        "select c.table_name from information_schema.columns c "
        "join information_schema.tables t using (table_schema, table_name) "
        "where c.table_schema = 'public' and c.column_name = 'tenant_id' "
        "and t.table_type = 'BASE TABLE'"
    )
    assert {r["table_name"] for r in rows} == set(TENANT_TABLES)


async def test_export_carries_the_tenants_data_and_only_the_tenants_data(
    migrated_db: str, superuser_conn: asyncpg.Connection[Any]
) -> None:
    mine = await _world(superuser_conn)
    theirs = await _world(superuser_conn)

    document = await export_tenant(mine.slug, migrated_db)

    assert set(document["tables"]) == set(TENANT_TABLES)
    assert document["tenant"]["slug"] == mine.slug
    tables = document["tables"]
    assert tables["tenant_config"][0]["config"] == {"onboarding": {"business": "Offboard Test Co"}}
    assert tables["messages"][0]["content"] == "my number is 0400 000 000"
    assert tables["quotes"][0]["total_cents"] == 1000
    everything = json.dumps(document)
    assert str(theirs.tenant_id) not in everything
    assert str(theirs.user_id) not in everything


async def test_export_replaces_the_bulky_derived_columns_with_their_size(
    migrated_db: str, superuser_conn: asyncpg.Connection[Any]
) -> None:
    world = await _world(superuser_conn)

    tables = (await export_tenant(world.slug, migrated_db))["tables"]

    asset = tables["tenant_assets"][0]
    assert "bytes" not in asset
    assert asset["bytes_length"] == len(b"\x89PNG-not-a-real-image")
    chunk = tables["knowledge_chunks"][0]
    assert "embedding" not in chunk
    assert "tsv" not in chunk
    assert chunk["embedding_dims"] == 384
    assert chunk["content"] == "We are open nine to five."


async def test_export_of_an_unknown_slug_is_an_error_not_an_empty_file(migrated_db: str) -> None:
    with pytest.raises(LookupError):
        await export_tenant("no-such-tenant-anywhere", migrated_db)


async def test_a_dry_run_reports_and_deletes_nothing(
    migrated_db: str, superuser_conn: asyncpg.Connection[Any], tmp_path: Path
) -> None:
    world = await _world(superuser_conn)
    fake = Recorder(storage_root=tmp_path)

    receipt = await offboard_tenant(
        world.slug,
        dsn=migrated_db,
        settings=CONFIGURED,
        cloudinary=fake.cloudinary(),
        storage=fake.storage,
        delete_auth_user=fake.delete_auth_user,
    )

    assert receipt.applied is False
    assert receipt.tenant_id == str(world.tenant_id)
    assert receipt.rows["messages"] == 1
    assert receipt.rows["quotes"] == 1
    assert receipt.cloudinary_public_ids == ["x-1"]
    assert receipt.auth_user_ids == [str(world.user_id)]
    assert receipt.storage_prefix == f"{world.tenant_id}/"
    assert (fake.cloudinary_calls, fake.storage.prefixes, fake.auth_users) == ([], [], [])
    assert (await _remaining(superuser_conn, world.tenant_id))["tenants"] == 1


async def test_apply_removes_the_tenant_everywhere_and_touches_no_other(
    migrated_db: str, superuser_conn: asyncpg.Connection[Any], tmp_path: Path
) -> None:
    mine = await _world(superuser_conn)
    theirs = await _world(superuser_conn)
    other_before = await _remaining(superuser_conn, theirs.tenant_id)
    fake = Recorder(storage_root=tmp_path)
    await LocalStorage(str(tmp_path)).put(f"{mine.tenant_id}/doc.pdf", b"x")

    receipt = await offboard_tenant(
        mine.slug,
        apply=True,
        dsn=migrated_db,
        settings=CONFIGURED,
        cloudinary=fake.cloudinary(),
        storage=fake.storage,
        delete_auth_user=fake.delete_auth_user,
    )

    assert receipt.applied is True
    assert len(fake.cloudinary_calls) == 1
    assert fake.cloudinary_calls[0].endswith("/image/destroy")
    assert fake.storage.prefixes == [f"{mine.tenant_id}/"]
    assert fake.auth_users == [mine.user_id]
    assert not (tmp_path / str(mine.tenant_id)).exists()
    # Every table is empty for the tenant, the quote included ...
    assert set((await _remaining(superuser_conn, mine.tenant_id)).values()) == {0}
    # ... and the other tenant is exactly as it was.
    assert await _remaining(superuser_conn, theirs.tenant_id) == other_before


async def test_a_failure_before_postgres_leaves_the_tenant_and_a_rerun_finishes(
    migrated_db: str, superuser_conn: asyncpg.Connection[Any], tmp_path: Path
) -> None:
    world = await _world(superuser_conn)
    fake = Recorder(storage_root=tmp_path, fail_storage_times=1)

    def run() -> Any:
        return offboard_tenant(
            world.slug,
            apply=True,
            dsn=migrated_db,
            settings=CONFIGURED,
            cloudinary=fake.cloudinary(),
            storage=fake.storage,
            delete_auth_user=fake.delete_auth_user,
        )

    with pytest.raises(OffboardError, match="storage is down"):
        await run()
    after_failure = await _remaining(superuser_conn, world.tenant_id)
    assert after_failure["tenants"] == 1
    assert after_failure["messages"] == 1
    # GoTrue is only reached once storage is done, so nothing was half-deleted there.
    assert fake.auth_users == []

    await run()

    assert set((await _remaining(superuser_conn, world.tenant_id)).values()) == {0}
    assert fake.auth_users == [world.user_id]


async def test_a_missing_credential_is_caught_before_anything_is_deleted(
    migrated_db: str, superuser_conn: asyncpg.Connection[Any], tmp_path: Path
) -> None:
    world = await _world(superuser_conn)
    fake = Recorder(storage_root=tmp_path)
    # Explicit empties: Settings reads the environment, which may carry real values.
    no_cloudinary = Settings(
        cloudinary_cloud_name="",
        cloudinary_api_key="",
        cloudinary_api_secret="",
        supabase_url="http://gotrue.test",
        supabase_service_role_key="k",
    )

    # Even the dry run refuses: a dry run that passes must be a run that can finish.
    with pytest.raises(OffboardError, match="Cloudinary"):
        await offboard_tenant(
            world.slug,
            dsn=migrated_db,
            settings=no_cloudinary,
            cloudinary=fake.cloudinary(no_cloudinary),
            storage=fake.storage,
            delete_auth_user=fake.delete_auth_user,
        )

    no_auth = Settings(
        cloudinary_cloud_name="c",
        cloudinary_api_key="k",
        cloudinary_api_secret="s",
        supabase_url="",
        supabase_service_role_key="",
    )
    with pytest.raises(OffboardError, match="SUPABASE_SERVICE_ROLE_KEY"):
        await offboard_tenant(
            world.slug,
            apply=True,
            dsn=migrated_db,
            settings=no_auth,
            cloudinary=fake.cloudinary(no_auth),
            storage=fake.storage,
        )

    assert (fake.cloudinary_calls, fake.storage.prefixes) == ([], [])
    assert (await _remaining(superuser_conn, world.tenant_id))["tenants"] == 1


async def test_an_unknown_slug_is_an_error_not_a_silent_no_op(migrated_db: str) -> None:
    with pytest.raises(LookupError):
        await offboard_tenant("no-such-tenant-anywhere", dsn=migrated_db, settings=CONFIGURED)


def test_apply_without_the_matching_confirmation_is_refused() -> None:
    for argv in (["--slug", "acme", "--apply"], ["--slug", "acme", "--apply", "--confirm", "acm"]):
        with pytest.raises(SystemExit) as exc:
            main(argv)
        assert exc.value.code == 2
