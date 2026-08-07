"""T-044: Tool-driven agent node.

One node that replaces the old supervisor + six-specialist topology. Runs a
tool-calling loop (max 8 iterations) - the LLM decides which tools to call,
each gets executed in Python, results feed back to the conversation. When the
model returns prose instead of tool calls, the loop ends and a route is
determined from the set of tools that were invoked.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any
from uuid import UUID

from langgraph.config import get_stream_writer
from langgraph.runtime import get_runtime
from pydantic import BaseModel, Field

from app.agents.spotlight import Spotlight, new_spotlight
from app.agents.state import AgentState, GraphContext
from app.agents.tools import lookup_order_or_ticket
from app.llm.provider import ChatMessage, ToolSpec
from app.retrieval.service import retrieve
from app.shared import db
from app.shared.limits import with_timeout

logger = logging.getLogger("app.agents.agent_node")

_MAX_ITERATIONS = 8
_REFUSAL_SCORE_THRESHOLD = 0.05

_SYSTEM_PROMPT = (
    "You are a customer-support and sales assistant for a business. You have "
    "access to tools that let you answer questions, recommend items, produce "
    "price quotes, look up order status, or escalate to a human. Decide which "
    "tool(s) to call based on what the customer asked:\n"
    "- search_knowledge: look up general information, policies, or FAQs\n"
    "- recommend_items: help choose products or services based on preferences\n"
    "- get_quote_inputs: produce a price quote for specific items\n"
    "- lookup_order_or_ticket: check status of an existing order or ticket\n"
    "- create_escalation: hand off to a human when you cannot help confidently\n"
    "If the customer is just greeting, saying thanks, or asking what you can do, "
    "respond directly without calling any tool. If you are unsure or the message "
    "is unclear, escalate."
)


def _tool_result(spotlight: Spotlight, payload: dict[str, Any]) -> str:
    """Serialize a tool result for the model, spotlight-wrapped (T-027).

    Everything a tool returns is ultimately tenant-authored - catalog names and
    descriptions, pricing-rule labels, order statuses, even an exception string
    that may quote a row. The agent loop feeds these straight back as ``tool``
    messages and then decides which tool to call next, so undelimited tool
    output is an instruction channel. Wrapping the whole payload rather than
    hand-picking fields means a later change to what a tool returns cannot
    silently open that channel again.
    """
    return spotlight.wrap(json.dumps(payload))


class _SearchKnowledgeArgs(BaseModel):
    query: str = Field(description="What to search the knowledge base for")


class _RecommendItemsArgs(BaseModel):
    preferences: str = Field(description="What the customer is looking for - needs, constraints")


class _SelectionChoice(BaseModel):
    rule_code: str | None = None
    catalog_item_id: str | None = None
    quantity: int = Field(ge=1, le=999)


class _GetQuoteInputsArgs(BaseModel):
    selections: list[_SelectionChoice] = Field(description="Items/services to quote")


class _LookupOrderArgs(BaseModel):
    ref_code: str = Field(description="The order/repair/ticket reference code")
    customer_ref: str | None = Field(default=None, description="Customer reference if known")


class _CreateEscalationArgs(BaseModel):
    reason: str = Field(description="Why this needs human attention")


async def _search_knowledge_impl(
    conn: Any,
    tenant_id: UUID,
    query: str,
    embedder: Any,
    reranker: Any,
) -> list[dict[str, Any]]:
    results = await retrieve(
        conn,
        tenant_id=tenant_id,
        query=query,
        embedder=embedder,
        reranker=reranker,
        top_k=5,
    )
    relevant = [chunk for chunk in results if chunk.score > _REFUSAL_SCORE_THRESHOLD]
    return [
        {"id": str(chunk.id), "content": chunk.content, "metadata": chunk.metadata}
        for chunk in relevant
    ]


async def _recommend_items_impl(
    conn: Any,
    tenant_id: UUID,
    preferences: str,
    embedder: Any,
    reranker: Any,
) -> list[dict[str, Any]]:
    results = await retrieve(
        conn,
        tenant_id=tenant_id,
        query=preferences,
        embedder=embedder,
        reranker=reranker,
        top_k=5,
        metadata_kind="catalog_item",
    )
    item_ids = [
        UUID(chunk.metadata["catalog_item_id"])
        for chunk in results
        if chunk.metadata.get("catalog_item_id")
    ]
    rows = (
        await conn.fetch(
            "select id, name, description, price_cents from catalog_items "
            "where tenant_id = $1 and id = any($2::uuid[]) and active",
            tenant_id,
            item_ids,
        )
        if item_ids
        else []
    )
    return [
        {
            "catalog_item_id": str(row["id"]),
            "name": row["name"],
            "description": row["description"],
            "price_cents": row["price_cents"],
        }
        for row in rows
    ]


async def _get_quote_inputs_impl(
    conn: Any,
    tenant_id: UUID,
    selections: list[dict[str, Any]],
) -> dict[str, Any]:
    from app.pricing.engine import Selection, SelectionError, compute_quote

    engine_selections = []
    for sel in selections:
        if sel.get("rule_code"):
            engine_selections.append(Selection("rule", sel["rule_code"], sel["quantity"]))
        elif sel.get("catalog_item_id"):
            engine_selections.append(Selection("item", sel["catalog_item_id"], sel["quantity"]))
        else:
            raise SelectionError("a selection must name a rule_code or a catalog_item_id")
    quote = await compute_quote(conn, tenant_id, engine_selections)
    return {
        "line_items": [item.to_dict() for item in quote.line_items],
        "subtotal_cents": quote.subtotal_cents,
        "tax_cents": quote.tax_cents,
        "total_cents": quote.total_cents,
    }


async def _create_escalation_impl(
    conn: Any,
    tenant_id: UUID,
    conversation_id: UUID,
    reason: str,
) -> None:
    await conn.execute(
        "insert into escalations (tenant_id, conversation_id, reason) values ($1, $2, $3) "
        "on conflict (tenant_id, conversation_id) where status = 'open' do nothing",
        tenant_id,
        conversation_id,
        reason,
    )
    await conn.execute(
        "update conversations set status = 'escalated' "
        "where id = $1 and tenant_id = $2 and status <> 'escalated'",
        conversation_id,
        tenant_id,
    )


def _determine_route(called_tools: set[str]) -> str:
    if not called_tools:
        return "conversation"
    if "create_escalation" in called_tools:
        return "escalation"
    if "get_quote_inputs" in called_tools:
        return "quoting"
    if "recommend_items" in called_tools:
        return "recommendation"
    if "lookup_order_or_ticket" in called_tools:
        return "order_status"
    if "search_knowledge" in called_tools:
        return "knowledge"
    return "conversation"


async def run(state: AgentState) -> dict[str, Any]:
    runtime = get_runtime(GraphContext)
    ctx = runtime.context
    writer = get_stream_writer()

    # One spotlight per turn: every tool result below is wrapped with it, and
    # the instruction that explains the delimiters ships in the same prompt.
    spotlight = new_spotlight()

    tail = state["messages"][-3:] if len(state["messages"]) > 3 else state["messages"]
    messages: list[ChatMessage] = [
        ChatMessage(role="system", content=f"{_SYSTEM_PROMPT}\n{spotlight.instruction()}"),
    ]
    for m in tail:
        messages.append(ChatMessage(role=m["role"], content=m["content"]))

    tools = [
        ToolSpec(
            name="search_knowledge",
            description="Search the business knowledge base for policies or FAQs",
            args_schema=_SearchKnowledgeArgs,
        ),
        ToolSpec(
            name="recommend_items",
            description="Recommend products/services based on customer preferences",
            args_schema=_RecommendItemsArgs,
        ),
        ToolSpec(
            name="get_quote_inputs",
            description="Produce a price quote for selected items/services",
            args_schema=_GetQuoteInputsArgs,
        ),
        ToolSpec(
            name="lookup_order_or_ticket",
            description="Look up the status of an existing order, repair, or ticket by code",
            args_schema=_LookupOrderArgs,
        ),
        ToolSpec(
            name="create_escalation",
            description="Escalate to a human agent when you cannot help confidently",
            args_schema=_CreateEscalationArgs,
        ),
    ]

    called_tools: set[str] = set()
    retrieved_chunks: list[dict[str, Any]] = []
    selections: list[dict[str, Any]] = []
    engine_quote: dict[str, Any] | None = None
    lookup_result: dict[str, Any] | None = None

    async with db.tenant_context(ctx.tenant_id, "customer") as conn:
        for _ in range(_MAX_ITERATIONS):
            with ctx.turn.span("agent_tool_call") as span:
                turn = await ctx.provider.chat_with_tools(
                    messages=messages,
                    tools=tools,
                    tool_choice="auto",
                )
                span.set(tool_calls=len(turn.tool_calls))

            if not turn.tool_calls:
                break

            called_tools.update(call.name for call in turn.tool_calls)
            tool_result_messages: list[ChatMessage] = []

            for call in turn.tool_calls:
                started = time.perf_counter()
                try:
                    if call.name == "search_knowledge":
                        sk_args = _SearchKnowledgeArgs.model_validate(call.args)
                        chunks = await _search_knowledge_impl(
                            conn,
                            ctx.tenant_id,
                            sk_args.query,
                            ctx.embedder,
                            ctx.reranker,
                        )
                        retrieved_chunks = chunks
                        result_text = _tool_result(spotlight, {"found": len(chunks)})
                        writer(
                            {
                                "type": "tool_call",
                                "name": "search_knowledge",
                                "arguments": call.args,
                                "result": {"chunks": len(chunks)},
                                "success": True,
                                "latency_ms": int((time.perf_counter() - started) * 1000),
                            }
                        )
                    elif call.name == "recommend_items":
                        ri_args = _RecommendItemsArgs.model_validate(call.args)
                        items = await _recommend_items_impl(
                            conn,
                            ctx.tenant_id,
                            ri_args.preferences,
                            ctx.embedder,
                            ctx.reranker,
                        )
                        selections = items
                        result_text = _tool_result(spotlight, {"found": len(items), "items": items})
                        writer(
                            {
                                "type": "tool_call",
                                "name": "recommend_items",
                                "arguments": call.args,
                                "result": {"items": len(items)},
                                "success": True,
                                "latency_ms": int((time.perf_counter() - started) * 1000),
                            }
                        )
                    elif call.name == "get_quote_inputs":
                        qi_args = _GetQuoteInputsArgs.model_validate(call.args)
                        raw_sel = [s.model_dump(exclude_none=True) for s in qi_args.selections]
                        quote = await _get_quote_inputs_impl(conn, ctx.tenant_id, raw_sel)
                        engine_quote = quote
                        result_text = _tool_result(
                            spotlight,
                            {
                                "total_cents": quote["total_cents"],
                                "line_items": quote["line_items"],
                            },
                        )
                        writer(
                            {
                                "type": "tool_call",
                                "name": "get_quote_inputs",
                                "arguments": call.args,
                                "result": {"total_cents": quote["total_cents"]},
                                "success": True,
                                "latency_ms": int((time.perf_counter() - started) * 1000),
                            }
                        )
                    elif call.name == "lookup_order_or_ticket":
                        lo_args = _LookupOrderArgs.model_validate(call.args)
                        result = await with_timeout(
                            lookup_order_or_ticket(
                                conn,
                                ctx.tenant_id,
                                lo_args.ref_code,
                                lo_args.customer_ref,
                            ),
                            ctx.tool_timeout_s,
                            what="order lookup",
                        )
                        lookup_result = {
                            "ref_code": result.ref_code,
                            "found": result.found,
                            "status": result.status,
                            "kind": result.kind,
                        }
                        result_text = _tool_result(
                            spotlight,
                            {
                                "found": result.found,
                                "status": result.status,
                                "kind": result.kind,
                            },
                        )
                        writer(
                            {
                                "type": "tool_call",
                                "name": "lookup_order_or_ticket",
                                "arguments": call.args,
                                "result": {
                                    "found": result.found,
                                    "status": result.status,
                                    "kind": result.kind,
                                },
                                "success": True,
                                "latency_ms": int((time.perf_counter() - started) * 1000),
                            }
                        )
                    elif call.name == "create_escalation":
                        ce_args = _CreateEscalationArgs.model_validate(call.args)
                        await _create_escalation_impl(
                            conn,
                            ctx.tenant_id,
                            UUID(state["conversation_id"]),
                            ce_args.reason,
                        )
                        writer({"type": "escalated"})
                        result_text = _tool_result(
                            spotlight, {"escalated": True, "reason": ce_args.reason}
                        )
                        writer(
                            {
                                "type": "tool_call",
                                "name": "create_escalation",
                                "arguments": call.args,
                                "result": {"escalated": True},
                                "success": True,
                                "latency_ms": int((time.perf_counter() - started) * 1000),
                            }
                        )
                    else:
                        logger.warning("unknown tool requested: %s", call.name)
                        result_text = _tool_result(
                            spotlight, {"error": f"unknown tool: {call.name}"}
                        )
                except Exception as exc:
                    logger.exception("tool %s failed", call.name)
                    result_text = _tool_result(spotlight, {"error": str(exc)})
                    writer(
                        {
                            "type": "tool_call",
                            "name": call.name,
                            "arguments": call.args,
                            "result": {"error": str(exc)},
                            "success": False,
                            "latency_ms": int((time.perf_counter() - started) * 1000),
                        }
                    )

                tool_result_messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.id,
                        "content": result_text,
                    }
                )

            messages.append(
                {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "id": c.id,
                            "type": "function",
                            "function": {"name": c.name, "arguments": json.dumps(c.args)},
                        }
                        for c in turn.tool_calls
                    ],
                }
            )
            messages.extend(tool_result_messages)

            if "create_escalation" in called_tools:
                break

    route = _determine_route(called_tools)

    if route == "escalation":
        return {
            "route": route,
            "escalated": True,
            "escalation_reason": "tool_requested",
        }

    return {
        "route": route,
        "retrieved_chunks": retrieved_chunks,
        "selections": selections,
        "engine_quote": engine_quote,
        "lookup": lookup_result,
    }
