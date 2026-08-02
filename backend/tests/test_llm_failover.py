"""FailoverProvider: transparent retry-once against a fallback provider.

The primary provider (OpenRouter's free tier) retries internally before this
layer runs; when its retries are exhausted, the call is retried once against a
fallback (Z.ai's free GLM Flash). These tests pin what fails over (survived
429s, unusable upstream bodies, network errors, malformed structured output),
what does not (ValueErrors like a too-small extract cap, and anything after a
stream's first delta), and that the fallback gets exactly one chance.

"""

from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
import pytest
from openai import RateLimitError
from pydantic import BaseModel

from app.llm.failover import FailoverProvider
from app.llm.provider import ChatMessage, LLMProvider, SchemaT, ToolSpec, ToolTurn


class _Controllable(BaseModel):
    value: str


class _Fake(LLMProvider):
    """A provider whose every call fails with a queued error or succeeds."""

    def __init__(
        self,
        *,
        name: str,
        failures: list[Exception],
        text: str = "fallback-text",
        supports_tools: bool = True,
    ) -> None:
        self.name = name
        self._failures = list(failures)
        self.text = text
        self._supports_tools = supports_tools
        self.extract_calls = 0
        self.chat_calls = 0
        self.stream_calls = 0
        self.tools_calls = 0

    def _maybe_fail(self) -> None:
        if self._failures:
            raise self._failures.pop(0)

    @property
    def supports_tools(self) -> bool:
        return self._supports_tools

    async def extract(
        self, *, system_prompt: str, user_input: str, schema: type[SchemaT]
    ) -> SchemaT:
        self.extract_calls += 1
        self._maybe_fail()
        return schema.model_validate({"value": self.text})

    async def chat(self, messages: list[ChatMessage]) -> str:
        self.chat_calls += 1
        self._maybe_fail()
        return self.text

    async def chat_stream(self, messages: list[ChatMessage]) -> AsyncIterator[str]:
        self.stream_calls += 1
        if self._failures:
            raise self._failures.pop(0)
        yield self.text

    async def chat_with_tools(
        self,
        *,
        messages: list[ChatMessage],
        tools: list[ToolSpec],
        tool_choice: str = "auto",
    ) -> ToolTurn:
        self.tools_calls += 1
        self._maybe_fail()
        return ToolTurn(text=self.text)


def _rate_limit() -> RateLimitError:
    request = httpx.Request("POST", "https://example.test/v1/chat/completions")
    response = httpx.Response(429, request=request)
    return RateLimitError("rate limited", response=response, body=None)


async def test_chat_fails_over_when_primary_retries_are_exhausted() -> None:
    primary = _Fake(name="primary", failures=[_rate_limit()])
    fallback = _Fake(name="fallback", failures=[])
    result = await FailoverProvider(primary, fallback).chat([{"role": "user", "content": "q"}])
    assert result == "fallback-text"
    assert primary.chat_calls == 1
    assert fallback.chat_calls == 1


async def test_chat_does_not_fail_over_on_a_value_error() -> None:
    """A ValueError (e.g. the extract cap is too small) is not a provider
    failure - the fallback has the same cap, so the error must propagate."""
    primary = _Fake(name="primary", failures=[ValueError("cap too small")])
    fallback = _Fake(name="fallback", failures=[])
    with pytest.raises(ValueError, match="cap too small"):
        await FailoverProvider(primary, fallback).chat([{"role": "user", "content": "q"}])
    assert fallback.chat_calls == 0


async def test_extract_fails_over_on_malformed_structured_output() -> None:
    try:
        _Controllable.model_validate({})
    except Exception as exc:  # noqa: BLE001 - re-raised through the fake below
        malformed = exc
    primary = _Fake(name="primary", failures=[malformed])
    fallback = _Fake(name="fallback", failures=[])
    result = await FailoverProvider(primary, fallback).extract(
        system_prompt="s", user_input="u", schema=_Controllable
    )
    assert result.value == "fallback-text"
    assert fallback.extract_calls == 1


async def test_stream_fails_over_before_the_first_delta() -> None:
    primary = _Fake(name="primary", failures=[_rate_limit()])
    fallback = _Fake(name="fallback", failures=[])
    deltas = [
        d
        async for d in FailoverProvider(primary, fallback).chat_stream(
            [{"role": "user", "content": "q"}]
        )
    ]
    assert deltas == ["fallback-text"]
    assert fallback.stream_calls == 1


async def test_stream_does_not_fail_over_after_the_first_delta() -> None:
    """Once tokens have flowed, a mid-stream failure must surface to the SSE
    client - a second attempt would duplicate already-yielded deltas. The
    fallback must never be called."""

    class _StreamingPrimary(_Fake):
        async def chat_stream(self, messages: list[ChatMessage]) -> AsyncIterator[str]:
            yield "first-delta"
            raise _rate_limit()

    primary = _StreamingPrimary(name="primary", failures=[])
    fallback = _Fake(name="fallback", failures=[])
    collected: list[str] = []
    with pytest.raises(RateLimitError):
        async for delta in FailoverProvider(primary, fallback).chat_stream(
            [{"role": "user", "content": "q"}]
        ):
            collected.append(delta)
    assert collected == ["first-delta"]
    assert fallback.stream_calls == 0


async def test_tool_calling_fails_over() -> None:
    primary = _Fake(name="primary", failures=[_rate_limit()])
    fallback = _Fake(name="fallback", failures=[])
    turn = await FailoverProvider(primary, fallback).chat_with_tools(
        messages=[{"role": "user", "content": "q"}], tools=[], tool_choice="none"
    )
    assert turn.text == "fallback-text"
    assert fallback.tools_calls == 1


async def test_fallback_gets_exactly_one_chance() -> None:
    """A fallback failure propagates - no second hop back to the primary."""
    primary = _Fake(name="primary", failures=[_rate_limit()])
    fallback = _Fake(name="fallback", failures=[_rate_limit()])
    with pytest.raises(RateLimitError):
        await FailoverProvider(primary, fallback).chat([{"role": "user", "content": "q"}])
    assert primary.chat_calls == 1
    assert fallback.chat_calls == 1


async def test_supports_tools_mirrors_the_primary() -> None:
    primary = _Fake(name="primary", failures=[], supports_tools=False)
    fallback = _Fake(name="fallback", failures=[], supports_tools=True)
    assert FailoverProvider(primary, fallback).supports_tools is False
