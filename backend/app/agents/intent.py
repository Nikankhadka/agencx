"""Intent and action vocabulary for a customer turn (descriptive metadata only).

Intent describes what the customer is trying to accomplish, in three broad
families. Action describes what the turn did about it. Escalation is an action,
not an intent: a customer can escalate on any family, and a missing or unknown
intent never blocks anything - every writer coerces through ``as_intent`` and
falls back to null. Nothing routes or gates on these values.
"""

from __future__ import annotations

from typing import Literal, cast

Intent = Literal["information", "offer", "support"]
Action = Literal["respond", "offer_followup", "escalate", "handoff"]

_INTENTS: frozenset[str] = frozenset(("information", "offer", "support"))
_ACTIONS: frozenset[str] = frozenset(("respond", "offer_followup", "escalate", "handoff"))

# Route -> intent. "escalation" is deliberately absent: an escalation's intent
# comes from the create_escalation tool argument or from intent_for_tools.
_ROUTE_INTENT: dict[str, Intent] = {
    "conversation": "information",
    "knowledge": "information",
    "order_status": "information",
    "quoting": "offer",
    "recommendation": "offer",
    "structured": "offer",
}

_OFFER_TOOLS: frozenset[str] = frozenset(
    ("get_quote_inputs", "calculate_quote", "show_catalog", "recommend_items")
)
_INFORMATION_TOOLS: frozenset[str] = frozenset(("search_knowledge", "lookup_order_or_ticket"))

# Suggested canonical values for create_escalation.reason. The field stays free
# text in the schema - these are guidance for the model, not an enum.
ESCALATION_REASONS: tuple[str, ...] = (
    "human_requested",
    "knowledge_missing",
    "pricing_confirmation_required",
    "business_decision_required",
    "order_or_service_issue",
    "complaint",
)


def as_intent(value: str | None) -> Intent | None:
    """Coerce an untrusted value to a known intent; unknown/None -> None."""
    return cast(Intent, value) if value in _INTENTS else None


def as_action(value: str | None) -> Action | None:
    """Coerce an untrusted value to a known action; unknown/None -> None."""
    return cast(Action, value) if value in _ACTIONS else None


def intent_for_route(route: str | None) -> Intent | None:
    return _ROUTE_INTENT.get(route or "")


def intent_for_tools(called_tools: set[str]) -> Intent | None:
    if called_tools & _OFFER_TOOLS:
        return "offer"
    if called_tools & _INFORMATION_TOOLS:
        return "information"
    return None
