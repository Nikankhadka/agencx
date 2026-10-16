"""T-009: the single retrieval entry point.

Bare chat (T-011), agents, and recommendation (phase 2) all call
``retrieve`` - none of them touch dense/sparse/fuse/rerank directly, so
swapping any one stage never touches a caller.

Slice 4 overlaps two independent steps. Sparse search needs no embedding and the
embedder holds no database connection, so the sparse query starts first and the
embedding runs beside it. Dense search cannot join them: a connection runs one
operation at a time (asyncpg raises InterfaceError for a second in-flight query)
and the RLS tenant context lives on the caller's connection, so dense is awaited
once the embedding is in hand AND the sparse query has landed. The fused inputs
stay ``[dense, sparse]`` in that order and the rerank call is untouched, so the
chunks and their order are identical to the sequential shape - only the clock
moves (``search_ms`` shrinks by whatever part of the sparse query the embedding
covered). Every embedder on the seam yields to the loop (``LocalEmbedder``
encodes inside ``run_in_threadpool``, the hosted ones await HTTP), so the overlap
is real work rather than a rearranged await order.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from typing import TYPE_CHECKING
from uuid import UUID

from app.observability.turn_record import record_retrieval
from app.retrieval.dense import dense_search
from app.retrieval.fuse import reciprocal_rank_fusion
from app.retrieval.sparse import sparse_search
from app.retrieval.types import RetrievedChunk

logger = logging.getLogger("app.retrieval.service")

if TYPE_CHECKING:
    from app.llm.embedder import Embedder
    from app.retrieval.rerank import Reranker
    from app.shared.db import AppConnection

DEFAULT_TOP_K = 5


async def retrieve(
    conn: AppConnection,
    *,
    tenant_id: UUID,
    query: str,
    embedder: Embedder,
    reranker: Reranker,
    top_k: int = DEFAULT_TOP_K,
    metadata_kind: str | None = None,
    exclude_metadata_kind: str | None = None,
) -> list[RetrievedChunk]:
    """Retrieve with optional include and exclude metadata-kind filters.

    The sparse query is started before the embedding and awaited once the
    embedding is in hand, before the dense query starts - see the module
    docstring. Its filters are passed through unchanged, and the failure
    semantics are the sequential ones: the awaited embedding raises first if it
    fails, because that is the call that was in flight when the old code would
    have raised.
    """
    started = time.perf_counter()
    sparse_task = asyncio.create_task(
        sparse_search(
            conn,
            tenant_id=tenant_id,
            query=query,
            metadata_kind=metadata_kind,
            exclude_metadata_kind=exclude_metadata_kind,
        )
    )
    try:
        query_embedding = (await embedder.embed([query]))[0]
    except BaseException:
        # The embedding is the awaited call here, so its error is the one the
        # caller sees - the same error the sequential shape raised, where
        # sparse_search had not been called yet. Cancel the in-flight task and
        # take its outcome so nothing is left for the GC to warn about.
        sparse_task.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await sparse_task
        raise
    embed_ms = round((time.perf_counter() - started) * 1000, 1)

    searched = time.perf_counter()
    # A connection runs ONE operation at a time: a second in-flight query on the
    # same asyncpg connection raises InterfaceError, and the RLS tenant context
    # lives on this connection, so the caller's connection is the only one this
    # function may use. That is why dense does not start until the sparse query
    # has landed - the overlap is sparse beside the embedding, and dense gets
    # the connection once it is free again. Its exception, if any, surfaces here
    # exactly as it did when this await came first in the sequence.
    sparse_results = await sparse_task
    dense_results = await dense_search(
        conn,
        tenant_id=tenant_id,
        query_embedding=query_embedding,
        metadata_kind=metadata_kind,
        exclude_metadata_kind=exclude_metadata_kind,
    )
    fused = reciprocal_rank_fusion([dense_results, sparse_results])
    search_ms = round((time.perf_counter() - searched) * 1000, 1)

    reranked = time.perf_counter()
    result = await reranker.rerank(query=query, candidates=fused, top_k=top_k)
    rerank_ms = round((time.perf_counter() - reranked) * 1000, 1)
    # Retrieval sits on the critical path of every knowledge/recommendation/
    # quoting turn, so its cost needs to be visible next to the LLM calls it is
    # measured against rather than being lumped into the specialist node's span.
    # The same numbers feed the per-turn latency record (slice 1).
    record_retrieval(embed_ms=embed_ms, search_ms=search_ms, rerank_ms=rerank_ms)
    logger.info(
        "retrieval",
        extra={
            "embed_ms": embed_ms,
            "search_ms": search_ms,
            "rerank_ms": rerank_ms,
            "total_ms": round((time.perf_counter() - started) * 1000, 1),
            "candidates": len(fused),
            "kept": len(result),
        },
    )
    return result
