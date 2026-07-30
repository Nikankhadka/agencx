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
