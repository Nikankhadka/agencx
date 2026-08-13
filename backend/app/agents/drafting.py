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
