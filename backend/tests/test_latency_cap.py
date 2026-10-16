"""Slice 2 (latency): the draft/prose output cap.

The cap is the shipped ``llm_max_tokens_draft`` default; it must reach the
prose calls (``chat``, ``chat_stream``, native ``chat_with_tools``) and stay
off the structured ``extract`` path, 0 must still mean uncapped, and a
truncated prose response must degrade gracefully (the partial text is returned,
the turn does not die) - truncation is only fatal on a structured output.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from types import SimpleNamespace
from typing import Any

import pytest

from app.llm.failover import FailoverProvider
from app.llm.openai_base import OpenAISDKProvider, UpstreamResponseError
from app.llm.provider import ChatMessage, LLMProvider, SchemaT, ToolSpec, ToolTurn
from app.shared.config import Settings

_DRAFT_CAP = 4096


def _usage(prompt: int = 1, completion: int = 1) -> SimpleNamespace:
    return SimpleNamespace(prompt_tokens=prompt, completion_tokens=completion)


def _delta(text: str | None) -> SimpleNamespace:
    return SimpleNamespace(
        choices=[SimpleNamespace(delta=SimpleNamespace(content=text))], usage=None
    )


def _usage_chunk() -> SimpleNamespace:
    return SimpleNamespace(choices=[], usage=_usage())


def _truncated_completion(content: str) -> SimpleNamespace:
    choice = SimpleNamespace(
        message=SimpleNamespace(content=content, parsed=None), finish_reason="length"
    )
    return SimpleNamespace(usage=_usage(), choices=[choice])


class _RecordingCompletions:
    """Captures each call's kwargs and returns a queued result / stream."""

    def __init__(self, result: Any) -> None:
        self._result = result
        self.kwargs: list[dict[str, Any]] = []
        self.calls = 0

    async def create(self, **kwargs: Any) -> Any:
        self.kwargs.append(kwargs)
        self.calls += 1
        return self._result


class _AsyncChunks:
    def __init__(self, chunks: list[Any]) -> None:
        self._chunks = list(chunks)

    def __aiter__(self) -> _AsyncChunks:
        return self

    async def __anext__(self) -> Any:
        if not self._chunks:
            raise StopAsyncIteration
        return self._chunks.pop(0)


def _provider(
    completions: _RecordingCompletions,
    *,
    max_tokens_draft: int = 0,
    max_tokens_extract: int = 0,
) -> OpenAISDKProvider:
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    return OpenAISDKProvider(
        client,
        "m",
        max_tokens_draft=max_tokens_draft,
        max_tokens_extract=max_tokens_extract,
    )


async def _drain(provider: OpenAISDKProvider) -> str:
    return "".join(
        [delta async for delta in provider.chat_stream([{"role": "user", "content": "q"}])]
    )


async def test_draft_cap_reaches_the_wire_on_chat_stream() -> None:
    stream = _AsyncChunks([_delta("hi"), _usage_chunk()])
    completions = _RecordingCompletions(stream)
    out = await _drain(_provider(completions, max_tokens_draft=_DRAFT_CAP))
    assert out == "hi"
    assert completions.kwargs[-1]["max_tokens"] == _DRAFT_CAP


async def test_zero_draft_cap_omits_the_field_on_chat_stream() -> None:
    stream = _AsyncChunks([_delta("hi")])
    completions = _RecordingCompletions(stream)
    await _drain(_provider(completions))
    assert "max_tokens" not in completions.kwargs[-1]


async def test_truncated_chat_prose_is_returned_not_raised() -> None:
    completions = _RecordingCompletions(_truncated_completion("A partial answ"))
    result = await _provider(completions, max_tokens_draft=8).chat(
        [{"role": "user", "content": "q"}]
    )
    assert result == "A partial answ"  # what arrived is used
    assert completions.calls == 1  # a length finish is not retried


