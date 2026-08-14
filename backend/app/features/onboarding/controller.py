"""Onboarding orchestration: turn loop, beat selection, draft validation, and
confirm gating.

Moved out of api/onboarding.py. Holds the business order of a confirm (gate,
validate drafts, resolve threshold, then persist atomically) and the
state-shaped response builder. The LLM turn loop still runs in
app/onboarding/agent.py; chip selections merge deterministically here.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status

from app.features.onboarding import service
from app.llm.embedder import Embedder
from app.llm.provider import LLMProvider
from app.onboarding import beats
from app.onboarding.agent import (
    OnboardingRecord,
    _assistant_reply_for,
    prepare_turn,
    run_turn,
    stream_reply,
)
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
    updated, _reply, persist = await run_turn(
        admin_message=text, record=onboarding, provider=bounded
    )
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


async def run_message_stream(
    *, tenant_id: UUID, text: str, provider: LLMProvider
) -> AsyncIterator[dict[str, object]]:
    """Streams one text turn as SSE-shaped events.

    Event order: ``progress`` -> ``token``* -> [``redraft``] -> ``token``* ->
    ``reply`` -> ``state`` -> ``done``. Two short DB writes per turn: the draft
    plus the user message persist before the stream starts (so a refresh
    mid-conversation survives), the assistant reply persists after the stream.
    """
    record = await service.load_record(tenant_id=tenant_id)
    onboarding = OnboardingRecord.from_jsonb(record)
    if onboarding.completed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="onboarding already confirmed",
        )
    # ponytail: platform default timeout (see run_message above).
    bounded = TimeLimitedProvider(provider, DEFAULT_LLM_TIMEOUT_S)
    plan = await prepare_turn(admin_message=text, record=onboarding, provider=bounded)
    if plan.persist:
        await service.save_record(tenant_id=tenant_id, record=plan.record.to_jsonb())

    yield {"type": "progress", "stage": "processing"}

    full = ""
    async for kind, payload in stream_reply(plan=plan, provider=bounded):
        if kind == "redraft":
            full = ""
            yield {"type": "redraft", "reason": payload}
        else:
            full += payload
            yield {"type": "token", "text": payload}
    # Kept for the old client; the new client reassembles ``token`` events.
    yield {"type": "reply", "text": full}

    if plan.persist:
        plan.record.history.append({"role": "assistant", "content": full})
        await service.save_record(tenant_id=tenant_id, record=plan.record.to_jsonb())

    record_data = plan.record.to_jsonb()
    completed = record_data.get("completed", False)
    nxt = beats.next_beat(plan.record.draft)
    yield {
        "type": "state",
        "draft": record_data.get("draft", {}),
        "completed": completed,
        "input": beats.input_spec(nxt).model_dump() if nxt else None,
        "can_confirm": nxt is None and not completed,
    }
    yield {"type": "done"}


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
