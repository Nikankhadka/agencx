"""T-044: agent node routing tests - verify that tool calls produce the
correct route in state. Replaces T-013's supervisor confidence-threshold
tests since routing is now done by the agent node's tool-calling loop.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import Any

import asyncpg
import pytest

from app.agents.graph import build_graph
from app.agents.state import AgentState, GraphContext
from app.llm.provider import ToolCall, ToolTurn
from app.retrieval.rerank import Reranker
from app.retrieval.types import RetrievedChunk
from app.shared import db
from tests.conftest import _app_dsn_for
from tests.fakes import ToolAwareFakeProvider, ZeroEmbedder

pytestmark = pytest.mark.db


class NoopReranker(Reranker):
    async def rerank(
        self, *, query: str, candidates: list[RetrievedChunk], top_k: int
    ) -> list[RetrievedChunk]:
        return candidates[:top_k]


def _make_tool_call(name: str, args: dict[str, object]) -> ToolCall:
    return ToolCall(id=f"call_{name}", name=name, args=args)


def _provider_for_route(route: str) -> ToolAwareFakeProvider:
    if route == "conversation":
        return ToolAwareFakeProvider(
            tool_call_sequence=[ToolTurn(text="Hello!", tool_calls=[])],
            stream_text="Hello! How can I help?",
            extract_route=route,
        )
    if route == "knowledge":
        return ToolAwareFakeProvider(
            tool_call_sequence=[
                ToolTurn(tool_calls=[_make_tool_call("search_knowledge", {"query": "test"})]),
                ToolTurn(text="ok", tool_calls=[]),
            ],
            stream_text="An answer.",
            extract_route=route,
        )
    if route == "recommendation":
        return ToolAwareFakeProvider(
            tool_call_sequence=[
                ToolTurn(tool_calls=[_make_tool_call("recommend_items", {"preferences": "test"})]),
                ToolTurn(text="ok", tool_calls=[]),
            ],
            stream_text="Try this.",
            extract_route=route,
        )
    if route == "quoting":
        return ToolAwareFakeProvider(
            tool_call_sequence=[
                ToolTurn(
                    tool_calls=[
                        _make_tool_call(
                            "get_quote_inputs",
                            {
                                "selections": [
                                    {"rule_code": "test-rule", "quantity": 1},
                                ]
                            },
                        )
                    ]
                ),
                ToolTurn(text="ok", tool_calls=[]),
            ],
            stream_text="Here is your quote.",
            extract_route=route,
        )
    if route == "order_status":
        return ToolAwareFakeProvider(
            tool_call_sequence=[
                ToolTurn(
                    tool_calls=[
                        _make_tool_call("lookup_order_or_ticket", {"ref_code": "R-1042"}),
                    ]
                ),
            ],
            stream_text="",
            extract_route=route,
        )
    if route == "escalation":
        return ToolAwareFakeProvider(
            tool_call_sequence=[
                ToolTurn(tool_calls=[_make_tool_call("create_escalation", {"reason": "test"})]),
            ],
            stream_text="",
            extract_route=route,
        )
    raise ValueError(f"unknown route: {route}")


def _initial_state(
    conversation_id: uuid.UUID, tenant_id: uuid.UUID, message: str = "hi"
) -> AgentState:
    return {
        "conversation_id": str(conversation_id),
        "tenant_id": str(tenant_id),
        "messages": [{"role": "customer", "content": message}],
        "route": None,
        "route_confidence": None,
        "retrieved_chunks": [],
        "selections": [],
        "engine_quote": None,
        "draft_response": "",
        "inspection": None,
        "escalated": False,
    }


async def _seed_tenant(
    conn: asyncpg.Connection[Any],
) -> tuple[uuid.UUID, uuid.UUID]:
    tenant_id: uuid.UUID = await conn.fetchval(
        "insert into tenants (slug, name) values ($1, 'Routing Test Co') returning id",
        f"routing-{uuid.uuid4().hex[:8]}",
    )
    await conn.execute("insert into tenant_config (tenant_id) values ($1)", tenant_id)
    conversation_id: uuid.UUID = await conn.fetchval(
        "insert into conversations (tenant_id) values ($1) returning id", tenant_id
    )
    return tenant_id, conversation_id


@pytest.fixture(autouse=True)
async def _pool(migrated_db: str) -> AsyncIterator[None]:
    await db.create_pool(dsn=_app_dsn_for(migrated_db), min_size=1, max_size=4)
    yield
    await db.close_pool()


@pytest.mark.parametrize(
    "route",
    ["conversation", "knowledge", "recommendation", "quoting", "order_status", "escalation"],
)
async def test_agent_node_sets_route_from_tool_calls(
    superuser_conn: asyncpg.Connection[Any], route: str
) -> None:
    tenant_id, conversation_id = await _seed_tenant(superuser_conn)
    graph = build_graph()
    context = GraphContext(
        tenant_id=tenant_id,
        provider=_provider_for_route(route),
        embedder=ZeroEmbedder(),
        reranker=NoopReranker(),
    )
    final_state = await graph.ainvoke(_initial_state(conversation_id, tenant_id), context=context)
    assert final_state["route"] == route


async def test_conversation_with_no_tools_stays_conversation(
    superuser_conn: asyncpg.Connection[Any],
) -> None:
    tenant_id, conversation_id = await _seed_tenant(superuser_conn)
    graph = build_graph()
    context = GraphContext(
        tenant_id=tenant_id,
        provider=ToolAwareFakeProvider(
            tool_call_sequence=[ToolTurn(text="Hi there!", tool_calls=[])],
            stream_text="Hello! Welcome.",
            extract_route="conversation",
        ),
        embedder=ZeroEmbedder(),
        reranker=NoopReranker(),
    )
    final_state = await graph.ainvoke(
        _initial_state(conversation_id, tenant_id, "hi"), context=context
    )
    assert final_state["route"] == "conversation"
    assert final_state["escalated"] is False


async def test_escalation_tool_produces_escalation_route(
    superuser_conn: asyncpg.Connection[Any],
) -> None:
    tenant_id, conversation_id = await _seed_tenant(superuser_conn)
    graph = build_graph()
    context = GraphContext(
        tenant_id=tenant_id,
        provider=_provider_for_route("escalation"),
        embedder=ZeroEmbedder(),
        reranker=NoopReranker(),
    )
    final_state = await graph.ainvoke(
        _initial_state(conversation_id, tenant_id, "I want a human"), context=context
    )
    assert final_state["route"] == "escalation"
    assert final_state["escalated"] is True
