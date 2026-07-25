"""Transient-failure retry in the shared OpenAI-SDK provider base.

Free-tier chat models fail transiently in two documented ways: upstream 429s
and the occasional malformed structured-output JSON (a pydantic
ValidationError from the SDK's parse). Before this, either aborted a whole
customer turn. These tests pin that a turn now rides out both, honors a
provider's Retry-After, and still gives up after the attempt budget.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from openai import RateLimitError
from pydantic import BaseModel, ValidationError

from app.llm import openai_base
from app.llm.openai_base import OpenAISDKProvider


def _rate_limit_error(retry_after: str | None = None) -> RateLimitError:
    headers = {"Retry-After": retry_after} if retry_after is not None else {}
    request = httpx.Request("POST", "https://example.test/v1/chat/completions")
    response = httpx.Response(429, headers=headers, request=request)
    return RateLimitError("rate limited", response=response, body=None)


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


async def test_extract_resamples_on_malformed_structured_output(
    _no_real_sleep: list[float],
) -> None:
    class _Schema(BaseModel):
        value: str

    try:
        _Schema.model_validate({})
    except ValidationError as exc:
        malformed = exc

    good = _completion("")
    good.choices[0].message.parsed = _Schema(value="parsed")
    completions = _Completions([malformed], good)
    result = await _provider(completions).extract(system_prompt="s", user_input="u", schema=_Schema)
    assert result.value == "parsed"
    assert completions.calls == 2
