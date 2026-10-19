"""Slice 1 (latency): the noise-floor and matrix tabulator.

Small in-memory fixtures pin the behaviours a later slice must be able to trust:
the budget-turn exclusion policy, the percentile pass-through, the
empty-sample delta rendering, and the all-turn calls column.
"""

from __future__ import annotations

from typing import Any

import pytest

from evals import latency_report


def _record(**overrides: Any) -> dict[str, Any]:
    record: dict[str, Any] = {
        "total_ms": 1000.0,
        "first_model_token_ms": 100.0,
        "first_prose_ms": 900.0,  # non-null means prose reached the customer
        "buffer_hold_ms": 800.0,
        "embed_ms": None,
        "search_ms": None,
        "rerank_ms": None,
        "path": "fast",
        "llm_call_count": 2,
        "input_tokens": 10,
        "output_tokens": 5,
        "cached_input_tokens": 4,
        "leg": None,
        "failover_engaged": False,
        "route": "knowledge",
    }
    record.update(overrides)
    return record


def _turn(record: dict[str, Any], *, model_match: bool = True) -> dict[str, Any]:
    return {"record": record, "model_match": model_match}


def _budget_turn(*, calls: int = 1) -> dict[str, Any]:
    # A budget turn let no prose out and made fewer calls than a completed one.
    return _turn(
        _record(total_ms=10000.0, first_prose_ms=None, buffer_hold_ms=None, llm_call_count=calls)
    )


def _artifact(*turns: dict[str, Any], tenant: str = "t1", label: str = "m") -> dict[str, Any]:
    return {
        "model": {"label": label, "api_model": label},
        "tenant": tenant,
        "turns": list(turns),
        "provider_pricing": {"prompt": "0.000001", "completion": "0.000002"},
        "command": "make latency",
        "generated_at": "2026-01-01T00:00:00Z",
    }


def _run(*artifacts: dict[str, Any]) -> dict[str, Any]:
    return {"run": "r", "command": "make latency", "artifacts": list(artifacts)}


def _metric_rows(markdown: str, metric: str) -> list[list[str]]:
    return [
        [cell.strip() for cell in line.split("|")[1:-1]]
        for line in markdown.splitlines()
        if line.startswith(f"| {metric} |")
    ]


def test_budget_turns_are_excluded_from_percentiles_and_counted() -> None:
    artifact = _artifact(_turn(_record(total_ms=1000.0)), _budget_turn())
    summary = latency_report._summary(artifact)
    assert summary["turns"] == 2
    assert summary["completed"] == 1
    assert summary["budget"] == 1
    # The budget turn's 10000ms must not enter the percentile.
    assert summary["metrics"]["total_ms"]["p50"] == 1000.0
    assert summary["metrics"]["total_ms"]["p95"] == 1000.0


def test_percentile_passes_through_the_shared_rule() -> None:
    artifact = _artifact(
        _turn(_record(total_ms=1000.0)),
        _turn(_record(total_ms=2000.0)),
        _turn(_record(total_ms=3000.0)),
    )
    summary = latency_report._summary(artifact)
    assert summary["metrics"]["total_ms"]["p50"] == pytest.approx(2000.0)
    # Linear interpolation: rank = 2*0.95 = 1.9 -> 2000 + 1000*0.9.
    assert summary["metrics"]["total_ms"]["p95"] == pytest.approx(2900.0)


def test_empty_sample_delta_renders_dash_not_the_other_runs_value() -> None:
    run1 = _run(_artifact(_turn(_record(total_ms=1000.0))))
    run2 = _run(_artifact(_budget_turn()))  # no completed turns
    markdown = latency_report._noise_markdown(run1, run2, "t")
    row = _metric_rows(markdown, "total_ms")[0]
    # metric | run1 p50 | run1 p95 | run2 p50 | run2 p95 | delta p50 | delta p95
    assert row[0] == "total_ms"
    assert row[1] == "1000.00"
    assert row[3] == "-" and row[4] == "-"  # run 2 has no sample
    assert row[5] == "-" and row[6] == "-"  # the delta is undefined, not 1000
    assert row[5] != "1000.00"


def test_calls_column_reports_the_all_turn_set() -> None:
    artifact = _artifact(_turn(_record(llm_call_count=2)), _budget_turn(calls=1))
    summary = latency_report._summary(artifact)
    assert summary["completed"] == 1
    # The budget turn made one call; the set must not read as an empty list.
    assert summary["all_calls"] == [1, 2]
    markdown = latency_report._matrix_markdown([summary], "t")
    row = next(line for line in markdown.splitlines() if line.startswith(f"| {summary['label']} |"))
    cells = [cell.strip() for cell in row.split("|")[1:-1]]
    calls_col = 10  # model, tenant, path, exp path, turns, budget, p50, p95, first, buffer, calls
    assert cells[calls_col] == "[1, 2]"
    assert "[]" not in row


def test_cached_input_tokens_are_summed_and_old_records_still_read() -> None:
    artifact = _artifact(
        _turn(_record(cached_input_tokens=750)),
        _turn(_record(cached_input_tokens=250)),
    )
    assert latency_report._summary(artifact)["cached_input_tokens"] == 1000

    # A committed slice-1/slice-4 artifact predates the key; the report must read
    # it as zero rather than raising.
    legacy = _artifact(_turn(_record()))
    legacy["turns"][0]["record"].pop("cached_input_tokens")
    assert latency_report._summary(legacy)["cached_input_tokens"] == 0


def test_matrix_reports_cached_tokens_without_moving_the_calls_column() -> None:
    summary = latency_report._summary(_artifact(_turn(_record(cached_input_tokens=750))))
    markdown = latency_report._matrix_markdown([summary], "t")
    header = next(line for line in markdown.splitlines() if line.startswith("| model |"))
    assert "cache tok" in header
    row = next(line for line in markdown.splitlines() if line.startswith(f"| {summary['label']} |"))
    cells = [cell.strip() for cell in row.split("|")[1:-1]]
    assert cells[10] == "[2]"  # calls column index is unchanged
    assert "750" in row


def test_model_match_ignores_error_turns_and_reports_their_count() -> None:
    artifact = _artifact(_turn(_record(), model_match=True), {"error": "boom"})
    summary = latency_report._summary(artifact)
    assert summary["model_match"] is True
    assert summary["error_turns"] == 1
    assert latency_report._model_match_cell(summary) == "True (1 err)"

    only_error = _artifact({"error": "boom"})
    error_summary = latency_report._summary(only_error)
    assert error_summary["model_match"] is None
    assert latency_report._model_match_cell(error_summary) == "n/a (1 err)"


def test_artifact_map_keys_by_model_and_tenant() -> None:
    run = _run(
        _artifact(_turn(_record()), tenant="t1", label="a"),
        _artifact(_turn(_record()), tenant="t1", label="b"),
    )
    mapping = latency_report._artifact_map(run)
    assert set(mapping) == {("a", "t1"), ("b", "t1")}
    # Two models on one tenant must not collapse the noise-floor headings.
    markdown = latency_report._noise_markdown(run, run, "t")
    assert "## a x t1" in markdown
    assert "## b x t1" in markdown
