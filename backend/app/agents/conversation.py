"""T-043: conversational greetings, thanks, and meta questions about the assistant.

Answers only about itself and the interaction, never about the business, and
ends by offering help. A sixth specialist - named by capability, never by
vertical - so "hi", "what's your name?", and "thanks" never escalate to a
human. ``draft_deterministic: False`` ensures inspection still runs, so
any model-authored mention of the business is caught before the customer
sees it.
"""

from __future__ import annotations

from typing import Any

from langgraph.config import get_stream_writer
from langgraph.runtime import get_runtime

from app.agents.drafting import stream_draft
from app.agents.state import AgentState, GraphContext
from app.llm.provider import ChatMessage

_SYSTEM_PROMPT = (
    "You are a friendly customer-support assistant. The customer sent a "
    "greeting, said thanks, or asked a meta question about who you are or "
    "what you can do. Respond naturally and warmly - greet them back, "
    "introduce yourself as an assistant, and offer to help with questions "
    "about products, services, pricing, or orders. Keep it short (1-2 "
    "sentences). Never answer questions about the business itself - if they "
    "ask what something costs or how something works, say 'I can help you "
    "find out about that' instead of guessing."
)


async def run(state: AgentState) -> dict[str, Any]:
    runtime = get_runtime(GraphContext)
    ctx = runtime.context
    writer = get_stream_writer()

    query = state["messages"][-1]["content"]
    messages: list[ChatMessage] = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": query},
    ]

    full_text = await stream_draft(ctx.provider, messages)
    return {"draft_response": full_text, "draft_deterministic": False}
