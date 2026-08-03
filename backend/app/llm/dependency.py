"""FastAPI dependencies for the configured LLMProvider and Embedder.

Shared by every router that needs one (onboarding, knowledge, chat) so tests
override a single callable and stub every call site at once. Both factories
key off settings enums (LLM_PROVIDER, EMBEDDER) - the reranker's pattern
(app/retrieval/rerank.py) - so providers are swapped by env, never by code.

When a fallback model + API key are configured, the returned provider is a
FailoverProvider: every call is served by the primary and retried once against
the fallback when the primary's own retries are exhausted. This is invisible
to callers - they still see a plain LLMProvider. The fallback vendor class is
selected by LLM_FALLBACK_PROVIDER ('zai' default, or 'openai_compat').
"""

from __future__ import annotations

import logging
from functools import lru_cache

from app.core.config import get_settings
from app.llm.azure import AzureOpenAIProvider
from app.llm.embedder import Embedder, get_embedder
from app.llm.failover import FailoverProvider
from app.llm.openai_compat import OpenAICompatProvider
from app.llm.provider import LLMProvider
from app.llm.zai import ZaiOpenAICompatProvider

logger = logging.getLogger(__name__)


def get_llm_provider() -> LLMProvider:
    settings = get_settings()
    primary: LLMProvider
    if settings.llm_provider == "openai_compat":
        primary = OpenAICompatProvider(settings, fallback=False)
    elif settings.llm_provider == "zai":
        primary = ZaiOpenAICompatProvider(settings, fallback=False)
    else:
        primary = AzureOpenAIProvider(settings)

    if settings.llm_fallback_model and settings.llm_fallback_api_key:
        if settings.llm_fallback_provider == "openai_compat":
            fallback: LLMProvider = OpenAICompatProvider(settings, fallback=True)
        else:
            fallback = ZaiOpenAICompatProvider(settings, fallback=True)
        return FailoverProvider(primary, fallback)

    if settings.llm_fallback_model:
        logger.warning("LLM_FALLBACK_MODEL set but LLM_FALLBACK_API_KEY missing; failover disabled")
    return primary


@lru_cache
def get_embedder_dependency() -> Embedder:
    # Cached (unlike the stateless chat providers) so LocalEmbedder's lazily
    # loaded sentence-transformers model is shared process-wide instead of
    # being re-loaded per request.
    return get_embedder(get_settings())
