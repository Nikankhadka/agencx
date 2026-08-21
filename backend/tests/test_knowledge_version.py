"""P-4: the derived knowledge version and what moves it.

Against real Postgres, because the whole point of the derivation is that the
database maintains it: the ``documents`` touch trigger (0018) and the
``tenant_config`` one (0003) are what make a re-ingest or a profile write
visible to the context-package cache. Stubbing them out would test nothing.

The re-ingest case runs the real ingestion pipeline rather than hand-writing the
UPDATE it issues - a pipeline that stopped touching the row is exactly the bug
this ticket exists to prevent, and only the real call can catch it.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from typing import Any

import asyncpg
import pytest
import pytest_asyncio

from app.ingestion.pipeline import process_document
from app.services.knowledge_version import knowledge_version
from app.shared import db
from app.shared.config import get_settings
from tests.conftest import _app_dsn_for
from tests.fakes import ZeroEmbedder

pytestmark = pytest.mark.db


@pytest.fixture(autouse=True)
def _uploads_dir(tmp_path: Path) -> Iterator[None]:
    import os

    original = os.environ.get("UPLOADS_DIR")
    os.environ["UPLOADS_DIR"] = str(tmp_path)
    get_settings.cache_clear()
    yield
    if original is None:
        os.environ.pop("UPLOADS_DIR", None)
    else:
        os.environ["UPLOADS_DIR"] = original
    get_settings.cache_clear()


@pytest_asyncio.fixture
async def pool(migrated_db: str) -> AsyncIterator[None]:
    await db.create_pool(dsn=_app_dsn_for(migrated_db), min_size=1, max_size=4)
    try:
        yield
    finally:
        await db.close_pool()


async def _seed_tenant(conn: asyncpg.Connection[Any]) -> uuid.UUID:
    tenant_id: uuid.UUID = await conn.fetchval(
        "insert into tenants (slug, name) values ($1, $2) returning id",
        f"kv-{uuid.uuid4().hex[:8]}",
        "Knowledge Version Co",
    )
    await conn.execute("insert into tenant_config (tenant_id) values ($1)", tenant_id)
    return tenant_id


async def _add_document(conn: asyncpg.Connection[Any], tenant_id: uuid.UUID) -> uuid.UUID:
    document_id: uuid.UUID = await conn.fetchval(
        "insert into documents (tenant_id, filename, doc_type, status) "
        "values ($1, 'faq.md', 'faq', 'ready') returning id",
        tenant_id,
    )
    return document_id


async def _version(tenant_id: uuid.UUID) -> Any:
    async with db.tenant_context(tenant_id, "customer") as conn:
        return await knowledge_version(conn, tenant_id)


async def test_version_is_stable_when_nothing_changes(
    pool: None, superuser_conn: asyncpg.Connection[Any]
) -> None:
    tenant_id = await _seed_tenant(superuser_conn)
    await _add_document(superuser_conn, tenant_id)

    first = await _version(tenant_id)
    second = await _version(tenant_id)

    assert first == second


async def test_upload_bumps_the_version(
    pool: None, superuser_conn: asyncpg.Connection[Any]
) -> None:
    tenant_id = await _seed_tenant(superuser_conn)
    before = await _version(tenant_id)

    await _add_document(superuser_conn, tenant_id)

    assert await _version(tenant_id) > before


async def test_profile_change_bumps_the_version(
    pool: None, superuser_conn: asyncpg.Connection[Any]
) -> None:
    tenant_id = await _seed_tenant(superuser_conn)
    await _add_document(superuser_conn, tenant_id)
    before = await _version(tenant_id)

    await superuser_conn.execute(
        'update tenant_config set config = \'{"profile": {"name": "Sam"}}\'::jsonb '
        "where tenant_id = $1",
        tenant_id,
    )

    assert await _version(tenant_id) > before


async def test_reingest_through_the_pipeline_bumps_the_version(
    pool: None, superuser_conn: asyncpg.Connection[Any]
) -> None:
    tenant_id = await _seed_tenant(superuser_conn)
    document_id = await _add_document(superuser_conn, tenant_id)
    upload = Path(get_settings().uploads_dir) / str(tenant_id)
    upload.mkdir(parents=True, exist_ok=True)
    (upload / f"{document_id}.md").write_bytes(b"We are open weekdays 9-5.")
    before = await _version(tenant_id)

    async with db.tenant_context(tenant_id, "tenant_admin") as conn:
        await process_document(
            conn, document_id=document_id, tenant_id=tenant_id, embedder=ZeroEmbedder()
        )

    after = await _version(tenant_id)
    assert after > before
    status = await superuser_conn.fetchval(
        "select status from documents where id = $1", document_id
    )
    assert status == "ready"


async def test_document_delete_bumps_the_version(
    pool: None, superuser_conn: asyncpg.Connection[Any]
) -> None:
    tenant_id = await _seed_tenant(superuser_conn)
    document_id = await _add_document(superuser_conn, tenant_id)
    before = await _version(tenant_id)

    await superuser_conn.execute("delete from documents where id = $1", document_id)

    # Deleting the newest document lowers the max - the version moves, which is
    # all the cache key needs (it compares for equality, never ordering).
    assert await _version(tenant_id) != before
