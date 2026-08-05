"""Universal OpenAI-compatible implementation of LLMProvider.

One class covers every vendor that speaks the OpenAI wire format - OpenRouter,
Groq, Google's Gemini compatibility endpoint, Z.ai, Together, a local Ollama,
and OpenAI itself. It takes credentials and capability knobs as constructor
input and nothing else: which endpoint/model/key it talks to, and whether the
vendor needs the looser json_object extract mode or an extra request body, are
all decided by the caller. The factory (app/llm/dependency.py) is the single
place that reads env (LLM_BASE_URL / LLM_API_KEY / LLM_MODEL and the
llm_fallback_* pair) and applies vendor-specific quirks - swapping hosted
vendors is an env change, never a code change.

``extract`` relies on structured outputs (``response_format=<pydantic
model>`` json_schema), which the target endpoint/model must support - free
models that do include Gemini flash, DeepSeek, Groq's llama-3.3-70b, and Z.ai's
GLM Flash line (which needs the json_object mode; pass
``json_object_extract=True``). The shared extract/chat/chat_stream bodies (with
transient-failure retry) live in OpenAISDKProvider; this class only builds the
client. Never touched by tests directly - they stub ``LLMProvider``.
"""

from __future__ import annotations

from openai import AsyncOpenAI

from app.llm.openai_base import SDK_TIMEOUT, OpenAISDKProvider


class OpenAICompatProvider(OpenAISDKProvider):
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        max_tokens_draft: int = 0,
        max_tokens_extract: int = 0,
        supports_tools: bool = True,
        # Extra request-body fields sent verbatim on every call (e.g. Z.ai's
        # "thinking": {"type": "disabled"}). Passed through to the base; see
        # OpenAISDKProvider for the structured-output mode knobs.
        extra_body: dict[str, object] | None = None,
        json_object_extract: bool = False,
    ) -> None:
        client = AsyncOpenAI(
            base_url=base_url,
            # Keyless endpoints (e.g. a local Ollama) ignore the value, but the
            # SDK requires one; hosted vendors reject a bad key server-side.
            api_key=api_key or "unused",
            # Explicit connect timeout so a hung connect fails fast rather than
            # consuming the tenant's whole llm_timeout budget.
            timeout=SDK_TIMEOUT,
        )

        super().__init__(
            client,
            model,
            max_tokens_draft=max_tokens_draft,
            max_tokens_extract=max_tokens_extract,
            supports_tools=supports_tools,
            extra_body=extra_body,
            json_object_extract=json_object_extract,
        )
