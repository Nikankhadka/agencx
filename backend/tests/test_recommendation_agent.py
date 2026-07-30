"""T-044: Recommendation agent tests - tool-driven agent node calls
recommend_items tool, draft node composes recommendation from selections.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator
from typing import Any

import asyncpg
import pytest

from app.agents.graph import build_graph
from app.agents.state import AgentState, GraphContext
from app.core import db
from app.ingestion.chunker import chunk_catalog_item
from app.llm.provider import ToolCall, ToolTurn
from app.retrieval.rerank import Reranker
from app.retrieval.types import RetrievedChunk
from tests.conftest import _app_dsn_for
from tests.fakes import EMBEDDING_DIM, ToolAwareFakeProvider, ZeroEmbedder

pytestmark = pytest.mark.db


class PassthroughReranker(Reranker):
    async def rerank(
        self, *, query: str, candidates: list[RetrievedChunk], top_k: int
    ) -> list[RetrievedChunk]:
        return candidates[:top_k]


def _initial_state(message: str) -> AgentState:
    return {
        "conversation_id": "test",
        "tenant_id": "test",
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


async def _seed_catalog(
    conn: asyncpg.Connection[Any], items: list[tuple[str, str, int | None]]
) -> tuple[uuid.UUID, list[uuid.UUID]]:
    tenant_id: uuid.UUID = await conn.fetchval(
        "insert into tenants (slug, name) values ($1, 'Recommend Test Co') returning id",
        f"recommend-{uuid.uuid4().hex[:8]}",
    )
    await conn.execute("insert into tenant_config (tenant_id) values ($1)", tenant_id)
    document_id: uuid.UUID = await conn.fetchval(
        "insert into documents (tenant_id, filename, doc_type, status) "
        "values ($1, 'catalog', 'catalog', 'ready') returning id",
        tenant_id,
    )
    item_ids = []
    for name, description, price_cents in items:
        item_id: uuid.UUID = await conn.fetchval(
            "insert into catalog_items (tenant_id, name, description, price_cents) "
            "values ($1, $2, $3, $4) returning id",
            tenant_id, name, description, price_cents,
        )
        item_ids.append(item_id)
        chunk = chunk_catalog_item(str(item_id), name, description, price_cents)
        await conn.execute(
            "insert into knowledge_chunks (tenant_id, document_id, content, embedding, metadata) "
            "values ($1, $2, $3, $4, $5)",
            tenant_id, document_id, chunk.content,
            [0.0] * EMBEDDING_DIM, json.dumps(chunk.metadata),
        )
    return tenant_id, item_ids


def _recommendation_provider(*, stream_text: str = "Try item one.") -> ToolAwareFakeProvider:
    return ToolAwareFakeProvider(
        tool_call_sequence=[
            ToolTurn(tool_calls=[
                ToolCall(id="call_r", name="recommend_items", args={"preferences": "durable"}),
            ]),
            ToolTurn(text="ok", tool_calls=[]),
        ],
        stream_text=stream_text,
        extract_route="recommendation",
    )


@pytest.fixture(autouse=True)
async def _pool(migrated_db: str) -> AsyncIterator[None]:
    await db.create_pool(dsn=_app_dsn_for(migrated_db), min_size=1, max_size=4)
    yield
    await db.close_pool()


async def test_recommendation_selections_are_subset_of_catalog(
    superuser_conn: asyncpg.Connection[Any],
) -> None:
    tenant_id, item_ids = await _seed_catalog(
        superuser_conn,
        [("Item One", "A durable widget", 4900), ("Item Two", "A fragile gadget", 2900)],
    )
    graph = build_graph()
    context = GraphContext(
        tenant_id=tenant_id,
        provider=_recommendation_provider(),
        embedder=ZeroEmbedder(),
        reranker=PassthroughReranker(),
    )
    final_state = await graph.ainvoke(_initial_state("I need something durable"), context=context)
    selections = final_state["selections"]
    assert selections
    selected_ids = {s["catalog_item_id"] for s in selections}
    assert selected_ids.issubset({str(i) for i in item_ids})


async def test_recommendation_price_comes_from_db_column(
    superuser_conn: asyncpg.Connection[Any],
) -> None:
    tenant_id, _item_ids = await _seed_catalog(
        superuser_conn, [("Item One", "A durable widget", 4900)]
    )
    graph = build_graph()
    context = GraphContext(
        tenant_id=tenant_id,
        provider=_recommendation_provider(),
        embedder=ZeroEmbedder(),
        reranker=PassthroughReranker(),
    )
    final_state = await graph.ainvoke(_initial_state("I need something durable"), context=context)
    assert final_state["selections"][0]["price_cents"] == 4900


async def test_recommendation_refuses_when_catalog_is_empty(
    superuser_conn: asyncpg.Connection[Any],
) -> None:
    tenant_id: uuid.UUID = await superuser_conn.fetchval(
        "insert into tenants (slug, name) values ($1, 'Empty Catalog Co') returning id",
        f"recommend-empty-{uuid.uuid4().hex[:8]}",
    )
    await superuser_conn.execute("insert into tenant_config (tenant_id) values ($1)", tenant_id)
    graph = build_graph()
    context = GraphContext(
        tenant_id=tenant_id,
        provider=_recommendation_provider(),
        embedder=ZeroEmbedder(),
        reranker=PassthroughReranker(),
    )
    final_state = await graph.ainvoke(_initial_state("I need something"), context=context)
    assert final_state["selections"] == []
    assert "don't have anything" in final_state["draft_response"]
