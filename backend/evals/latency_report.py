"""Slice 1 (latency): the noise-floor and matrix report from run artifacts.

Reads the committed JSON under the evidence folder and writes two markdown
tables beside them (``noise-floor.md``, ``matrix.md``). Percentiles use the same
linear-interpolation rule as ``app/observability/percentile.py``.

A turn that never let prose out (the turn budget fired, or the path escalated
before a draft) is counted as ``budget``, not silently averaged into the
percentiles - only completed turns feed p50/p95. A delta is rendered ``-`` when
either side has no completed sample, never as the other side's value. The calls
column reports the set over ALL turns, so exclusion cannot make it read as "no
calls". ``model_match`` ignores turns without a verdict (an error turn) and
reports their count instead of reading them as a mismatch.

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
        turn["record"] for turn in artifact.get("turns", []) if isinstance(turn.get("record"), dict)
    ]


def _p(values: list[float], p: float) -> float | None:
    return percentile(values, p) if values else None


def _fmt(value: float | None, digits: int = 1) -> str:
    return "-" if value is None else f"{value:.{digits}f}"


def _delta(a: float | None, b: float | None) -> float | None:
    """Absolute difference, or ``None`` when either side has no sample - a delta
    from an empty sample is undefined, never the other side's value."""
    return None if a is None or b is None else abs(a - b)


def _max_delta(*deltas: float | None) -> float | None:
    present = [d for d in deltas if d is not None]
    return max(present) if present else None


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
    values = [v for v in (_per_turn_metric(r, metric) for r in completed) if v is not None]
    return {"p50": _p(values, 50), "p95": _p(values, 95)}


def _summary(artifact: dict[str, Any]) -> dict[str, Any]:
    turns = artifact.get("turns", [])
    records = _records(artifact)
    completed = [r for r in records if r["first_prose_ms"] is not None]
    # A turn with no model_match verdict (an error turn) is not a mismatch: it
    # is excluded from the verdict and counted separately.
    matched = [bool(t["model_match"]) for t in turns if "model_match" in t]
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
        # The set over every turn, so an excluded turn's calls still show.
        "all_calls": sorted({int(r["llm_call_count"]) for r in records}),
        "completed_routes": sorted({str(r["route"]) for r in completed if r["route"]}),
        "expected_path": artifact.get("expected_path"),
        "expected_calls": artifact.get("expected_llm_calls"),
        "input_tokens": int(sum(float(r["input_tokens"]) for r in records)),
        "output_tokens": int(sum(float(r["output_tokens"]) for r in records)),
        "cost_usd": cost,
        "model_match": all(matched) if matched else None,
        "error_turns": sum(1 for t in turns if "error" in t),
        "failover": any(bool(r["failover_engaged"]) for r in records),
    }


def _model_match_cell(summary: dict[str, Any]) -> str:
    verdict = summary["model_match"]
    base = "n/a" if verdict is None else str(verdict)
    return f"{base} ({summary['error_turns']} err)" if summary["error_turns"] else base


