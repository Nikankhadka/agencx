"""The strict json_schema extraction wire shape (the openai_compat / Gemini path).

openai>=2.45 rejects passing a pydantic BaseModel class straight into
``chat.completions.create(response_format=...)`` - the SDK wants the explicit
``json_schema`` dict. These tests pin the strict mode's wire shape so a future
version bump cannot silently re-break every openai_compat extract (the zai
json_object mode is pinned in test_llm_zai.py).

"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from pydantic import BaseModel

from app.llm.openai_base import OpenAISDKProvider
from app.observability.cost import collect_usage


class _Schema(BaseModel):
    value: str


def _completion(content: str, *, model: str | None = None) -> SimpleNamespace:
    message = SimpleNamespace(content=content, parsed=None)
    fields: dict[str, Any] = {
        "usage": SimpleNamespace(prompt_tokens=1, completion_tokens=1),
        "choices": [SimpleNamespace(message=message)],
    }
    if model is not None:
        fields["model"] = model
    return SimpleNamespace(**fields)


class _RecordingCompletions:
    """Captures kwargs per call; yields a queued sequence of results."""

    def __init__(self, results: list[Any]) -> None:
        self._results = list(results)
        self.calls: list[dict[str, Any]] = []

    async def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        return self._results.pop(0)


def _strict_provider(completions: _RecordingCompletions) -> OpenAISDKProvider:
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    return OpenAISDKProvider(client, "gemini-3.5-flash")


async def test_strict_extract_sends_json_schema_wire_format() -> None:
    completions = _RecordingCompletions([_completion('{"value": "ok"}')])
    result = await _strict_provider(completions).extract(
        system_prompt="extract the value", user_input="free text", schema=_Schema
    )
    assert result.value == "ok"

    call = completions.calls[0]
    response_format = call["response_format"]
    assert response_format["type"] == "json_schema"
    assert response_format["json_schema"]["name"] == "_Schema"
    assert response_format["json_schema"]["schema"] == _Schema.model_json_schema()


async def test_reported_usage_names_the_served_model() -> None:
    # A gateway can answer with a different (or versioned) model than requested;
    # the reported usage must carry what the response named, not what was asked
    # for, or the latency record's model-identity check is a tautology.
    completions = _RecordingCompletions(
        [_completion('{"value": "ok"}', model="gemini-3.5-flash-001")]
    )
    with collect_usage() as usages:
        await _strict_provider(completions).extract(
            system_prompt="extract the value", user_input="free text", schema=_Schema
        )
    assert [u.model for u in usages] == ["gemini-3.5-flash-001"]


async def test_reported_usage_falls_back_to_the_configured_model() -> None:
    # The response carries no model name: report the configured id.
    completions = _RecordingCompletions([_completion('{"value": "ok"}')])
    with collect_usage() as usages:
        await _strict_provider(completions).extract(
            system_prompt="extract the value", user_input="free text", schema=_Schema
        )
    assert [u.model for u in usages] == ["gemini-3.5-flash"]
