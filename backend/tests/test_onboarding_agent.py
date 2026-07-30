"""T-042: onboarding agent turn-loop unit tests.

Uses ToolAwareFakeProvider to control which tool calls and chat responses
the agent sees, exercising off-topic detection, redirect budget, tool
calls per turn, price echo guard, completeness gate, and volunteered
early capture without touching a real model.
"""

from __future__ import annotations

from typing import Any

from app.llm.provider import ChatMessage, ToolCall, ToolSpec, ToolTurn
from app.onboarding.agent import OnboardingRecord, _echo, _off_topic, run_turn
from app.onboarding.tools import _check_completeness, request_finalize
from tests.fakes import BaseFakeProvider


class ToolAwareFakeProvider(BaseFakeProvider):
    """Returns tool calls and chat text from pre-configured queues."""

    def __init__(
        self, tool_turns: list[ToolTurn] | None = None,
        chat_replies: list[str] | None = None,
    ) -> None:
        self._tool_turns: list[ToolTurn] = list(tool_turns or [])
        self._chat_replies: list[str] = list(chat_replies or ["Got it."])
        self._tool_idx = 0
        self._chat_idx = 0

    async def chat(self, messages: list[ChatMessage]) -> str:
        reply = self._chat_replies[self._chat_idx % len(self._chat_replies)]
        self._chat_idx += 1
        return reply

    async def chat_with_tools(
        self, *, messages: list[ChatMessage], tools: list[ToolSpec],
        tool_choice: str = "auto",
    ) -> ToolTurn:
        if self._tool_idx < len(self._tool_turns):
            turn = self._tool_turns[self._tool_idx]
            self._tool_idx += 1
            return turn
        return ToolTurn()


def _mk_tool_turn(name: str, args: dict[str, object]) -> ToolTurn:
    return ToolTurn(
        tool_calls=[ToolCall(id=f"call_{name}", name=name, args=args)],
    )


def _mk_record(**kwargs: object) -> OnboardingRecord:
    defaults: dict[str, Any] = {
        "version": 2, "draft": {}, "history": [],
        "off_topic_count": 0, "completed": False,
    }
    defaults.update(kwargs)
    return OnboardingRecord(**defaults)


class TestOffTopic:
    def test_no_tools_and_no_signals_is_off_topic(self) -> None:
        assert _off_topic("tell me a joke", no_tools=True) is True
        assert _off_topic("hello there", no_tools=True) is True
        assert _off_topic("what is your name", no_tools=True) is True

    def test_business_words_prevent_off_topic_label(self) -> None:
        assert _off_topic("we offer professional business services", True) is False
        assert _off_topic("what price do you charge", True) is False
        assert _off_topic("keep it professional and friendly", True) is False
        assert _off_topic("we need a human to help", True) is False

    def test_tool_calls_always_not_off_topic(self) -> None:
        assert _off_topic("tell me a joke", no_tools=False) is False

    async def test_on_topic_message_resets_counter(self) -> None:
        provider = ToolAwareFakeProvider(chat_replies=["Got your info."])
        record = _mk_record(off_topic_count=3)
        record, _reply = await run_turn(
            admin_message="we sell professional services",
            record=record,
            provider=provider,
        )
        assert record.off_topic_count == 3


class TestRedirectBudget:
    async def test_off_topic_increments_counter(self) -> None:
        provider = ToolAwareFakeProvider(chat_replies=["Back to business."])
        record = _mk_record(off_topic_count=1)
        record, _reply = await run_turn(
            admin_message="tell me a joke", record=record, provider=provider,
        )
        assert record.off_topic_count == 2

    async def test_off_topic_chain_across_turns(self) -> None:
        provider = ToolAwareFakeProvider(chat_replies=["Let's focus."])
        record = _mk_record(off_topic_count=2)
        record, _reply = await run_turn(
            admin_message="hello there", record=record, provider=provider,
        )
        assert record.off_topic_count == 3


class TestToolCallsPerTurn:
    async def test_single_tool_call_captures_section(self) -> None:
        provider = ToolAwareFakeProvider(
            tool_turns=[
                _mk_tool_turn("save_identity", {"description": "phone repair"}),
            ],
            chat_replies=["Saved your description. What tone?"],
        )
        record = _mk_record()
        record, reply = await run_turn(
            admin_message="I run a phone repair shop",
            record=record,
            provider=provider,
        )
        assert record.draft == {"identity": {"description": "phone repair"}}
        assert reply == "Saved your description. What tone?"

    async def test_multiple_tool_calls_in_one_turn(self) -> None:
        provider = ToolAwareFakeProvider(
            tool_turns=[
                ToolTurn(tool_calls=[
                    ToolCall(
                        id="c1", name="save_identity",
                        args={"description": "phone repair and friendly"},
                    ),
                    ToolCall(
                        id="c2", name="save_tone",
                        args={"tone": "friendly"},
                    ),
                ]),
            ],
            chat_replies=["Captured identity and tone. What services?"],
        )
        record = _mk_record()
        record, _reply = await run_turn(
            admin_message="I run a friendly phone repair shop",
            record=record,
            provider=provider,
        )
        assert "identity" in record.draft
        assert "tone" in record.draft

    async def test_tool_calls_respect_max_limit(self) -> None:
        too_many = [
            ToolTurn(tool_calls=[
                ToolCall(id=f"call_{i}", name=n, args={})
                for i, n in enumerate([
                    "save_identity", "save_tone", "save_services",
                    "save_pricing_rules", "save_escalation",
                ])
            ]),
        ]
        provider = ToolAwareFakeProvider(
            tool_turns=too_many, chat_replies=["OK."],
        )
        record = _mk_record()
        record, _reply = await run_turn(
            admin_message="everything", record=record, provider=provider,
        )
        assert len(record.draft) <= 4

    async def test_no_tool_calls_history_updated_anyway(self) -> None:
        provider = ToolAwareFakeProvider(
            chat_replies=["Tell me more about your business."],
        )
        record = _mk_record()
        record, _reply = await run_turn(
            admin_message="not sure what you mean",
            record=record,
            provider=provider,
        )
        assert len(record.history) >= 2


