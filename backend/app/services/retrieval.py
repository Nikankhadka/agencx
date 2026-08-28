"""O-4: the two-path business-context seam.

One entry point, two paths, chosen by a measured token count:

- **fast path** - the tenant's whole corpus fits the prompt budget, so it is
  returned as-is. No embedding, no fusion, no rerank: for a small corpus the
  scoring round-trip costs latency without adding information the model would
  not get from reading everything.
- **hybrid path** - the corpus is over budget, so the existing dense + sparse +
  RRF + rerank pipeline runs unchanged and returns its top-k.

Both paths return the same ``RetrievedChunk`` shape (id, content, metadata), so
citations render identically either way. What differs is ``score``, and callers
must not read it blind: on the fast path nothing was scored, so ``fast_path``
says which world the chunks came from. A relevance-threshold filter is only
meaningful on the hybrid path - on the fast path "is this relevant" is the
model's job, backstopped by grounding inspection.

The threshold is a token count, never a branch on business type or size (I8): a
one-page dental clinic and a one-page restaurant take the same path, and either
grows out of it by adding material.
"""

from __future__ import annotations

import json
import logging
import math
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID

from app.retrieval.service import DEFAULT_TOP_K, retrieve
from app.retrieval.types import RetrievedChunk
from app.shared.config import get_settings

if TYPE_CHECKING:
    from app.llm.embedder import Embedder
    from app.retrieval.rerank import Reranker
    from app.shared.db import AppConnection

logger = logging.getLogger("app.services.retrieval")

# Tokens are estimated from character count rather than run through a real
# tokenizer: every candidate model has its own, none of them ships with the
# backend, and pulling one in to decide a cache-shaped question would be a
# dependency for a number that only needs to be conservative. 3.0 chars/token is
# below what English prose actually averages (~4), so the estimate over-counts -
# the failure mode is taking the hybrid path when the fast path would have fit,
# which costs latency, never correctness.
CHARS_PER_TOKEN = 3.0

# Headroom inside the budget for what the caller has not measured: the model's
# own answer, plus whatever the prompt carries beyond the numbers passed in.
ANSWER_RESERVE_TOKENS = 800


def estimate_tokens(chars: int) -> int:
    """Conservative token estimate for ``chars`` characters of text."""
    return math.ceil(chars / CHARS_PER_TOKEN)


@dataclass(frozen=True)
class BusinessContext:
    """The material an answer is grounded in, plus which path produced it."""

    chunks: list[RetrievedChunk]
    fast_path: bool


async def corpus_chars(conn: AppConnection, tenant_id: UUID) -> int:
    """Total characters of ready knowledge for the tenant. One indexed sum.

    Scoped to ready documents so the measurement covers exactly the text
    ``whole_corpus`` would return - measuring one set and sending another is how
    a budget check quietly stops meaning anything.
    """
    total: int | None = await conn.fetchval(
        "select sum(length(c.content)) from knowledge_chunks c "
        "join documents d on d.id = c.document_id "
        "where c.tenant_id = $1 and d.status = 'ready' "
        "and coalesce(c.metadata->>'kind', '') <> 'catalog_item'",
        tenant_id,
    )
    return total or 0


def fits_fast_path(*, corpus_chars: int, overhead_chars: int = 0) -> bool:
    """Whether corpus + prompt overhead + an answer fits the configured budget.

    ``overhead_chars`` is the caller's already-assembled prompt material (system
    prompt, tenant profile) - P-3 passes its real length so the budget covers the
    whole prompt, not just the corpus.
    """
    budget = get_settings().corpus_fast_path_max_tokens
    needed = estimate_tokens(corpus_chars + overhead_chars) + ANSWER_RESERVE_TOKENS
    return needed <= budget


async def whole_corpus(conn: AppConnection, tenant_id: UUID) -> list[RetrievedChunk]:
    """Every ready chunk for the tenant, in ingest order, unscored.

    Document order then ``chunk_index`` (the chunker stamps it on every prose and
    record chunk) reassembles each document as it was written, which is how the
    model reads it best - and, being fully deterministic, it also keeps citation
    numbering stable for the life of a cached package. ``c.id`` only breaks ties
    for chunks with no index at all (catalog items).
    """
    rows = await conn.fetch(
        "select c.id, c.content, c.metadata from knowledge_chunks c "
        "join documents d on d.id = c.document_id "
        "where c.tenant_id = $1 and d.status = 'ready' "
        "and coalesce(c.metadata->>'kind', '') <> 'catalog_item' "
        "order by d.uploaded_at, c.document_id, "
        "  (c.metadata->>'chunk_index')::int nulls last, c.id",
        tenant_id,
    )
    return [
        RetrievedChunk(id=row["id"], content=row["content"], metadata=json.loads(row["metadata"]))
        for row in rows
    ]


async def get_business_context(
    conn: AppConnection,
    *,
    tenant_id: UUID,
    query: str,
    embedder: Embedder,
    reranker: Reranker,
    top_k: int = DEFAULT_TOP_K,
    overhead_chars: int = 0,
) -> BusinessContext:
    """The grounding material for ``query``, by whichever path the corpus earns."""
    started = time.perf_counter()
    total_chars = await corpus_chars(conn, tenant_id)
    if fits_fast_path(corpus_chars=total_chars, overhead_chars=overhead_chars):
        chunks = await whole_corpus(conn, tenant_id)
        logger.info(
            "business context",
            extra={
                "path": "fast",
                "corpus_chars": total_chars,
                "chunks": len(chunks),
                "total_ms": round((time.perf_counter() - started) * 1000, 1),
            },
        )
        return BusinessContext(chunks=chunks, fast_path=True)

    chunks = await retrieve(
        conn,
        tenant_id=tenant_id,
        query=query,
        embedder=embedder,
        reranker=reranker,
        top_k=top_k,
    )
    logger.info(
        "business context",
        extra={
            "path": "hybrid",
            "corpus_chars": total_chars,
            "chunks": len(chunks),
            "total_ms": round((time.perf_counter() - started) * 1000, 1),
        },
    )
    return BusinessContext(chunks=chunks, fast_path=False)
