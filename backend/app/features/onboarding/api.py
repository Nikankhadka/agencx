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
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator, model_validator

from app.features.knowledge.api import KnowledgeRecord, _absolute_url, _reject_upload
from app.features.knowledge.models import KnowledgeSection
from app.features.onboarding import controller
from app.features.tenants.slug import validate_slug
from app.llm.dependency import get_embedder_dependency, get_llm_provider
from app.llm.embedder import Embedder
from app.llm.provider import LLMProvider
from app.onboarding.beats import InputSpec
from app.onboarding.flow import (
    CorrectionTarget,
    FieldCorrection,
    PendingOffering,
    ProfileDraft,
)
from app.shared import auth
from app.shared.errors import request_id
from app.shared.limits import LimitTimeout

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/onboarding", tags=["onboarding"])


class OnboardingStateResponse(BaseModel):
    stage: str
    prompt: str
    # O-1: the draft is a flat profile - one string per captured field.
    draft: dict[str, Any]
    completed: bool
    history: list[dict[str, str]]
    input: InputSpec | None
    can_confirm: bool
    suggested_slug: str | None
    offering_candidates: list[PendingOffering]
    paused_beat: str | None
    pending_confirmation: dict[str, str] | None = None
    skipped: list[str] = Field(default_factory=list)
    revision: int = 0
    # 29: required beats the source did not find, in beat order. The review
    # sheet renders one note; it never renders empty rows.
    missing_required: list[str] = Field(default_factory=list)


class OnboardingSuggestionsResponse(BaseModel):
    count: int
    candidates: list[PendingOffering]


class OnboardingSuggestionsRequest(BaseModel):
    candidates: list[PendingOffering] = Field(default_factory=list, max_length=100)


class SelectionPayload(BaseModel):
    beat: str
    values: list[str] = Field(default_factory=list)


class CorrectionPayload(BaseModel):
    field: CorrectionTarget
    value: str = Field(min_length=1, max_length=2000)
    raw: str = Field(default="", max_length=2000)


class OnboardingMessageRequest(BaseModel):
    text: str | None = None
    selection: SelectionPayload | None = None
    resume: bool = False
    correction: CorrectionPayload | None = None
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=120)

    @model_validator(mode="after")
    def _exactly_one_of_text_or_selection(self) -> OnboardingMessageRequest:
        if (
            sum(
                (
                    self.text is not None,
                    self.selection is not None,
                    self.resume,
                    self.correction is not None,
                )
            )
            != 1
        ):
            raise ValueError(
                "provide exactly one of 'text', 'selection', 'resume', or 'correction'"
            )
        return self


class OnboardingConfirmResponse(BaseModel):
    tenant_id: UUID
    slug: str


class OnboardingConfirmRequest(BaseModel):
    # W-7: the go-live screen confirms the public address only. Name and type
    # were captured (and validated) during the interview; the founder asked not
    # to re-confirm details already given, so this carries just the slug.
    slug: str | None = Field(default=None, min_length=3, max_length=40)

    @field_validator("slug")
    @classmethod
    def _check_slug(cls, value: str | None) -> str | None:
        return value if value is None else validate_slug(value)


class OnboardingKnowledgeRequest(BaseModel):
    sections: list[KnowledgeSection] = Field(default_factory=list)
    offerings: list[PendingOffering] = Field(default_factory=list)


class OnboardingKnowledgeResponse(BaseModel):
    record: KnowledgeRecord
    offering_candidates: list[PendingOffering]


class OnboardingKnowledgeBatchDocument(BaseModel):
    document_id: UUID
    sections: list[KnowledgeSection] = Field(default_factory=list)


class OnboardingKnowledgeBatchRequest(BaseModel):
    documents: list[OnboardingKnowledgeBatchDocument] = Field(min_length=1, max_length=5)
    offerings: list[PendingOffering] = Field(default_factory=list)
    accept_price_changes: bool = False
    # 29: business-details edits made on the review sheet, saved with the batch.
    # ProfileDraft is the field authority, so a key it does not know is a 422
    # rather than a silent drop.
    profile: dict[str, str] | None = None

    @field_validator("profile")
    @classmethod
    def _known_profile_fields(cls, profile: dict[str, str] | None) -> dict[str, str] | None:
        if profile is None:
            return None
        unknown = sorted(set(profile) - set(ProfileDraft.model_fields))
        if unknown:
            raise ValueError(f"unknown profile fields: {', '.join(unknown)}")
        return profile

    @field_validator("documents")
    @classmethod
    def _document_ids_are_unique(
        cls, documents: list[OnboardingKnowledgeBatchDocument]
    ) -> list[OnboardingKnowledgeBatchDocument]:
        if len({document.document_id for document in documents}) != len(documents):
            raise ValueError("document_id values must be unique")
        return documents


