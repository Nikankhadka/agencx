"""Slice 1 (latency): the per-turn record.

Pins the exact key set, the accumulation of the cross-module measures, and the
single-log-line emission the runner taps.
"""

from __future__ import annotations

import logging

import pytest

from app.observability.turn_record import (
    TurnRecord,
    build_record,
    collect_turn_record,
    emit_turn_record,
    record_path,
    record_retrieval,
    record_route,
)

# The exact keys the record must always carry (plan of record 13-latency).
EXPECTED_KEYS = {
    "total_ms",
    "first_model_token_ms",
    "first_prose_ms",
    "buffer_hold_ms",
    "embed_ms",
    "search_ms",
    "rerank_ms",
    "path",
    "llm_call_count",
    "input_tokens",
    "output_tokens",
    "leg",
    "failover_engaged",
    "route",
}


def test_record_always_carries_exactly_the_required_keys() -> None:
    record = build_record(
        TurnRecord(),
        total_ms=1.0,
        first_model_token_ms=None,
        first_prose_ms=None,
        buffer_hold_ms=None,
        llm_call_count=0,
        input_tokens=0,
        output_tokens=0,
        leg=None,
        failover_engaged=False,
    )
    assert set(record) == EXPECTED_KEYS
    assert record["path"] is None
    assert record["embed_ms"] is None
    assert record["leg"] is None
    assert record["failover_engaged"] is False


def test_sink_collects_component_measures_and_totals_retrieval() -> None:
    with collect_turn_record() as record:
        record_path("hybrid")
        record_retrieval(embed_ms=1.0, search_ms=2.0, rerank_ms=3.0)
        # A second pass (a redraft) adds its stage timings; a stage not run
        # contributes nothing.
        record_retrieval(embed_ms=0.5, search_ms=None, rerank_ms=1.0)
        record_route("knowledge")
        # First write wins, so a later node's route cannot clobber the decided
        # one; a value outside the vocabulary is ignored.
        record_route("quoting")
        record_route("not-a-route")
        record_route(None)
    assert record.path == "hybrid"
    assert record.embed_ms == 1.5
    assert record.search_ms == 2.0
    assert record.rerank_ms == 4.0
    assert record.route == "knowledge"


def test_measures_drop_silently_without_a_sink() -> None:
    # No collector open (an eval, a non-chat caller): these must not raise.
    record_path("fast")
    record_retrieval(embed_ms=1.0, search_ms=1.0, rerank_ms=1.0)
    record_route("knowledge")


def test_emit_logs_one_line_keyed_to_the_turn(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO, logger="app.latency"):
        payload = emit_turn_record(
            TurnRecord(path="fast", route="knowledge"),
            tenant_id="tenant-1",
            conversation_id="conversation-1",
            usage_models=["deepseek/deepseek-v4.1-flash", "deepseek/deepseek-v4.1-flash"],
            total_ms=1234.5,
            first_model_token_ms=400.0,
            first_prose_ms=800.0,
            buffer_hold_ms=400.0,
            llm_call_count=2,
            input_tokens=1000,
            output_tokens=200,
            leg="primary",
            failover_engaged=False,
        )
    lines = [r for r in caplog.records if r.name == "app.latency"]
    assert len(lines) == 1
    assert vars(lines[0]).get("latency_turn") == payload
    assert payload["tenant_id"] == "tenant-1"
    assert payload["conversation_id"] == "conversation-1"
    # Distinct models only, sorted.
    assert payload["usage_models"] == ["deepseek/deepseek-v4.1-flash"]
    record = payload["record"]
    assert isinstance(record, dict)
    assert set(record) == EXPECTED_KEYS
    assert record["llm_call_count"] == 2
    assert record["buffer_hold_ms"] == 400.0
