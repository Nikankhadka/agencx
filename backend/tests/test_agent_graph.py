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

from app.agents.agent_node import _grounded_terminal_prose
from app.agents.graph import build_graph
from app.agents.state import AgentState, GraphContext
from app.ingestion.chunker import chunk_catalog_item
from app.llm.embedder import Embedder
from app.llm.provider import ToolCall, ToolTurn
from app.retrieval.rerank import Reranker
from app.retrieval.types import RetrievedChunk
from app.shared import db
from tests.conftest import _app_dsn_for
from tests.fakes import EMBEDDING_DIM, ToolAwareFakeProvider, ZeroEmbedder

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


@pytest.mark.parametrize(
    ("route", "expected_intent", "expected_action"),
    [
        ("conversation", "information", "respond"),
        ("knowledge", "information", "offer_followup"),
        ("recommendation", "offer", "offer_followup"),
        ("quoting", "offer", "offer_followup"),
        ("order_status", "information", "respond"),
        ("escalation", None, "escalate"),
    ],
)
async def test_state_carries_intent_and_action_per_route(
    route: str,
    expected_intent: str | None,
    expected_action: str,
    superuser_conn: asyncpg.Connection[Any],
) -> None:
    """Intent is descriptive metadata: the prose/offer routes fall back to the
    route mapping, deterministic refusals that already offer forwarding set
    ``offer_followup``, and an escalation always lands ``escalate``."""
    tenant_id, conversation_id = await _seed_tenant_with_conversation(superuser_conn)
    graph = build_graph()
    context = GraphContext(
        tenant_id=tenant_id,
        provider=_provider_for_route(route, tenant_id=tenant_id),
        embedder=ZeroEmbedder(),
        reranker=FakeReranker(),
    )
    initial_state = _initial_state(tenant_id=tenant_id, conversation_id=conversation_id)
    final_state = await graph.ainvoke(initial_state, context=context)
    assert final_state.get("intent") == expected_intent
    assert final_state.get("action") == expected_action


@pytest.mark.parametrize(
    ("route", "expected_author"),
    [
        ("conversation", "agent"),
        ("recommendation", "draft"),
        ("quoting", "draft"),
        ("order_status", "draft"),
        ("escalation", "escalation"),
    ],
)
async def test_author_node_names_the_producing_node(
    route: str, expected_author: str, superuser_conn: asyncpg.Connection[Any]
) -> None:
    """F-3: every path lands a real node name on the trace's author field -
    the agent fast path, draft-node prose/refusals, and the escalation
    handoff."""
    tenant_id, conversation_id = await _seed_tenant_with_conversation(superuser_conn)
    graph = build_graph()
    context = GraphContext(
        tenant_id=tenant_id,
        provider=_provider_for_route(route, tenant_id=tenant_id),
        embedder=ZeroEmbedder(),
        reranker=FakeReranker(),
    )
    initial_state = _initial_state(tenant_id=tenant_id, conversation_id=conversation_id)
    final_state = await graph.ainvoke(initial_state, context=context)
    assert final_state["author_node"] == expected_author


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
    assert final_state["author_node"] == "price_gate"
    assert final_state["intent"] == "information"
    assert final_state["action"] == "escalate"
    row_intent = await superuser_conn.fetchval(
        "select intent from escalations where conversation_id = $1", conversation_id
    )
    assert row_intent == "information"


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
    assert final_state["author_node"] == "escalation"

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


class ExplodingEmbedder(Embedder):
    """Stands in for the live failure that exposed all of this: Google retired
    ``text-embedding-004`` and started 404ing it, so every ``recommend_items``
    call raised inside the tool loop."""

    async def embed(self, texts: list[str]) -> list[list[float]]:
        raise RuntimeError("404 Not Found: embedding model is gone")


