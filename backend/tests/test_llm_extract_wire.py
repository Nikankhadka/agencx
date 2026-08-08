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
