"""T-006 / T-042: tenant-admin onboarding (Surface-2 Copilot).

The T-006 state machine is retired; turn logic lives in app/onboarding/agent.py.
JSON contract on POST /api/onboarding/message unchanged.
New: POST /api/onboarding/message/stream returns SSE.
Handlers live in controller.py, persistence in service.py.
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import AsyncIterator
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, model_validator

from app.features.onboarding import controller
from app.llm.dependency import get_embedder_dependency, get_llm_provider
from app.llm.embedder import Embedder
from app.llm.provider import LLMProvider
from app.onboarding.beats import InputSpec
from app.shared import auth
from app.shared.limits import LimitTimeout

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/onboarding", tags=["onboarding"])


class OnboardingStateResponse(BaseModel):
    stage: str
    prompt: str
    draft: dict[str, dict[str, object]]
    completed: bool
    history: list[dict[str, str]]
    input: InputSpec | None
    can_confirm: bool


class SelectionPayload(BaseModel):
    beat: str
    values: list[str] = Field(default_factory=list)


class OnboardingMessageRequest(BaseModel):
    text: str | None = None
    selection: SelectionPayload | None = None

    @model_validator(mode="after")
    def _exactly_one_of_text_or_selection(self) -> OnboardingMessageRequest:
        if (self.text is None) == (self.selection is None):
            raise ValueError("provide exactly one of 'text' or 'selection'")
        return self


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
    if body.selection is not None:
        record_data = await controller.run_selection(
            tenant_id=admin.tenant_id,
            selection=controller.Selection(beat=body.selection.beat, values=body.selection.values),
        )
    else:
        assert body.text is not None
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
    if body.text is None:
        raise HTTPException(status_code=400, detail="stream accepts text messages only")
    text = body.text

    async def _stream() -> AsyncIterator[str]:
        async def _sse(event: dict[str, object]) -> str:
            return f"data: {json.dumps(event)}\n\n"

        stream_started = time.perf_counter()
        try:
            reply, record_data = await controller.run_message_stream_core(
                tenant_id=admin.tenant_id, text=text, provider=provider
            )
        except HTTPException as exc:
            yield await _sse({"type": "error", "detail": exc.detail})
            return
        except LimitTimeout:
            yield await _sse(
                {"type": "error", "detail": "That took too long - please send your message again."}
            )
            return
        except Exception:
            # Never let an unexpected failure become a silent empty stream
            # (the client would hang on a forever-streaming bubble).
            logger.exception("onboarding stream failed")
            yield await _sse(
                {
                    "type": "error",
                    "detail": "Something went wrong on my side - please send that again.",
                }
            )
            return
        logger.info(
            "onboarding stream",
            extra={
                "step": "reply_ready",
                "duration_ms": round((time.perf_counter() - stream_started) * 1000, 1),
            },
        )
        yield await _sse({"type": "progress", "stage": "processing"})
        yield await _sse({"type": "reply", "text": reply})
        yield await _sse(
            {
                "type": "state",
                "draft": record_data.get("draft", {}),
                "completed": record_data.get("completed", False),
            }
        )
        yield await _sse({"type": "done"})
        logger.info(
            "onboarding stream",
            extra={
                "step": "stream_done",
                "duration_ms": round((time.perf_counter() - stream_started) * 1000, 1),
            },
        )

    return StreamingResponse(_stream(), media_type="text/event-stream")


@router.post("/confirm", response_model=OnboardingConfirmResponse)
async def confirm(
    admin: Annotated[auth.AuthedTenantAdmin, Depends(auth.require_tenant_admin)],
    embedder: Annotated[Embedder, Depends(get_embedder_dependency)],
) -> OnboardingConfirmResponse:
    result = await controller.confirm(tenant_id=admin.tenant_id, embedder=embedder)
    return OnboardingConfirmResponse(**result)