async def test_a_failing_tool_does_not_take_the_turn_down_with_it(
    superuser_conn: asyncpg.Connection[Any],
) -> None:
    """A tool that raises is caught, reported back to the model, and the turn
    still answers the customer.

    The loop has always caught the tool's own exception. What it did not survive
    was its own bookkeeping afterwards, and the difference never showed up here
    because the log line that raised is only reached when logging is enabled for
    INFO - production's level, not pytest's default. ``pyproject.toml`` now pins
    the suite to INFO so this test exercises the same code path the deploy runs.
    """
    tenant_id, conversation_id = await _seed_tenant_with_conversation(superuser_conn)
    graph = build_graph()
    context = GraphContext(
        tenant_id=tenant_id,
        provider=_provider_for_route("recommendation", tenant_id=tenant_id),
        embedder=ExplodingEmbedder(),
        reranker=FakeReranker(),
    )
    initial_state = _initial_state(tenant_id=tenant_id, conversation_id=conversation_id)
    final_state = await graph.ainvoke(initial_state, context=context)

    assert final_state["draft_response"], "a failing tool must not silence the turn"
    # Nothing about a dead tool is a handoff: the model is handed the error and
    # answers from what it already has.
    assert final_state["escalated"] is False


# --- slice 3: a grounded tool turn is answered by the agent itself ---


async def _seed_tenant_with_chunk_and_conversation(
    conn: asyncpg.Connection[Any],
) -> tuple[uuid.UUID, uuid.UUID]:
    """A tenant whose corpus holds one chunk, so search_knowledge returns it."""
    tenant_id, conversation_id = await _seed_tenant_with_conversation(conn)
    document_id: uuid.UUID = await conn.fetchval(
        "insert into documents (tenant_id, filename, doc_type, status) "
        "values ($1, 'faq.md', 'faq', 'ready') returning id",
        tenant_id,
    )
    await conn.execute(
        "insert into knowledge_chunks (tenant_id, document_id, content, embedding, metadata) "
        "values ($1, $2, $3, $4, $5)",
        tenant_id,
        document_id,
        "We are open weekdays 9-5.",
        [0.0] * EMBEDDING_DIM,
        json.dumps({"source": "faq.md", "chunk_index": 0, "kind": "prose"}),
    )
    return tenant_id, conversation_id


async def _seed_tenant_with_catalog_and_conversation(
    conn: asyncpg.Connection[Any],
) -> tuple[uuid.UUID, uuid.UUID]:
    """A tenant whose catalog holds one active item, so recommend_items finds it."""
    tenant_id, conversation_id = await _seed_tenant_with_conversation(conn)
    document_id: uuid.UUID = await conn.fetchval(
        "insert into documents (tenant_id, filename, doc_type, status) "
        "values ($1, 'catalog', 'catalog', 'ready') returning id",
        tenant_id,
    )
    item_id: uuid.UUID = await conn.fetchval(
        "insert into offerings (tenant_id, name, description, price_cents) "
        "values ($1, 'Item One', 'A durable widget', 4900) returning id",
        tenant_id,
    )
    chunk = chunk_catalog_item(str(item_id), "Item One", "A durable widget", 4900)
    await conn.execute(
        "insert into knowledge_chunks (tenant_id, document_id, content, embedding, metadata) "
        "values ($1, $2, $3, $4, $5)",
        tenant_id,
        document_id,
        chunk.content,
        [0.0] * EMBEDDING_DIM,
        json.dumps(chunk.metadata),
    )
    return tenant_id, conversation_id


def _grounded_knowledge_provider(
    *, prose: str = "We are open weekdays 9-5 [1].", rounds: int = 1
) -> ToolAwareFakeProvider:
    """A knowledge turn: ``rounds`` retrieval rounds, then grounded prose."""
    tool_rounds = [
        ToolTurn(
            tool_calls=[
                ToolCall(id=f"call_s{i}", name="search_knowledge", args={"query": f"q{i}"}),
            ]
        )
        for i in range(rounds)
    ]
    return ToolAwareFakeProvider(
        tool_call_sequence=[*tool_rounds, ToolTurn(text=prose, tool_calls=[])],
        stream_text="(the draft node must not run on this turn)",
        extract_route="knowledge",
    )


