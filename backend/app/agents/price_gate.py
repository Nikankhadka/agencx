"""T-018/C-2: the price-provenance gate as a graph node.

Runs after **every** draft, not just the money routes. It was built when the
only prose carrying figures came from Quoting and Recommendation; the lean
assistant answers from knowledge, which is now where a figure is most likely
to appear, so a route-based bypass was a hole rather than a saving. A reply
with no figures costs one regex sweep.

Deterministic - delegates to app/pricing/validation_gate.py, no LLM call. A
violating draft gets exactly one redraft (violations listed back to the
producing node via ``price_violations``); a second violation escalates with
reason ``price_provenance``. Emits a ``redraft`` stream event so the customer
surface clears the violating text it already saw - full buffering until
inspection passes is T-021's job and is a recorded latency tradeoff, not
something this node half-implements.
"""

from __future__ import annotations

from typing import Any

from langgraph.config import get_stream_writer

from app.agents.state import AgentState
from app.pricing.validation_gate import validate

GATE_ESCALATION_MESSAGE = (
    "I couldn't put together a reliable answer on pricing, so I'm handing "
    "this to a human who can. They'll pick it up from here."
)


def owner_material(state: AgentState) -> list[str]:
    """The tenant's own text this turn had in front of it (C-1).

    The chunks are whatever the turn was grounded in - the whole corpus on the
    fast path, the retrieved set on the hybrid path - and ``owner_material``
    carries the interview profile, which is prompt material but never a chunk,
    so a price the owner typed into their profile counts too.
    """
    material = [chunk["content"] for chunk in state["retrieved_chunks"] if chunk.get("content")]
    profile = state.get("owner_material")
    if profile:
        material.append(profile)
    return material


async def run(state: AgentState) -> dict[str, Any]:
    # A template or refusal constant carries no model-authored figure, so
    # there is nothing here to check - same reasoning, and the same skip,
    # that inspection applies to these drafts.
    if state.get("draft_deterministic"):
        return {"price_gate_decision": "ok"}

    provenance = [
        selection["price_cents"]
        for selection in state["selections"]
        if isinstance(selection.get("price_cents"), int)
    ]
    violations = validate(
        state["draft_response"],
        state["engine_quote"],
        provenance,
        owner_material(state),
    )

    if not violations:
        return {"price_gate_decision": "ok"}

    writer = get_stream_writer()
    if not state.get("price_gate_attempted"):
        writer({"type": "redraft"})
        return {
            "price_gate_decision": "retry",
            "price_violations": violations,
            "price_gate_attempted": True,
        }

    writer({"type": "refusal", "text": GATE_ESCALATION_MESSAGE})
    return {
        "price_gate_decision": "escalate",
        "escalated": True,
        "escalation_reason": "price_provenance",
        "draft_response": GATE_ESCALATION_MESSAGE,
    }
