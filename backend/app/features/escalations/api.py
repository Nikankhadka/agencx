"""T-020/T-031: the tenant-admin escalations queue - list, claim, resolve.

Claim/resolve transitions live in service.py; the controller maps outcomes to
404/409. Request/response models below are the queue's API contract (Surface
2's Escalations tab).
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, field_validator

from app.features.escalations import controller
from app.shared import auth

router = APIRouter(prefix="/api/escalations", tags=["escalations"])


class EscalationResponse(BaseModel):
    id: UUID
    conversation_id: UUID
    reason: str
    # C-6: what the customer actually wants, in one line, for the owner to read
    # in the Chats list instead of a reason code. Null on rows written before
    # C-6 and whenever the model omitted it - the client falls back to reason.
    summary: str | None = None
    status: str
    created_at: datetime
    resolved_at: datetime | None


class ResolveRequest(BaseModel):
    message: str | None = None

    @field_validator("message")
    @classmethod
    def _blank_is_none(cls, value: str | None) -> str | None:
        # A structured client (or a human typing then deleting) may send an
        # empty/whitespace-only string rather than omitting the field - treat
        # it the same as "no message" (same convention as T-019's blank
        # customer_ref handling).
        if value is not None and not value.strip():
            return None
        return value


@router.get("", response_model=list[EscalationResponse])
async def list_escalations(
    admin: Annotated[auth.AuthedTenantAdmin, Depends(auth.require_tenant_admin)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[EscalationResponse]:
    return [
        EscalationResponse(**row)
        for row in await controller.list_escalations(
            tenant_id=str(admin.tenant_id), limit=limit, offset=offset
        )
    ]


@router.post("/{escalation_id}/claim", response_model=EscalationResponse)
async def claim_escalation(
    escalation_id: UUID,
    admin: Annotated[auth.AuthedTenantAdmin, Depends(auth.require_tenant_admin)],
) -> EscalationResponse:
    return EscalationResponse(
        **await controller.claim(tenant_id=str(admin.tenant_id), escalation_id=str(escalation_id))
    )


@router.post("/{escalation_id}/resolve", response_model=EscalationResponse)
async def resolve_escalation(
    escalation_id: UUID,
    body: ResolveRequest,
    admin: Annotated[auth.AuthedTenantAdmin, Depends(auth.require_tenant_admin)],
) -> EscalationResponse:
    return EscalationResponse(
        **await controller.resolve(
            tenant_id=str(admin.tenant_id), escalation_id=str(escalation_id), message=body.message
        )
    )
