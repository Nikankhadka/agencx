"""T-044: Draft node - composes the final customer-facing response from data
collected by the agent node's tool calls.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from langgraph.config import get_stream_writer
from langgraph.runtime import get_runtime

from app.agents.drafting import stream_draft
from app.agents.spotlight import new_spotlight
from app.agents.state import AgentState, GraphContext
from app.core import db
from app.llm.provider import ChatMessage

_KNOWLEDGE_REFUSAL = (
    "I don't have information about that. Please contact the business directly for help."
)
_RECOMMENDATION_REFUSAL = (
    "I don't have anything that matches what you're looking for. "
    "Please contact the business directly for help."
)
_QUOTING_NO_CANDIDATES = (
    "I can't put together a quote for that - the business hasn't listed "
    "anything I could price it from. Please contact them directly."
)
_ORDER_NOT_FOUND_TEMPLATE = "I can't find {ref_code} - please double-check the code."
_ORDER_ASK_FOR_CODE = "Could you share the order, repair, or ticket code so I can look it up?"
_ORDER_FOUND_TEMPLATE = 'Your {kind} {ref_code} is currently "{status}".'

_SYSTEM_PROMPT_CONVERSATION = (
    "You are a friendly customer-support assistant. The customer sent a "
    "greeting, said thanks, or asked a meta question about who you are or "
    "what you can do. Respond naturally and warmly - greet them back, "
    "introduce yourself as an assistant, and offer to help with questions "
    "about products, services, pricing, or orders. Keep it short (1-2 "
    "sentences). Never answer questions about the business itself - if they "
    "ask what something costs or how something works, say 'I can help you "
    "find out about that' instead of guessing."
)


def _build_knowledge_prompt(
    chunks: list[dict[str, Any]], tenant_prompt: str, tone: str,
    violations: list[str] | None,
) -> str:
    spotlight = new_spotlight()
    context_block = "\n\n".join(
        f"[{i + 1}] {spotlight.wrap(c['content'])}" for i, c in enumerate(chunks)
    )
    base = tenant_prompt or "You are the AI support and sales assistant for this business."
    prompt = (
        f"{base}\nTone: {tone or 'friendly'}.\n{spotlight.instruction()}\n"
        "Answer the customer's question using ONLY the numbered context below. "
        "Cite every factual claim with its bracket number, e.g. [1]. If the "
        "context doesn't fully answer the question, say what you don't know - "
        "never invent information.\n\n"
        f"Context:\n{context_block}"
    )
    if violations:
        prompt += (
            "\n\nYour previous draft was rejected: "
            + "; ".join(violations) + ". Redraft now, addressing this."
        )
    return prompt


def _build_recommendation_prompt(
    selections: list[dict[str, Any]], violations: list[str] | None,
) -> str:
    spotlight = new_spotlight()
    items_block = "\n".join(
        f"[{i + 1}] {spotlight.wrap(sel['name'] + ': ' + (sel['description'] or ''))}"
        + (f" (${sel['price_cents'] / 100:.2f})" if sel.get("price_cents") is not None else "")
        for i, sel in enumerate(selections)
    )
    prompt = (
        "You are a sales assistant recommending items to a customer. Recommend "
        "ONLY from the numbered list below, with a short reason for each - never "
        "invent an item or a price that isn't listed.\n"
        f"{spotlight.instruction()}\n\nAvailable items:\n{items_block}"
    )
    if violations:
        prompt += (
            "\n\nYour previous draft was rejected: " + "; ".join(violations)
            + ". Redraft now, addressing this - name prices only exactly as listed above, "
            "or leave them out entirely."
        )
    return prompt


def _build_quoting_prompt(
    engine_quote: dict[str, Any], violations: list[str] | None,
) -> str:
    coverage = "\n".join(
        f"- {item['label']} x{item['quantity']}" for item in engine_quote["line_items"]
    )
    prompt = (
        "You are presenting a price quote to a customer. A quote card showing "
        "the exact line items, quantities, and totals is displayed alongside "
        "your message. Briefly explain what the quote covers, referring to the "
        "card for figures. Do NOT state any prices, totals, or other monetary "
        "amounts yourself - the card is the single source of numbers.\n\n"
        f"The quote covers:\n{coverage}"
    )
    if violations:
        prompt += (
            "\n\nYour previous draft was rejected: "
            + "; ".join(violations)
            + ". Redraft now, addressing this - state no monetary amounts yourself either way."
        )
    return prompt


async def run(state: AgentState) -> dict[str, Any]:
    runtime = get_runtime(GraphContext)
    ctx = runtime.context
    writer = get_stream_writer()
    route = state["route"]
    query = state["messages"][-1]["content"]

    if state.get("escalated"):
        handoff = state.get("draft_response")
        if not handoff:
            handoff = (
                "Thanks for your patience - a human will pick this up "
                "from here and follow up with you."
            )
            writer({"type": "refusal", "text": handoff})
        return {"draft_response": handoff, "draft_deterministic": True, "escalated": True}

    violations = state.get("price_violations") or state.get("inspection_violations")
    clear_violations: dict[str, Any] = {}
    if state.get("price_violations"):
        clear_violations["price_violations"] = []
    if state.get("inspection_violations"):
        clear_violations["inspection_violations"] = []

    if route == "conversation":
        messages: list[ChatMessage] = [
            {"role": "system", "content": _SYSTEM_PROMPT_CONVERSATION},
            {"role": "user", "content": query},
        ]
        text = await stream_draft(ctx.provider, messages)
        return {"draft_response": text, "draft_deterministic": False}

    if route == "knowledge":
        retrieved_chunks = state.get("retrieved_chunks", [])
        if not retrieved_chunks:
            writer({"type": "refusal", "text": _KNOWLEDGE_REFUSAL})
            return {"draft_response": _KNOWLEDGE_REFUSAL, "retrieved_chunks": [],
                    "draft_deterministic": True}
        citations = [
            {"index": i + 1, "source": _citation_source(c), "snippet": c["content"][:200]}
            for i, c in enumerate(retrieved_chunks)
        ]
        writer({"type": "citations", "citations": citations})
        async with db.tenant_context(ctx.tenant_id, "customer") as conn:
            config_row = await conn.fetchrow(
                "select system_prompt, tone from tenant_config where tenant_id = $1",
                ctx.tenant_id,
            )
        system_prompt = _build_knowledge_prompt(
            retrieved_chunks,
            tenant_prompt=config_row["system_prompt"] if config_row else "",
            tone=config_row["tone"] if config_row else "",
            violations=violations,
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": query},
        ]
        text = await stream_draft(ctx.provider, messages)
        return {"draft_response": text, "retrieved_chunks": retrieved_chunks, **clear_violations}

    if route == "recommendation":
        selections = state.get("selections", [])
        if not selections:
            writer({"type": "refusal", "text": _RECOMMENDATION_REFUSAL})
            return {"draft_response": _RECOMMENDATION_REFUSAL, "selections": [],
                    "draft_deterministic": True}
        system_prompt = _build_recommendation_prompt(selections, violations)
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": query},
        ]
        text = await stream_draft(ctx.provider, messages)
        return {"draft_response": text, "selections": selections, **clear_violations}

    if route == "quoting":
        engine_quote = state.get("engine_quote")
        if not engine_quote:
            writer({"type": "refusal", "text": _QUOTING_NO_CANDIDATES})
            return {"draft_response": _QUOTING_NO_CANDIDATES, "selections": [],
                    "draft_deterministic": True}
        if not engine_quote.get("quote_id"):
            import json as _json
            async with db.tenant_context(ctx.tenant_id, "customer") as conn:
                quote_id = await conn.fetchval(
                    "insert into quotes (tenant_id, conversation_id, line_items, "
                    "subtotal_cents, tax_cents, total_cents, status) "
                    "values ($1, $2, $3, $4, $5, $6, 'sent') returning id",
                    ctx.tenant_id, UUID(state["conversation_id"]),
                    _json.dumps(engine_quote["line_items"]),
                    engine_quote["subtotal_cents"], engine_quote["tax_cents"],
                    engine_quote["total_cents"],
                )
            engine_quote["quote_id"] = str(quote_id)
            engine_quote["status"] = "sent"
        writer({"type": "quote", "quote": engine_quote})
        system_prompt = _build_quoting_prompt(engine_quote, violations)
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": query},
        ]
        text = await stream_draft(ctx.provider, messages)
        return {"draft_response": text, "selections": state.get("selections", []),
                "engine_quote": engine_quote, **clear_violations}

    if route == "order_status":
        lookup = state.get("lookup") or {}
        ref_code = lookup.get("ref_code")
        if not ref_code:
            writer({"type": "refusal", "text": _ORDER_ASK_FOR_CODE})
            return {"draft_response": _ORDER_ASK_FOR_CODE, "draft_deterministic": True,
                    "lookup": {"ref_code": None, "found": False}}
        if not lookup.get("found"):
            text = _ORDER_NOT_FOUND_TEMPLATE.format(ref_code=ref_code)
            writer({"type": "refusal", "text": text})
            return {"draft_response": text, "draft_deterministic": True,
                    "lookup": {"ref_code": ref_code, "found": False}}
        text = _ORDER_FOUND_TEMPLATE.format(
            kind=lookup.get("kind", ""), ref_code=lookup.get("ref_code", ""),
            status=lookup.get("status", ""),
        )
        writer({"type": "token", "text": text})
        return {"draft_response": text, "draft_deterministic": True, "lookup": lookup}

    import logging as _logging
    _logging.getLogger("app.agents.draft_node").warning(
        "draft_node: unknown route %s, falling back to conversation", route)
    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT_CONVERSATION},
        {"role": "user", "content": query},
    ]
    text = await stream_draft(ctx.provider, messages)
    return {"draft_response": text, "draft_deterministic": False}


def _citation_source(chunk: dict[str, Any]) -> str:
    metadata = chunk.get("metadata", {})
    if metadata.get("kind") == "catalog_item":
        return "catalog"
    source = metadata.get("source")
    return str(source) if source else "knowledge base"
