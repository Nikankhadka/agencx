"""The json_object extraction mode the 'zai' role needs.

Z.ai's free GLM Flash models are OpenAI-compatible but document only the
looser ``json_object`` response format, not strict json_schema - so the schema
travels in the system prompt and the raw content is pydantic-validated
client-side. These tests pin that the json_object mode sends the right wire
shape, that malformed content is retried like the strict path, and that the
thinking-disabled extra_body reaches the wire. The provider class itself is
universal (OpenAICompatProvider); which role gets these quirks is decided by
the factory (test_llm_dependency.py).

"""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import BaseModel

from app.llm import openai_base
from app.llm.openai_base import OpenAISDKProvider


@pytest.fixture(autouse=True)
def _no_real_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    """Never actually sleep in a retry test."""

    async def _fake_sleep(_: float) -> None:
        return None

    monkeypatch.setattr("app.llm.openai_base.asyncio.sleep", _fake_sleep)


class _Schema(BaseModel):
    value: str


def _completion(content: str) -> SimpleNamespace:
    message = SimpleNamespace(content=content, parsed=None)
    return SimpleNamespace(
        usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1),
        choices=[SimpleNamespace(message=message)],
    )


class _RecordingCompletions:
    """Captures kwargs per call; yields a queued sequence of results."""

    def __init__(self, results: list[Any]) -> None:
        self._results = list(results)
        self.calls: list[dict[str, Any]] = []

    async def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        return self._results.pop(0)


def _json_object_provider(completions: _RecordingCompletions) -> OpenAISDKProvider:
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    return OpenAISDKProvider(client, "glm-4.7-flash", json_object_extract=True)


async def test_json_object_extract_sends_json_object_mode_and_schema() -> None:
    completions = _RecordingCompletions([_completion('{"value": "ok"}')])
    result = await _json_object_provider(completions).extract(
        system_prompt="extract the value", user_input="free text", schema=_Schema
    )
    assert result.value == "ok"

    call = completions.calls[0]
    assert call["response_format"] == {"type": "json_object"}
    # The schema must be embedded in the system prompt, since json_object mode
    # does not carry it on the wire.
    system_prompt: str = call["messages"][0]["content"]
    assert json.dumps(_Schema.model_json_schema()) in system_prompt
    assert call["model"] == "glm-4.7-flash"


async def test_json_object_extract_retries_malformed_content() -> None:
    """Malformed raw content joins the retry path exactly like the strict
    path's validation failure: resample, don't abort the turn."""
    completions = _RecordingCompletions(
        [_completion('{"wrong_key": 1}'), _completion('{"value": "recovered"}')]
    )
    result = await _json_object_provider(completions).extract(
        system_prompt="s", user_input="u", schema=_Schema
    )
    assert result.value == "recovered"
    assert len(completions.calls) == 2


async def test_json_object_extract_gives_up_after_the_attempt_budget() -> None:
    persistently_bad = _RecordingCompletions(
        [_completion('{"wrong_key": 1}') for _ in range(openai_base._RETRY_ATTEMPTS)]
    )
    with pytest.raises(Exception, match="value"):
        await _json_object_provider(persistently_bad).extract(
            system_prompt="s", user_input="u", schema=_Schema
        )
    assert len(persistently_bad.calls) == openai_base._RETRY_ATTEMPTS


async def test_thinking_disabled_reaches_the_wire_on_every_call() -> None:
    completions = _RecordingCompletions([_completion("hi")])
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    provider = OpenAISDKProvider(
        client,
        "glm-4.7-flash",
        extra_body={"thinking": {"type": "disabled"}},
    )
    await provider.chat([{"role": "user", "content": "q"}])
    assert completions.calls[0]["extra_body"] == {"thinking": {"type": "disabled"}}
