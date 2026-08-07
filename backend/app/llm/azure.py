"""Azure OpenAI implementation of LLMProvider (T-006).

Uses structured outputs (``response_format=<pydantic model>``) so extraction
is schema-validated by the API itself rather than by hand-parsing free-text
model output. The shared extract/chat/chat_stream bodies (with transient-
failure retry) live in OpenAISDKProvider; this class only builds the Azure
client. Never touched by tests directly - they stub ``LLMProvider``.
"""

from __future__ import annotations

from openai import AsyncAzureOpenAI

from app.llm.openai_base import SDK_TIMEOUT, OpenAISDKProvider
from app.shared.config import Settings

_API_VERSION = "2024-10-21"


class AzureOpenAIProvider(OpenAISDKProvider):
    def __init__(self, settings: Settings) -> None:
        client = AsyncAzureOpenAI(
            azure_endpoint=settings.azure_openai_endpoint,
            api_key=settings.azure_openai_api_key,
            api_version=_API_VERSION,
            # Explicit connect timeout so a hung connect fails fast rather than
            # consuming the tenant's whole llm_timeout budget.
            timeout=SDK_TIMEOUT,
        )

        # Azure OpenAI always supports native tool calling.
        supports_tools = True
        if settings.llm_tool_calling == "off":
            supports_tools = False
        elif settings.llm_tool_calling == "on":
            supports_tools = True

        super().__init__(
            client,
            settings.azure_openai_chat_deployment,
            max_tokens_draft=settings.llm_max_tokens_draft,
            max_tokens_extract=settings.llm_max_tokens_extract,
            supports_tools=supports_tools,
        )
