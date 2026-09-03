"""T-011/T-012: bare customer chat, now routed through the agent graph.

``POST /api/chat`` is unauthenticated (the customer surface has no login) -
tenant scope comes entirely from the slug, resolved the same way T-005's
public tenant lookup does. This module frames controller events as SSE and
persists the customer message; turn mechanics live in controller.py, rows in
service.py.
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.features.chat import controller, service
from app.llm.dependency import get_embedder_dependency, get_llm_provider
from app.llm.embedder import Embedder
from app.llm.provider import LLMProvider
from app.retrieval.dependency import get_reranker_dependency
from app.retrieval.rerank import Reranker
from app.shared.errors import request_id

logger = logging.getLogger("app.features.chat.api")

router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatRequest(BaseModel):
    slug: str
    conversation_id: UUID | None = None
    message: str = Field(min_length=1)


class PublicMessage(BaseModel):
    id: UUID
    role: str
    content: str
    created_at: datetime


def _sse(event: dict[str, object]) -> str:
    return f"data: {json.dumps(event)}\n\n"


@router.post("")
async def chat(
    request: Request,
    body: ChatRequest,
    provider: Annotated[LLMProvider, Depends(get_llm_provider)],
    embedder: Annotated[Embedder, Depends(get_embedder_dependency)],
    reranker: Annotated[Reranker, Depends(get_reranker_dependency)],
) -> StreamingResponse:
    try:
        tenant_id = await service.resolve_active_tenant(body.slug)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="unknown tenant slug"
        ) from exc

    try:
        (
            conversation_id,
            status_now,
            limits,
            over_budget,
        ) = await service.resolve_conversation(
            tenant_id=tenant_id,
            conversation_id=body.conversation_id,
            message=body.message,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="conversation not found"
        ) from exc

    def _wrap(events: AsyncIterator[dict[str, object]]) -> StreamingResponse:
        async def safe_events() -> AsyncIterator[dict[str, object]]:
            try:
                async for event in events:
                    yield event
            except Exception:
                # The stream has already begun, so the failure cannot become a
                # Problem Details response - it goes out as an `error` event
                # instead. Log it here regardless: this is the last place the
                # traceback exists, and swallowing it would leave a customer's
                # failed turn with no record at all.
                logger.exception("chat stream failed mid-turn")
                yield {
                    "type": "error",
                    "code": "internal_error",
                    "detail": "Something went wrong on my side - please send that again.",
                    "request_id": request_id(request),
                }

        return StreamingResponse(
            (_sse(event) async for event in safe_events()), media_type="text/event-stream"
        )

    # T-020/C-5: a limit stop is terminal - such a conversation never gets
    # another agent turn (the customer's message above is still kept, so the
    # transcript is complete for whoever picks it up on Surface 2). Agent and
    # guardrail handoffs no longer write this status, so they never land here.
    if status_now == "escalated":
        return _wrap(controller.stream_escalated_response(conversation_id=conversation_id))

    # C-6: a staff member is answering this conversation. The message is kept
    # (above) and reaches them in the Chats thread; the assistant stays quiet
    # rather than talking over the human who took it. Not terminal - a handback
    # returns the conversation to 'open' and the next turn runs normally.
    if status_now == "human":
        return _wrap(controller.stream_human_handled(conversation_id=conversation_id))

    # T-028: over the daily budget - graceful handoff, graph never invoked.
    if over_budget:
        return _wrap(
            controller.stream_budget_escalation(
                tenant_id=tenant_id, conversation_id=conversation_id
            )
        )

    return _wrap(
        controller.stream_chat_response(
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            message=body.message,
            provider=provider,
            embedder=embedder,
            reranker=reranker,
            limits=limits,
        )
    )


@router.get("/{conversation_id}/messages", response_model=list[PublicMessage])
async def get_conversation_messages(
    conversation_id: UUID,
    slug: str,
    after: Annotated[datetime | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 200,
) -> list[PublicMessage]:
    """T-031: unauthenticated transcript poll for the customer surface - the
    only way a resolved escalation's human_agent reply reaches an
    already-open customer tab (no push/websocket mechanism exists anywhere
    in this codebase). Trust model matches POST /api/chat's conversation_id:
    knowing the UUID is the capability, same as the rest of this bare
    customer surface (no login).

    ``after`` lets a client that already has the transcript up to some
    timestamp poll for only what's new, rather than re-fetching the whole
    history on every 5s tick."""
    try:
        tenant_id = await service.resolve_active_tenant(slug)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="unknown tenant slug"
        ) from exc
    try:
        rows = await service.list_messages(
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            after=after,
            limit=limit,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="conversation not found"
        ) from exc
    return [PublicMessage(**row) for row in rows]
