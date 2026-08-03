"""T-006 / T-042: tenant-admin onboarding (Surface-2 Copilot).

The T-006 state machine is retired; turn logic lives in app/onboarding/agent.py.
JSON contract on POST /api/onboarding/message unchanged.
New: POST /api/onboarding/message/stream returns SSE.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.core import auth, db
from app.ingestion.pipeline import ingest_catalog_items
from app.llm.dependency import get_embedder_dependency, get_llm_provider
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

if TYPE_CHECKING:
    from app.core.db import AppConnection

router = APIRouter(prefix="/api/onboarding", tags=["onboarding"])


class OnboardingStateResponse(BaseModel):
    stage: str
    prompt: str
    draft: dict[str, dict[str, Any]]
    completed: bool


class OnboardingMessageRequest(BaseModel):
    text: str = Field(min_length=1)


class OnboardingConfirmResponse(BaseModel):
    tenant_id: UUID
    catalog_items_created: int
    pricing_rules_created: int


async def _load_record(conn: AppConnection, tenant_id: UUID) -> dict[str, Any]:
    raw = await conn.fetchval(
        "select config->'onboarding' from tenant_config where tenant_id = $1",
        tenant_id,
    )
    return json.loads(raw) if raw is not None else {}


async def _save_record(conn: AppConnection, tenant_id: UUID, record: dict[str, Any]) -> None:
    await conn.execute(
        "update tenant_config set config = jsonb_set("
        "config, '{onboarding}', $2::jsonb, true), "
        "updated_at = now() where tenant_id = $1",
        tenant_id,
        json.dumps(record),
    )


_ORDER = ["identity", "tone", "services", "pricing_rules", "escalation_threshold"]


def _response_from_record(record: dict[str, Any]) -> OnboardingStateResponse:
    onboarding = OnboardingRecord.from_jsonb(record)
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
    return OnboardingStateResponse(
        stage=stage,
        prompt=prompt,
        draft=draft,
        completed=completed,
    )


@router.get("/state", response_model=OnboardingStateResponse)
async def get_state(
    admin: Annotated[auth.AuthedTenantAdmin, Depends(auth.require_tenant_admin)],
) -> OnboardingStateResponse:
    async with db.tenant_context(admin.tenant_id, "tenant_admin") as conn:
        record = await _load_record(conn, admin.tenant_id)
    return _response_from_record(record)


@router.post("/message", response_model=OnboardingStateResponse)
async def post_message(
    body: OnboardingMessageRequest,
    admin: Annotated[auth.AuthedTenantAdmin, Depends(auth.require_tenant_admin)],
    provider: Annotated[LLMProvider, Depends(get_llm_provider)],
) -> OnboardingStateResponse:
    async with db.tenant_context(admin.tenant_id, "tenant_admin") as conn:
        record = await _load_record(conn, admin.tenant_id)
        onboarding = OnboardingRecord.from_jsonb(record)
        if onboarding.completed:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="onboarding already confirmed",
            )
        updated, _reply = await run_turn(
            admin_message=body.text,
            record=onboarding,
            provider=provider,
        )
        record_data = updated.to_jsonb()
        await _save_record(conn, admin.tenant_id, record_data)
    return _response_from_record(record_data)


@router.post("/message/stream")
async def post_message_stream(
    body: OnboardingMessageRequest,
    admin: Annotated[auth.AuthedTenantAdmin, Depends(auth.require_tenant_admin)],
    provider: Annotated[LLMProvider, Depends(get_llm_provider)],
) -> StreamingResponse:
    def _sse_str(event: dict[str, object]) -> str:
        return f"data: {json.dumps(event)}\n\n"

    async def _stream() -> AsyncIterator[str]:
        async with db.tenant_context(admin.tenant_id, "tenant_admin") as conn:
            record = await _load_record(conn, admin.tenant_id)
            onboarding = OnboardingRecord.from_jsonb(record)
            if onboarding.completed:
                yield _sse_str(
                    {"type": "error", "detail": "onboarding already confirmed"},
                )
                return
            yield _sse_str({"type": "progress", "stage": "processing"})
            updated, reply = await run_turn(
                admin_message=body.text,
                record=onboarding,
                provider=provider,
            )
            record_data = updated.to_jsonb()
            await _save_record(conn, admin.tenant_id, record_data)
            yield _sse_str({"type": "reply", "text": reply})
            yield _sse_str({"type": "done"})

    return StreamingResponse(_stream(), media_type="text/event-stream")


def _cents(dollars: float) -> int:
    return round(dollars * 100)


@router.post("/confirm", response_model=OnboardingConfirmResponse)
async def confirm(
    admin: Annotated[auth.AuthedTenantAdmin, Depends(auth.require_tenant_admin)],
    embedder: Annotated[Embedder, Depends(get_embedder_dependency)],
) -> OnboardingConfirmResponse:
    async with db.tenant_context(admin.tenant_id, "tenant_admin") as conn:
        record = await _load_record(conn, admin.tenant_id)
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
        sp = (
            "You are the AI support and sales assistant for this business. "
            f"About the business: {identity.description}"
        )
        await conn.execute(
            "update tenant_config set system_prompt=$2, tone=$3, "
            "escalation_threshold=$4, updated_at=now() where tenant_id=$1",
            admin.tenant_id,
            sp,
            tone.tone,
            threshold,
        )
        for item in services.items:
            pc = _cents(item.price_dollars) if item.price_dollars is not None else None
            await conn.execute(
                "insert into catalog_items (tenant_id, name, description, "
                "price_cents) values ($1, $2, $3, $4)",
                admin.tenant_id,
                item.name,
                item.description,
                pc,
            )
        unpriced = [
            r.code
            for r in rules.rules
            if r.unit_amount_dollars is None or r.unit_amount_dollars <= 0
        ]
        if unpriced:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"pricing rules missing a positive amount: {sorted(unpriced)}",
            )
        for rule in rules.rules:
            amount = rule.unit_amount_dollars
            if amount is None:
                continue
            await conn.execute(
                "insert into pricing_rules (tenant_id, code, label, "
                "unit_amount_cents, unit) values ($1, $2, $3, $4, $5)",
                admin.tenant_id,
                rule.code,
                rule.label,
                _cents(amount),
                rule.unit,
            )
        await ingest_catalog_items(
            conn,
            tenant_id=admin.tenant_id,
            embedder=embedder,
        )
        onboarding.completed = True
        record_data = onboarding.to_jsonb()
        await _save_record(conn, admin.tenant_id, record_data)
    return OnboardingConfirmResponse(
        tenant_id=admin.tenant_id,
        catalog_items_created=len(services.items),
        pricing_rules_created=len(rules.rules),
    )
