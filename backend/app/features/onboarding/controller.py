"""Onboarding orchestration: turn loop, draft validation, and confirm gating.

Moved out of api/onboarding.py. Holds the business order of a confirm (gate,
validate drafts, resolve threshold, then persist atomically) and the
state-shaped response builder. The LLM turn loop still runs in
app/onboarding/agent.py.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import HTTPException, status

from app.features.onboarding import service
from app.llm.embedder import Embedder
from app.llm.provider import LLMProvider
from app.onboarding.agent import OnboardingRecord, run_turn
from app.onboarding.flow import (
    EscalationDraft,
    IdentityDraft,
    PricingRulesDraft,
    ServicesDraft,
    ToneDraft,
    resolve_threshold,
)
from app.onboarding.tools import request_finalize

_ORDER = ["identity", "tone", "services", "pricing_rules", "escalation_threshold"]


def _cents(dollars: float) -> int:
    return round(dollars * 100)


def response_from_record(record_data: dict[str, Any]) -> dict[str, Any]:
    onboarding = OnboardingRecord.from_jsonb(record_data)
    draft = onboarding.draft
    completed = onboarding.completed
    captured = len(draft)
    stage = "confirm" if completed or captured >= len(_ORDER) else _ORDER[captured]
    prompt = ""
    for msg in reversed(onboarding.history):
        if msg.get("role") == "assistant":
            prompt = msg.get("content", "")
            break
    if not prompt:
        prompt = "I am ready to help set up your assistant. Tell me about your business."
    return {
        "stage": stage,
        "prompt": prompt,
        "draft": draft,
        "completed": completed,
    }


async def load_record_state(*, tenant_id: UUID) -> dict[str, Any]:
    record = await service.load_record(tenant_id=tenant_id)
    return response_from_record(record)


async def run_message(*, tenant_id: UUID, text: str, provider: LLMProvider) -> dict[str, Any]:
    record = await service.load_record(tenant_id=tenant_id)
    onboarding = OnboardingRecord.from_jsonb(record)
    if onboarding.completed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="onboarding already confirmed",
        )
    updated, _reply = await run_turn(admin_message=text, record=onboarding, provider=provider)
    record_data = updated.to_jsonb()
    await service.save_record(tenant_id=tenant_id, record=record_data)
    return record_data


async def run_message_stream_core(
    *, tenant_id: UUID, text: str, provider: LLMProvider
) -> tuple[str, dict[str, Any]]:
    """Shared streaming core: returns (reply_text, record_data). The SSE
    framing stays in api.py."""
    record = await service.load_record(tenant_id=tenant_id)
    onboarding = OnboardingRecord.from_jsonb(record)
    if onboarding.completed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="onboarding already confirmed",
        )
    updated, reply = await run_turn(
        admin_message=text,
        record=onboarding,
        provider=provider,
    )
    record_data = updated.to_jsonb()
    await service.save_record(tenant_id=tenant_id, record=record_data)
    return reply, record_data


async def confirm(*, tenant_id: UUID, embedder: Embedder) -> dict[str, Any]:
    record = await service.load_record(tenant_id=tenant_id)
    onboarding = OnboardingRecord.from_jsonb(record)
    if onboarding.completed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="already confirmed",
        )
    draft = onboarding.draft
    gate = request_finalize(draft)
    if not gate.ok:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"incomplete - missing: {'; '.join(gate.missing)}",
        )
    identity = IdentityDraft.model_validate(draft["identity"])
    tone = ToneDraft.model_validate(draft["tone"])
    services = ServicesDraft.model_validate(draft["services"])
    rules = PricingRulesDraft.model_validate(draft["pricing_rules"])
    esc = EscalationDraft.model_validate(draft["escalation_threshold"])
    threshold = resolve_threshold(esc)

    system_prompt = (
        "You are the AI support and sales assistant for this business. "
        f"About the business: {identity.description}"
    )
    service_items = [
        {
            "name": item.name,
            "description": item.description,
            "price_cents": _cents(item.price_dollars) if item.price_dollars is not None else None,
        }
        for item in services.items
    ]
    service_rules = [
        {
            "code": rule.code,
            "label": rule.label,
            "unit_amount_cents": _cents(rule.unit_amount_dollars)
            if rule.unit_amount_dollars is not None
            else None,
            "unit": rule.unit,
        }
        for rule in rules.rules
    ]
    onboarding.completed = True
    try:
        await service.apply_confirmation(
            tenant_id=tenant_id,
            system_prompt=system_prompt,
            tone=tone.tone,
            escalation_threshold=threshold,
            services=service_items,
            pricing_rules=service_rules,
            embedder=embedder,
            completed_record=onboarding.to_jsonb(),
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    return {
        "tenant_id": tenant_id,
        "catalog_items_created": len(service_items),
        "pricing_rules_created": len(service_rules),
    }