def _artifact_map(run: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    """Key by (model label, tenant): a file carrying two models for one tenant
    cannot silently collapse onto one key."""
    return {(art["model"]["label"], art["tenant"]): art for art in run["artifacts"]}


def _noise_markdown(run1: dict[str, Any], run2: dict[str, Any], generated: str) -> str:
    a1 = _artifact_map(run1)
    a2 = _artifact_map(run2)
    keys = [key for key in a1 if key in a2]
    multi = len({label for label, _ in keys}) > 1

    def name(key: tuple[str, str]) -> str:
        label, tenant = key
        return f"{label} x {tenant}" if multi else tenant

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
    deltas: dict[str, dict[tuple[str, str], float | None]] = {}
    for key in keys:
        s1 = _summary(a1[key])
        s2 = _summary(a2[key])
        lines += [
            f"## {name(key)}",
            "",
            "| metric | run1 p50 | run1 p95 | run2 p50 | run2 p95 "
            "| abs delta p50 | abs delta p95 |",
            "|---|---|---|---|---|---|---|",
        ]
        for metric in _ALL_METRICS:
            m1 = s1["metrics"][metric]
            m2 = s2["metrics"][metric]
            d50 = _delta(m1["p50"], m2["p50"])
            d95 = _delta(m1["p95"], m2["p95"])
            lines.append(
                f"| {metric} | {_fmt(m1['p50'], 2)} | {_fmt(m1['p95'], 2)} "
                f"| {_fmt(m2['p50'], 2)} | {_fmt(m2['p95'], 2)} "
                f"| {_fmt(d50, 2)} | {_fmt(d95, 2)} |"
            )
            deltas.setdefault(metric, {})
            deltas[metric][key] = _max_delta(d50, d95)
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
        "larger of the two runs' p50 and p95 absolute deltas (the max column); "
        "`-` means a run had no completed sample to compare.",
        "",
        "| metric | " + " | ".join(name(key) for key in keys) + " |",
        "|---" * (len(keys) + 1) + "|",
    ]
    for metric in _ALL_METRICS:
        cells = " | ".join(_fmt(deltas[metric][key], 2) for key in keys)
        lines.append(f"| {metric} | {cells} |")
    lines += [
        "",
        "A later slice's metric change on a tenant+config counts as a real "
        "improvement only when it exceeds that metric's threshold above; "
        "anything inside the band is noise and must not be claimed.",
        "",
    ]
    return "\n".join(lines)


def _comparability_notes(summaries: list[dict[str, Any]]) -> list[str]:
    lines = [
        "## Comparability note",
        "",
        "A completed turn's route varies, and a catalog-card turn "
        "(`route: structured`) answers from the inline catalog with no draft "
        "call - its `total_ms` and `buffer_hold_ms` are not comparable to a "
        "drafted-answer turn. A row's p50/p95 mixes whatever routes completed, "
        "so read the routes before comparing two models.",
        "",
    ]
    for s in summaries:
        if s["completed"] == 0:
            lines.append(
                f"- {s['label']} x {s['tenant']}: no completed turns; p50/p95 "
                "are unavailable (every turn hit the turn budget)."
            )
        elif s["completed_routes"] == ["structured"]:
            lines.append(
                f"- {s['label']} x {s['tenant']}: all {s['completed']} completed "
                "turns are card turns (route `structured`) - not comparable to a "
                "drafted-answer row."
            )
    lines.append("")
    return lines


def _matrix_markdown(mt: list[dict[str, Any]], generated: str) -> str:
    lines = [
        "# Model matrix (one row per model x tenant)",
        "",
        f"Generated: {generated}. Percentiles are over completed turns only; "
        "`budget` turns are the turn-budget (or pre-draft escalation) count, and "
        "the calls column is the set over all turns.",
        "",
        "| model | tenant | path (obs) | exp path | turns | budget | p50 total_ms | "
        "p95 total_ms | p50 first_tok | p50 buffer | calls (all turns) | exp calls | "
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
            f"| {s['all_calls']} | {s['expected_calls']} "
            f"| {s['input_tokens']}/{s['output_tokens']} | {_fmt(s['cost_usd'], 6)} "
            f"| {_model_match_cell(s)} | {s['failover']} |"
        )
    lines.append("")
    lines += _comparability_notes(mt)
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
    summaries = sorted((_summary(art) for art in matrix), key=lambda s: (s["label"], s["tenant"]))
    (data / "matrix.md").write_text(_matrix_markdown(summaries, generated))

    for s in summaries:
        m = s["metrics"]["total_ms"]
        print(
            f"{s['label']} {s['tenant']}: completed {s['completed']}/{s['turns']} "
            f"p50={_fmt(m['p50'])} p95={_fmt(m['p95'])} calls={s['all_calls']} "
            f"cost=${_fmt(s['cost_usd'], 6)} match={_model_match_cell(s)}"
        )
    print(f"wrote {data / 'noise-floor.md'} and {data / 'matrix.md'}")


if __name__ == "__main__":
    main()
