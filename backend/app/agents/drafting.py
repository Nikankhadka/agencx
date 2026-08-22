"""Shared streaming-draft helper for the specialist agents.

Every specialist (recommendation, knowledge, quoting) streams its prose draft
the same way, on both the initial pass and a gate-triggered redraft: emit each
delta to the customer as a ``token`` event and accumulate the full text to
return in ``draft_response``. This is that one loop, in one place, so the token
event shape and accumulation can never drift between nodes.
"""

from __future__ import annotations

import logging
import time

from langgraph.config import get_stream_writer

from app.llm.provider import ChatMessage, LLMProvider

logger = logging.getLogger("app.agents.drafting")

# C-3: the prompt half of the money guardrail, shared by every surface that
# authors customer-facing prose - the one-call agent turn (agent_node) and
# every redraft (draft_node). The deterministic gate remains the sole arbiter;
# this exists so the model mostly complies and the gate mostly passes instead
# of mostly rewriting, because every catch costs a redraft and a redraft is
# latency the customer feels (PRD section 9).
MONEY_GUIDANCE = (
    "About prices, fees, and any other amounts: state a figure only when the "
    "material contains that exact figure. Never add amounts together, work out "
    "a total, apply tax or a discount, round, or estimate - and never soften "
    "one with 'about', 'around' or 'roughly'. A figure is either the one the "
    "business published or it is not yours to give. If you are not sure of a "
    "price, say so plainly and offer to have the owner confirm it."
)


async def stream_draft(provider: LLMProvider, messages: list[ChatMessage]) -> str:
    """Stream ``messages`` through ``provider``, forwarding each delta as a
    ``token`` event, and return the accumulated draft text. Must run inside a
    graph node (it uses the run-scoped stream writer)."""
    writer = get_stream_writer()
    started = time.perf_counter()
    text = ""
    async for delta in provider.chat_stream(messages):
        text += delta
        writer({"type": "token", "text": delta})
    logger.info(
        "agent draft",
        extra={
            "duration_ms": round((time.perf_counter() - started) * 1000, 1),
            "chars": len(text),
        },
    )
    return text
