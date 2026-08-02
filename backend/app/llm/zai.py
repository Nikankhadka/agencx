"""Z.ai (Zhipu AI) OpenAI-compatible fallback provider.

Z.ai's free GLM Flash models are the budget safety net behind OpenRouter's
free tier: same OpenAI wire format, but two quirks handled here rather than in
the shared base:

- ``extract`` must use ``response_format={"type": "json_object"}`` - Z.ai
  documents only the looser json_object mode, not strict json_schema, so the
  schema travels in the system prompt and the base validates the raw content
  (json_object_extract=True).
- glm-4.7-flash has hidden reasoning tokens enabled by default, which tax
  latency on a budget; every call sends ``thinking: {"type": "disabled"}``.

Never touched by tests directly - they stub ``LLMProvider``.
"""

from __future__ import annotations

from openai import AsyncOpenAI

from app.core.config import Settings
from app.llm.openai_base import SDK_TIMEOUT, OpenAISDKProvider

# Z.ai's OpenAI-compatible base path (their GLM Flash models live under
# /api/paas/v4, not the OpenAI-style /v1).
ZAI_BASE_URL = "https://api.z.ai/api/paas/v4/"


class ZaiOpenAICompatProvider(OpenAISDKProvider):
    def __init__(self, settings: Settings) -> None:
        client = AsyncOpenAI(
            base_url=settings.llm_fallback_base_url or ZAI_BASE_URL,
            api_key=settings.llm_fallback_api_key,
            # Explicit connect timeout so a hung connect fails fast rather than
            # consuming the tenant's whole llm_timeout budget.
            timeout=SDK_TIMEOUT,
        )

        # GLM-4.7-Flash supports native function calling and structured output
        # (json_object). Thinking is off: reasoning tokens cost latency for no
        # gain on this workload, and json_object extraction validates the
        # content pydantic-side anyway.
        super().__init__(
            client,
            settings.llm_fallback_model,
            max_tokens_draft=settings.llm_max_tokens_draft,
            max_tokens_extract=settings.llm_max_tokens_extract,
            supports_tools=True,
            extra_body={"thinking": {"type": "disabled"}},
            json_object_extract=True,
        )
