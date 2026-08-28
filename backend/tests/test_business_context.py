"""O-4: the two-path business-context seam.

Against real Postgres, because the path decision is made from a real corpus
measurement and the fast path is a real query. The estimator is deterministic
(characters, not a tokenizer), so "below" and "above" the threshold are seeded
exactly rather than approximately: the threshold setting is squeezed down for
the over-budget case instead of seeding a megabyte of prose.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator, Iterator
from typing import Any

import asyncpg
import pytest
import pytest_asyncio

from app.retrieval.rerank import Reranker
from app.retrieval.types import RetrievedChunk
from app.services.retrieval import (
    ANSWER_RESERVE_TOKENS,
    estimate_tokens,
    fits_fast_path,
    get_business_context,
)
from app.shared import db
from app.shared.config import get_settings
from tests.conftest import _app_dsn_for
from tests.fakes import EMBEDDING_DIM, ZeroEmbedder

pytestmark = pytest.mark.db


class PassthroughReranker(Reranker):
    """Identity passthrough (test_retrieval.py's pattern) - the hybrid path's
    wiring is what matters here, not cross-encoder scores."""

    async def rerank(
        self, *, query: str, candidates: list[RetrievedChunk], top_k: int
    ) -> list[RetrievedChunk]:
        return sorted(candidates, key=lambda c: c.score, reverse=True)[:top_k]


@pytest.fixture
def tiny_budget() -> Iterator[None]:
    """Force every corpus over budget: the reserve alone exhausts the budget."""
    original = os.environ.get("CORPUS_FAST_PATH_MAX_TOKENS")
    os.environ["CORPUS_FAST_PATH_MAX_TOKENS"] = str(ANSWER_RESERVE_TOKENS)
    get_settings.cache_clear()
    yield
    if original is None:
        os.environ.pop("CORPUS_FAST_PATH_MAX_TOKENS", None)
    else:
        os.environ["CORPUS_FAST_PATH_MAX_TOKENS"] = original
    get_settings.cache_clear()


@pytest_asyncio.fixture
async def pool(migrated_db: str) -> AsyncIterator[None]:
    await db.create_pool(dsn=_app_dsn_for(migrated_db), min_size=1, max_size=4)
    try:
        yield
    finally:
        await db.close_pool()


async def _seed_corpus(
    conn: asyncpg.Connection[Any], *, contents: list[str], status: str = "ready"
) -> uuid.UUID:
    tenant_id: uuid.UUID = await conn.fetchval(
        "insert into tenants (slug, name) values ($1, $2) returning id",
        f"ctx-{uuid.uuid4().hex[:8]}",
        "Context Test Co",
    )
    await conn.execute("insert into tenant_config (tenant_id) values ($1)", tenant_id)
    document_id = await conn.fetchval(
        "insert into documents (tenant_id, filename, doc_type, status) "
        "values ($1, 'faq.md', 'faq', $2) returning id",
        tenant_id,
        status,
    )
    for index, content in enumerate(contents):
        await conn.execute(
            "insert into knowledge_chunks (tenant_id, document_id, content, embedding, metadata) "
            "values ($1, $2, $3, $4, $5::jsonb)",
            tenant_id,
            document_id,
            content,
            [0.0] * EMBEDDING_DIM,
            f'{{"source": "faq.md", "chunk_index": {index}}}',
        )
    return tenant_id


async def _context(tenant_id: uuid.UUID, query: str = "when are you open?") -> Any:
    async with db.tenant_context(tenant_id, "customer") as conn:
        return await get_business_context(
            conn,
            tenant_id=tenant_id,
            query=query,
            embedder=ZeroEmbedder(),
            reranker=PassthroughReranker(),
        )


# --- the threshold itself ------------------------------------------------------


def test_estimator_is_conservative() -> None:
    # Under-counting is the dangerous direction (an over-budget prompt), so the
    # estimate must be at least the ~4 chars/token English prose really averages.
    assert estimate_tokens(4000) >= 1000


def test_overhead_counts_against_the_budget() -> None:
    budget_chars = get_settings().corpus_fast_path_max_tokens * 3
    assert fits_fast_path(corpus_chars=100)
    assert not fits_fast_path(corpus_chars=100, overhead_chars=budget_chars)


# --- path selection ------------------------------------------------------------


async def test_small_corpus_takes_the_fast_path(
    pool: None, superuser_conn: asyncpg.Connection[Any]
) -> None:
    tenant_id = await _seed_corpus(
        superuser_conn, contents=["We are open weekdays 9-5.", "Repairs take 48 hours."]
    )

    context = await _context(tenant_id)

    assert context.fast_path is True
    assert [c.content for c in context.chunks] == [
        "We are open weekdays 9-5.",
        "Repairs take 48 hours.",
    ]


async def test_large_corpus_takes_the_hybrid_path(
    pool: None, superuser_conn: asyncpg.Connection[Any], tiny_budget: None
) -> None:
    tenant_id = await _seed_corpus(
        superuser_conn, contents=["We are open weekdays 9-5.", "Repairs take 48 hours."]
    )

    context = await _context(tenant_id)

    assert context.fast_path is False
    assert context.chunks  # the hybrid pipeline still returns the seeded chunks


async def test_both_paths_return_the_same_shape(
    pool: None, superuser_conn: asyncpg.Connection[Any]
) -> None:
    contents = ["We are open weekdays 9-5.", "Repairs take 48 hours."]
    fast_tenant = await _seed_corpus(superuser_conn, contents=contents)
    fast = await _context(fast_tenant)

    os.environ["CORPUS_FAST_PATH_MAX_TOKENS"] = str(ANSWER_RESERVE_TOKENS)
    get_settings.cache_clear()
    try:
        hybrid_tenant = await _seed_corpus(superuser_conn, contents=contents)
        hybrid = await _context(hybrid_tenant)
    finally:
        os.environ.pop("CORPUS_FAST_PATH_MAX_TOKENS", None)
        get_settings.cache_clear()

    # Citations render off id/content/metadata, so those must be populated
    # identically whichever path produced the chunk.
    for chunk in [*fast.chunks, *hybrid.chunks]:
        assert isinstance(chunk.id, uuid.UUID)
        assert chunk.content
        assert chunk.metadata["source"] == "faq.md"


async def test_fast_path_skips_documents_that_are_not_ready(
    pool: None, superuser_conn: asyncpg.Connection[Any]
) -> None:
    # A half-ingested document's chunks must never be handed to the model as
    # settled knowledge - the hybrid path has never returned them either.
    tenant_id = await _seed_corpus(
        superuser_conn, contents=["Draft pricing, do not quote."], status="processing"
    )

    context = await _context(tenant_id)

    assert context.fast_path is True
    assert context.chunks == []


async def test_fast_path_excludes_catalog_chunks(
    pool: None, superuser_conn: asyncpg.Connection[Any]
) -> None:
    tenant_id = await _seed_corpus(superuser_conn, contents=["We are open weekdays 9-5."])
    document_id = await superuser_conn.fetchval(
        "insert into documents (tenant_id, filename, doc_type, status) "
        "values ($1, 'catalog', 'catalog', 'ready') returning id",
        tenant_id,
    )
    await superuser_conn.execute(
        "insert into knowledge_chunks (tenant_id, document_id, content, embedding, metadata) "
        "values ($1, $2, 'Discontinued repair for $1', $3, '{\"kind\": \"catalog_item\"}'::jsonb)",
        tenant_id,
        document_id,
        [0.0] * EMBEDDING_DIM,
    )

    context = await _context(tenant_id)

    assert [chunk.content for chunk in context.chunks] == ["We are open weekdays 9-5."]


async def test_empty_corpus_is_a_fast_path_with_nothing_in_it(
    pool: None, superuser_conn: asyncpg.Connection[Any]
) -> None:
    tenant_id = await _seed_corpus(superuser_conn, contents=[])

    context = await _context(tenant_id)

    assert context.fast_path is True
    assert context.chunks == []


async def test_context_never_crosses_tenants(
    pool: None, superuser_conn: asyncpg.Connection[Any]
) -> None:
    mine = await _seed_corpus(superuser_conn, contents=["Our warranty is 12 months."])
    await _seed_corpus(superuser_conn, contents=["Their warranty is 3 months."])

    context = await _context(mine)

    assert [c.content for c in context.chunks] == ["Our warranty is 12 months."]
