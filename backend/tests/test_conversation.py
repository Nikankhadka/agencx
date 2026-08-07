"""T-044: conversation node tests with tool-driven agent - no tools
called routes to "conversation", draft node composes greeting.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import Any

import asyncpg
import pytest

from app.agents.graph import build_graph
from app.agents.state import AgentState, GraphContext
from app.llm.provider import ToolTurn
from app.retrieval.rerank import Reranker
from app.retrieval.types import RetrievedChunk
from app.shared import db
from tests.conftest import _app_dsn_for
from tests.fakes import ToolAwareFakeProvider, ZeroEmbedder

pytestmark = pytest.mark.db


async def _seed_tenant_with_conversation(
    conn: asyncpg.Connection[Any],
) -> tuple[uuid.UUID, uuid.UUID]:
    tenant_id: uuid.UUID = await conn.fetchval(
        "insert into tenants (slug, name) values ($1, 'Conversation Test Co') returning id",
        f"convo-{uuid.uuid4().hex[:8]}",
    )
    await conn.execute("insert into tenant_config (tenant_id) values ($1)", tenant_id)
    conversation_id: uuid.UUID = await conn.fetchval(
        "insert into conversations (tenant_id) values ($1) returning id", tenant_id
    )
    return tenant_id, conversation_id


def _initial_state(
    tenant_id: uuid.UUID, conversation_id: uuid.UUID, message: str = "hi"
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


class NoopReranker(Reranker):
    async def rerank(
        self, *, query: str, candidates: list[RetrievedChunk], top_k: int
    ) -> list[RetrievedChunk]:
        return candidates[:top_k]


def _conversation_provider(*, stream_text: str) -> ToolAwareFakeProvider:
    return ToolAwareFakeProvider(
        tool_call_sequence=[ToolTurn(text="Greeting response", tool_calls=[])],
        stream_text=stream_text,
        extract_route="conversation",
    )


@pytest.fixture(autouse=True)
async def _pool(migrated_db: str) -> AsyncIterator[None]:
    await db.create_pool(dsn=_app_dsn_for(migrated_db), min_size=1, max_size=4)
    yield
    await db.close_pool()


async def test_conversation_route_produces_draft_response(
    superuser_conn: asyncpg.Connection[Any],
) -> None:
    tenant_id, conversation_id = await _seed_tenant_with_conversation(superuser_conn)
    graph = build_graph()
    context = GraphContext(
        tenant_id=tenant_id,
        provider=_conversation_provider(
            stream_text="Hello! I'm the virtual assistant here. How can I help you today?"
        ),
        embedder=ZeroEmbedder(),
        reranker=NoopReranker(),
    )
    final_state = await graph.ainvoke(
        _initial_state(tenant_id, conversation_id, "hi"), context=context
    )
    assert final_state["route"] == "conversation"
    assert final_state["draft_response"] != ""
    assert "Hello" in final_state["draft_response"]
    assert final_state.get("draft_deterministic") is False
    assert final_state["escalated"] is False


async def test_conversation_route_does_not_escalate(
    superuser_conn: asyncpg.Connection[Any],
) -> None:
    tenant_id, conversation_id = await _seed_tenant_with_conversation(superuser_conn)
    graph = build_graph()
    context = GraphContext(
        tenant_id=tenant_id,
        provider=_conversation_provider(stream_text="Hello! I'm the virtual assistant here."),
        embedder=ZeroEmbedder(),
        reranker=NoopReranker(),
    )
    final_state = await graph.ainvoke(
        _initial_state(tenant_id, conversation_id, "hi"), context=context
    )
    assert final_state["escalated"] is False
    status = await superuser_conn.fetchval(
        "select status from conversations where id = $1", conversation_id
    )
    assert status != "escalated"
    assert status == "open"
