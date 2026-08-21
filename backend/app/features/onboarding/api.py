"""T-006 / T-042: tenant-admin onboarding (Surface-2 Copilot).

The T-006 state machine is retired; turn logic lives in app/onboarding/agent.py.
JSON contract on POST /api/onboarding/message unchanged.
POST /api/onboarding/message/stream returns SSE in this event order:
``progress`` -> ``token``* -> [``redraft``] -> ``token``* -> ``reply`` ->
``state`` -> ``done``. ``token`` deltas reassemble into the reply; ``redraft``
signals the price-echo guard tripped and the client should drop tokens so far.
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
from app.llm.dependency import get_llm_provider
from app.llm.provider import LLMProvider
from app.onboarding.beats import InputSpec
from app.shared import auth
from app.shared.limits import LimitTimeout

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/onboarding", tags=["onboarding"])


class OnboardingStateResponse(BaseModel):
    stage: str
    prompt: str
    # O-1: the draft is a flat profile - one string per captured field.
    draft: dict[str, str]
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
        # O-1 made every beat a text beat, so nothing is satisfied by a chip.
        # The payload stays in the contract until E-1 rebuilds this surface.
        raise HTTPException(status_code=409, detail="onboarding is text-only")
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
            async for event in controller.run_message_stream(
                tenant_id=admin.tenant_id, text=text, provider=provider
            ):
                yield await _sse(event)
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
                "step": "stream_done",
                "duration_ms": round((time.perf_counter() - stream_started) * 1000, 1),
            },
        )

    return StreamingResponse(_stream(), media_type="text/event-stream")


@router.post("/confirm", response_model=OnboardingConfirmResponse)
async def confirm(
    admin: Annotated[auth.AuthedTenantAdmin, Depends(auth.require_tenant_admin)],
) -> OnboardingConfirmResponse:
    result = await controller.confirm(tenant_id=admin.tenant_id)
    return OnboardingConfirmResponse(**result)
