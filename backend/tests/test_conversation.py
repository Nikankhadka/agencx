"""T-043: conversation node tests with a stubbed provider."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import Any

import asyncpg
import pytest

from app.agents.graph import build_graph
from app.agents.state import AgentState, GraphContext
from app.core import db
from app.llm.provider import ChatMessage, SchemaT
from app.retrieval.rerank import Reranker
from app.retrieval.types import RetrievedChunk
from tests.conftest import _app_dsn_for
from tests.fakes import BaseFakeProvider, ZeroEmbedder

pytestmark = pytest.mark.db


async def _seed_tenant_with_conversation(
    conn: asyncpg.Connection[Any], *, escalation_threshold: float = 0.5
) -> tuple[uuid.UUID, uuid.UUID]:
    tenant_id: uuid.UUID = await conn.fetchval(
        "insert into tenants (slug, name) values ($1, 'Conversation Test Co') returning id",
        f"convo-{uuid.uuid4().hex[:8]}",
    )
    await conn.execute(
        "insert into tenant_config (tenant_id, escalation_threshold) values ($1, $2)",
        tenant_id,
        escalation_threshold,
    )
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


def _forced_route(route: str):
    async def supervisor_stub(state: AgentState) -> dict[str, Any]:
        return {"route": route, "route_confidence": 1.0}

    return supervisor_stub


class NoopReranker(Reranker):
    async def rerank(
        self, *, query: str, candidates: list[RetrievedChunk], top_k: int
    ) -> list[RetrievedChunk]:
        return candidates[:top_k]


class ConversationProvider(BaseFakeProvider):
    """Fake provider that supplies a greeting response via chat_stream and
    a route decision via extract."""

    def __init__(self, *, route: str, confidence: float) -> None:
        self._route = route
        self._confidence = confidence

    async def extract(
        self, *, system_prompt: str, user_input: str, schema: type[SchemaT]
    ) -> SchemaT:
        return schema.model_validate(
            {"route": self._route, "confidence": self._confidence, "reason": "test"}
        )

    async def chat_stream(self, messages: list[ChatMessage]) -> AsyncIterator[str]:
        yield "Hello! I'm the virtual assistant here. How can I help you today?"


@pytest.fixture(autouse=True)
async def _pool(migrated_db: str) -> AsyncIterator[None]:
    await db.create_pool(dsn=_app_dsn_for(migrated_db), min_size=1, max_size=4)
    yield
    await db.close_pool()


async def test_conversation_route_produces_draft_response(
    superuser_conn: asyncpg.Connection[Any],
) -> None:
    """The conversation node generates a greeting response and sets
    draft_deterministic: False so inspection still runs."""
    tenant_id, conversation_id = await _seed_tenant_with_conversation(superuser_conn)
    graph = build_graph(supervisor_node=_forced_route("conversation"))
    context = GraphContext(
        tenant_id=tenant_id,
        provider=ConversationProvider(route="conversation", confidence=0.9),
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
    """A greeting is a high-confidence conversation classification and
    should not escalate to a human."""
    tenant_id, conversation_id = await _seed_tenant_with_conversation(superuser_conn)
    graph = build_graph(supervisor_node=_forced_route("conversation"))
    context = GraphContext(
        tenant_id=tenant_id,
        provider=ConversationProvider(route="conversation", confidence=0.9),
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


async def test_conversation_below_threshold_still_escalates(
    superuser_conn: asyncpg.Connection[Any],
) -> None:
    """An ambiguous message below the confidence threshold still escalates
    even if the model picked 'conversation' - the gate still applies."""
    tenant_id, conversation_id = await _seed_tenant_with_conversation(
        superuser_conn, escalation_threshold=0.5
    )
    graph = build_graph()
    context = GraphContext(
        tenant_id=tenant_id,
        provider=ConversationProvider(route="conversation", confidence=0.2),
        embedder=ZeroEmbedder(),
        reranker=NoopReranker(),
    )

    final_state = await graph.ainvoke(
        _initial_state(tenant_id, conversation_id, "asdkjfh asdkjfh"), context=context
    )

    # Low confidence force-escalates regardless of route - the confidence gate
    # still applies to conversation.
    assert final_state["route"] == "escalation"
    assert final_state["escalated"] is True
