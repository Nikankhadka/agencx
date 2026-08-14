"""T-042: onboarding tool implementations."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.onboarding import beats
from app.onboarding.flow import (
    BusinessDraft,
    EscalationDraft,
    IdentityDraft,
    KycDraft,
    PaymentDraft,
    PricingRulesDraft,
    ReadbackDraft,
    ServicesDraft,
    TaxDraft,
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


def save_business(draft: dict[str, Any], args: BusinessDraft) -> dict[str, Any]:
    draft["business"] = args.model_dump()
    return draft


def save_tax(draft: dict[str, Any], args: TaxDraft) -> dict[str, Any]:
    draft["tax"] = args.model_dump()
    return draft


def save_payment(draft: dict[str, Any], args: PaymentDraft) -> dict[str, Any]:
    draft["payment"] = args.model_dump()
    return draft


def save_readback(draft: dict[str, Any], args: ReadbackDraft) -> dict[str, Any]:
    draft["readback"] = args.model_dump()
    return draft


def save_kyc(draft: dict[str, Any], args: KycDraft) -> dict[str, Any]:
    draft["kyc"] = args.model_dump()
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
    return beats.check_completeness(draft)


def request_finalize(draft: dict[str, Any]) -> ToolResult:
    missing = _check_completeness(draft)
    if missing:
        return ToolResult(ok=False, missing=missing)
    return ToolResult(ok=True, message="All required sections complete.")
