"""T-042: agentic onboarding copilot unit tests.

Tests the agent turn loop (structured extraction + merge), the completeness
gate, off-topic handling, price echo check, and legacy state migration.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.llm.provider import ChatMessage, SchemaT
from app.onboarding.agent import (
    Directive,
    OnboardingRecord,
    _echo,
    run_turn,
)
from app.onboarding.flow import (
    BusinessDraft,
    CatalogItemDraft,
    IdentityDraft,
    ServicesDraft,
)
from app.onboarding.tools import (
    request_finalize,
    save_business,
    save_identity,
    save_services,
)
from tests.fakes import BaseFakeProvider

# --- fake providers ------------------------------------------------------------


class _ExtractFake(BaseFakeProvider):
    """Returns a sequence of DraftUpdate dicts, then a text-only chat reply.

    Records the extract() inputs and chat() messages so tests can assert what
    the agent loop feeds back to the model (stateful extraction context and the
    composed directive).
    """

    def __init__(
        self,
        updates: list[dict[str, Any]] | None = None,
        replies: list[str] | None = None,
    ):
        self._updates = list(updates or [])
        self._replies = replies or ["Got it."]
        self._update_idx = 0
        self._reply_idx = 0
        self.extract_inputs: list[str] = []
        self.chat_messages: list[list[ChatMessage]] = []

    async def extract(
        self, *, system_prompt: str, user_input: str, schema: type[SchemaT]
    ) -> SchemaT:
        self.extract_inputs.append(user_input)
        if self._update_idx < len(self._updates):
            data = self._updates[self._update_idx]
            self._update_idx += 1
            return schema.model_validate(data)
        return schema.model_validate({})

    async def chat(self, messages: list[ChatMessage]) -> str:
        self.chat_messages.append(messages)
        r = self._replies[self._reply_idx % len(self._replies)]
        self._reply_idx += 1
        return r


# --- tool execution ------------------------------------------------------------


def test_save_identity_updates_draft() -> None:
    draft: dict[str, Any] = {}
    result = save_identity(draft, IdentityDraft(description="A phone repair shop"))
    assert result["identity"]["description"] == "A phone repair shop"


def test_save_services_stores_items_with_optional_prices() -> None:
    draft: dict[str, Any] = {}
    svc = ServicesDraft(
        items=[
            CatalogItemDraft(name="Screen repair", price_dollars=89.5),
            CatalogItemDraft(name="Battery replacement", price_dollars=None),
        ]
    )
    result = save_services(draft, svc)
    items = result["services"]["items"]
    assert len(items) == 2
    assert items[0]["price_dollars"] == 89.5
    assert items[1]["price_dollars"] is None


def test_save_business_stores_business_section() -> None:
    draft: dict[str, Any] = {}
    result = save_business(
        draft,
        BusinessDraft(
            name="Bytefix Repairs",
            is_team=True,
            hours="Mon-Fri 9-6",
            contact="555-0100",
            inbound_channels=["website"],
        ),
    )
    assert result["business"]["name"] == "Bytefix Repairs"
    assert result["business"]["is_team"] is True
    assert result["business"]["inbound_channels"] == ["website"]


# --- completeness gate ---------------------------------------------------------


def _complete_draft() -> dict[str, Any]:
    return {
        "business": {
            "name": "Bytefix Repairs",
            "is_team": True,
            "hours": "Mon-Fri 9-6",
            "contact": "555-0100",
            "inbound_channels": ["website", "phone"],
        },
        "identity": {"description": "A shop"},
        "readback": {"confirmed": True},
        "services": {"items": [{"name": "Fix", "price_dollars": 50.0}]},
        "pricing_rules": {"rules": [{"code": "rush", "unit_amount_dollars": 25.0}]},
        "tax": {"has_business_number": False, "business_number": "", "tax_registered": True},
        "payment": {"processing_mode": "DIRECT", "terms": "full_before", "deposit_pct": None},
        "kyc": {"requested": False, "skipped": False},
        "tone": {"tone": "friendly"},
        "escalation_threshold": {"_resolved_threshold": 0.5},
    }


def test_completeness_gate_passes_when_all_sections_present() -> None:
    result = request_finalize(_complete_draft())
    assert result.ok
    assert result.missing == []


def test_completeness_gate_fails_when_missing_sections() -> None:
    draft = {
        "identity": {"description": "A shop"},
    }
    result = request_finalize(draft)
    assert not result.ok
    assert len(result.missing) > 0
    assert any("business name" in m for m in result.missing)


def test_completeness_gate_requires_service_price() -> None:
    draft = _complete_draft()
    draft["services"] = {"items": [{"name": "Fix", "price_dollars": None}]}
    result = request_finalize(draft)
    assert not result.ok
    assert any("at least one service or product with a price" in m for m in result.missing)


def test_completeness_gate_requires_pricing_rule_amounts() -> None:
    draft = _complete_draft()
    draft["pricing_rules"] = {"rules": [{"code": "rush", "unit_amount_dollars": None}]}
    result = request_finalize(draft)
    assert not result.ok
    assert any("amounts for pricing rules" in m for m in result.missing)


# --- price echo check ----------------------------------------------------------


def test_reply_with_known_price_is_not_flagged() -> None:
    draft = {"services": {"items": [{"name": "Fix", "price_dollars": 89.5}]}}
    assert not _echo("Screen repair costs $89.50.", draft)


def test_reply_with_unknown_price_is_flagged() -> None:
    draft = {"services": {"items": [{"name": "Fix", "price_dollars": 50.0}]}}
    assert _echo("Screen repair costs $89.50.", draft)


def test_reply_with_no_prices_is_not_flagged() -> None:
    draft = {"services": {"items": [{"name": "Fix", "price_dollars": 50.0}]}}
    assert not _echo("We offer screen repair.", draft)


# --- legacy state migration ----------------------------------------------------


def test_from_jsonb_migrates_legacy_format() -> None:
    legacy = {"state": {"draft": {"identity": {"description": "old shop"}}}, "completed": False}
    record = OnboardingRecord.from_jsonb(legacy)
    assert record.version == 2
    assert record.draft["identity"]["description"] == "old shop"
    assert not record.completed


def test_from_jsonb_reads_v2_format() -> None:
    v2 = {"version": 2, "draft": {"identity": {"description": "new shop"}}, "completed": True}
    record = OnboardingRecord.from_jsonb(v2)
    assert record.draft["identity"]["description"] == "new shop"
    assert record.completed


def test_to_jsonb_roundtrips() -> None:
    record = OnboardingRecord(
        version=2,
        draft={"identity": {"description": "test"}},
        completed=False,
    )
    data = record.to_jsonb()
    restored = OnboardingRecord.from_jsonb(data)
    assert restored.draft == record.draft
    assert restored.completed == record.completed


# --- agent turn loop -----------------------------------------------------------


@pytest.mark.asyncio
async def test_run_turn_extracts_identity_from_complex_message() -> None:
    """The reported failure: a free-form business description must be captured
    on the first try, not dropped because the model answered in prose."""
    provider = _ExtractFake(
        updates=[
            {"identity": {"description": "A mobile phone business selling cases and more."}},
        ],
        replies=["Got it - a mobile phone business! How should the assistant sound?"],
    )
    record = OnboardingRecord()
    updated, reply, persist = await run_turn(
        admin_message=(
            "this is a mobile phone business mostly selling phone cases and everything else"
        ),
        record=record,
        provider=provider,
    )

    assert updated.draft["identity"]["description"] == (
        "A mobile phone business selling cases and more."
    )
    assert "mobile phone" in reply
    assert persist is True
    assert len(updated.history) >= 2


@pytest.mark.asyncio
async def test_run_turn_extracts_business_name() -> None:
    provider = _ExtractFake(
        updates=[{"business": {"name": "Bytefix Repairs"}}],
        replies=["Got it - Bytefix Repairs!"],
    )
    record = OnboardingRecord()
    updated, reply, persist = await run_turn(
        admin_message="we are called Bytefix Repairs", record=record, provider=provider
    )

    assert updated.draft["business"]["name"] == "Bytefix Repairs"
    assert "Bytefix Repairs" in reply
    assert persist is True


@pytest.mark.asyncio
async def test_run_turn_merges_services_and_prices() -> None:
    provider = _ExtractFake(
        updates=[
            {
                "services": {
                    "items": [{"name": "Screen repair", "price_dollars": 89.5}],
                },
            },
        ],
        replies=["Services recorded."],
    )
    record = OnboardingRecord()
    updated, _reply, persist = await run_turn(
        admin_message="I fix cracked screens for $89.50", record=record, provider=provider
    )

    items = updated.draft["services"]["items"]
    assert items[0]["name"] == "Screen repair"
    assert items[0]["price_dollars"] == 89.5
    assert persist is True


@pytest.mark.asyncio
async def test_run_turn_uses_next_question() -> None:
    provider = _ExtractFake(
        updates=[{"next_question": "What services do you offer?"}],
        replies=["What services do you offer?"],
    )
    record = OnboardingRecord(draft={"identity": {"description": "A shop"}})
    _updated, reply, _persist = await run_turn(
        admin_message="ok go on", record=record, provider=provider
    )

    assert reply == "What services do you offer?"
    system_prompts = [m["content"] for m in provider.chat_messages[0] if m["role"] == "system"]
    assert any("What services do you offer?" in p for p in system_prompts)


@pytest.mark.asyncio
async def test_run_turn_extraction_is_stateful() -> None:
    """The extract call sees the already-captured draft so it can fill what is
    still missing instead of re-asking for what it has."""
    provider = _ExtractFake(updates=[{"tone": {"tone": "friendly"}}], replies=["Tone noted."])
    record = OnboardingRecord(draft={"identity": {"description": "A shop"}})
    _updated, _reply, _persist = await run_turn(
        admin_message="keep it friendly", record=record, provider=provider
    )

    assert "A shop" in provider.extract_inputs[0]


@pytest.mark.asyncio
async def test_run_turn_handles_completed_record() -> None:
    provider = _ExtractFake(updates=[], replies=[])
    record = OnboardingRecord(completed=True)
    updated, reply, persist = await run_turn(
        admin_message="anything", record=record, provider=provider
    )
    assert "already complete" in reply
    assert updated.completed
    assert persist is False


@pytest.mark.asyncio
async def test_run_turn_off_topic_answers_gently() -> None:
    provider = _ExtractFake(
        updates=[
            {
                "off_topic": True,
                "meta_reply": "I'm Wren, your onboarding copilot.",
                "next_question": "What is your business?",
            },
        ],
        replies=["I'm Wren, your onboarding copilot. What is your business?"],
    )
    record = OnboardingRecord(draft={"identity": {"description": "A shop"}})
    updated, reply, persist = await run_turn(
        admin_message="who are you", record=record, provider=provider
    )

    assert persist is False
    assert updated.off_topic_count == 0
    assert updated.history == []
    assert "Wren" in reply
    system_prompts = [m["content"] for m in provider.chat_messages[0] if m["role"] == "system"]
    assert any("Briefly answer" in p for p in system_prompts)


@pytest.mark.asyncio
async def test_run_turn_off_topic_keeps_prior_history() -> None:
    """A no-op off-topic turn must not append to or drop existing history."""
    provider = _ExtractFake(
        updates=[
            {
                "off_topic": True,
                "meta_reply": "I'm Wren.",
                "next_question": "What is your business?",
            }
        ],
        replies=["I'm Wren. What is your business?"],
    )
    record = OnboardingRecord(
        draft={"identity": {"description": "A shop"}},
        history=[
            {"role": "user", "content": "I run a shop"},
            {"role": "assistant", "content": "Got it."},
        ],
    )
    updated, _reply, persist = await run_turn(admin_message="hi", record=record, provider=provider)

    assert persist is False
    assert len(updated.history) == 2
    assert updated.draft["identity"]["description"] == "A shop"


@pytest.mark.asyncio
async def test_run_turn_price_echo_triggers_redraft() -> None:
    """When the model invents a price not in the draft, the reply is redrafted."""
    provider = _ExtractFake(
        updates=[{"identity": {"description": "A shop"}}],
        replies=[
            "Screen repair is $199.",  # invented price - should trigger redraft
            "Got it, I've captured your description.",
        ],
    )
    record = OnboardingRecord()
    updated, reply, _persist = await run_turn(
        admin_message="we fix phones", record=record, provider=provider
    )

    assert updated.draft["identity"]["description"] == "A shop"
    assert "captured" in reply.lower()


# --- directive shape -----------------------------------------------------------


def test_directive_as_prompt_with_acknowledged() -> None:
    d = Directive(acknowledged=["business description"], ask_for="assistant tone")
    prompt = d.as_prompt()
    assert "business description" in prompt
    assert "assistant tone" in prompt


def test_directive_meta_answer() -> None:
    d = Directive(meta_answer="I'm Wren.", ask_for="business description")
    prompt = d.as_prompt()
    assert "Briefly answer" in prompt
    assert "business description" in prompt


def test_directive_all_captured() -> None:
    d = Directive()
    assert "All info captured." in d.as_prompt()
