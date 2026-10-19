"""Slice 1 (latency): the per-turn record.

A customer turn's latency is spread across the code that produces it:

- the chat controller owns ``total_ms``, the first-token/first-prose gap, and
  (via the existing sinks) the token counts and which provider leg answered;
- the two retrieval paths know ``embed_ms`` / ``search_ms`` / ``rerank_ms`` and
  the fast-versus-hybrid ``path``;
- the agent tracing wrapper knows the ``route``.

This module is the one place they meet. Components write the measures they own
into a per-turn accumulator; the controller reads it back and emits exactly one
record per graph turn as a single structured log line. The runner taps that
line. A turn that never reaches the graph (a terminal limit stop, a
human-handled reply, an escalated conversation) opens no sink and records
nothing - which is correct, because no model work happened.

It mirrors ``collect_usage`` (app/observability/cost.py) and ``collect_legs``
(app/llm/failover.py), and for the same reason: the graph runs in child tasks
that get a copy of the context, so only mutation of a *shared object* opened by
the turn is visible back to the turn that opened it.

The record carries exactly these keys, each always present and ``None`` where a
measure does not apply:

``total_ms``, ``first_model_token_ms``, ``first_prose_ms``, ``buffer_hold_ms``,
``embed_ms``, ``search_ms``, ``rerank_ms``, ``path``, ``llm_call_count``,
``input_tokens``, ``output_tokens``, ``cached_input_tokens``, ``leg``,
``failover_engaged``, ``route``.

``cached_input_tokens`` (slice 5) is the turn's total provider prompt-cache
reads - the signal that the stable prefix (see ``app/agents/spotlight.py``) is
actually being cached. It is a subset of ``input_tokens``, so it is
observability only, not an extra input count.

``llm_call_count`` is ``len(usages)`` - the number of provider calls that
reported token usage. One caveat: in a failover race both legs can complete
before the loser is cancelled, so a raced turn can report one more call than
the graph asked for. The record's ``leg`` and ``usage_models`` make that
visible rather than silent.

``usage_models`` carries the model each call's provider response named (the
**served** model, from the response body - see ``app/llm/openai_base.py``), not
the id that was requested, so a gateway that answers with a different model is
visible in the evidence. A provider whose response omits the model name reports
the configured id.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass

LATENCY_LOGGER_NAME = "app.latency"

_logger = logging.getLogger(LATENCY_LOGGER_NAME)

# The exact keys the per-turn record carries. One definition, referenced by
# ``build_record`` (whose literal must match it), the runner, and the tests.
RECORD_KEYS: frozenset[str] = frozenset(
    {
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
        "cached_input_tokens",
        "leg",
        "failover_engaged",
        "route",
    }
)


@dataclass
class TurnRecord:
    """The measures a turn's components write before the controller emits."""

    path: str | None = None
    route: str | None = None
    embed_ms: float | None = None
    search_ms: float | None = None
    rerank_ms: float | None = None

    def add_retrieval(
        self,
        *,
        embed_ms: float | None,
        search_ms: float | None,
        rerank_ms: float | None,
    ) -> None:
        """Add one retrieval's stage timings to the turn's totals.

        A turn can retrieve more than once (a redraft, or a recommendation
        pass after a knowledge pass), so the record reports the turn's total
        retrieval cost rather than one arbitrary pass. A stage not run in a
        pass contributes nothing.
        """
        self.embed_ms = _add(self.embed_ms, embed_ms)
        self.search_ms = _add(self.search_ms, search_ms)
        self.rerank_ms = _add(self.rerank_ms, rerank_ms)


def _add(total: float | None, value: float | None) -> float | None:
    if value is None:
        return total
    return value if total is None else round(total + value, 1)


# The route values the graph's decision point produces (``_determine_route`` in
# app/agents/agent_node.py, plus the "structured" value for a card response).
# A node's returned ``route`` is only accepted when it is one of these.
_ROUTE_VOCABULARY = frozenset(
    {
        "conversation",
        "knowledge",
        "recommendation",
        "quoting",
        "order_status",
        "escalation",
        "structured",
    }
)


_sink: ContextVar[TurnRecord | None] = ContextVar("_turn_record_sink", default=None)


