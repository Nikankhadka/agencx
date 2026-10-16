"""Slice 1 (latency): the noise-floor and matrix report from run artifacts.

Reads the committed JSON under the evidence folder and writes two markdown
tables beside them (``noise-floor.md``, ``matrix.md``). Percentiles use the same
linear-interpolation rule as ``app/observability/percentile.py``.

A turn that never let prose out (the turn budget fired, or the path escalated
before a draft) is counted as ``budget``, not silently averaged into the
percentiles - only completed turns feed p50/p95.

Usage::

    python -m evals.latency_report --data /evidence/data
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from app.observability.percentile import percentile

_TIME_METRICS = ("total_ms", "first_model_token_ms", "buffer_hold_ms")
# Metrics carried as per-turn numbers in the same p50/p95/delta shape.
_ALL_METRICS = (*_TIME_METRICS, "llm_call_count", "tokens")


def _load(path: Path) -> dict[str, Any]:
    with path.open() as fh:
        data: dict[str, Any] = json.load(fh)
    return data


def _records(artifact: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        turn["record"]
        for turn in artifact.get("turns", [])
        if isinstance(turn.get("record"), dict)
    ]


def _p(values: list[float], p: float) -> float | None:
    return percentile(values, p) if values else None


def _fmt(value: float | None, digits: int = 1) -> str:
    return "-" if value is None else f"{value:.{digits}f}"


def _per_turn_metric(record: dict[str, Any], metric: str) -> float | None:
    if metric == "tokens":
        return float(record["input_tokens"]) + float(record["output_tokens"])
    if metric == "llm_call_count":
        return float(record["llm_call_count"])
    value = record.get(metric)
    return None if value is None else float(value)


def _metric_stats(artifact: dict[str, Any], metric: str) -> dict[str, float | None]:
    """p50/p95 over completed turns (prose reached the customer)."""
    completed = [r for r in _records(artifact) if r["first_prose_ms"] is not None]
    values = [
        v for v in (_per_turn_metric(r, metric) for r in completed) if v is not None
    ]
    return {"p50": _p(values, 50), "p95": _p(values, 95)}


def _summary(artifact: dict[str, Any]) -> dict[str, Any]:
    records = _records(artifact)
    completed = [r for r in records if r["first_prose_ms"] is not None]
    tokens = [float(r["input_tokens"]) + float(r["output_tokens"]) for r in records]
    pricing = artifact.get("provider_pricing")
    cost: float | None = None
    if isinstance(pricing, dict) and pricing.get("prompt") and pricing.get("completion"):
        cost = round(
            sum(float(r["input_tokens"]) for r in records) * float(pricing["prompt"])
            + sum(float(r["output_tokens"]) for r in records) * float(pricing["completion"]),
            6,
        )
    return {
        "label": artifact["model"]["label"],
        "tenant": artifact["tenant"],
        "command": artifact.get("command"),
        "generated_at": artifact.get("generated_at"),
        "turns": len(records),
        "completed": len(completed),
        "budget": len(records) - len(completed),
        "metrics": {metric: _metric_stats(artifact, metric) for metric in _ALL_METRICS},
        "paths": sorted({str(r["path"]) for r in records if r["path"]}),
        "observed_calls": sorted({int(r["llm_call_count"]) for r in completed}),
        "expected_path": artifact.get("expected_path"),
        "expected_calls": artifact.get("expected_llm_calls"),
        "input_tokens": int(sum(float(r["input_tokens"]) for r in records)),
        "output_tokens": int(sum(float(r["output_tokens"]) for r in records)),
        "tokens_mean": round(sum(tokens) / len(tokens), 1) if tokens else None,
        "cost_usd": cost,
        "model_match": all(bool(t.get("model_match")) for t in artifact.get("turns", [])),
        "failover": any(bool(r["failover_engaged"]) for r in records),
    }


def _artifact_pair(run: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {art["tenant"]: art for art in run["artifacts"]}


def _noise_markdown(
    run1: dict[str, Any], run2: dict[str, Any], generated: str
) -> str:
    a1 = _artifact_pair(run1)
    a2 = _artifact_pair(run2)
    tenants = [t for t in a1 if t in a2]
    lines = [
        "# Noise floor (two runs of unchanged code)",
        "",
        f"Run 1: `{run1['command']}`",
        "",
        f"Run 2: `{run2['command']}`",
        "",
        f"Generated: {generated}",
        "",
    ]
    deltas: dict[str, dict[str, float]] = {}
    for tenant in tenants:
        s1 = _summary(a1[tenant])
        s2 = _summary(a2[tenant])
        lines += [
            f"## {tenant}",
            "",
            "| metric | run1 p50 | run1 p95 | run2 p50 | run2 p95 "
            "| abs delta p50 | abs delta p95 |",
            "|---|---|---|---|---|---|---|",
        ]
        for metric in _ALL_METRICS:
            m1 = s1["metrics"][metric]
            m2 = s2["metrics"][metric]
            d50 = abs((m1["p50"] or 0.0) - (m2["p50"] or 0.0))
            d95 = abs((m1["p95"] or 0.0) - (m2["p95"] or 0.0))
            lines.append(
                f"| {metric} | {_fmt(m1['p50'], 2)} | {_fmt(m1['p95'], 2)} "
                f"| {_fmt(m2['p50'], 2)} | {_fmt(m2['p95'], 2)} "
                f"| {d50:.2f} | {d95:.2f} |"
            )
            deltas.setdefault(metric, {})
            deltas[metric][tenant] = max(d50, d95)
        lines += [
            "",
            f"Completed {s1['completed']}/{s1['turns']} (run 1), "
            f"{s2['completed']}/{s2['turns']} (run 2); budget/escalation turns "
            f"{s1['budget']} and {s2['budget']}. Paths {s1['paths']}.",
            "",
        ]
    lines += [
        "## Tolerance rule",
        "",
        "Movement counts as real only when it exceeds the measured run-to-run "
        "spread. Concretely, for a metric and tenant below, the threshold is the "
        "larger of the two runs' p50 and p95 absolute deltas (the max column):",
        "",
        "| metric | " + " | ".join(tenants) + " |",
        "|---" * (len(tenants) + 1) + "|",
    ]
    for metric in _ALL_METRICS:
        cells = " | ".join(f"{deltas[metric][t]:.2f}" for t in tenants)
        lines.append(f"| {metric} | {cells} |")
    lines += [
        "",
        "A later slice's metric change on a tenant+config counts as a real "
        "improvement only when it exceeds that metric's threshold above; "
        "anything inside the band is noise and must not be claimed.",
        "",
    ]
    return "\n".join(lines)


def _matrix_markdown(mt: list[dict[str, Any]], generated: str) -> str:
    lines = [
        "# Model matrix (one row per model x tenant)",
        "",
        f"Generated: {generated}. Percentiles are over completed turns only; "
        "`budget` turns are the turn-budget (or pre-draft escalation) count.",
        "",
        "| model | tenant | path (obs) | exp path | turns | budget | p50 total_ms | "
        "p95 total_ms | p50 first_tok | p50 buffer | calls (obs set) | exp calls | "
        "in/out tok | cost usd | model_match | failover |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for s in mt:
        m = s["metrics"]
        lines.append(
            f"| {s['label']} | {s['tenant']} | {','.join(s['paths']) or '-'} "
            f"| {s['expected_path']} | {s['turns']} | {s['budget']} "
            f"| {_fmt(m['total_ms']['p50'])} | {_fmt(m['total_ms']['p95'])} "
            f"| {_fmt(m['first_model_token_ms']['p50'])} | {_fmt(m['buffer_hold_ms']['p50'])} "
            f"| {s['observed_calls']} | {s['expected_calls']} "
            f"| {s['input_tokens']}/{s['output_tokens']} | {_fmt(s['cost_usd'], 6)} "
            f"| {s['model_match']} | {s['failover']} |"
        )
    lines.append("")
    lines.append("## Provenance")
    lines.append("")
    for s in mt:
        lines.append(f"- {s['label']} x {s['tenant']}: `{s['command']}` at {s['generated_at']}")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else "")
    parser.add_argument("--data", default="/evidence/data")
    args = parser.parse_args()
    data = Path(args.data)

    run1 = _load(data / "noise-run1.json")
    run2 = _load(data / "noise-run2.json")
    generated = str(run1["artifacts"][0].get("generated_at") or "")
    (data / "noise-floor.md").write_text(_noise_markdown(run1, run2, generated))

    matrix = [_load(path) for path in sorted(data.glob("matrix-*.json"))]
    summaries = sorted(
        (_summary(art) for art in matrix), key=lambda s: (s["label"], s["tenant"])
    )
    (data / "matrix.md").write_text(_matrix_markdown(summaries, generated))

    for s in summaries:
        m = s["metrics"]["total_ms"]
        print(
            f"{s['label']} {s['tenant']}: completed {s['completed']}/{s['turns']} "
            f"p50={_fmt(m['p50'])} p95={_fmt(m['p95'])} calls={s['observed_calls']} "
            f"cost=${_fmt(s['cost_usd'], 6)} match={s['model_match']}"
        )
    print(f"wrote {data / 'noise-floor.md'} and {data / 'matrix.md'}")


if __name__ == "__main__":
    main()
