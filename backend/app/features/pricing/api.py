"""T-031: Surface 2's Pricing tab - pricing_rules inline editing + a
read-only offerings list.

Currency conversion happens ONLY at this API boundary (PricingRuleUpdate):
the client sends a decimal dollar string/number, this module converts it to
integer cents server-side - never trusting a client-supplied cents value.
Handlers live in controller.py, persistence in service.py.
"""

from __future__ import annotations

from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, field_validator

from app.features.pricing import controller
from app.shared import auth

router = APIRouter(prefix="/api/pricing", tags=["pricing"])

_MAX_DOLLARS = Decimal("1000000")


class PricingRuleResponse(BaseModel):
    id: UUID
    code: str
    label: str
    unit_amount_cents: int
    unit: str
    active: bool
    updated_at: datetime


class CatalogItemResponse(BaseModel):
    id: UUID
    name: str
    description: str
    price_cents: int | None
    active: bool
    updated_at: datetime


class PricingRuleUpdate(BaseModel):
    code: str | None = None
    label: str | None = None
    unit_amount_dollars: Decimal | None = None
    unit: str | None = None
    active: bool | None = None

    @field_validator("code", "label", "unit")
    @classmethod
    def _reject_blank(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("must not be blank")
        return value

    @field_validator("unit_amount_dollars", mode="before")
    @classmethod
    def _parse_dollars(cls, value: object) -> Decimal | None:
        if value is None:
            return None
        try:
            amount = Decimal(str(value))
        except InvalidOperation as exc:
            raise ValueError("not a valid decimal amount") from exc
        if not amount.is_finite():
            raise ValueError("amount must be finite")
        if amount < 0:
            raise ValueError("amount must not be negative")
        if amount > _MAX_DOLLARS:
            raise ValueError(f"amount must not exceed {_MAX_DOLLARS}")
        # At most 2 decimal places - reject e.g. 1.999 rather than silently
        # rounding an admin-authored price to something they didn't type.
        if amount != amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP):
            raise ValueError("amount must have at most 2 decimal places")
        return amount

    def cents(self) -> int | None:
        if self.unit_amount_dollars is None:
            return None
        return int((self.unit_amount_dollars * 100).to_integral_value(rounding=ROUND_HALF_UP))


@router.get("/rules", response_model=list[PricingRuleResponse])
async def list_pricing_rules(
    admin: Annotated[auth.AuthedTenantAdmin, Depends(auth.require_owner)],
) -> list[PricingRuleResponse]:
    return [
        PricingRuleResponse(**row)
        for row in await controller.list_rules(tenant_id=str(admin.tenant_id))
    ]


@router.patch("/rules/{rule_id}", response_model=PricingRuleResponse)
async def update_pricing_rule(
    rule_id: UUID,
    body: PricingRuleUpdate,
    admin: Annotated[auth.AuthedTenantAdmin, Depends(auth.require_owner)],
) -> PricingRuleResponse:
    whitelist = {
        "code": body.code,
        "label": body.label,
        "unit_amount_cents": body.cents(),
        "unit": body.unit,
        "active": body.active,
    }
    updates = {key: value for key, value in whitelist.items() if value is not None}
    return PricingRuleResponse(
        **await controller.update_rule(
            tenant_id=str(admin.tenant_id), rule_id=str(rule_id), updates=updates
        )
    )


@router.get("/catalog", response_model=list[CatalogItemResponse])
async def list_catalog_items(
    admin: Annotated[auth.AuthedTenantAdmin, Depends(auth.require_owner)],
) -> list[CatalogItemResponse]:
    return [
        CatalogItemResponse(**row)
        for row in await controller.list_catalog(tenant_id=str(admin.tenant_id))
    ]
