"""Onboarding orchestration: turn loop, beat selection, draft validation, and
confirm gating.

Moved out of api/onboarding.py. Holds the business order of a confirm (gate,
validate drafts, resolve threshold, then persist atomically) and the
state-shaped response builder. The LLM turn loop still runs in
app/onboarding/agent.py; chip selections merge deterministically here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status

from app.features.onboarding import service
from app.llm.embedder import Embedder
from app.llm.provider import LLMProvider
from app.onboarding import beats
from app.onboarding.agent import OnboardingRecord, run_turn
from app.onboarding.flow import (
    BusinessDraft,
    EscalationDraft,
    IdentityDraft,
    PaymentDraft,
    PricingRulesDraft,
    ServicesDraft,
    TaxDraft,
    ToneDraft,
    resolve_threshold,
)
from app.onboarding.tools import request_finalize
from app.shared.limits import DEFAULT_LLM_TIMEOUT_S, TimeLimitedProvider


@dataclass(frozen=True)
class Selection:
    beat: str
    values: list[str] = field(default_factory=list)


def _cents(dollars: float) -> int:
    return round(dollars * 100)


def _fmt_dollars(dollars: float) -> str:
    return f"{dollars:g}"


def response_from_record(record_data: dict[str, Any]) -> dict[str, Any]:
    onboarding = OnboardingRecord.from_jsonb(record_data)
    draft = onboarding.draft
    completed = onboarding.completed
    beat = beats.next_beat(draft)
    stage = beat.key if beat else "confirm"
    prompt = ""
    for msg in reversed(onboarding.history):
        if msg.get("role") == "assistant":
            prompt = msg.get("content", "")
            break
    if not prompt:
        prompt = (
            "Hi, I'm Wren, your personal agent to set up your business agent. "
            "To get started: tell me the name of your business."
        )
    return {
        "stage": stage,
        "prompt": prompt,
        "draft": draft,
        "completed": completed,
        "history": onboarding.history,
        "input": beats.input_spec(beat) if beat else None,
        "can_confirm": beat is None and not completed,
    }


async def load_record_state(*, tenant_id: UUID) -> dict[str, Any]:
    record = await service.load_record(tenant_id=tenant_id)
    return response_from_record(record)


def _selection_user_message(beat: beats.Beat, values: list[str]) -> str:
    if beat.kind == "cta" and not values:
        return beat.cta_label or beat.label
    return ", ".join(chip.label for chip in beat.chips if chip.value in values)


def _readback_summary(draft: dict[str, Any]) -> str:
    business = draft.get("business") or {}
    identity = draft.get("identity") or {}
    services = draft.get("services") or {}
    tone = draft.get("tone") or {}
    lines: list[str] = []
    if business.get("name"):
        lines.append(f"Your business: {business['name']}")
    if identity.get("description"):
        lines.append(f"What you do: {identity['description']}")
    is_team = business.get("is_team")
    if is_team is not None:
        lines.append("You're a team" if is_team else "It's just you")
    items = services.get("items") or []
    priced = [i for i in items if i.get("price_dollars") is not None]
    if priced:
        lines.append(
            "Services: "
            + ", ".join(f"{i['name']} at ${_fmt_dollars(i['price_dollars'])}" for i in priced)
        )
    if tone.get("tone"):
        lines.append(f"Tone: {tone['tone']}")
    lines.append("Does everything look right?")
    return "\n".join(lines)


def _activation_summary(draft: dict[str, Any]) -> str:
    business = draft.get("business") or {}
    name = business.get("name")
    if name:
        intro = f"Your agent for {name} is ready to go live."
    else:
        intro = "Your agent is ready to go live."
    return f"{intro} Hit confirm to publish it."


def _assistant_reply_for(draft: dict[str, Any]) -> str:
    nxt = beats.next_beat(draft)
    if nxt is None:
        return _activation_summary(draft)
    if nxt.key == "readback":
        return _readback_summary(draft)
    return f"Got it. {nxt.ask}"


def _finalize_reply(updated: OnboardingRecord, reply: str) -> tuple[OnboardingRecord, str]:
    """Replace the LLM reply with a deterministic summary at readback/completion.

    The readback recap and the activation summary are server-synthesized from the
    draft (never the model) - the same guarantee as the T-042 ADR. Only runs on
    persisted turns, so a no-op off-topic turn is never rewritten.
    """
    nxt = beats.next_beat(updated.draft)
    if nxt is None or nxt.key == "readback":
        summary = _assistant_reply_for(updated.draft)
        if updated.history and updated.history[-1].get("role") == "assistant":
            updated.history[-1]["content"] = summary
        return updated, summary
    return updated, reply


async def run_message(*, tenant_id: UUID, text: str, provider: LLMProvider) -> dict[str, Any]:
    record = await service.load_record(tenant_id=tenant_id)
    onboarding = OnboardingRecord.from_jsonb(record)
    if onboarding.completed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="onboarding already confirmed",
        )
    # ponytail: use the platform default timeout rather than resolving the
    # tenant's per-tenant llm_timeout_s; resolve TenantLimits like
    # features/chat/controller.py if onboarding ever needs per-tenant overrides.
    bounded = TimeLimitedProvider(provider, DEFAULT_LLM_TIMEOUT_S)
    updated, reply, persist = await run_turn(
        admin_message=text, record=onboarding, provider=bounded
    )
    if persist:
        updated, reply = _finalize_reply(updated, reply)
    record_data = updated.to_jsonb()
    if persist:
        await service.save_record(tenant_id=tenant_id, record=record_data)
    return record_data


async def run_selection(*, tenant_id: UUID, selection: Selection) -> dict[str, Any]:
    """Merge a chip selection deterministically - no LLM call.

    Rejects a stale beat (the client was showing an older widget than the server's
    current first-unsatisfied beat) with a 409 so the client re-syncs from /state.
    """
    record = await service.load_record(tenant_id=tenant_id)
    onboarding = OnboardingRecord.from_jsonb(record)
    if onboarding.completed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="onboarding already confirmed",
        )
    beat = beats.next_beat(onboarding.draft)
    if beat is None or selection.beat != beat.key:
        current = beat.key if beat else "confirm"
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"stale selection - current beat is {current}",
        )
    beats.apply_selection(onboarding.draft, selection.beat, selection.values)
    user_message = _selection_user_message(beat, selection.values)
    reply = _assistant_reply_for(onboarding.draft)
    onboarding.history.append({"role": "user", "content": user_message})
    onboarding.history.append({"role": "assistant", "content": reply})
    record_data = onboarding.to_jsonb()
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
    # ponytail: platform default timeout (see run_message above).
    bounded = TimeLimitedProvider(provider, DEFAULT_LLM_TIMEOUT_S)
    updated, reply, persist = await run_turn(
        admin_message=text,
        record=onboarding,
        provider=bounded,
    )
    if persist:
        updated, reply = _finalize_reply(updated, reply)
    record_data = updated.to_jsonb()
    if persist:
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
    business = BusinessDraft.model_validate(draft["business"])
    identity = IdentityDraft.model_validate(draft["identity"])
    tone = ToneDraft.model_validate(draft["tone"])
    services = ServicesDraft.model_validate(draft["services"])
    rules = PricingRulesDraft.model_validate(draft["pricing_rules"])
    esc = EscalationDraft.model_validate(draft["escalation_threshold"])
    tax = TaxDraft.model_validate(draft["tax"])
    payment = PaymentDraft.model_validate(draft["payment"])
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
            business_name=business.name,
            processing_mode=payment.processing_mode or "DIRECT",
            config_extra={
                "business": business.model_dump(),
                "payment": payment.model_dump(),
                "tax": tax.model_dump(),
            },
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
