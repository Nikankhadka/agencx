"""Shared tracing utilities for agent graph nodes (T-044, extracted from graph.py)."""

from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any

from langgraph.config import get_stream_writer
from langgraph.runtime import get_runtime

from app.agents.state import AgentState, GraphContext

logger = logging.getLogger("app.agents.graph")

_SPAN_ATTR_KEYS = (
    "route", "route_confidence", "route_reason", "price_gate_decision",
    "inspection_decision", "escalated", "escalation_reason", "draft_deterministic",
)

_PROGRESS_STAGES = {
    "supervisor": "routing", "agent": "routing", "draft": "answering",
    "conversation": "answering", "knowledge": "answering",
    "recommendation": "answering", "quoting": "quoting",
    "order_status": "answering", "escalation": "escalating",
    "inspection": "checking", "price_gate": "checking",
}


def _span_attrs(result: dict[str, Any]) -> dict[str, Any]:
    attrs = {key: result[key] for key in _SPAN_ATTR_KEYS if key in result}
    if "retrieved_chunks" in result:
        attrs["chunks"] = len(result["retrieved_chunks"])
    if "selections" in result:
        attrs["selections"] = len(result["selections"])
    if "inspection" in result and result["inspection"]:
        for check, verdict in result["inspection"].items():
            attrs[f"inspection_{check}"] = verdict.get("passed")
    return attrs


def traced(name: str, node: Callable[[AgentState], Awaitable[dict[str, Any]]]) -> Any:
    async def wrapped(state: AgentState) -> dict[str, Any]:
        turn = get_runtime(GraphContext).context.turn
        stage = _PROGRESS_STAGES.get(name)
        if stage is not None:
            get_stream_writer()({"type": "progress", "stage": stage})
        started = time.perf_counter()
        with turn.span(name) as span:
            result = await node(state)
            duration_ms = round((time.perf_counter() - started) * 1000, 1)
            attrs = _span_attrs(result)
            span.set(**attrs, duration_ms=duration_ms)
            logger.info(
                "agent node",
                extra={"node": name, "duration_ms": duration_ms,
                       "route": result.get("route", state.get("route"))},
            )
            return result
    return wrapped
