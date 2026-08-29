"""Dashboards persistence: cost/volume metrics + latest eval runs.

Moved from api/dashboards.py. The threshold constants below are mirrored from
evals/*.py's own gate constants (RECALL_AT_5_GATE, FAITHFULNESS_GATE, etc.) -
app/ deliberately does not import evals/ at runtime (evals/ imports app/,
never the reverse, everywhere else in this codebase). test_dashboards_api.py's
threshold-sync test keeps the two from drifting apart. Note these are each
eval's own absolute target, not necessarily what CI's regression gate checks
for generation/trajectory/injection (run_gate.py gates those three against the
previous run, not the absolute number, since an LLM-judged score depends on
which model answered).

A real tenant provisioned through onboarding will typically have ZERO eval_runs
rows - evals run in CI against seeded/scratch tenants (bytefix, throwaway
leakage/injection probes), not automatically against every tenant. An empty
eval section is the common case, not an edge case.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from app.shared import db
from app.shared.config import get_settings

_DAILY_SERIES_DAYS = 30

# Mirrored from evals/*.py - see module docstring.
GATE_THRESHOLDS: dict[str, dict[str, float]] = {
    "retrieval": {"recall_at_5": 0.85},  # retrieval_eval.RECALL_AT_5_GATE
    "generation": {
        "faithfulness": 0.85,  # generation_eval.FAITHFULNESS_GATE
        "answer_relevancy": 0.85,  # generation_eval.RELEVANCY_GATE
    },
    "trajectory": {"tool_correctness": 0.90},  # trajectory_eval.TOOL_CORRECTNESS_GATE
    "injection": {"pass_rate": 0.80},  # injection_eval.PASS_GATE
    "leakage": {"pass_rate": 1.0},  # zero-tolerance
}


async def cost_dashboard(*, tenant_id: str, role: str = "tenant_admin") -> dict[str, Any]:
    """Cost + volume aggregates and the last-30-days series for the tenant."""
    now = datetime.now(UTC)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday_start = today_start - timedelta(days=1)
    month_start = today_start.replace(day=1)
    prev_month_start = (month_start - timedelta(days=1)).replace(day=1)
    series_start = today_start - timedelta(days=_DAILY_SERIES_DAYS - 1)

    async with db.tenant_context(tenant_id, role) as conn:
        cost_row = await conn.fetchrow(
            "select "
            "  coalesce(sum(cost_usd) filter (where created_at >= $2), 0) as cost_today, "
            "  coalesce(sum(cost_usd) filter ("
            "    where created_at >= $3 and created_at < $2), 0) as cost_yesterday, "
            "  coalesce(sum(cost_usd) filter (where created_at >= $4), 0) as cost_this_month, "
            "  coalesce(sum(cost_usd) filter ("
            "    where created_at >= $5 and created_at < $4), 0) as cost_prev_month, "
            "  coalesce(sum(cost_usd) filter ("
            "    where conversation_id is not null), 0) as conv_cost_total, "
            "  count(distinct conversation_id) filter ("
            "    where conversation_id is not null) as costed_conversations "
            "from cost_logs where tenant_id = $1",
            tenant_id,
            today_start,
            yesterday_start,
            month_start,
            prev_month_start,
        )
        assert cost_row is not None

        volume_row = await conn.fetchrow(
            "select "
            "  (select count(*) from conversations where tenant_id = $1) as conversation_count, "
            "  (select count(distinct conversation_id) from escalations "
            "   where tenant_id = $1) as escalated_conversations",
            tenant_id,
        )
        assert volume_row is not None

        daily_rows = await conn.fetch(
            "select (created_at at time zone 'utc')::date as day, sum(cost_usd) as cost_usd "
            "from cost_logs where tenant_id = $1 and created_at >= $2 "
            "group by 1 order by 1",
            tenant_id,
            series_start,
        )

    costed_conversations = cost_row["costed_conversations"]
    avg_cost = (
        float(cost_row["conv_cost_total"]) / costed_conversations
        if costed_conversations > 0
        else None
    )
    conversation_count = volume_row["conversation_count"]
    escalated_count = volume_row["escalated_conversations"]
    escalation_rate = escalated_count / conversation_count if conversation_count > 0 else None

    by_day = {row["day"]: float(row["cost_usd"]) for row in daily_rows}
    daily_costs = [
        {"day": day, "cost_usd": by_day.get(day, 0.0)}
        for day in ((series_start + timedelta(days=i)).date() for i in range(_DAILY_SERIES_DAYS))
    ]

    cost_this_month = float(cost_row["cost_this_month"])
    budget = get_settings().llm_monthly_budget_usd

    return {
        "cost_today_usd": float(cost_row["cost_today"]),
        "cost_yesterday_usd": float(cost_row["cost_yesterday"]),
        "cost_this_month_usd": cost_this_month,
        "cost_prev_month_usd": float(cost_row["cost_prev_month"]),
        "avg_cost_per_conversation_usd": avg_cost,
        "conversation_count": conversation_count,
        "escalated_conversation_count": escalated_count,
        "escalation_rate": escalation_rate,
        "daily_costs": daily_costs,
        "monthly_budget_usd": budget,
        "monthly_budget_used": budget_usage(cost_this_month, budget),
    }


# P-1 US-3: the $10/month testing ceiling stops being a hope the moment the
# number is on the same screen as the spend. Warning fires at 80% so there is
# room to react, not a post-mortem.
BUDGET_WARNING_FRACTION = 0.8


def budget_usage(spent_usd: float, budget_usd: float) -> dict[str, Any]:
    """Fraction of the monthly budget spent, and whether that is worth flagging."""
    if budget_usd <= 0:
        return {"fraction": None, "warning": False}
    fraction = spent_usd / budget_usd
    return {
        "fraction": round(fraction, 4),
        "warning": fraction >= BUDGET_WARNING_FRACTION,
    }


async def eval_runs(*, tenant_id: str, role: str = "tenant_admin") -> list[dict[str, Any]]:
    """The latest eval_runs row per configured run_type."""
    async with db.tenant_context(tenant_id, role) as conn:
        rows = await conn.fetch(
            "select distinct on (run_type) run_type, metrics, git_sha, created_at "
            "from eval_runs where tenant_id = $1 "
            "  and run_type = any($2::text[]) "
            "order by run_type, created_at desc",
            tenant_id,
            list(GATE_THRESHOLDS.keys()),
        )
    return [dict(row) for row in rows]
