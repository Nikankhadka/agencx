"""Transparent failover between two LLM providers.

The primary provider (OpenRouter's free tier in the demo) is retried
internally by OpenAISDKProvider before anything reaches this layer; when its
retries are exhausted the failure is treated as "this provider is unusable
right now" and the whole call is retried once against a fallback provider
(Z.ai's free GLM Flash models - slower but a second, independent free tier).

What fails over: a 429 that survived three backoff retries, an unusable
upstream error body under a 200, a network-level failure, or repeatedly
malformed structured output. What does not: a ValueError (e.g. the extract
cap being too small - a different fallback provider has the same cap) and
``LimitTimeout`` (a tenant budget protection, not a provider failure - the
outer TimeLimitedProvider raises it after this layer runs, so it never
surfaces here).

``chat_stream`` only fails over before the first delta: once tokens have
flowed, a mid-stream failure must surface to the SSE client, because a second
attempt would duplicate what was already yielded.

Never touched by tests directly - they stub ``LLMProvider``.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator

import httpx
from openai import APIConnectionError, RateLimitError
from pydantic import ValidationError

from app.llm.openai_base import UpstreamResponseError
from app.llm.provider import ChatMessage, LLMProvider, SchemaT, ToolSpec, ToolTurn

logger = logging.getLogger(__name__)

# Failures that mean "this provider is unusable right now" - retrying it
# again is pointless, so the fallback provider gets the call instead.
# APIConnectionError covers the SDK's timeouts and connection errors (the SDK
# wraps raw httpx failures, so both are listed for completeness).
_FAILOVER_ERRORS = (
    RateLimitError,
    APIConnectionError,
    httpx.HTTPError,
    UpstreamResponseError,
    ValidationError,
)


class FailoverProvider(LLMProvider):
    """Delegates every call to ``primary``; on a failure that survives the
    primary's own retries, retries the call once against ``fallback``."""

    def __init__(self, primary: LLMProvider, fallback: LLMProvider) -> None:
        self._primary = primary
        self._fallback = fallback

    @property
    def supports_tools(self) -> bool:
        # Mirror the primary: it is what serves every call that succeeds, and
        # the emulated-vs-native decision is made from its capability.
        return self._primary.supports_tools

    async def extract(
        self, *, system_prompt: str, user_input: str, schema: type[SchemaT]
    ) -> SchemaT:
        try:
            return await self._primary.extract(
                system_prompt=system_prompt, user_input=user_input, schema=schema
            )
        except _FAILOVER_ERRORS as error:
            logger.warning(
                "primary llm extract failed (%s: %s); failing over", type(error).__name__, error
            )
            return await self._fallback.extract(
                system_prompt=system_prompt, user_input=user_input, schema=schema
            )

    async def chat(self, messages: list[ChatMessage]) -> str:
        try:
            return await self._primary.chat(messages)
        except _FAILOVER_ERRORS as error:
            logger.warning(
                "primary llm chat failed (%s: %s); failing over", type(error).__name__, error
            )
            return await self._fallback.chat(messages)

    async def chat_stream(self, messages: list[ChatMessage]) -> AsyncIterator[str]:
        stream = self._primary.chat_stream(messages)
        try:
            first = await stream.__anext__()
        except StopAsyncIteration:
            # Primary produced an empty stream; nothing to fail over, nothing
            # to yield.
            return
        except _FAILOVER_ERRORS as error:
            logger.warning(
                "primary llm chat_stream failed before first delta (%s: %s); failing over",
                type(error).__name__,
                error,
            )
            stream = self._fallback.chat_stream(messages)
            try:
                first = await stream.__anext__()
            except StopAsyncIteration:
                return
        # One failover hop only: a failure mid-stream (or the fallback's own
        # first-delta failure) propagates to the SSE client, which already
        # owns graceful escalation.
        yield first
        async for delta in stream:
            yield delta

    async def chat_with_tools(
        self,
        *,
        messages: list[ChatMessage],
        tools: list[ToolSpec],
        tool_choice: str = "auto",
    ) -> ToolTurn:
        try:
            return await self._primary.chat_with_tools(
                messages=messages, tools=tools, tool_choice=tool_choice
            )
        except _FAILOVER_ERRORS as error:
            logger.warning(
                "primary llm chat_with_tools failed (%s: %s); failing over",
                type(error).__name__,
                error,
            )
            return await self._fallback.chat_with_tools(
                messages=messages, tools=tools, tool_choice=tool_choice
            )
