"""T-006 / T-042: tenant-admin onboarding (Surface-2 Copilot).

The T-006 state machine is retired; turn logic lives in app/onboarding/agent.py.
JSON contract on POST /api/onboarding/message unchanged.
New: POST /api/onboarding/message/stream returns SSE.
Handlers live in controller.py, persistence in service.py.
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.features.onboarding import controller
from app.llm.dependency import get_embedder_dependency, get_llm_provider
from app.llm.embedder import Embedder
from app.llm.provider import LLMProvider
from app.shared import auth

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/onboarding", tags=["onboarding"])


class OnboardingStateResponse(BaseModel):
    stage: str
    prompt: str
    draft: dict[str, dict[str, object]]
    completed: bool


class OnboardingMessageRequest(BaseModel):
    text: str = Field(min_length=1)


class OnboardingConfirmResponse(BaseModel):
    tenant_id: UUID
    catalog_items_created: int
    pricing_rules_created: int


@router.get("/state", response_model=OnboardingStateResponse)
async def get_state(
    admin: Annotated[auth.AuthedTenantAdmin, Depends(auth.require_tenant_admin)],
) -> OnboardingStateResponse:
    record = await controller.load_record_state(tenant_id=admin.tenant_id)
    return OnboardingStateResponse(**record)


@router.post("/message", response_model=OnboardingStateResponse)
async def post_message(
    body: OnboardingMessageRequest,
    admin: Annotated[auth.AuthedTenantAdmin, Depends(auth.require_tenant_admin)],
    provider: Annotated[LLMProvider, Depends(get_llm_provider)],
) -> OnboardingStateResponse:
    record_data = await controller.run_message(
        tenant_id=admin.tenant_id, text=body.text, provider=provider
    )
    return OnboardingStateResponse(**controller.response_from_record(record_data))


@router.post("/message/stream")
async def post_message_stream(
    body: OnboardingMessageRequest,
    admin: Annotated[auth.AuthedTenantAdmin, Depends(auth.require_tenant_admin)],
    provider: Annotated[LLMProvider, Depends(get_llm_provider)],
) -> StreamingResponse:
    async def _stream() -> AsyncIterator[str]:
        async def _sse(event: dict[str, object]) -> str:
            return f"data: {json.dumps(event)}\n\n"

        try:
            reply, _record = await controller.run_message_stream_core(
                tenant_id=admin.tenant_id, text=body.text, provider=provider
            )
        except HTTPException as exc:
            yield await _sse({"type": "error", "detail": exc.detail})
            return
        except Exception:
            # Never let an unexpected failure become a silent empty stream
            # (the client would hang on a forever-streaming bubble).
            logger.exception("onboarding stream failed")
            yield await _sse({"type": "error", "detail": "internal error"})
            return
        yield await _sse({"type": "progress", "stage": "processing"})
        yield await _sse({"type": "reply", "text": reply})
        yield await _sse({"type": "done"})

    return StreamingResponse(_stream(), media_type="text/event-stream")


@router.post("/confirm", response_model=OnboardingConfirmResponse)
async def confirm(
    admin: Annotated[auth.AuthedTenantAdmin, Depends(auth.require_tenant_admin)],
    embedder: Annotated[Embedder, Depends(get_embedder_dependency)],
) -> OnboardingConfirmResponse:
    result = await controller.confirm(tenant_id=admin.tenant_id, embedder=embedder)
    return OnboardingConfirmResponse(**result)
