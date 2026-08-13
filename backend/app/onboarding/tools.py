"""T-042: onboarding tool implementations."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.onboarding.flow import (
    EscalationDraft,
    IdentityDraft,
    PricingRulesDraft,
    ServicesDraft,
    ToneDraft,
    _incomplete_rules,
    resolve_threshold,
)


class ToolResult(BaseModel):
    ok: bool = True
    message: str = Field(default="")
    missing: list[str] = Field(default_factory=list)


def save_identity(draft: dict[str, Any], args: IdentityDraft) -> dict[str, Any]:
    draft["identity"] = args.model_dump()
    return draft


def save_tone(draft: dict[str, Any], args: ToneDraft) -> dict[str, Any]:
    draft["tone"] = args.model_dump()
    return draft


def save_services(draft: dict[str, Any], args: ServicesDraft) -> dict[str, Any]:
    draft["services"] = args.model_dump()
    return draft


def save_pricing_rules(draft: dict[str, Any], args: PricingRulesDraft) -> dict[str, Any]:
    rules = args.model_dump()
    missing = _incomplete_rules(args.rules)
    if missing:
        rules["_unpriced"] = [r.code for r in missing]
    draft["pricing_rules"] = rules
    return draft


def save_escalation(draft: dict[str, Any], args: EscalationDraft) -> dict[str, Any]:
    raw = args.model_dump()
    raw["_resolved_threshold"] = resolve_threshold(args)
    draft["escalation_threshold"] = raw
    return draft


def _check_completeness(draft: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    identity = draft.get("identity")
    tone = draft.get("tone")
    services = draft.get("services")
    pricing = draft.get("pricing_rules")
    escalation = draft.get("escalation_threshold")

    if not identity or not identity.get("description"):
        missing.append("business description")
    if not tone or not tone.get("tone"):
        missing.append("assistant tone")

    items = services.get("items", []) if services and isinstance(services, dict) else []
    if not items:
        missing.append("at least one service or product with a price")
    else:
        unpriced = [i.get("name", "unknown") for i in items if i.get("price_dollars") is None]
        if unpriced:
            missing.append(f"prices for services: {', '.join(unpriced)}")

    rules = pricing.get("rules", []) if pricing and isinstance(pricing, dict) else []
    unpriced_rules = [
        r.get("code", r.get("label", "unknown"))
        for r in rules
        if r.get("unit_amount_dollars") is None or r.get("unit_amount_dollars", 0) <= 0
    ]
    if unpriced_rules:
        missing.append(f"amounts for pricing rules: {', '.join(unpriced_rules)}")

    if not escalation or not escalation.get("_resolved_threshold"):
        missing.append("escalation posture")
    return missing


def request_finalize(draft: dict[str, Any]) -> ToolResult:
    missing = _check_completeness(draft)
    if missing:
        return ToolResult(ok=False, missing=missing)
    return ToolResult(ok=True, message="All required sections complete.")
