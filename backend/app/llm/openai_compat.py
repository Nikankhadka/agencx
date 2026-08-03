"""Generic OpenAI-compatible implementation of LLMProvider.

One class covers every vendor that speaks the OpenAI wire format - OpenRouter,
Groq, Google's Gemini compatibility endpoint, Together, a local Ollama, and
OpenAI itself - selected purely by LLM_BASE_URL / LLM_API_KEY / LLM_MODEL, so
swapping hosted chat vendors is an env change, never a code change.

``extract`` relies on structured outputs (``response_format=<pydantic
model>`` json_schema), which the target endpoint/model must support - free
models that do include Gemini flash, DeepSeek, and Groq's llama-3.3-70b. The
shared extract/chat/chat_stream bodies (with transient-failure retry) live in
OpenAISDKProvider; this class only builds the client. The same class also
serves the fallback position: ``fallback=False`` (the default - primary is the
sane default role) reads the primary ``llm_*`` settings; ``fallback=True``
reads the ``llm_fallback_*`` settings so any OpenAI-compatible vendor can fail
over behind a Z.ai primary.
"""

from __future__ import annotations

from openai import AsyncOpenAI

from app.core.config import Settings
from app.llm.openai_base import SDK_TIMEOUT, OpenAISDKProvider


class OpenAICompatProvider(OpenAISDKProvider):
    def __init__(self, settings: Settings, *, fallback: bool = False) -> None:
        base_url = settings.llm_fallback_base_url if fallback else settings.llm_base_url
        api_key = settings.llm_fallback_api_key if fallback else settings.llm_api_key
        model = settings.llm_fallback_model if fallback else settings.llm_model
        client = AsyncOpenAI(
            base_url=base_url,
            # Keyless endpoints (e.g. a local Ollama) ignore the value, but the
            # SDK requires one; hosted vendors reject a bad key server-side.
            api_key=api_key or "unused",
            # Explicit connect timeout so a hung connect fails fast rather than
            # consuming the tenant's whole llm_timeout budget.
            timeout=SDK_TIMEOUT,
        )

        # T-041: resolve tool-calling support. 'off' forces the emulated path
        # (free models without native function calling); 'on' forces native;
        # 'auto' (default) infers from the model.
        supports_tools = True
        if settings.llm_tool_calling == "off":
            supports_tools = False
        elif settings.llm_tool_calling == "on":
            supports_tools = True
        # 'auto': native is the default; tests can force emulated.

        super().__init__(
            client,
            model,
            max_tokens_draft=settings.llm_max_tokens_draft,
            max_tokens_extract=settings.llm_max_tokens_extract,
            supports_tools=supports_tools,
        )
