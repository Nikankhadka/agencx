"""Intent/action vocabulary: pure mappings, no classifier, no gate.

These are the coercion and lookup helpers app/agents/intent.py offers. They
never raise and never see a database, so this file carries no ``db`` mark.
"""

from __future__ import annotations

import pytest

from app.agents.intent import (
    ESCALATION_REASONS,
    as_action,
    as_intent,
    intent_for_route,
    intent_for_tools,
)


@pytest.mark.parametrize("route", ["conversation", "knowledge", "order_status"])
def test_information_routes(route: str) -> None:
    assert intent_for_route(route) == "information"


@pytest.mark.parametrize("route", ["quoting", "recommendation", "structured"])
def test_offer_routes(route: str) -> None:
    assert intent_for_route(route) == "offer"


@pytest.mark.parametrize("route", ["escalation", None, "unknown", ""])
def test_escalation_and_unknown_routes_have_no_intent(route: str | None) -> None:
    assert intent_for_route(route) is None


@pytest.mark.parametrize(
    "tool", ["get_quote_inputs", "calculate_quote", "show_catalog", "recommend_items"]
)
def test_offer_tools(tool: str) -> None:
    assert intent_for_tools({tool}) == "offer"


@pytest.mark.parametrize("tool", ["search_knowledge", "lookup_order_or_ticket"])
def test_information_tools(tool: str) -> None:
    assert intent_for_tools({tool}) == "information"


def test_offer_beats_information_when_both_are_present() -> None:
    assert intent_for_tools({"search_knowledge", "calculate_quote"}) == "offer"


def test_no_recognized_tools_have_no_intent() -> None:
    assert intent_for_tools(set()) is None
    assert intent_for_tools({"create_escalation"}) is None


@pytest.mark.parametrize("value", ["information", "offer", "support"])
def test_valid_intents_pass_through(value: str) -> None:
    assert as_intent(value) == value


@pytest.mark.parametrize("value", ["escalation", "unknown", "", None])
def test_unknown_intents_coerce_to_none(value: str | None) -> None:
    assert as_intent(value) is None


@pytest.mark.parametrize("value", ["respond", "offer_followup", "escalate", "handoff"])
def test_valid_actions_pass_through(value: str) -> None:
    assert as_action(value) == value


@pytest.mark.parametrize("value", ["support", "unknown", "", None])
def test_unknown_actions_coerce_to_none(value: str | None) -> None:
    assert as_action(value) is None


def test_escalation_reasons_are_unique_and_complete() -> None:
    assert len(ESCALATION_REASONS) == len(set(ESCALATION_REASONS))
    assert set(ESCALATION_REASONS) == {
        "human_requested",
        "knowledge_missing",
        "pricing_confirmation_required",
        "business_decision_required",
        "order_or_service_issue",
        "complaint",
    }