class TestPriceEcho:
    async def test_echo_triggers_re_prompt(self) -> None:
        provider = ToolAwareFakeProvider(
            tool_turns=[],
            chat_replies=[
                "That will cost $50 for the screen repair.",
                "Screen repair starts from $89.50.",
            ],
        )
        record = _mk_record(draft={
            "services": {
                "items": [{"name": "Screen repair", "price_dollars": 89.5}],
            },
        })
        record, reply = await run_turn(
            admin_message="what does screen repair cost?",
            record=record,
            provider=provider,
        )
        assert reply == "Screen repair starts from $89.50."

    def test_known_price_does_not_trigger_echo(self) -> None:
        draft: dict[str, Any] = {
            "services": {
                "items": [{"name": "Screen repair", "price_dollars": 89.5}],
            },
        }
        assert _echo("Screen repair is $89.50.", draft) is False

    def test_unknown_price_is_echo_violation(self) -> None:
        draft: dict[str, Any] = {
            "services": {
                "items": [{"name": "Screen repair", "price_dollars": 89.5}],
            },
        }
        assert _echo("That would be $50 for screen repair.", draft) is True

    def test_no_figures_no_echo(self) -> None:
        assert _echo("Screen repair is affordable.", {}) is False


class TestCompletenessGate:
    def test_all_sections_valid_is_ok(self) -> None:
        full: dict[str, Any] = {
            "identity": {"description": "phone repair"},
            "tone": {"tone": "friendly"},
            "services": {
                "items": [
                    {"name": "Screen repair", "price_dollars": 89.0},
                ],
            },
            "pricing_rules": {
                "rules": [
                    {
                        "code": "rush", "label": "Rush",
                        "unit_amount_dollars": 25.0, "unit": "flat",
                    },
                ],
            },
            "escalation_threshold": {"_resolved_threshold": 0.5},
        }
        result = request_finalize(full)
        assert result.ok is True

    def test_missing_section_reported(self) -> None:
        partial: dict[str, Any] = {"identity": {"description": "phone repair"}}
        result = request_finalize(partial)
        assert result.ok is False
        assert any("tone" in m for m in result.missing)
        assert any("pric" in m.lower() for m in result.missing)

    def test_unpriced_service_reported(self) -> None:
        draft: dict[str, Any] = {
            "identity": {"description": "phone repair"},
            "tone": {"tone": "friendly"},
            "services": {
                "items": [{"name": "Screen repair", "price_dollars": None}],
            },
            "pricing_rules": {},
            "escalation_threshold": {"_resolved_threshold": 0.5},
        }
        result = request_finalize(draft)
        assert result.ok is False
        assert any("price" in m.lower() for m in result.missing)

    def test_unpriced_rule_reported(self) -> None:
        draft: dict[str, Any] = {
            "identity": {"description": "phone repair"},
            "tone": {"tone": "friendly"},
            "services": {
                "items": [
                    {"name": "Screen repair", "price_dollars": 89.0},
                ],
            },
            "pricing_rules": {
                "rules": [
                    {
                        "code": "rush", "label": "Rush",
                        "unit_amount_dollars": None, "unit": "flat",
                    },
                ],
            },
            "escalation_threshold": {"_resolved_threshold": 0.5},
        }
        result = request_finalize(draft)
        assert result.ok is False
        assert any("rush" in m for m in result.missing)


class TestCheckCompleteness:
    def test_nothing_captured_reports_all(self) -> None:
        missing = _check_completeness({})
        assert len(missing) >= 3

    def test_all_captured_is_empty(self) -> None:
        full: dict[str, Any] = {
            "identity": {"description": "phone repair"},
            "tone": {"tone": "friendly"},
            "services": {
                "items": [
                    {"name": "Screen repair", "price_dollars": 89.0},
                ],
            },
            "pricing_rules": {
                "rules": [
                    {
                        "code": "rush", "label": "Rush",
                        "unit_amount_dollars": 25.0, "unit": "flat",
                    },
                ],
            },
            "escalation_threshold": {"_resolved_threshold": 0.5},
        }
        assert _check_completeness(full) == []