class OnboardingKnowledgeBatchFailure(BaseModel):
    document_id: UUID
    error: str


class OnboardingKnowledgeBatchResponse(BaseModel):
    published: list[UUID]
    failed: list[OnboardingKnowledgeBatchFailure]
    offering_candidates: list[PendingOffering]


class OnboardingSourceUrlRequest(BaseModel):
    # 31: the link editor's body. `replace_document_id` names the source being
    # swapped out; absent means the link is an extra source.
    url: str = Field(min_length=1, max_length=2048)
    replace_document_id: UUID | None = None


class OnboardingSourceUrlResponse(BaseModel):
    # 31: the sheet needs the document's own candidates, the page needs the
    # state - one call answers both.
    state: OnboardingStateResponse
    document: KnowledgeRecord | None


@router.get("/state", response_model=OnboardingStateResponse)
async def get_state(
    admin: Annotated[auth.AuthedTenantAdmin, Depends(auth.require_owner)],
) -> OnboardingStateResponse:
    record = await controller.load_record_state(tenant_id=admin.tenant_id)
    return OnboardingStateResponse(**record)


@router.get("/suggestions", response_model=OnboardingSuggestionsResponse)
async def get_suggestions(
    admin: Annotated[auth.AuthedTenantAdmin, Depends(auth.require_owner)],
) -> OnboardingSuggestionsResponse:
    record = await controller.load_offering_suggestions(tenant_id=admin.tenant_id)
    return OnboardingSuggestionsResponse(**record)


@router.put("/suggestions", response_model=OnboardingSuggestionsResponse)
async def put_suggestions(
    body: OnboardingSuggestionsRequest,
    admin: Annotated[auth.AuthedTenantAdmin, Depends(auth.require_owner)],
    embedder: Annotated[Embedder, Depends(get_embedder_dependency)],
) -> OnboardingSuggestionsResponse:
    record = await controller.save_offering_suggestions(
        tenant_id=admin.tenant_id,
        candidates=body.candidates,
        embedder=embedder,
    )
    return OnboardingSuggestionsResponse(**record)


# W-11a: registered before the "/knowledge/{document_id}" route below - Starlette
# matches routes in declaration order and "{document_id}" would otherwise
# swallow "/knowledge/batch" (matching "batch" as the path segment, then 422ing
# when FastAPI tries to parse it as a UUID) before this route is ever tried.
@router.put("/knowledge/batch", response_model=OnboardingKnowledgeBatchResponse)
async def save_onboarding_knowledge_batch(
    body: OnboardingKnowledgeBatchRequest,
    admin: Annotated[auth.AuthedTenantAdmin, Depends(auth.require_owner)],
    embedder: Annotated[Embedder, Depends(get_embedder_dependency)],
) -> OnboardingKnowledgeBatchResponse:
    published, failed, offerings = await controller.save_onboarding_knowledge_batch(
        tenant_id=admin.tenant_id,
        documents=[
            (document.document_id, [section.model_dump() for section in document.sections])
            for document in body.documents
        ],
        offerings=body.offerings,
        accept_price_changes=body.accept_price_changes,
        embedder=embedder,
        profile=body.profile,
    )
    return OnboardingKnowledgeBatchResponse(
        published=published,
        failed=[
            OnboardingKnowledgeBatchFailure(document_id=document_id, error=error)
            for document_id, error in failed
        ],
        offering_candidates=offerings,
    )


@router.post("/source", response_model=OnboardingStateResponse)
async def post_source(
    admin: Annotated[auth.AuthedTenantAdmin, Depends(auth.require_owner)],
    provider: Annotated[LLMProvider, Depends(get_llm_provider)],
    file: Annotated[UploadFile, File()],
) -> OnboardingStateResponse:
    """29: a file answers the source stage.

    Same validation edge as every other upload - the allowlist, the size cap
    and the empty-file check all come from ``_reject_upload`` so this door
    cannot drift from the Knowledge screen's. One read of the file fills the
    profile blanks and returns the reviewed candidates as onboarding state.
    """
    body = await file.read()
    ext = _reject_upload(file, body, "other")
    record_data = await controller.run_source_upload(
        tenant_id=admin.tenant_id,
        filename=file.filename or "",
        body=body,
        extension=ext,
        provider=provider,
    )
    return OnboardingStateResponse(**controller.response_from_record(record_data))


