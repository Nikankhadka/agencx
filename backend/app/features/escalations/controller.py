"""Escalations handlers: map the queue + claim/resolve transitions to HTTP.

Handler logic that moved out of api/escalations.py. The race-safe conditional
updates live in service.py - the controller only distinguishes the outcomes
(404 vs 409) and builds response rows.
"""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status

from app.features.escalations import service


async def list_escalations(
    *, tenant_id: str, limit: int, offset: int, role: str = "tenant_admin"
) -> list[dict[str, Any]]:
    return await service.list_escalations(
        tenant_id=tenant_id, limit=limit, offset=offset, role=role
    )


async def claim(
    *, tenant_id: str, escalation_id: str, role: str = "tenant_admin"
) -> dict[str, Any]:
    result = await service.claim(tenant_id=tenant_id, escalation_id=escalation_id, role=role)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="escalation not found")
    if "__conflict__" in result:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=result["__conflict__"])
    return result


async def resolve(
    *, tenant_id: str, escalation_id: str, message: str | None, role: str = "tenant_admin"
) -> dict[str, Any]:
    result = await service.resolve(
        tenant_id=tenant_id, escalation_id=escalation_id, message=message, role=role
    )
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="escalation not found")
    if "conflict" in result:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=result["conflict"])
    return result
