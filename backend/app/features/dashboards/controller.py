"""Dashboards handlers: shape cost/volume and eval-run rows into the API.

Handler logic that moved out of api/dashboards.py. Persistence and the
GATE_THRESHOLDS contract live in service.py; this layer rehydrates jsonb
columns, computes check verdicts against the thresholds, and builds the
response dicts api.py validates into its models.
"""

from __future__ import annotations

import json
from typing import Any

from app.features.dashboards import service


async def cost_dashboard(*, tenant_id: str) -> dict[str, Any]:
    return await service.cost_dashboard(tenant_id=tenant_id)


async def eval_dashboard(*, tenant_id: str) -> dict[str, Any]:
    """Rehydrate the latest eval runs against GATE_THRESHOLDS into the
    run/check shape consumed by the frontend."""
    runs: list[dict[str, Any]] = []
    for row in await service.eval_runs(tenant_id=tenant_id):
        run_type = row["run_type"]
        metrics = json.loads(row["metrics"])
        checks: list[dict[str, Any]] = []
        for metric_name, threshold in service.GATE_THRESHOLDS[run_type].items():
            raw_value = metrics.get(metric_name)
            value = float(raw_value) if isinstance(raw_value, (int, float)) else None
            checks.append(
                {
                    "metric": metric_name,
                    "value": value,
                    "threshold": threshold,
                    # Missing/non-numeric metric fails closed, matching
                    # run_gate.regression_pass's treatment of an absent metric.
                    "passed": value is not None and value >= threshold,
                }
            )
        runs.append(
            {
                "run_type": run_type,
                "created_at": row["created_at"],
                "git_sha": row["git_sha"],
                "metrics": metrics,
                "checks": checks,
                "passed": all(check["passed"] for check in checks),
            }
        )
    return {"runs": runs}