@router.post("/source/url", response_model=OnboardingSourceUrlResponse)
async def post_source_url(
    body: OnboardingSourceUrlRequest,
    admin: Annotated[auth.AuthedTenantAdmin, Depends(auth.require_owner)],
    provider: Annotated[LLMProvider, Depends(get_llm_provider)],
) -> OnboardingSourceUrlResponse:
    """31: read one link, or replace a source in place, in one call.

    A page the site reader cannot read is a 422 naming the failure category and
    writes nothing. A confirmed onboarding is a 409.
    """
    result = await controller.run_source_url(
        tenant_id=admin.tenant_id,
        url=_absolute_url(body.url.strip()),
        replace_document_id=body.replace_document_id,
        provider=provider,
    )
    return OnboardingSourceUrlResponse(
        state=OnboardingStateResponse(**controller.response_from_record(result["state"])),
        document=(
            KnowledgeRecord(**result["document"]) if result["document"] is not None else None
        ),
    )


@router.put("/knowledge/{document_id}", response_model=OnboardingKnowledgeResponse)
async def save_onboarding_knowledge(
    document_id: UUID,
    body: OnboardingKnowledgeRequest,
    admin: Annotated[auth.AuthedTenantAdmin, Depends(auth.require_owner)],
    embedder: Annotated[Embedder, Depends(get_embedder_dependency)],
) -> OnboardingKnowledgeResponse:
    record, offerings = await controller.save_onboarding_knowledge(
        tenant_id=admin.tenant_id,
        document_id=document_id,
        sections=[section.model_dump() for section in body.sections],
        offerings=body.offerings,
        embedder=embedder,
    )
    return OnboardingKnowledgeResponse(
        record=KnowledgeRecord(**record), offering_candidates=offerings
    )


@router.post("/message", response_model=OnboardingStateResponse)
async def post_message(
    body: OnboardingMessageRequest,
    admin: Annotated[auth.AuthedTenantAdmin, Depends(auth.require_owner)],
    provider: Annotated[LLMProvider, Depends(get_llm_provider)],
    embedder: Annotated[Embedder, Depends(get_embedder_dependency)],
) -> OnboardingStateResponse:
    if body.resume:
        record_data = await controller.run_resume(
            tenant_id=admin.tenant_id, idempotency_key=body.idempotency_key
        )
        return OnboardingStateResponse(**controller.response_from_record(record_data))
    if body.selection is not None:
        record_data = await controller.run_selection(
            tenant_id=admin.tenant_id,
            beat_key=body.selection.beat,
            values=body.selection.values,
            idempotency_key=body.idempotency_key,
        )
        return OnboardingStateResponse(**controller.response_from_record(record_data))
    if body.correction is not None:
        record_data = await controller.run_correction(
            tenant_id=admin.tenant_id,
            correction=FieldCorrection(**body.correction.model_dump()),
            provider=provider,
            idempotency_key=body.idempotency_key,
        )
        return OnboardingStateResponse(**controller.response_from_record(record_data))
    assert body.text is not None
    record_data = await controller.run_message(
        tenant_id=admin.tenant_id,
        text=body.text,
        provider=provider,
        embedder=embedder,
        idempotency_key=body.idempotency_key,
    )
    return OnboardingStateResponse(**controller.response_from_record(record_data))


@router.post("/message/stream")
async def post_message_stream(
    request: Request,
    body: OnboardingMessageRequest,
    admin: Annotated[auth.AuthedTenantAdmin, Depends(auth.require_owner)],
    provider: Annotated[LLMProvider, Depends(get_llm_provider)],
    embedder: Annotated[Embedder, Depends(get_embedder_dependency)],
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
                tenant_id=admin.tenant_id,
                text=text,
                provider=provider,
                embedder=embedder,
                idempotency_key=body.idempotency_key,
            ):
                yield await _sse(event)
        except HTTPException as exc:
            yield await _sse(
                {
                    "type": "error",
                    "code": f"http_{exc.status_code}",
                    "detail": "The request could not be completed.",
                    "request_id": request_id(request),
                }
            )
            return
        except LimitTimeout:
            yield await _sse(
                {
                    "type": "error",
                    "code": "timeout",
                    "detail": "That took too long - please send your message again.",
                    "request_id": request_id(request),
                }
            )
            return
        except Exception:
            # Never let an unexpected failure become a silent empty stream
            # (the client would hang on a forever-streaming bubble).
            logger.exception("onboarding stream failed")
            yield await _sse(
                {
                    "type": "error",
                    "code": "internal_error",
                    "detail": "Something went wrong on my side - please send that again.",
                    "request_id": request_id(request),
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
    admin: Annotated[auth.AuthedTenantAdmin, Depends(auth.require_owner)],
    body: OnboardingConfirmRequest | None = None,
    embedder: Annotated[Embedder | None, Depends(get_embedder_dependency)] = None,
) -> OnboardingConfirmResponse:
    result = await controller.confirm(
        tenant_id=admin.tenant_id,
        slug=body.slug if body else None,
        embedder=embedder,
    )
    return OnboardingConfirmResponse(**result)
