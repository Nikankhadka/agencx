"""Slice 4: the retrieval steps overlap, so they need their own proof.

Three things have to hold, and each has a test that fails if it does not:

* the sparse query starts before the embedding finishes (the overlap is real,
  not a rearranged await order) and dense still waits for the embedding;
* the chunks and their order are unchanged against the pre-slice-4 sequence for
  the same corpus (same inputs, same fusion order, same rerank);
* the failure semantics are unchanged, and the in-flight task is handled.

The two search seams are monkeypatched in the ordering and failure tests so
those need no database and no live model; the equivalence test uses the real
functions against a seeded corpus.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import uuid
from collections.abc import AsyncIterator
from typing import Any

import asyncpg
import pytest
import pytest_asyncio

from app.llm.embedder import Embedder
from app.retrieval.dense import dense_search
from app.retrieval.fuse import reciprocal_rank_fusion
from app.retrieval.rerank import Reranker
from app.retrieval.service import retrieve
from app.retrieval.sparse import sparse_search
from app.retrieval.types import RetrievedChunk
from app.shared import db
from tests.conftest import _app_dsn_for
from tests.fakes import EMBEDDING_DIM

# Generous next to the events the fakes set, tight enough that a regression to
# the sequential shape fails fast instead of hanging.
_ORDERING_TIMEOUT_S = 2.0

# Stands in for the connection in the tests that fake both search seams, so
# nothing ever reaches it. Any, so mypy does not demand a real asyncpg connection.
_NO_CONN: Any = object()


def _basis_vector(index: int) -> list[float]:
    """An orthogonal unit vector along dimension `index` (test_retrieval.py's
    helper), so embedding distance ordering is unambiguous without a model."""
    vector = [0.0] * EMBEDDING_DIM
    vector[index] = 1.0
    return vector


class _CallableEmbedder(Embedder):
    """An embedder whose body the test supplies."""

    def __init__(self, body: Any) -> None:
        self._body = body

    async def embed(self, texts: list[str]) -> list[list[float]]:
        result: list[list[float]] = await self._body(texts)
        return result


class _FixedEmbedder(Embedder):
    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [_basis_vector(0) for _ in texts]


class _ScoreReranker(Reranker):
    """Identity passthrough ordered by fused score (test_retrieval.py's fake)."""

    async def rerank(
        self, *, query: str, candidates: list[RetrievedChunk], top_k: int
    ) -> list[RetrievedChunk]:
        return sorted(candidates, key=lambda c: c.score, reverse=True)[:top_k]


class _Recorder:
    """Shared event log and rendezvous for the ordering test."""

    def __init__(self) -> None:
        self.order: list[str] = []
        self.sparse_started = asyncio.Event()
        self.sparse_kwargs: dict[str, Any] = {}


async def test_sparse_starts_inside_the_embedding_window_and_dense_waits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The structural claim: sparse runs while the embedding is in flight.

    The embedder blocks until sparse has started, so a sequential implementation
    cannot get past it - the wait times out and the recorded order shows sparse
    arriving after the embed finished.
    """
    recorder = _Recorder()
    tenant_id = uuid.uuid4()

    async def fake_sparse(*args: Any, **kwargs: Any) -> list[RetrievedChunk]:
        recorder.sparse_kwargs.update(kwargs)
        recorder.order.append("sparse_start")
        recorder.sparse_started.set()
        await asyncio.sleep(0)
        recorder.order.append("sparse_end")
        return []

    async def fake_dense(*args: Any, **kwargs: Any) -> list[RetrievedChunk]:
        recorder.order.append("dense_start")
        return []

    async def embed_body(texts: list[str]) -> list[list[float]]:
        recorder.order.append("embed_start")
        saw_sparse = False
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(recorder.sparse_started.wait(), timeout=_ORDERING_TIMEOUT_S)
            saw_sparse = True
        recorder.order.append("embed_end")
        assert saw_sparse, "sparse had not started while the embedding was in flight"
        return [_basis_vector(0) for _ in texts]

    monkeypatch.setattr("app.retrieval.service.sparse_search", fake_sparse)
    monkeypatch.setattr("app.retrieval.service.dense_search", fake_dense)

    result = await retrieve(
        _NO_CONN,
        tenant_id=tenant_id,
        query="screen repair",
        embedder=_CallableEmbedder(embed_body),
        reranker=_ScoreReranker(),
        metadata_kind="prose",
        exclude_metadata_kind="catalog_item",
    )

    assert result == []
    assert recorder.order.index("sparse_start") < recorder.order.index("embed_end")
    assert recorder.order.index("dense_start") > recorder.order.index("embed_end")
    # One connection, one operation: dense must not start while sparse is in
    # flight (asyncpg raises InterfaceError for that).
    assert recorder.order.index("dense_start") > recorder.order.index("sparse_end")
    # The sparse filters are forwarded unchanged.
    assert recorder.sparse_kwargs == {
        "tenant_id": tenant_id,
        "query": "screen repair",
        "metadata_kind": "prose",
        "exclude_metadata_kind": "catalog_item",
    }


async def test_embed_failure_cancels_the_in_flight_sparse_task(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The embedding is the awaited call, so its error is the one that surfaces.

    The sequential shape never reached sparse_search when the embedding failed;
    here sparse is already running, so it must be cancelled and its outcome
    taken rather than left for the GC to warn about.
    """
    recorder = _Recorder()
    cancelled = asyncio.Event()

    async def slow_sparse(*args: Any, **kwargs: Any) -> list[RetrievedChunk]:
        recorder.sparse_started.set()
        try:
            await asyncio.sleep(30)
        except asyncio.CancelledError:
            cancelled.set()
            raise
        return []

    async def embed_body(texts: list[str]) -> list[list[float]]:
        await asyncio.wait_for(recorder.sparse_started.wait(), timeout=_ORDERING_TIMEOUT_S)
        raise RuntimeError("embedding backend is down")

    monkeypatch.setattr("app.retrieval.service.sparse_search", slow_sparse)

    with pytest.raises(RuntimeError, match="embedding backend is down"):
        await retrieve(
            _NO_CONN,
            tenant_id=uuid.uuid4(),
            query="q",
            embedder=_CallableEmbedder(embed_body),
            reranker=_ScoreReranker(),
        )
    assert cancelled.is_set(), "the in-flight sparse task was not cancelled and awaited"


async def test_sparse_failure_still_surfaces(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failing sparse search raises exactly where it used to: at its await."""

    async def failing_sparse(*args: Any, **kwargs: Any) -> list[RetrievedChunk]:
        raise ValueError("sparse boom")

    async def ok_dense(*args: Any, **kwargs: Any) -> list[RetrievedChunk]:
        return []

    async def ok_embed(texts: list[str]) -> list[list[float]]:
        return [_basis_vector(0) for _ in texts]

    monkeypatch.setattr("app.retrieval.service.sparse_search", failing_sparse)
    monkeypatch.setattr("app.retrieval.service.dense_search", ok_dense)

    with pytest.raises(ValueError, match="sparse boom"):
        await retrieve(
            _NO_CONN,
            tenant_id=uuid.uuid4(),
            query="q",
            embedder=_CallableEmbedder(ok_embed),
            reranker=_ScoreReranker(),
        )


@pytest_asyncio.fixture
async def pool(migrated_db: str) -> AsyncIterator[Any]:
    created = await db.create_pool(dsn=_app_dsn_for(migrated_db), min_size=1, max_size=4)
    try:
        yield created
    finally:
        await db.close_pool()


async def _seed_tenant(
    conn: asyncpg.Connection[Any], *, slug: str, contents: list[tuple[str, list[float]]]
) -> uuid.UUID:
    tenant_id: uuid.UUID = await conn.fetchval(
        "insert into tenants (slug, name) values ($1, $2) returning id",
        slug,
        "Parallel Retrieval Test Co",
    )
    await conn.execute("insert into tenant_config (tenant_id) values ($1)", tenant_id)
    document_id: uuid.UUID = await conn.fetchval(
        "insert into documents (tenant_id, filename, doc_type, status) "
        "values ($1, 'doc.md', 'policy', 'ready') returning id",
        tenant_id,
    )
    for content, embedding in contents:
        await conn.execute(
            "insert into knowledge_chunks (tenant_id, document_id, content, embedding, metadata) "
            "values ($1, $2, $3, $4, '{}')",
            tenant_id,
            document_id,
            content,
            embedding,
        )
    return tenant_id


async def _sequential_retrieve(
    conn: Any,
    *,
    tenant_id: uuid.UUID,
    query: str,
    embedder: Embedder,
    reranker: Reranker,
    top_k: int = 5,
) -> list[RetrievedChunk]:
    """The pre-slice-4 order, spelled out: embed, dense, sparse, fuse, rerank."""
    query_embedding = (await embedder.embed([query]))[0]
    dense_results = await dense_search(conn, tenant_id=tenant_id, query_embedding=query_embedding)
    sparse_results = await sparse_search(conn, tenant_id=tenant_id, query=query)
    fused = reciprocal_rank_fusion([dense_results, sparse_results])
    return await reranker.rerank(query=query, candidates=fused, top_k=top_k)


@pytest.mark.db
async def test_both_orders_return_the_same_chunks(
    pool: Any, superuser_conn: asyncpg.Connection[Any]
) -> None:
    """Same inputs, same lists, same fusion, same rerank - so the same chunks in
    the same order (ids and scores), whichever order the steps ran in.

    The corpus mixes all three fusion shapes: a chunk that is both the dense and
    the sparse winner, one only sparse finds, and one only dense finds."""
    tenant_id = await _seed_tenant(
        superuser_conn,
        slug=f"parallel-{uuid.uuid4().hex[:8]}",
        contents=[
            ("Screen repair for a cracked phone", _basis_vector(0)),
            ("screen screen screen repair repair", _basis_vector(1)),
            ("Battery replacement while you wait", _basis_vector(0)),
            ("Screen protector fitting", _basis_vector(2)),
        ],
    )
    embedder = _FixedEmbedder()
    reranker = _ScoreReranker()

    async with db.tenant_context(tenant_id, "customer") as conn:
        overlapped = await retrieve(
            conn,
            tenant_id=tenant_id,
            query="screen repair",
            embedder=embedder,
            reranker=reranker,
        )

    async with db.tenant_context(tenant_id, "customer") as conn:
        sequential = await _sequential_retrieve(
            conn,
            tenant_id=tenant_id,
            query="screen repair",
            embedder=embedder,
            reranker=reranker,
        )

    assert [chunk.id for chunk in overlapped] == [chunk.id for chunk in sequential]
    assert [chunk.score for chunk in overlapped] == [chunk.score for chunk in sequential]
    assert [chunk.content for chunk in overlapped] == [chunk.content for chunk in sequential]
    # A real fusion of both lists, not an empty or single-source result: two
    # chunks are dense hits (basis vector 0), two are sparse hits, one is both.
    assert len(overlapped) == 4


@pytest.mark.db
async def test_metadata_filters_reach_the_searches(
    pool: Any, superuser_conn: asyncpg.Connection[Any]
) -> None:
    """The overlap must not disturb the include/exclude filters: a catalog
    chunk stays out when excluded, in the same order shape as the sequence."""
    tenant_id = await _seed_tenant(
        superuser_conn,
        slug=f"parallel-filters-{uuid.uuid4().hex[:8]}",
        contents=[
            ("Screen repair for a cracked phone", _basis_vector(0)),
            ("Screen protector fitting", _basis_vector(0)),
        ],
    )
    await superuser_conn.execute(
        "update knowledge_chunks set metadata = $2::jsonb where tenant_id = $1 "
        "and content = 'Screen protector fitting'",
        tenant_id,
        json.dumps({"kind": "catalog_item"}),
    )
    embedder = _FixedEmbedder()
    reranker = _ScoreReranker()

    async with db.tenant_context(tenant_id, "customer") as conn:
        results = await retrieve(
            conn,
            tenant_id=tenant_id,
            query="screen protector",
            embedder=embedder,
            reranker=reranker,
            exclude_metadata_kind="catalog_item",
        )

    assert [chunk.content for chunk in results] == ["Screen repair for a cracked phone"]