def _context_for(provider: ToolAwareFakeProvider, *, tenant_id: uuid.UUID) -> GraphContext:
    return GraphContext(
        tenant_id=tenant_id,
        provider=provider,
        embedder=ZeroEmbedder(),
        reranker=FakeReranker(),
    )


async def _node_order(
    provider: ToolAwareFakeProvider, *, tenant_id: uuid.UUID, conversation_id: uuid.UUID
) -> list[str]:
    graph = build_graph()
    order: list[str] = []
    initial_state = _initial_state(tenant_id=tenant_id, conversation_id=conversation_id)
    async for update in graph.astream(
        initial_state, context=_context_for(provider, tenant_id=tenant_id), stream_mode="updates"
    ):
        order.extend(update.keys())
    return order


async def _final_state(
    provider: ToolAwareFakeProvider, *, tenant_id: uuid.UUID, conversation_id: uuid.UUID
) -> dict[str, Any]:
    graph = build_graph()
    initial_state = _initial_state(tenant_id=tenant_id, conversation_id=conversation_id)
    return await graph.ainvoke(initial_state, context=_context_for(provider, tenant_id=tenant_id))


async def test_grounded_knowledge_turn_is_answered_by_the_agent(
    superuser_conn: asyncpg.Connection[Any],
) -> None:
    """Slice 3: search_knowledge's result now carries the chunks, so the loop's
    terminal prose is grounded, becomes the draft, and the draft node is skipped
    - one model call fewer than before on this turn."""
    tenant_id, conversation_id = await _seed_tenant_with_chunk_and_conversation(superuser_conn)

    provider = _grounded_knowledge_provider()
    order = await _node_order(provider, tenant_id=tenant_id, conversation_id=conversation_id)
    assert order == ["agent", "price_gate", "inspection"]

    provider = _grounded_knowledge_provider()
    final_state = await _final_state(provider, tenant_id=tenant_id, conversation_id=conversation_id)
    assert final_state["draft_response"] == "We are open weekdays 9-5 [1]."
    assert final_state["author_node"] == "agent"
    assert final_state["route"] == "knowledge"
    assert len(final_state["retrieved_chunks"]) == 1
    assert final_state["retrieved_chunks"][0]["content"] == "We are open weekdays 9-5."
    assert final_state["retrieved_chunks"][0]["metadata"]["source"] == "faq.md"
    # The draft node composed nothing - the agent's own prose shipped.
    assert provider.draft_prompts == []
    # Two model calls: the retrieval round and the grounded prose. The third the
    # draft node used to spend here is the call slice 3 removed.
    assert len(provider.tool_call_messages) == 2


async def test_multi_round_grounded_turn_keeps_every_round(
    superuser_conn: asyncpg.Connection[Any],
) -> None:
    """The saving is the draft node's call, never a loop round: a turn that
    searches twice still runs both rounds and the prose that closes them."""
    tenant_id, conversation_id = await _seed_tenant_with_chunk_and_conversation(superuser_conn)
    provider = _grounded_knowledge_provider(rounds=2)
    order = await _node_order(provider, tenant_id=tenant_id, conversation_id=conversation_id)
    assert order == ["agent", "price_gate", "inspection"]
    assert len(provider.tool_call_messages) == 3
    # Each round was fed the results of the rounds before it - neither round was
    # collapsed and neither result was dropped.
    assert not any(m["role"] == "tool" for m in provider.tool_call_messages[0])
    assert len([m for m in provider.tool_call_messages[1] if m["role"] == "tool"]) == 1
    assert len([m for m in provider.tool_call_messages[2] if m["role"] == "tool"]) == 2


