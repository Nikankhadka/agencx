"""Slice 7 (latency): the runner's conversation mode.

The multi-turn instrument is only honest if a ``reuse`` run sends the id the
previous turn actually opened. These tests pin the two modes at the one call
site that talks to ``POST /api/chat``: ``fresh`` (the default and the historical
behaviour) sends no id at all, and ``reuse`` sends turn 1's opened id on turn 2,
and so on. ``_drive_turn`` is faked so the assertion is about the ids the runner
passes, not about the chat controller.
"""

from __future__ import annotations

import argparse
from typing import Any

import httpx
import pytest

from evals import latency_run

_MODEL: dict[str, Any] = {
    "label": "test/model",
    "route": "test",
    "base_url": "http://provider.invalid/v1",
    "api_model": "test-model",
    "models_url": "http://provider.invalid/v1/models",
    "key_env": "TEST_KEY",
    "tier": "candidate",
}
_TENANT: dict[str, Any] = {"slug": "tenant", "messages": ["first", "second"]}


async def _run(
    monkeypatch: pytest.MonkeyPatch,
    *,
    conversation: str,
    turns: int = 5,
    coalesce: int = 0,
) -> tuple[list[str | None], list[str], dict[str, Any]]:
    """Drive ``turns`` faked turns and return (ids passed, messages sent, artifact)."""
    passed: list[str | None] = []
    sent: list[str] = []
    opened = iter([f"conversation-{index}" for index in range(1, turns + 1)])

    async def fake_fetch(http: httpx.AsyncClient, url: str, key: str) -> list[dict[str, Any]]:
        return [{"id": "test-model", "pricing": {}}]

    async def fake_drive(
        client: httpx.AsyncClient,
        *,
        slug: str,
        message: str,
        conversation_id: str | None,
    ) -> tuple[str | None, list[str], str | None]:
        passed.append(conversation_id)
        sent.append(message)
        return next(opened), ["conversation"], None

    monkeypatch.setattr(latency_run, "_fetch_provider_models", fake_fetch)
    monkeypatch.setattr(latency_run, "_drive_turn", fake_drive)

    async with httpx.AsyncClient() as client:
        result = await latency_run._run_model_tenant(
            client,
            client,
            model=_MODEL,
            tenant=_TENANT,
            turns=turns,
            command="make latency",
            handler=latency_run._RecordHandler(),
            conversation=conversation,
            coalesce=coalesce,
        )
    return passed, sent, result


async def test_fresh_sends_no_conversation_id_on_every_turn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    passed, _, result = await _run(monkeypatch, conversation="fresh")
    assert passed == [None, None, None, None, None]
    assert result["conversation_mode"] == "fresh"


async def test_reuse_sends_the_previous_turns_id(monkeypatch: pytest.MonkeyPatch) -> None:
    passed, _, result = await _run(monkeypatch, conversation="reuse")
    # Turn 1 opens the conversation; every later turn must join that same one.
    assert passed == [None, "conversation-1", "conversation-2", "conversation-3", "conversation-4"]
    assert result["conversation_mode"] == "reuse"


def test_single_legs_blanks_the_configured_chain(monkeypatch: pytest.MonkeyPatch) -> None:
    """The default mode pins exactly one leg, as every earlier run did."""
    import os

    from app.shared.config import get_settings

    monkeypatch.setenv("TEST_KEY", "test-key")
    monkeypatch.setenv("LLM_FALLBACK_MODEL", "fallback-model")
    monkeypatch.setenv("LLM_FAILOVER_MODEL", "failover-model")

    latency_run._pin_model(_MODEL, legs="single")

    assert os.environ["LLM_FALLBACK_MODEL"] == ""
    assert os.environ["LLM_FAILOVER_MODEL"] == ""
    assert get_settings().llm_fallback_model == ""


def test_single_legs_keep_a_leg_key_for_a_later_pinned_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A row may authenticate with a leg's key (the Groq row uses LLM_FALLBACK_API_KEY).

    ``single`` still blanks the fallback MODEL, so no race is configured; pinning
    an earlier row must not blank the key a later row reads.
    """
    import os

    monkeypatch.setenv("TEST_KEY", "test-key")
    monkeypatch.setenv("LLM_FALLBACK_API_KEY", "groq-key")
    monkeypatch.setenv("LLM_FALLBACK_MODEL", "fallback-model")

    latency_run._pin_model(_MODEL, legs="single")
    latency_run._pin_model({**_MODEL, "key_env": "LLM_FALLBACK_API_KEY"}, legs="single")

    assert os.environ["LLM_FALLBACK_API_KEY"] == "groq-key"
    assert os.environ["LLM_FALLBACK_MODEL"] == ""


def test_configured_legs_keep_the_env_chain(monkeypatch: pytest.MonkeyPatch) -> None:
    """Configured mode leaves the fallback/failover legs the container's .env set."""
    import os

    from app.shared.config import get_settings

    monkeypatch.setenv("TEST_KEY", "test-key")
    monkeypatch.setenv("LLM_FALLBACK_MODEL", "fallback-model")
    monkeypatch.setenv("LLM_FAILOVER_MODEL", "failover-model")

    latency_run._pin_model(_MODEL, legs="configured")

    assert os.environ["LLM_FALLBACK_MODEL"] == "fallback-model"
    assert os.environ["LLM_FAILOVER_MODEL"] == "failover-model"
    assert get_settings().llm_fallback_model == "fallback-model"
    assert get_settings().llm_failover_model == "failover-model"


def test_coalesce_joins_the_first_n_messages_with_a_blank_line() -> None:
    assert latency_run._coalesced(["first", "second", "third"], 2) == "first\n\nsecond"


def test_coalesce_off_is_the_first_message_untouched() -> None:
    """0 (and any negative) is the historical single-message behaviour."""
    assert latency_run._coalesced(["first", "second"], 0) == "first"
    assert latency_run._coalesced(["first", "second"], -1) == "first"


def test_coalesce_past_the_list_joins_every_message() -> None:
    assert latency_run._coalesced(["first", "second"], 9) == "first\n\nsecond"


async def test_coalesce_sends_one_combined_message_and_records_provenance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, sent, result = await _run(monkeypatch, conversation="fresh", turns=1, coalesce=3)
    assert sent == ["first\n\nsecond"]
    assert result["messages"] == ["first", "second"]
    assert result["coalesce"] == 3
    assert result["coalesced_message"] == "first\n\nsecond"


async def test_coalesce_off_keeps_cycling_one_message_per_turn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, sent, result = await _run(monkeypatch, conversation="fresh", turns=3, coalesce=0)
    assert sent == ["first", "second", "first"]
    assert "coalesce" not in result
    assert "coalesced_message" not in result


def test_make_command_carries_the_coalesce_flag() -> None:
    args = argparse.Namespace(
        models=None, tenants=None, turns=1, conversation="fresh", legs="single", coalesce=3
    )
    assert "LATENCY_COALESCE=3" in latency_run._make_command(args).split()
