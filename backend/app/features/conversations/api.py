"""T-031: Surface 2's Conversations tab - list + full-transcript detail with
per-message trace (tool calls, inspection verdicts, cost).

Handlers live in controller.py, persistence in service.py. The per-message
cost attribution (lateral join against cost_logs, see service.py) is exact,
not approximate - see its module docstring.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, field_validator

from app.features.chat import service as chat_service
from app.features.conversations import controller
from app.shared import auth

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


class ConversationSummary(BaseModel):
    id: UUID
    customer_ref: str | None
    status: str
    created_at: datetime
    message_count: int
    # C-6: what the owner's Chats list shows without opening anything - the
    # amber "needs you" dot, the line explaining why, and the last thing said.
    needs_attention: bool = False
    pending_summary: str | None = None
    last_message: str | None = None
    last_activity_at: datetime | None = None


class ToolCallDetail(BaseModel):
    id: UUID
    tool_name: str
    arguments: dict[str, Any]
    result: Any
    success: bool
    latency_ms: int | None


class MessageDetail(BaseModel):
    id: UUID
    role: str
    content: str
    agent_node: str | None
    created_at: datetime
    metadata: dict[str, Any]
    cost_usd: float | None
    tool_calls: list[ToolCallDetail]


class ConversationDetail(BaseModel):
    id: UUID
    customer_ref: str | None
    channel: str
    status: str
    created_at: datetime
    total_cost_usd: float
    messages: list[MessageDetail]


@router.get("", response_model=list[ConversationSummary])
async def list_conversations(
    admin: Annotated[auth.AuthedTenantAdmin, Depends(auth.require_tenant_admin)],
    status_filter: Annotated[
        Literal["open", "human", "escalated", "closed"] | None, Query(alias="status")
    ] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[ConversationSummary]:
    return [
        ConversationSummary(**row)
        for row in await controller.list_conversations(
            tenant_id=str(admin.tenant_id),
            status_filter=status_filter,
            limit=limit,
            offset=offset,
        )
    ]


@router.get("/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(
    conversation_id: UUID,
    admin: Annotated[auth.AuthedTenantAdmin, Depends(auth.require_tenant_admin)],
) -> ConversationDetail:
    return ConversationDetail(
        **await controller.get_conversation_detail(
            tenant_id=str(admin.tenant_id), conversation_id=str(conversation_id)
        )
    )


class HumanReplyRequest(BaseModel):
    message: str

    @field_validator("message")
    @classmethod
    def _must_say_something(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("message cannot be blank")
        return value.strip()


async def _switch_handler(*, tenant_id: UUID, conversation_id: UUID, human: bool) -> None:
    if not await chat_service.set_conversation_handler(
        tenant_id=tenant_id, conversation_id=conversation_id, human=human
    ):
        # Either the conversation is not this tenant's, or it is not in the
        # state this transition starts from - an already-taken-over thread, or
        # one a tenant limit ended. 409 rather than 404 so the client resyncs
        # the row instead of concluding it vanished (the escalations queue's
        # existing convention for a lost race).
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="conversation is not in a state that allows this",
        )


@router.post("/{conversation_id}/takeover", status_code=status.HTTP_204_NO_CONTENT)
async def take_over_conversation(
    conversation_id: UUID,
    admin: Annotated[auth.AuthedTenantAdmin, Depends(auth.require_tenant_admin)],
) -> None:
    """C-6: the staff member is the voice now; the assistant stays silent until
    handed back. Available on any conversation, not only a flagged one - a
    business steps into its own conversations whenever it wants to."""
    await _switch_handler(tenant_id=admin.tenant_id, conversation_id=conversation_id, human=True)


@router.post("/{conversation_id}/handback", status_code=status.HTTP_204_NO_CONTENT)
async def hand_back_conversation(
    conversation_id: UUID,
    admin: Annotated[auth.AuthedTenantAdmin, Depends(auth.require_tenant_admin)],
) -> None:
    """C-6: the assistant resumes. The takeover interlude stays in the history,
    so its next turn reads what the human said rather than contradicting it."""
    await _switch_handler(tenant_id=admin.tenant_id, conversation_id=conversation_id, human=False)


@router.post("/{conversation_id}/reply", status_code=status.HTTP_204_NO_CONTENT)
async def reply_as_human(
    conversation_id: UUID,
    body: HumanReplyRequest,
    admin: Annotated[auth.AuthedTenantAdmin, Depends(auth.require_tenant_admin)],
) -> None:
    """C-6: a staff member's own words into the customer's open chat, picked up
    by the transcript poll C-5 left running.

    Requires the conversation to be taken over first: replying underneath a
    live assistant would put two voices in one thread, each unaware of the
    other mid-turn.
    """
    detail = await controller.get_conversation_detail(
        tenant_id=str(admin.tenant_id), conversation_id=str(conversation_id)
    )
    if detail["status"] != "human":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="take over the conversation before replying",
        )
    await chat_service.post_human_reply(
        tenant_id=admin.tenant_id, conversation_id=conversation_id, message=body.message
    )