async def test_money_tool_turn_still_runs_the_draft_node(
    superuser_conn: asyncpg.Connection[Any],
) -> None:
    """C-2: after a money tool the draft node remains the only writer, even on a
    tenant whose corpus would otherwise ground the agent's prose."""
    tenant_id, conversation_id = await _seed_tenant_with_chunk_and_conversation(superuser_conn)
    provider = _provider_for_route("quoting", tenant_id=tenant_id)
    order = await _node_order(provider, tenant_id=tenant_id, conversation_id=conversation_id)
    assert order == ["agent", "draft", "price_gate", "inspection"]

    provider = _provider_for_route("quoting", tenant_id=tenant_id)
    final_state = await _final_state(provider, tenant_id=tenant_id, conversation_id=conversation_id)
    assert final_state["author_node"] == "draft"


def test_money_tool_output_never_becomes_the_agent_draft() -> None:
    """The same rule at the predicate: a money tool disqualifies the prose
    whatever the route ends up being called."""
    chunk = {"id": "1", "content": "We are open weekdays 9-5.", "metadata": {}}
    assert _grounded_terminal_prose(
        route="knowledge",
        called_tools={"search_knowledge"},
        retrieved_chunks=[chunk],
        selections=[],
    )
    assert not _grounded_terminal_prose(
        route="knowledge",
        called_tools={"search_knowledge", "calculate_quote"},
        retrieved_chunks=[chunk],
        selections=[],
    )


def _grounded_recommendation_provider() -> ToolAwareFakeProvider:
    """A recommendation turn: one recommend_items round, then grounded prose."""
    return ToolAwareFakeProvider(
        tool_call_sequence=[
            ToolTurn(
                tool_calls=[
                    ToolCall(id="call_r", name="recommend_items", args={"preferences": "durable"}),
                ]
            ),
            ToolTurn(text="Item One is a durable widget.", tool_calls=[]),
        ],
        stream_text="(the draft node must not run on this turn)",
        extract_route="recommendation",
    )


async def test_grounded_recommendation_turn_is_answered_by_the_agent(
    superuser_conn: asyncpg.Connection[Any],
) -> None:
    """recommend_items already carried its items, so this route is grounded by
    the same rule once the agent's prose ships as the draft."""
    tenant_id, conversation_id = await _seed_tenant_with_catalog_and_conversation(superuser_conn)

    provider = _grounded_recommendation_provider()
    order = await _node_order(provider, tenant_id=tenant_id, conversation_id=conversation_id)
    assert order == ["agent", "price_gate", "inspection"]

    provider = _grounded_recommendation_provider()
    final_state = await _final_state(provider, tenant_id=tenant_id, conversation_id=conversation_id)
    assert final_state["draft_response"] == "Item One is a durable widget."
    assert final_state["author_node"] == "agent"
    assert final_state["selections"]
    assert provider.draft_prompts == []


async def test_grounded_prose_citations_name_the_tool_chunks(
    superuser_conn: asyncpg.Connection[Any],
) -> None:
    """Citations on the new path come from the chunks the tool handed the model,
    which is exactly what the prose was written from."""
    tenant_id, conversation_id = await _seed_tenant_with_chunk_and_conversation(superuser_conn)
    provider = _grounded_knowledge_provider()
    graph = build_graph()
    initial_state = _initial_state(tenant_id=tenant_id, conversation_id=conversation_id)
    events: list[dict[str, Any]] = []
    async for event in graph.astream(
        initial_state, context=_context_for(provider, tenant_id=tenant_id), stream_mode="custom"
    ):
        events.append(event)

    citation_events = [event for event in events if event.get("type") == "citations"]
    assert len(citation_events) == 1
    assert citation_events[0]["citations"] == [
        {
            "index": 1,
            "source": "faq.md",
            "snippet": "We are open weekdays 9-5.",
        }
    ]
