"""T-044: graph topology - given tool calls that produce each route, the
right node sequence runs (agent -> draft -> [price_gate] -> inspection).
"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator
from typing import Any

import asyncpg
import pytest
import pytest_asyncio

from app.agents.graph import build_graph
from app.agents.state import AgentState, GraphContext
from app.llm.provider import ToolCall, ToolTurn
from app.retrieval.rerank import Reranker
from app.retrieval.types import RetrievedChunk
from app.shared import db
from tests.conftest import _app_dsn_for
from tests.fakes import ToolAwareFakeProvider, ZeroEmbedder

pytestmark = pytest.mark.db


@pytest_asyncio.fixture(autouse=True)
async def _pool(migrated_db: str) -> AsyncIterator[None]:
    await db.create_pool(dsn=_app_dsn_for(migrated_db), min_size=1, max_size=4)
    yield
    await db.close_pool()


class FakeReranker(Reranker):
    async def rerank(
        self, *, query: str, candidates: list[RetrievedChunk], top_k: int
    ) -> list[RetrievedChunk]:
        return candidates[:top_k]


def _make_tool_call(name: str, args: dict[str, object]) -> ToolCall:
    return ToolCall(id=f"call_{name}", name=name, args=args)


def _provider_for_route(route: str, *, tenant_id: uuid.UUID) -> ToolAwareFakeProvider:
    if route == "conversation":
        return ToolAwareFakeProvider(
            tool_call_sequence=[ToolTurn(text="Hello!", tool_calls=[])],
            stream_text="Hello! I'm the virtual assistant. How can I help you today?",
            extract_route=route,
        )
    if route == "knowledge":
        return ToolAwareFakeProvider(
            tool_call_sequence=[
                ToolTurn(tool_calls=[_make_tool_call("search_knowledge", {"query": "test"})]),
                ToolTurn(text="ok", tool_calls=[]),
            ],
            stream_text="An answer [1].",
            extract_route=route,
        )
    if route == "recommendation":
        return ToolAwareFakeProvider(
            tool_call_sequence=[
                ToolTurn(tool_calls=[_make_tool_call("recommend_items", {"preferences": "test"})]),
                ToolTurn(text="ok", tool_calls=[]),
            ],
            stream_text="Try item one.",
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


def _initial_state(*, tenant_id: uuid.UUID, conversation_id: uuid.UUID) -> AgentState:
    return {
        "conversation_id": str(conversation_id),
        "tenant_id": str(tenant_id),
        "messages": [{"role": "customer", "content": "hi"}],
        "route": None,
        "route_confidence": None,
        "retrieved_chunks": [],
        "selections": [],
        "engine_quote": None,
        "draft_response": "",
        "inspection": None,
        "escalated": False,
    }


async def _seed_tenant_with_conversation(
    conn: asyncpg.Connection[Any],
) -> tuple[uuid.UUID, uuid.UUID]:
    tenant_id: uuid.UUID = await conn.fetchval(
        "insert into tenants (slug, name) values ($1, 'Topology Test Co') returning id",
        f"topology-{uuid.uuid4().hex[:8]}",
    )
    await conn.execute("insert into tenant_config (tenant_id) values ($1)", tenant_id)
    conversation_id: uuid.UUID = await conn.fetchval(
        "insert into conversations (tenant_id) values ($1) returning id", tenant_id
    )
    return tenant_id, conversation_id


async def _run_and_collect_node_order(
    route: str, *, tenant_id: uuid.UUID, conversation_id: uuid.UUID
) -> list[str]:
    graph = build_graph()
    context = GraphContext(
        tenant_id=tenant_id,
        provider=_provider_for_route(route, tenant_id=tenant_id),
        embedder=ZeroEmbedder(),
        reranker=FakeReranker(),
    )
    order: list[str] = []
    initial_state = _initial_state(tenant_id=tenant_id, conversation_id=conversation_id)
    async for update in graph.astream(initial_state, context=context, stream_mode="updates"):
        order.extend(update.keys())
    return order


@pytest.mark.parametrize(
    "route", ["conversation", "recommendation", "quoting", "order_status", "escalation"]
)
async def test_forced_route_runs_agent_draft_inspection(
    route: str, superuser_conn: asyncpg.Connection[Any]
) -> None:
    tenant_id, conversation_id = await _seed_tenant_with_conversation(superuser_conn)
    order = await _run_and_collect_node_order(
        route, tenant_id=tenant_id, conversation_id=conversation_id
    )
    # C-2: every route traverses price_gate, not only the money ones. A draft
    # with no figures leaves it in a regex sweep, and a deterministic draft
    # (order_status, escalation) short-circuits inside the node.
    if route == "conversation":
        # P-3: no tool call means the agent already wrote the answer, so the
        # draft node is skipped - one LLM call, then the gates.
        assert order == ["agent", "price_gate", "inspection"]
    else:
        assert order == ["agent", "draft", "price_gate", "inspection"]


# --- C-2: the money gate covers the answer path, not just the money routes ---


async def _seed_tenant_with_priced_profile(
    conn: asyncpg.Connection[Any],
) -> tuple[uuid.UUID, uuid.UUID]:
    """A tenant whose owner typed a price into the interview profile.

    The profile is prompt material but never a retrieved chunk, so this also
    covers C-1's ``owner_material`` wiring end to end.
    """
    tenant_id: uuid.UUID = await conn.fetchval(
        "insert into tenants (slug, name) values ($1, 'Gate Coverage Co') returning id",
        f"coverage-{uuid.uuid4().hex[:8]}",
    )
    await conn.execute(
        "insert into tenant_config (tenant_id, config) values ($1, $2)",
        tenant_id,
        json.dumps({"profile": {"services": "Screen repair, $89 flat"}}),
    )
    conversation_id: uuid.UUID = await conn.fetchval(
        "insert into conversations (tenant_id) values ($1) returning id", tenant_id
    )
    return tenant_id, conversation_id


async def _answer_directly(
    draft: str,
    *,
    redraft: str,
    tenant_id: uuid.UUID,
    conversation_id: uuid.UUID,
) -> dict[str, Any]:
    """One direct answer (no tool call), with ``redraft`` ready if the gate
    sends it back."""
    provider = ToolAwareFakeProvider(
        tool_call_sequence=[ToolTurn(text=draft, tool_calls=[])],
        stream_text=redraft,
        extract_route="conversation",
    )
    graph = build_graph()
    context = GraphContext(
        tenant_id=tenant_id,
        provider=provider,
        embedder=ZeroEmbedder(),
        reranker=FakeReranker(),
    )
    initial_state = _initial_state(tenant_id=tenant_id, conversation_id=conversation_id)
    return await graph.ainvoke(initial_state, context=context)


async def test_figure_from_the_owner_profile_passes_the_gate(
    superuser_conn: asyncpg.Connection[Any],
) -> None:
    tenant_id, conversation_id = await _seed_tenant_with_priced_profile(superuser_conn)
    final_state = await _answer_directly(
        "A screen repair is $89 flat.",
        redraft="(should not be needed)",
        tenant_id=tenant_id,
        conversation_id=conversation_id,
    )
    assert final_state["draft_response"] == "A screen repair is $89 flat."
    assert final_state["escalated"] is False


async def test_invented_figure_on_the_answer_path_is_redrafted(
    superuser_conn: asyncpg.Connection[Any],
) -> None:
    tenant_id, conversation_id = await _seed_tenant_with_priced_profile(superuser_conn)
    final_state = await _answer_directly(
        "A screen repair is $250.",
        redraft="A screen repair is $89 flat.",
        tenant_id=tenant_id,
        conversation_id=conversation_id,
    )
    assert final_state["draft_response"] == "A screen repair is $89 flat."
    assert final_state["escalated"] is False


async def test_second_invented_figure_on_the_answer_path_escalates(
    superuser_conn: asyncpg.Connection[Any],
) -> None:
    tenant_id, conversation_id = await _seed_tenant_with_priced_profile(superuser_conn)
    final_state = await _answer_directly(
        "A screen repair is $250.",
        redraft="Fine, $240 then.",
        tenant_id=tenant_id,
        conversation_id=conversation_id,
    )
    assert final_state["escalated"] is True
    assert final_state["escalation_reason"] == "price_provenance"


async def test_hedging_the_owners_own_price_is_a_violation(
    superuser_conn: asyncpg.Connection[Any],
) -> None:
    """89 is allowed; "about $89" is the model guessing, not the owner's price."""
    tenant_id, conversation_id = await _seed_tenant_with_priced_profile(superuser_conn)
    final_state = await _answer_directly(
        "It's about $89.",
        redraft="A screen repair is $89 flat.",
        tenant_id=tenant_id,
        conversation_id=conversation_id,
    )
    assert final_state["draft_response"] == "A screen repair is $89 flat."


async def test_escalation_route_sets_escalated_flag(
    superuser_conn: asyncpg.Connection[Any],
) -> None:
    tenant_id, conversation_id = await _seed_tenant_with_conversation(superuser_conn)
    graph = build_graph()
    context = GraphContext(
        tenant_id=tenant_id,
        provider=_provider_for_route("escalation", tenant_id=tenant_id),
        embedder=ZeroEmbedder(),
        reranker=FakeReranker(),
    )
    initial_state = _initial_state(tenant_id=tenant_id, conversation_id=conversation_id)
    final_state = await graph.ainvoke(initial_state, context=context)
    assert final_state["escalated"] is True

    status = await superuser_conn.fetchval(
        "select status from conversations where id = $1", conversation_id
    )
    # C-5: the handoff is recorded, the conversation is not ended. A tenant
    # limit stop is the only thing that writes 'escalated' now.
    assert status == "open"


async def test_every_node_is_registered() -> None:
    graph = build_graph()
    node_names = set(graph.get_graph().nodes.keys())
    expected = {"agent", "draft", "price_gate", "inspection", "escalation", "__start__", "__end__"}
    assert node_names == expected
