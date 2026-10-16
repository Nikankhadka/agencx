"""Slice 1 (latency): the per-turn record.

Pins the exact key set (one definition, ``turn_record.RECORD_KEYS``), the
accumulation of the cross-module measures, the single-log-line emission the
runner taps, and that the route vocabulary tracks the graph's own routes.
"""

from __future__ import annotations

import ast
import inspect
import logging
import textwrap

import pytest

from app.agents import agent_node
from app.observability.turn_record import (
    _ROUTE_VOCABULARY,
    RECORD_KEYS,
    TurnRecord,
    build_record,
    collect_turn_record,
    emit_turn_record,
    record_path,
    record_retrieval,
    record_route,
)


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
    assert set(record) == RECORD_KEYS
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
    assert set(record) == RECORD_KEYS
    assert record["llm_call_count"] == 2
    assert record["buffer_hold_ms"] == 400.0


def _routes_returned_by_the_decision_point() -> set[str]:
    """Every string literal ``agent_node._determine_route`` returns, read from
    its source so a new route cannot hide behind a branch the test does not
    call directly."""
    source = textwrap.dedent(inspect.getsource(agent_node._determine_route))
    tree = ast.parse(source)
    return {
        node.value.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Return)
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
    }


def test_route_vocabulary_tracks_the_graphs_routes() -> None:
    """``record.route`` is nulled for any value outside its vocabulary, so the
    vocabulary must equal the routes the graph's decision point can return (plus
    the ``structured`` card value). Adding a route to
    ``agent_node._determine_route`` without updating ``_ROUTE_VOCABULARY`` fails
    here instead of silently nulling the record's route."""
    returned = _routes_returned_by_the_decision_point()
    assert returned, "expected _determine_route to return route literals"
    assert returned <= _ROUTE_VOCABULARY
    assert _ROUTE_VOCABULARY == returned | {"structured"}