@contextmanager
def collect_turn_record() -> Iterator[TurnRecord]:
    """Open a fresh accumulator for the duration of a turn. Nesting replaces
    the sink and restores the previous one (contextvars are task-local)."""
    record = TurnRecord()
    token = _sink.set(record)
    try:
        yield record
    finally:
        _sink.reset(token)


def _active() -> TurnRecord | None:
    return _sink.get()


def record_retrieval(
    *, embed_ms: float | None, search_ms: float | None, rerank_ms: float | None
) -> None:
    """Called by the retrieval entry point. No active sink (an eval, a test,
    a non-chat caller) means the measure is dropped."""
    record = _active()
    if record is not None:
        record.add_retrieval(embed_ms=embed_ms, search_ms=search_ms, rerank_ms=rerank_ms)


def record_path(path: str) -> None:
    """Which path produced the grounding material ('fast' or 'hybrid')."""
    record = _active()
    if record is not None:
        record.path = path


def record_route(route: str | None) -> None:
    """The turn's decided route, written by the agent tracing wrapper.

    First write wins, and only a value in ``_ROUTE_VOCABULARY`` is accepted.
    The graph's decision point (the ``agent`` node, always the first traced
    node) is the only node that returns a route today, so the first value is
    the decided one - last-write-wins would let a later node's incidental value
    clobber it. The vocabulary guard rejects anything a future node might
    return that is not one of the graph's routes.
    """
    record = _active()
    if record is None or record.route is not None or route not in _ROUTE_VOCABULARY:
        return
    record.route = route


def build_record(
    record: TurnRecord,
    *,
    total_ms: float,
    first_model_token_ms: float | None,
    first_prose_ms: float | None,
    buffer_hold_ms: float | None,
    llm_call_count: int,
    input_tokens: int,
    output_tokens: int,
    leg: str | None,
    failover_engaged: bool,
    cached_input_tokens: int = 0,
) -> dict[str, object]:
    """The exact 15-key record. Every key is present; ``None`` is a measure
    that did not apply (a deterministic turn writes no prose; the fast path
    embeds and reranks nothing). ``cached_input_tokens`` defaults to 0 so a
    caller that does not collect it still produces a complete record."""
    return {
        "total_ms": total_ms,
        "first_model_token_ms": first_model_token_ms,
        "first_prose_ms": first_prose_ms,
        "buffer_hold_ms": buffer_hold_ms,
        "embed_ms": record.embed_ms,
        "search_ms": record.search_ms,
        "rerank_ms": record.rerank_ms,
        "path": record.path,
        "llm_call_count": llm_call_count,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cached_input_tokens": cached_input_tokens,
        "leg": leg,
        "failover_engaged": failover_engaged,
        "route": record.route,
    }


def emit_turn_record(
    record: TurnRecord,
    *,
    tenant_id: str,
    conversation_id: str,
    usage_models: Sequence[str],
    total_ms: float,
    first_model_token_ms: float | None,
    first_prose_ms: float | None,
    buffer_hold_ms: float | None,
    llm_call_count: int,
    input_tokens: int,
    output_tokens: int,
    leg: str | None,
    failover_engaged: bool,
    cached_input_tokens: int = 0,
) -> dict[str, object]:
    """Emit one record for the turn as a single structured log line, and
    return the payload so an in-process caller can also read it directly.

    The line is on ``app.latency`` and keyed to the tenant and conversation;
    ``usage_models`` names the served model of every call that reported usage,
    so a turn served by an unexpected model is visible in the evidence rather
    than averaged in.
    """
    payload: dict[str, object] = {
        "record": build_record(
            record,
            total_ms=total_ms,
            first_model_token_ms=first_model_token_ms,
            first_prose_ms=first_prose_ms,
            buffer_hold_ms=buffer_hold_ms,
            llm_call_count=llm_call_count,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            leg=leg,
            failover_engaged=failover_engaged,
            cached_input_tokens=cached_input_tokens,
        ),
        "tenant_id": tenant_id,
        "conversation_id": conversation_id,
        "usage_models": sorted(set(usage_models)),
    }
    _logger.info("latency turn", extra={"latency_turn": payload})
    return payload
