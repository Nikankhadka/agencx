"""T-042: agentic onboarding copilot unit tests.

Tests the agent turn loop, tool execution, completeness gate, off-topic
detection, price echo check, and legacy state migration.
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from app.llm.provider import ChatMessage, LLMProvider, SchemaT, ToolCall, ToolSpec, ToolTurn
from app.onboarding.agent import (
    Directive,
    OnboardingRecord,
    _echo,
    _off_topic,
    run_turn,
)
from app.onboarding.flow import (
    CatalogItemDraft,
    EscalationDraft,
    IdentityDraft,
    PricingRuleDraft,
    PricingRulesDraft,
    ServicesDraft,
    ToneDraft,
)
from app.onboarding.tools import (
    TOOL_REGISTRY,
    ToolResult,
    _check_completeness,
    request_finalize,
    save_identity,
    save_services,
)
from tests.fakes import BaseFakeProvider


# --- fake providers ------------------------------------------------------------


class _ToolFake(BaseFakeProvider):
    """Returns a sequence of tool calls then a text-only turn."""

    def __init__(self, tool_turns: list[list[ToolCall]], replies: list[str] | None = None):
        self._turns = tool_turns
        self._replies = replies or ["Got it."]
        self._call = 0
        self._reply = 0

    async def chat_with_tools(self, *, messages, tools, tool_choice="auto"):
        if self._call < len(self._turns):
            tc = self._turns[self._call]
            self._call += 1
            return ToolTurn(tool_calls=tc)
        return ToolTurn()

    async def chat(self, messages):
        r = self._replies[self._reply % len(self._replies)]
        self._reply += 1
        return r


class _ExtractStub(BaseFakeProvider):
    async def extract(self, *, system_prompt: str, user_input: str, schema: type[SchemaT]) -> SchemaT:
        return schema.model_validate({})


# --- tool execution ------------------------------------------------------------


def test_save_identity_updates_draft():
    draft: dict = {}
    result = save_identity(draft, IdentityDraft(description="A phone repair shop"))
    assert result["identity"]["description"] == "A phone repair shop"


def test_save_services_stores_items_with_optional_prices():
    draft: dict = {}
    svc = ServicesDraft(items=[
        CatalogItemDraft(name="Screen repair", price_dollars=89.5),
        CatalogItemDraft(name="Battery replacement", price_dollars=None),
    ])
    result = save_services(draft, svc)
    items = result["services"]["items"]
    assert len(items) == 2
    assert items[0]["price_dollars"] == 89.5
    assert items[1]["price_dollars"] is None


# --- completeness gate ---------------------------------------------------------


def test_completeness_gate_passes_when_all_sections_present():
    draft = {
        "identity": {"description": "A shop"},
        "tone": {"tone": "friendly"},
        "services": {"items": [{"name": "Fix", "price_dollars": 50.0}]},
        "pricing_rules": {"rules": [{"code": "rush", "unit_amount_dollars": 25.0}]},
        "escalation_threshold": {"_resolved_threshold": 0.5},
    }
    result = request_finalize(draft)
    assert result.ok
    assert result.missing == []


def test_completeness_gate_fails_when_missing_sections():
    draft = {
        "identity": {"description": "A shop"},
    }
    result = request_finalize(draft)
    assert not result.ok
    assert len(result.missing) > 0
    assert any("assistant tone" in m for m in result.missing)


def test_completeness_gate_requires_service_price():
    draft = {
        "identity": {"description": "A shop"},
        "tone": {"tone": "friendly"},
        "services": {"items": [{"name": "Fix", "price_dollars": None}]},
        "pricing_rules": {"rules": []},
        "escalation_threshold": {"_resolved_threshold": 0.5},
    }
    result = request_finalize(draft)
    assert not result.ok
    assert any("prices for" in m for m in result.missing)


def test_completeness_gate_requires_pricing_rule_amounts():
    draft = {
        "identity": {"description": "A shop"},
        "tone": {"tone": "friendly"},
        "services": {"items": [{"name": "Fix", "price_dollars": 50.0}]},
        "pricing_rules": {"rules": [{"code": "rush", "unit_amount_dollars": None}]},
        "escalation_threshold": {"_resolved_threshold": 0.5},
    }
    result = request_finalize(draft)
    assert not result.ok
    assert any("amounts for pricing rules" in m for m in result.missing)


# --- off-topic detection -------------------------------------------------------


def test_onboarding_message_is_not_off_topic():
    assert not _off_topic("we fix phones and tablets", no_tools=True)


def test_unrelated_question_is_off_topic():
    assert _off_topic("what is the meaning of life?", no_tools=True)


def test_message_with_tools_is_never_off_topic():
    assert not _off_topic("what is the meaning of life?", no_tools=False)


# --- price echo check ----------------------------------------------------------


def test_reply_with_known_price_is_not_flagged():
    draft = {"services": {"items": [{"name": "Fix", "price_dollars": 89.5}]}}
    assert not _echo("Screen repair costs $89.50.", draft)


def test_reply_with_unknown_price_is_flagged():
    draft = {"services": {"items": [{"name": "Fix", "price_dollars": 50.0}]}}
    assert _echo("Screen repair costs $89.50.", draft)


def test_reply_with_no_prices_is_not_flagged():
    draft = {"services": {"items": [{"name": "Fix", "price_dollars": 50.0}]}}
    assert not _echo("We offer screen repair.", draft)


# --- legacy state migration ----------------------------------------------------


def test_from_jsonb_migrates_legacy_format():
    legacy = {"state": {"draft": {"identity": {"description": "old shop"}}}, "completed": False}
    record = OnboardingRecord.from_jsonb(legacy)
    assert record.version == 2
    assert record.draft["identity"]["description"] == "old shop"
    assert not record.completed


def test_from_jsonb_reads_v2_format():
    v2 = {"version": 2, "draft": {"identity": {"description": "new shop"}}, "completed": True}
    record = OnboardingRecord.from_jsonb(v2)
    assert record.draft["identity"]["description"] == "new shop"
    assert record.completed


def test_to_jsonb_roundtrips():
    record = OnboardingRecord(version=2, draft={"identity": {"description": "test"}}, completed=False)
    data = record.to_jsonb()
    restored = OnboardingRecord.from_jsonb(data)
    assert restored.draft == record.draft
    assert restored.completed == record.completed


# --- agent turn loop -----------------------------------------------------------


@pytest.mark.asyncio
async def test_run_turn_captures_tool_result_and_returns_reply():
    provider = _ToolFake(
        tool_turns=[
            [ToolCall(id="c1", name="save_identity", args={"description": "A phone shop"})],
        ],
        replies=["I've captured your business description. What's next?"],
    )
    record = OnboardingRecord()
    updated, reply = await run_turn(admin_message="we fix phones", record=record, provider=provider)

    assert updated.draft["identity"]["description"] == "A phone shop"
    assert "phone shop" in reply or "captured" in reply.lower()
    assert len(updated.history) >= 2  # user + assistant messages


@pytest.mark.asyncio
async def test_run_turn_no_tools_asks_for_next():
    provider = _ToolFake(tool_turns=[], replies=["What services do you offer?"])
    record = OnboardingRecord(draft={"identity": {"description": "A shop"}})
    updated, reply = await run_turn(admin_message="ok go on", record=record, provider=provider)
    # Should have asked for the next section (tone)
    assert len(updated.draft) == 1  # only identity
    assert len(updated.history) >= 2


@pytest.mark.asyncio
async def test_run_turn_handles_completed_record():
    provider = _ToolFake(tool_turns=[], replies=[])
    record = OnboardingRecord(completed=True)
    updated, reply = await run_turn(admin_message="anything", record=record, provider=provider)
    assert "already complete" in reply
    assert updated.completed


@pytest.mark.asyncio
async def test_run_turn_off_topic_increments_count():
    provider = _ToolFake(tool_turns=[], replies=["I'm here to help you set up the assistant."])
    record = OnboardingRecord(draft={"identity": {"description": "A shop"}})
    updated, reply = await run_turn(
        admin_message="what is the capital of France?", record=record, provider=provider
    )
    assert updated.off_topic_count == 1


@pytest.mark.asyncio
async def test_run_turn_price_echo_triggers_redraft():
    """When the model invents a price not in the draft, the reply is redrafted."""
    provider = _ToolFake(
        tool_turns=[
            [ToolCall(id="c1", name="save_identity", args={"description": "A shop"})],
        ],
        replies=[
            "Screen repair is $199.",  # invented price - should trigger redraft
            "Got it, I've captured your description.",
        ],
    )
    record = OnboardingRecord()
    updated, reply = await run_turn(admin_message="we fix phones", record=record, provider=provider)

    assert updated.draft["identity"]["description"] == "A shop"
    # The final reply should be the redrafted version, not the one with an invented price
    assert "captured" in reply.lower()


@pytest.mark.asyncio
async def test_run_turn_unknown_tool_is_skipped():
    """A hallucinated tool name should not crash the turn. Both the unknown and
    the valid tool call are in the same ToolTurn - only the known one sticks."""
    provider = _ToolFake(
        tool_turns=[
            [
                ToolCall(id="c1", name="nonexistent_tool", args={}),
                ToolCall(id="c2", name="save_identity", args={"description": "A shop"}),
            ],
        ],
        replies=["Got it."],
    )
    record = OnboardingRecord()
    updated, reply = await run_turn(admin_message="we fix phones", record=record, provider=provider)
    assert updated.draft["identity"]["description"] == "A shop"


# --- directive shape -----------------------------------------------------------


def test_directive_as_prompt_with_acknowledged():
    d = Directive(acknowledged=["save_identity"], ask_for="assistant tone")
    prompt = d.as_prompt()
    assert "save_identity" in prompt
    assert "assistant tone" in prompt


def test_directive_redirect_firmness():
    d = Directive(redirect_firmness=2)
    prompt = d.as_prompt()
    assert "Decline" in prompt or "firmly" in prompt.lower()
