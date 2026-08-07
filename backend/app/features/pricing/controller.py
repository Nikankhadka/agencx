"""Pricing handlers: whitelist the updatable columns and map outcomes to HTTP.

Handler logic that moved out of api/pricing.py. The dollar-to-cents boundary
lives in api.py's request model (PricingRuleUpdate.cents()); this layer builds
the update dict from the validated body, hands it to the persistence layer,
and maps 404/409 outcomes. The set-clause column whitelist is fixed here - it
is enforced by service.py's SQL building from this dict's keys.
"""

from __future__ import annotations

from typing import Any

import asyncpg
from fastapi import HTTPException, status

from app.features.pricing import service


async def list_rules(*, tenant_id: str) -> list[dict[str, Any]]:
    return await service.list_rules(tenant_id=tenant_id)


async def list_catalog(*, tenant_id: str) -> list[dict[str, Any]]:
    return await service.list_catalog(tenant_id=tenant_id)


async def update_rule(*, tenant_id: str, rule_id: str, updates: dict[str, Any]) -> dict[str, Any]:
    if not updates:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="no fields to update"
        )
    try:
        row = await service.update_rule(tenant_id=tenant_id, rule_id=rule_id, updates=updates)
    except asyncpg.UniqueViolationError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"a rule with code {updates.get('code')!r} already exists",
        ) from exc
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="pricing rule not found")
    return row
