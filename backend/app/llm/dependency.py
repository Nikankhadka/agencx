"""FastAPI dependencies for the configured LLMProvider and Embedder.

Shared by every router that needs one (onboarding, knowledge, chat) so tests
override a single callable and stub every call site at once. Both factories
key off settings enums (LLM_PROVIDER, EMBEDDER) - the reranker's pattern
(app/retrieval/rerank.py) - so providers are swapped by env, never by code.

When a fallback model + API key are configured, the returned provider is a
FailoverProvider: every call is served by the primary and retried once against
the fallback when the primary's own retries are exhausted. This is invisible
to callers - they still see a plain LLMProvider. The fallback vendor is
selected by LLM_FALLBACK_PROVIDER ('zai' default, or 'openai_compat').

This module is the one place env meets providers: it reads the llm_* and
llm_fallback_* settings, picks the vendor, and applies the vendor quirks that
fall outside the OpenAI wire format. 'zai' means Z.ai's GLM Flash line: base
URL defaults to Z.ai when empty, extract uses the looser json_object mode, and
every call sends thinking disabled - all resolved here because the provider
class itself is universal.
"""

from __future__ import annotations

import logging
from functools import lru_cache

from app.llm.azure import AzureOpenAIProvider
from app.llm.embedder import Embedder, get_embedder
from app.llm.failover import FailoverProvider
from app.llm.openai_compat import OpenAICompatProvider
from app.llm.provider import LLMProvider
from app.shared.config import Settings, get_settings

logger = logging.getLogger(__name__)

# Z.ai's OpenAI-compatible base path (their GLM Flash models live under
# /api/paas/v4, not the OpenAI-style /v1).
ZAI_BASE_URL = "https://api.z.ai/api/paas/v4/"

# GLM-4.7-Flash has hidden reasoning tokens enabled by default, which tax
# latency on a budget; every call sends thinking disabled. json_object extract
# is the other Z.ai quirk (they document only json_object, not strict
# json_schema) - see OpenAISDKProvider.
_ZAI_EXTRA_BODY: dict[str, object] = {"thinking": {"type": "disabled"}}


def _openai_compat(settings: Settings, *, fallback: bool, zai: bool) -> OpenAICompatProvider:
    base_url = settings.llm_fallback_base_url if fallback else settings.llm_base_url
    api_key = settings.llm_fallback_api_key if fallback else settings.llm_api_key
    model = settings.llm_fallback_model if fallback else settings.llm_model
    return OpenAICompatProvider(
        base_url=base_url or (ZAI_BASE_URL if zai else ""),
        api_key=api_key,
        model=model,
        max_tokens_draft=settings.llm_max_tokens_draft,
        max_tokens_extract=settings.llm_max_tokens_extract,
        # T-041: 'off' forces the emulated extract()-based path; 'on' and the
        # default 'auto' use native function calling.
        supports_tools=settings.llm_tool_calling != "off",
        extra_body=_ZAI_EXTRA_BODY if zai else None,
        json_object_extract=zai,
    )


def get_llm_provider() -> LLMProvider:
    settings = get_settings()
    if settings.llm_provider == "azure":
        return AzureOpenAIProvider(settings)

    primary = _openai_compat(settings, fallback=False, zai=settings.llm_provider == "zai")

    if settings.llm_fallback_model and settings.llm_fallback_api_key:
        fallback = _openai_compat(
            settings,
            fallback=True,
            zai=settings.llm_fallback_provider != "openai_compat",
        )
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
