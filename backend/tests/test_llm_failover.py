"""FailoverProvider: transparent retry-once against a fallback provider.

The primary provider (OpenRouter's free tier) retries internally before this
layer runs; when its retries are exhausted, the call is retried once against a
fallback (Z.ai's free GLM Flash). These tests pin what fails over (survived
429s, unusable upstream bodies, network errors, malformed structured output),
what does not (ValueErrors like a too-small extract cap, and anything after a
stream's first delta), and that the fallback gets exactly one chance.

"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

import httpx
import pytest
from openai import BadRequestError, RateLimitError
from pydantic import BaseModel

from app.llm.failover import FailoverProvider, collect_legs
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
        delay_s: float = 0.0,
    ) -> None:
        self.name = name
        self._failures = list(failures)
        self.text = text
        self._supports_tools = supports_tools
        # P-2: how long this leg takes to produce anything. The race is driven
        # by real (tiny) delays rather than mocked clocks, because what is being
        # tested is asyncio's ordering, not arithmetic.
        self._delay_s = delay_s
        self.extract_calls = 0
        self.chat_calls = 0
        self.stream_calls = 0
        self.tools_calls = 0

    async def _wait(self) -> None:
        if self._delay_s:
            await asyncio.sleep(self._delay_s)

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
        await self._wait()
        self._maybe_fail()
        return schema.model_validate({"value": self.text})

    async def chat(self, messages: list[ChatMessage]) -> str:
        self.chat_calls += 1
        await self._wait()
        self._maybe_fail()
        return self.text

    async def chat_stream(self, messages: list[ChatMessage]) -> AsyncIterator[str]:
        self.stream_calls += 1
        await self._wait()
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
        await self._wait()
        self._maybe_fail()
        return ToolTurn(text=self.text)


def _rate_limit() -> RateLimitError:
    request = httpx.Request("POST", "https://example.test/v1/chat/completions")
    response = httpx.Response(429, request=request)
    return RateLimitError("rate limited", response=response, body=None)


def _bad_request() -> BadRequestError:
    request = httpx.Request("POST", "https://example.test/v1/chat/completions")
    response = httpx.Response(400, request=request)
    return BadRequestError("invalid tool history", response=response, body={"error": {}})


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


async def test_tool_calling_does_not_fail_over_on_deterministic_400() -> None:
    primary = _Fake(name="primary", failures=[_bad_request()])
    fallback = _Fake(name="fallback", failures=[])
    with pytest.raises(BadRequestError):
        await FailoverProvider(primary, fallback).chat_with_tools(
            messages=[{"role": "user", "content": "q"}], tools=[], tool_choice="auto"
        )
    assert primary.tools_calls == 1
    assert fallback.tools_calls == 0


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


# --- P-2: the latency budget and the first-wins race ---------------------------

# The budget is passed explicitly at a fraction of a second so the tests race
# real tasks without a real 4-second wait; the production default is 4.0s.
_BUDGET = 0.05


def _quota_exhausted() -> RateLimitError:
    request = httpx.Request("POST", "https://example.test/v1/chat/completions")
    response = httpx.Response(429, request=request)
    return RateLimitError(
        "You exceeded your current quota, please check your plan and billing details",
        response=response,
        body=None,
    )


async def test_fast_primary_answers_alone() -> None:
    primary = _Fake(name="primary", failures=[], text="primary-text")
    fallback = _Fake(name="fallback", failures=[])

    with collect_legs() as legs:
        result = await FailoverProvider(primary, fallback, ttft_budget_s=_BUDGET).chat(
            [{"role": "user", "content": "q"}]
        )

    assert result == "primary-text"
    assert fallback.chat_calls == 0
    assert legs.leg == "primary"
    assert legs.failover_engaged is False
    assert legs.ttft_ms is not None


async def test_slow_primary_is_raced_and_the_faster_leg_wins() -> None:
    primary = _Fake(name="primary", failures=[], text="primary-text", delay_s=10.0)
    fallback = _Fake(name="fallback", failures=[], text="fallback-text")

    with collect_legs() as legs:
        result = await FailoverProvider(primary, fallback, ttft_budget_s=_BUDGET).chat(
            [{"role": "user", "content": "q"}]
        )

    # Both legs ran - the slow one was never cancelled for being slow, only for
    # losing - and the customer got exactly one answer.
    assert result == "fallback-text"
    assert primary.chat_calls == 1
    assert fallback.chat_calls == 1
    assert legs.leg == "fallback"
    assert legs.failover_engaged is True


async def test_a_slow_primary_that_finishes_first_still_wins() -> None:
    """Past the budget is not a disqualification: the race is a race."""
    primary = _Fake(name="primary", failures=[], text="primary-text", delay_s=_BUDGET * 2)
    fallback = _Fake(name="fallback", failures=[], text="fallback-text", delay_s=10.0)

    with collect_legs() as legs:
        result = await FailoverProvider(primary, fallback, ttft_budget_s=_BUDGET).chat(
            [{"role": "user", "content": "q"}]
        )

    assert result == "primary-text"
    assert legs.leg == "primary"
    assert legs.failover_engaged is True


async def test_the_losing_leg_is_cancelled_not_left_running() -> None:
    started = asyncio.Event()
    finished = asyncio.Event()

    class _Watched(_Fake):
        async def chat(self, messages: list[ChatMessage]) -> str:
            started.set()
            try:
                await asyncio.sleep(10.0)
            finally:
                # Only reached on cancellation, which is the point: a loser that
                # kept running would still be burning a provider's quota.
                finished.set()
            return "never"

    primary = _Watched(name="primary", failures=[])
    fallback = _Fake(name="fallback", failures=[], text="fallback-text")

    result = await FailoverProvider(primary, fallback, ttft_budget_s=_BUDGET).chat(
        [{"role": "user", "content": "q"}]
    )

    assert result == "fallback-text"
    assert started.is_set()
    await asyncio.sleep(0)  # let the cancellation land
    assert finished.is_set()


async def test_both_legs_failing_raises_rather_than_hanging() -> None:
    primary = _Fake(name="primary", failures=[_rate_limit()], delay_s=_BUDGET * 2)
    fallback = _Fake(name="fallback", failures=[_rate_limit()])

    with pytest.raises(RateLimitError):
        await FailoverProvider(primary, fallback, ttft_budget_s=_BUDGET).chat(
            [{"role": "user", "content": "q"}]
        )


async def test_hard_429_makes_the_leg_sit_out_the_rest_of_the_turn() -> None:
    # "You exceeded your current quota" is terminal for the turn; a plain 429
    # (slow down) is not, and keeps its existing retry-then-fail-over path.
    primary = _Fake(name="primary", failures=[_quota_exhausted(), _quota_exhausted()])
    fallback = _Fake(name="fallback", failures=[], text="fallback-text")
    provider = FailoverProvider(primary, fallback, ttft_budget_s=_BUDGET)

    with collect_legs() as legs:
        first = await provider.chat([{"role": "user", "content": "q"}])
        second = await provider.chat([{"role": "user", "content": "q2"}])

    assert first == second == "fallback-text"
    assert primary.chat_calls == 1  # the second call skipped it entirely
    assert legs.skip_reasons == ["primary:hard_429"]


async def test_a_transient_429_does_not_mark_the_leg_skipped() -> None:
    primary = _Fake(name="primary", failures=[_rate_limit()], text="primary-text")
    fallback = _Fake(name="fallback", failures=[], text="fallback-text")
    provider = FailoverProvider(primary, fallback, ttft_budget_s=_BUDGET)

    with collect_legs() as legs:
        await provider.chat([{"role": "user", "content": "q"}])
        second = await provider.chat([{"role": "user", "content": "q2"}])

    assert second == "primary-text"  # still in the rotation
    assert legs.skip_reasons == []


async def test_stream_races_the_first_delta_and_the_loser_is_discarded() -> None:
    primary = _Fake(name="primary", failures=[], text="primary-text", delay_s=10.0)
    fallback = _Fake(name="fallback", failures=[], text="fallback-text")

    provider = FailoverProvider(primary, fallback, ttft_budget_s=_BUDGET)
    deltas = [delta async for delta in provider.chat_stream([{"role": "user", "content": "q"}])]

    # One stream reaches the caller, never an interleaving of two.
    assert deltas == ["fallback-text"]


async def test_three_legs_nest_and_the_third_can_win() -> None:
    primary = _Fake(name="primary", failures=[], text="primary-text", delay_s=10.0)
    fallback = _Fake(name="fallback", failures=[], text="fallback-text", delay_s=10.0)
    failover = _Fake(name="failover", failures=[], text="failover-text")

    chain = FailoverProvider(
        primary,
        FailoverProvider(fallback, failover, ttft_budget_s=_BUDGET),
        ttft_budget_s=_BUDGET,
    )
    with collect_legs() as legs:
        result = await chain.chat([{"role": "user", "content": "q"}])

    assert result == "failover-text"
    assert legs.failover_engaged is True


async def test_telemetry_carries_no_content() -> None:
    primary = _Fake(name="primary", failures=[], text="a secret completion")
    with collect_legs() as legs:
        await FailoverProvider(primary, primary, ttft_budget_s=_BUDGET).chat(
            [{"role": "user", "content": "a private question"}]
        )

    attributes = legs.as_attributes()
    assert set(attributes) <= {"ttft_ms", "leg", "failover_engaged", "skip_reason"}
    assert "secret" not in str(attributes)
    assert "private" not in str(attributes)
