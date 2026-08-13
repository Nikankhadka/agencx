"""Transient-failure retry and output caps in the shared OpenAI-SDK provider base.

Free-tier chat models fail transiently in three documented ways: upstream 429s,
the occasional malformed structured-output JSON (a pydantic ValidationError
when the raw content is validated client-side), and - observed live against
OpenRouter - a 200 whose body carries ``choices: null`` because the gateway
forwarded an upstream provider failure. Before this, any of them aborted a whole customer turn; the
null-choices case was the worst, since it surfaced as a bare TypeError from
inside the SDK's own parser and killed the SSE stream with no terminal event,
leaving the customer's chat bubble spinning forever.

These tests pin that a turn rides out all three, honors a provider's
Retry-After, still gives up after the attempt budget, and that the configured
output caps reach the wire (uncapped when set to 0).
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from openai import LengthFinishReasonError, RateLimitError
from pydantic import BaseModel, ValidationError

from app.llm import openai_base
from app.llm.openai_base import OpenAISDKProvider


def _rate_limit_error(retry_after: str | None = None) -> RateLimitError:
    headers = {"Retry-After": retry_after} if retry_after is not None else {}
    request = httpx.Request("POST", "https://example.test/v1/chat/completions")
    response = httpx.Response(429, headers=headers, request=request)
    return RateLimitError("rate limited", response=response, body=None)


def _daily_quota_error() -> RateLimitError:
    """A Gemini free-tier daily-quota 429: RESOURCE_EXHAUSTED with a per-day
    quotaId - non-transient, the model stays exhausted until tomorrow."""
    request = httpx.Request("POST", "https://example.test/v1/chat/completions")
    response = httpx.Response(429, request=request)
    body = {
        "error": {
            "code": 429,
            "message": (
                "Quota exceeded for metric: "
                "generativelanguage.googleapis.com/generate_content_free_tier_requests, "
                "limit: 20"
            ),
            "status": "RESOURCE_EXHAUSTED",
            "details": [
                {
                    "@type": "type.googleapis.com/google.rpc.QuotaFailure",
                    "violations": [
                        {
                            "quotaMetric": (
                                "generativelanguage.googleapis.com/"
                                "generate_content_free_tier_requests"
                            ),
                            "quotaId": "GenerateRequestsPerDayPerProjectPerModel-FreeTier",
                            "quotaValue": "20",
                        }
                    ],
                }
            ],
        }
    }
    return RateLimitError("429", response=response, body=body)


def _completion(content: str) -> SimpleNamespace:
    message = SimpleNamespace(content=content, parsed=None)
    return SimpleNamespace(
        usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1),
        choices=[SimpleNamespace(message=message)],
    )


class _Completions:
    """Stand-in for client.chat.completions whose create() raises a queued
    sequence of errors, then returns the given result."""

    def __init__(self, errors: list[Exception], result: Any) -> None:
        self._errors = list(errors)
        self._result = result
        self.calls = 0

    async def _next(self) -> Any:
        self.calls += 1
        if self._errors:
            raise self._errors.pop(0)
        return self._result

    async def create(self, **_: Any) -> Any:
        return await self._next()

    async def parse(self, **_: Any) -> Any:
        return await self._next()


def _provider(completions: _Completions) -> OpenAISDKProvider:
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    return OpenAISDKProvider(client, "test-model")


@pytest.fixture(autouse=True)
def _no_real_sleep(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    """Never actually sleep in a retry test; record the delays instead."""
    delays: list[float] = []

    async def _fake_sleep(seconds: float) -> None:
        delays.append(seconds)

    monkeypatch.setattr("app.llm.openai_base.asyncio.sleep", _fake_sleep)
    return delays


async def test_chat_retries_past_a_transient_429(_no_real_sleep: list[float]) -> None:
    completions = _Completions([_rate_limit_error()], _completion("hi"))
    result = await _provider(completions).chat([{"role": "user", "content": "q"}])
    assert result == "hi"
    assert completions.calls == 2  # one failure, one success


async def test_chat_honors_retry_after_header(_no_real_sleep: list[float]) -> None:
    completions = _Completions([_rate_limit_error(retry_after="3")], _completion("ok"))
    await _provider(completions).chat([{"role": "user", "content": "q"}])
    assert _no_real_sleep == [3.0]  # backed off by exactly the header value


async def test_chat_gives_up_after_the_attempt_budget(_no_real_sleep: list[float]) -> None:
    always_429 = _Completions([_rate_limit_error() for _ in range(10)], _completion("never"))
    with pytest.raises(RateLimitError):
        await _provider(always_429).chat([{"role": "user", "content": "q"}])
    assert always_429.calls == openai_base._RETRY_ATTEMPTS


async def test_chat_does_not_retry_a_daily_quota(_no_real_sleep: list[float]) -> None:
    """A non-transient daily-quota 429 must surface immediately (so the outer
    FailoverProvider fires on the first try) instead of burning the retry
    budget against a model that stays exhausted until tomorrow."""
    exhausted = _Completions([_daily_quota_error()], _completion("never"))
    with pytest.raises(RateLimitError):
        await _provider(exhausted).chat([{"role": "user", "content": "q"}])
    assert exhausted.calls == 1
    assert _no_real_sleep == []  # no backoff was slept


def test_is_daily_quota_detects_resource_exhausted() -> None:
    assert openai_base._is_daily_quota(_daily_quota_error()) is True


def test_is_daily_quota_ignores_a_transient_429() -> None:
    assert openai_base._is_daily_quota(_rate_limit_error()) is False


async def test_extract_resamples_on_malformed_structured_output(
    _no_real_sleep: list[float],
) -> None:
    class _Schema(BaseModel):
        value: str

    try:
        _Schema.model_validate({})
    except ValidationError as exc:
        malformed = exc

    good = _completion('{"value": "parsed"}')
    completions = _Completions([malformed], good)
    result = await _provider(completions).extract(system_prompt="s", user_input="u", schema=_Schema)
    assert result.value == "parsed"
    assert completions.calls == 2


# --- null-choices upstream error bodies ------------------------------------------


def _completion_without_choices() -> SimpleNamespace:
    """What OpenRouter actually returns when the upstream provider behind a
    ``:free`` model fails: a 200 whose body has no choices at all."""
    return SimpleNamespace(
        usage=SimpleNamespace(prompt_tokens=1, completion_tokens=0), choices=None
    )


class _SequencedCompletions(_Completions):
    """Returns a queued sequence of successful bodies, one per call."""

    def __init__(self, results: list[Any]) -> None:
        super().__init__([], None)
        self._results = list(results)

    async def _next(self) -> Any:
        self.calls += 1
        return self._results.pop(0)


async def test_chat_retries_past_a_null_choices_body(_no_real_sleep: list[float]) -> None:
    completions = _SequencedCompletions([_completion_without_choices(), _completion("recovered")])
    result = await _provider(completions).chat([{"role": "user", "content": "q"}])
    assert result == "recovered"
    assert completions.calls == 2  # one unusable body, one success


async def test_chat_gives_up_on_persistent_null_choices(_no_real_sleep: list[float]) -> None:
    """The turn must fail with a named, catchable error rather than a bare
    TypeError escaping from inside the SDK."""
    always_empty = _Completions([], _completion_without_choices())
    with pytest.raises(openai_base.UpstreamResponseError):
        await _provider(always_empty).chat([{"role": "user", "content": "q"}])
    assert always_empty.calls == openai_base._RETRY_ATTEMPTS


async def test_extract_converts_sdk_typeerror_into_a_retryable_error(
    _no_real_sleep: list[float],
) -> None:
    """The SDK iterates ``completion.choices`` inside its own parser, so a null
    body surfaces as TypeError before our code sees the response. That must
    become an UpstreamResponseError, not propagate as-is."""

    class _Schema(BaseModel):
        value: str

    sdk_failure = TypeError("'NoneType' object is not iterable")
    completions = _Completions([sdk_failure] * 10, _completion(""))
    with pytest.raises(openai_base.UpstreamResponseError):
        await _provider(completions).extract(system_prompt="s", user_input="u", schema=_Schema)
    assert completions.calls == openai_base._RETRY_ATTEMPTS


# --- output caps ------------------------------------------------------------------


class _RecordingCompletions(_Completions):
    """Captures the kwargs each call was made with, to assert what reaches the wire."""

    def __init__(self, result: Any) -> None:
        super().__init__([], result)
        self.kwargs: list[dict[str, Any]] = []

    async def create(self, **kwargs: Any) -> Any:
        self.kwargs.append(kwargs)
        return await self._next()

    async def parse(self, **kwargs: Any) -> Any:
        self.kwargs.append(kwargs)
        return await self._next()


async def test_configured_caps_reach_the_wire() -> None:
    completions = _RecordingCompletions(_completion("hi"))
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    provider = OpenAISDKProvider(client, "m", max_tokens_draft=400, max_tokens_extract=256)

    await provider.chat([{"role": "user", "content": "q"}])
    assert completions.kwargs[-1]["max_tokens"] == 400

    class _Schema(BaseModel):
        value: str

    completions._result = _completion('{"value": "v"}')
    await provider.extract(system_prompt="s", user_input="u", schema=_Schema)
    assert completions.kwargs[-1]["max_tokens"] == 256


async def test_cap_hit_during_extraction_names_the_reasoning_model_cause(
    _no_real_sleep: list[float],
) -> None:
    """A cap too low for a reasoning model's thinking tokens must fail with an
    actionable message naming the cap, not an opaque SDK error - and must not
    burn retries, since the same cap yields the same result."""

    class _Schema(BaseModel):
        value: str

    length_error = LengthFinishReasonError(completion=_completion(""))  # type: ignore[arg-type]
    completions = _Completions([length_error] * 5, _completion(""))
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    provider = OpenAISDKProvider(client, "m", max_tokens_extract=256)

    with pytest.raises(ValueError, match="LLM_MAX_TOKENS_EXTRACT"):
        await provider.extract(system_prompt="s", user_input="u", schema=_Schema)
    assert completions.calls == 1  # not retried


async def test_zero_cap_sends_no_max_tokens_field() -> None:
    """A disabled cap must omit the field entirely rather than send 0, which
    providers would read as "emit nothing"."""
    completions = _RecordingCompletions(_completion("hi"))
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    await OpenAISDKProvider(client, "m").chat([{"role": "user", "content": "q"}])
    assert "max_tokens" not in completions.kwargs[-1]