async def test_truncated_chat_stream_ends_gracefully() -> None:
    last = SimpleNamespace(
        choices=[SimpleNamespace(delta=SimpleNamespace(content=None), finish_reason="length")],
        usage=_usage(completion=3),
    )
    stream = _AsyncChunks([_delta("half an "), last])
    out = await _drain(_provider(_RecordingCompletions(stream), max_tokens_draft=_DRAFT_CAP))
    assert out == "half an "  # the truncated stream still yields what arrived


def test_shipped_draft_cap_default_is_4096_and_extract_stays_uncapped() -> None:
    """The shipped default is the real change: local dev must not pin it back to
    0 (backend/.env does not set either cap)."""
    assert Settings.model_fields["llm_max_tokens_draft"].default == _DRAFT_CAP
    assert Settings.model_fields["llm_max_tokens_extract"].default == 0


# --- the cap also sits on the native tool-calling call -----------------------


def _tool_call_completion(arguments: str) -> SimpleNamespace:
    tool_call = SimpleNamespace(
        id="c1", function=SimpleNamespace(name="search_knowledge", arguments=arguments)
    )
    message = SimpleNamespace(content=None, parsed=None, tool_calls=[tool_call])
    return SimpleNamespace(
        usage=_usage(), choices=[SimpleNamespace(message=message, finish_reason="length")]
    )


async def test_truncated_tool_call_args_raise_a_controlled_error() -> None:
    """A length-truncated tool-call payload surfaces as the failover-class
    UpstreamResponseError - never a raw JSON parse error, and never a silently
    accepted unparseable tool call."""
    completions = _RecordingCompletions(_tool_call_completion('{"query": "half a quest'))
    provider = _provider(completions, max_tokens_draft=8)
    with pytest.raises(UpstreamResponseError) as excinfo:
        await provider.chat_with_tools(messages=[{"role": "user", "content": "q"}], tools=[])
    assert "unparseable arguments" in str(excinfo.value)
    assert completions.calls == 1  # the same leg is not re-asked


class _ErroringProvider(LLMProvider):
    def __init__(self, error: Exception) -> None:
        self._error = error
        self.calls = 0

    async def extract(
        self, *, system_prompt: str, user_input: str, schema: type[SchemaT]
    ) -> SchemaT:
        raise NotImplementedError

    async def chat(self, messages: list[ChatMessage]) -> str:
        raise NotImplementedError

    async def chat_stream(self, messages: list[ChatMessage]) -> AsyncIterator[str]:
        raise NotImplementedError
        yield

    async def chat_with_tools(
        self, *, messages: list[ChatMessage], tools: list[ToolSpec], tool_choice: str = "auto"
    ) -> ToolTurn:
        self.calls += 1
        raise self._error


class _ConstantToolProvider(LLMProvider):
    async def extract(
        self, *, system_prompt: str, user_input: str, schema: type[SchemaT]
    ) -> SchemaT:
        raise NotImplementedError

    async def chat(self, messages: list[ChatMessage]) -> str:
        return "fallback answer"

    async def chat_stream(self, messages: list[ChatMessage]) -> AsyncIterator[str]:
        raise NotImplementedError
        yield

    async def chat_with_tools(
        self, *, messages: list[ChatMessage], tools: list[ToolSpec], tool_choice: str = "auto"
    ) -> ToolTurn:
        return ToolTurn(text="fallback answer", tool_calls=[])


async def test_truncated_tool_call_is_re_asked_on_the_next_leg() -> None:
    """UpstreamResponseError is failover-class, so with a second leg configured
    the model is asked again there instead of the turn dying."""
    primary = _ErroringProvider(UpstreamResponseError("truncated tool args"))
    fallback = _ConstantToolProvider()
    turn = await FailoverProvider(primary, fallback, ttft_budget_s=5.0).chat_with_tools(
        messages=[{"role": "user", "content": "q"}], tools=[]
    )
    assert turn.text == "fallback answer"
    assert primary.calls == 1
