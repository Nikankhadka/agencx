"""T-042: onboarding agent tools."""

from __future__ import annotations
from typing import Any
from pydantic import BaseModel
from app.llm.provider import ToolSpec
from app.onboarding.flow import (
    _REQUIRED_SECTIONS, EscalationDraft, IdentityDraft,
    PricingRulesDraft, ServicesDraft, ToneDraft, _incomplete_rules,
)

def _apply_identity(d, a):
    p = IdentityDraft.model_validate(a); d["identity"] = p.model_dump(); return p
def _apply_tone(d, a):
    p = ToneDraft.model_validate(a); d["tone"] = p.model_dump(); return p
def _apply_services(d, a):
    p = ServicesDraft.model_validate(a); d["services"] = p.model_dump(); return p
def _apply_pricing_rules(d, a):
    p = PricingRulesDraft.model_validate(a); d["pricing_rules"] = p.model_dump(); return p
def _apply_escalation(d, a):
    p = EscalationDraft.model_validate(a); d["escalation_threshold"] = p.model_dump(); return p

class FinalizeResult(BaseModel):
    ready: bool
    missing: list[str] = []
    unpriced_rules: list[str] = []
    message: str = ""

def request_finalize(draft):
    missing = []
    for n, s in _REQUIRED_SECTIONS.items():
        if n not in draft: missing.append(n); continue
        try: s.model_validate(draft[n])
        except Exception: missing.append(n)
    unpriced = []
    if "pricing_rules" in draft:
        try: rules = PricingRulesDraft.model_validate(draft["pricing_rules"]).rules
        except Exception: rules = []
        unpriced = [r.code for r in _incomplete_rules(rules)]
    if not missing and not unpriced:
        return FinalizeResult(ready=True, message="All complete.")
    parts = []
    if missing: parts.append(f"Still need: {', '.join(missing)}")
    if unpriced: parts.append(f"Unpriced rules: {', '.join(unpriced)}")
    return FinalizeResult(ready=False, missing=missing, unpriced_rules=unpriced, message=" ".join(parts))

ONBOARDING_TOOLS = [
    ToolSpec(name="save_identity", description="Save business description", args_schema=IdentityDraft),
    ToolSpec(name="save_tone", description="Save tone preference", args_schema=ToneDraft),
    ToolSpec(name="save_services", description="Save services/products", args_schema=ServicesDraft),
    ToolSpec(name="save_pricing_rules", description="Save pricing rules", args_schema=PricingRulesDraft),
    ToolSpec(name="save_escalation", description="Save escalation posture", args_schema=EscalationDraft),
]

TOOL_HANDLERS = {
    "save_identity": _apply_identity, "save_tone": _apply_tone,
    "save_services": _apply_services, "save_pricing_rules": _apply_pricing_rules,
    "save_escalation": _apply_escalation,
}
