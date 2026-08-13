"""T-006 / T-042: onboarding schemas + threshold resolver + completeness gate.

The old T-006 state machine (advance, OnboardingState, PROMPTS, STAGE_ORDER,
next_prompt) is retired and replaced by agent.py - see ADR in
docs/archive/decisions-log.md (2026-07-30).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class IdentityDraft(BaseModel):
    description: str


class ToneDraft(BaseModel):
    tone: str


class CatalogItemDraft(BaseModel):
    name: str
    description: str = ""
    price_dollars: float | None = None


class ServicesDraft(BaseModel):
    items: list[CatalogItemDraft] = Field(default_factory=list)


class PricingRuleDraft(BaseModel):
    code: str
    label: str
    unit_amount_dollars: float | None = None
    unit: str = "each"


class PricingRulesDraft(BaseModel):
    rules: list[PricingRuleDraft] = Field(default_factory=list)


class EscalationDraft(BaseModel):
    posture: Literal["rarely", "balanced", "cautious"] | None = None
    threshold: float | None = None


class DraftUpdate(BaseModel):
    """Per-turn structured extraction result: what the owner stated this turn.

    Transient - never persisted. Any non-null section is merged into the
    accumulated draft by the agent; ``off_topic``/``next_question``/``meta_reply``
    drive the reply directive. Prices are only ever the dollar figures the owner
    literally said; the model must not invent an amount.
    """

    off_topic: bool = False
    identity: IdentityDraft | None = None
    tone: ToneDraft | None = None
    services: ServicesDraft | None = None
    pricing_rules: PricingRulesDraft | None = None
    escalation: EscalationDraft | None = None
    next_question: str | None = None
    meta_reply: str | None = None


_POSTURE_THRESHOLDS: dict[str, float] = {
    "rarely": 0.25,
    "balanced": 0.5,
    "cautious": 0.75,
}
DEFAULT_ESCALATION_THRESHOLD = 0.5


def resolve_threshold(draft: EscalationDraft) -> float:
    if draft.threshold is not None and 0.0 <= draft.threshold <= 1.0:
        return draft.threshold
    if draft.posture is not None:
        return _POSTURE_THRESHOLDS[draft.posture]
    return DEFAULT_ESCALATION_THRESHOLD


def _incomplete_rules(rules: list[PricingRuleDraft]) -> list[PricingRuleDraft]:
    return [r for r in rules if r.unit_amount_dollars is None or r.unit_amount_dollars <= 0]


_REQUIRED_SECTIONS: dict[str, type[BaseModel]] = {
    "identity": IdentityDraft,
    "tone": ToneDraft,
    "services": ServicesDraft,
    "pricing_rules": PricingRulesDraft,
    "escalation_threshold": EscalationDraft,
}
