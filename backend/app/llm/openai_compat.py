"""Generic OpenAI-compatible implementation of LLMProvider.

One class covers every vendor that speaks the OpenAI wire format - OpenRouter,
Groq, Google's Gemini compatibility endpoint, Together, a local Ollama, and
OpenAI itself - selected purely by LLM_BASE_URL / LLM_API_KEY / LLM_MODEL, so
swapping hosted chat vendors is an env change, never a code change.

``extract`` relies on structured outputs (``response_format=<pydantic
model>`` json_schema), which the target endpoint/model must support - free
models that do include Gemini flash, DeepSeek, and Groq's llama-3.3-70b. The
shared extract/chat/chat_stream bodies (with transient-failure retry) live in
OpenAISDKProvider; this class only builds the client. Never touched by tests
directly - they stub ``LLMProvider``.
"""

from __future__ import annotations

from openai import AsyncOpenAI

from app.core.config import Settings
from app.llm.openai_base import SDK_TIMEOUT, OpenAISDKProvider


class OpenAICompatProvider(OpenAISDKProvider):
    def __init__(self, settings: Settings) -> None:
        client = AsyncOpenAI(
            base_url=settings.llm_base_url,
            # Keyless endpoints (e.g. a local Ollama) ignore the value, but the
            # SDK requires one; hosted vendors reject a bad key server-side.
            api_key=settings.llm_api_key or "unused",
            # Explicit connect timeout so a hung connect fails fast rather than
            # consuming the tenant's whole llm_timeout budget.
            timeout=SDK_TIMEOUT,
        )
        super().__init__(client, settings.llm_model)
