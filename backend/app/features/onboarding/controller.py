"""Onboarding orchestration: turn loop, draft validation, and confirm gating.

Moved out of api/onboarding.py. Holds the business order of a confirm (gate,
then persist) and the state-shaped response builder. The LLM turn loop runs in
app/onboarding/agent.py. O-1 made onboarding text-only: every beat is
satisfied by extraction, so there is no deterministic selection path here.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status

from app.features.onboarding import service
from app.llm.provider import LLMProvider
from app.onboarding import beats
from app.onboarding.agent import (
    OnboardingRecord,
    prepare_turn,
    run_turn,
    stream_reply,
)
from app.onboarding.flow import ProfileDraft
from app.onboarding.tools import request_finalize
from app.shared.limits import DEFAULT_LLM_TIMEOUT_S, TimeLimitedProvider


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
        prompt = "Hi! I'll help you set up your business. To get started, what's your name?"
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
        "stage": nxt.key if nxt else "confirm",
        "draft": record_data.get("draft", {}),
        "completed": completed,
        "input": beats.input_spec(nxt).model_dump() if nxt else None,
        "can_confirm": nxt is None and not completed,
    }
    yield {"type": "done"}


async def confirm(*, tenant_id: UUID) -> dict[str, Any]:
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
    # The gate above guarantees all seven fields; extra keys (a pre-O-1 draft's
    # orphan sections) are ignored rather than rejected.
    profile = ProfileDraft.model_validate(draft)
    # business_type is the owner's own free text, so it gets its own sentence
    # rather than an apposition - "Bytefix Repairs, phone repair shop" and
    # "Northgate Family Dental, A three-chair practice..." both read badly.
    system_prompt = (
        f"You are the assistant for {profile.business_name}. "
        f"About the business: {profile.business_type.rstrip('.')}. "
        "Answer only from the business's own material; when the answer isn't "
        "there, say so and offer to have the owner follow up."
    )
    onboarding.completed = True
    await service.apply_confirmation(
        tenant_id=tenant_id,
        system_prompt=system_prompt,
        business_name=profile.business_name,
        profile=profile.model_dump(),
        completed_record=onboarding.to_jsonb(),
    )
    return {"tenant_id": tenant_id}
