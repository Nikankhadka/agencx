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

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.features.conversations import controller
from app.shared import auth

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


class ConversationSummary(BaseModel):
    id: UUID
    customer_ref: str | None
    status: str
    created_at: datetime
    message_count: int


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
        Literal["open", "escalated", "closed"] | None, Query(alias="status")
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
