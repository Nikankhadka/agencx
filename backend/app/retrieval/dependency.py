"""FastAPI dependency for the configured Reranker (T-011).

Mirrors app/llm/dependency.py's pattern - tests override this one callable
to stub reranking everywhere it's used.
"""

from __future__ import annotations

from functools import lru_cache

from app.retrieval.rerank import CohereReranker, Reranker, get_reranker
from app.shared.config import get_settings


@lru_cache
def get_reranker_dependency() -> Reranker:
    # Cached (like the embedder) so the local cross-encoder's lazily loaded
    # model is shared process-wide instead of being re-loaded per request, and
    # the Cohere backend's pooled HTTP client is reused across turns.
    return get_reranker(get_settings())


async def close_reranker() -> None:
    """Release the cached reranker's held resources (the Cohere HTTP client) on
    app shutdown. A no-op for the local backend. Also clears the cache so a
    subsequent call rebuilds cleanly (used by tests)."""
    if get_reranker_dependency.cache_info().currsize:
        reranker = get_reranker_dependency()
        if isinstance(reranker, CohereReranker):
            await reranker.aclose()
    get_reranker_dependency.cache_clear()
