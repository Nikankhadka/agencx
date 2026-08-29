"""T-034: Surface 2's Dashboards tab - cost/volume metrics from cost_logs and
conversations/escalations, plus the latest eval_runs row per run_type shown
against this project's own gate thresholds.

Threshold constants live in service.py (see its docstring for the mirroring
note). Handlers live in controller.py.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.features.dashboards import controller
from app.shared import auth

router = APIRouter(prefix="/api/dashboards", tags=["dashboards"])


class DailyCost(BaseModel):
    day: date
    cost_usd: float


class BudgetUsage(BaseModel):
    """Where this month's spend sits against the standing testing budget (P-1).
    ``fraction`` is None when no budget is configured."""

    fraction: float | None
    warning: bool


class CostDashboard(BaseModel):
    cost_today_usd: float
    cost_yesterday_usd: float
    cost_this_month_usd: float
    cost_prev_month_usd: float
    avg_cost_per_conversation_usd: float | None
    conversation_count: int
    escalated_conversation_count: int
    escalation_rate: float | None
    daily_costs: list[DailyCost]
    monthly_budget_usd: float
    monthly_budget_used: BudgetUsage


class EvalCheck(BaseModel):
    metric: str
    value: float | None
    threshold: float
    passed: bool


class EvalRunSummary(BaseModel):
    run_type: str
    created_at: datetime
    git_sha: str
    metrics: dict[str, Any]
    checks: list[EvalCheck]
    passed: bool


class EvalDashboard(BaseModel):
    runs: list[EvalRunSummary]


@router.get("/costs", response_model=CostDashboard)
async def get_cost_dashboard(
    admin: Annotated[auth.AuthedTenantAdmin, Depends(auth.require_tenant_admin)],
) -> CostDashboard:
    return CostDashboard(
        **await controller.cost_dashboard(tenant_id=str(admin.tenant_id), role=admin.role)
    )


@router.get("/evals", response_model=EvalDashboard)
async def get_eval_dashboard(
    admin: Annotated[auth.AuthedTenantAdmin, Depends(auth.require_tenant_admin)],
) -> EvalDashboard:
    return EvalDashboard(
        **await controller.eval_dashboard(tenant_id=str(admin.tenant_id), role=admin.role)
    )
