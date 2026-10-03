"""RF-10: the opening-phase preferred-name ask, its persisted cap, and the
customer-facing contact event.

The opening phase is the window before the first escalation or handoff (D39).
The agent node runs exactly once per turn, so the ask counter is deterministic:
the node appends the ask instruction and increments ``opening_name_asks`` in the
same turn, and after two asks the prompt goes quiet. These tests drive the real
graph against a real seeded conversation and a recording fake provider, then
assert the system prompt the model actually received and the row the turn wrote.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import Any

import asyncpg
import pytest

from app.agents.agent_node import _OPENING_NAME_GUIDANCE, _OPENING_NAME_SUPPRESS
from app.agents.graph import build_graph
from app.agents.state import AgentState, GraphContext
from app.llm.provider import ToolCall, ToolTurn
from app.retrieval.rerank import Reranker
from app.retrieval.types import RetrievedChunk
from app.services.context_package import clear_cache
from app.shared import db
from tests.conftest import _app_dsn_for
from tests.fakes import ToolAwareFakeProvider, ZeroEmbedder

pytestmark = pytest.mark.db


class NoopReranker(Reranker):
    async def rerank(
        self, *, query: str, candidates: list[RetrievedChunk], top_k: int
    ) -> list[RetrievedChunk]:
        return candidates[:top_k]


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


@pytest.fixture(autouse=True)
async def _pool(migrated_db: str) -> AsyncIterator[None]:
    clear_cache()
    await db.create_pool(dsn=_app_dsn_for(migrated_db), min_size=1, max_size=4)
    yield
    await db.close_pool()
    clear_cache()


async def _seed_tenant_with_conversation(
    conn: asyncpg.Connection[Any],
) -> tuple[uuid.UUID, uuid.UUID]:
    tenant_id: uuid.UUID = await conn.fetchval(
        "insert into tenants (slug, name) values ($1, 'Name Test Co') returning id",
        f"name-{uuid.uuid4().hex[:8]}",
    )
    await conn.execute("insert into tenant_config (tenant_id) values ($1)", tenant_id)
    conversation_id: uuid.UUID = await conn.fetchval(
        "insert into conversations (tenant_id) values ($1) returning id", tenant_id
    )
    return tenant_id, conversation_id


def _prose_provider(text: str = "Hi there.") -> ToolAwareFakeProvider:
    return ToolAwareFakeProvider(
        tool_call_sequence=[ToolTurn(text=text, tool_calls=[])],
        stream_text=text,
        extract_route="conversation",
    )


async def _run_turn(
    *, tenant_id: uuid.UUID, conversation_id: uuid.UUID, provider: ToolAwareFakeProvider
) -> list[dict[str, Any]]:
    graph = build_graph()
    context = GraphContext(
        tenant_id=tenant_id,
        provider=provider,
        embedder=ZeroEmbedder(),
        reranker=NoopReranker(),
    )
    return [
        event
        async for event in graph.astream(
            _initial_state(tenant_id=tenant_id, conversation_id=conversation_id),
            context=context,
            stream_mode="custom",
        )
    ]


def _system_prompt_seen(provider: ToolAwareFakeProvider) -> str:
    assert provider.tool_call_messages, "the agent node never called the provider"
    return provider.tool_call_messages[0][0]["content"]


async def _ask_count(conn: asyncpg.Connection[Any], conversation_id: uuid.UUID) -> int:
    value = await conn.fetchval(
        "select opening_name_asks from conversations where id = $1", conversation_id
    )
    assert isinstance(value, int)
    return value


async def test_opening_asks_are_capped_at_two_then_suppressed(
    superuser_conn: asyncpg.Connection[Any],
) -> None:
    tenant_id, conversation_id = await _seed_tenant_with_conversation(superuser_conn)

    # Turn 1 and turn 2 each carry the ask instruction and bump the counter.
    for expected in (1, 2):
        provider = _prose_provider()
        await _run_turn(tenant_id=tenant_id, conversation_id=conversation_id, provider=provider)
        prompt = _system_prompt_seen(provider)
        assert _OPENING_NAME_GUIDANCE in prompt
        assert _OPENING_NAME_SUPPRESS not in prompt
        assert await _ask_count(superuser_conn, conversation_id) == expected

    # Turn 3 appends no ask: the suppression line instead, and the cap holds.
    provider = _prose_provider()
    await _run_turn(tenant_id=tenant_id, conversation_id=conversation_id, provider=provider)
    prompt = _system_prompt_seen(provider)
    assert _OPENING_NAME_GUIDANCE not in prompt
    assert _OPENING_NAME_SUPPRESS in prompt
    assert await _ask_count(superuser_conn, conversation_id) == 2


async def test_a_known_name_never_asks_again_and_reamounces_the_name(
    superuser_conn: asyncpg.Connection[Any],
) -> None:
    tenant_id, conversation_id = await _seed_tenant_with_conversation(superuser_conn)
    await superuser_conn.execute(
        "update conversations set customer_ref = 'Sam' where id = $1", conversation_id
    )

    provider = _prose_provider()
    events = await _run_turn(
        tenant_id=tenant_id, conversation_id=conversation_id, provider=provider
    )
    prompt = _system_prompt_seen(provider)
    assert _OPENING_NAME_GUIDANCE not in prompt
    assert _OPENING_NAME_SUPPRESS not in prompt
    assert "never ask for their name again" in prompt
    assert await _ask_count(superuser_conn, conversation_id) == 0
    # The stored name is re-announced to the customer surface at turn start.
    assert {"type": "contact", "name": "Sam"} in events


async def test_a_handoff_ends_the_opening_phase_and_stops_the_ask(
    superuser_conn: asyncpg.Connection[Any],
) -> None:
    tenant_id, conversation_id = await _seed_tenant_with_conversation(superuser_conn)
    await superuser_conn.execute(
        "insert into escalations (tenant_id, conversation_id, reason) values ($1, $2, 'human')",
        tenant_id,
        conversation_id,
    )

    provider = _prose_provider()
    await _run_turn(tenant_id=tenant_id, conversation_id=conversation_id, provider=provider)
    prompt = _system_prompt_seen(provider)
    assert _OPENING_NAME_GUIDANCE not in prompt
    # A handoff is not the cap; nothing is appended at all.
    assert _OPENING_NAME_SUPPRESS not in prompt
    assert await _ask_count(superuser_conn, conversation_id) == 0


async def test_set_customer_contact_emits_a_contact_event_without_email(
    superuser_conn: asyncpg.Connection[Any],
) -> None:
    tenant_id, conversation_id = await _seed_tenant_with_conversation(superuser_conn)
    provider = ToolAwareFakeProvider(
        tool_call_sequence=[
            ToolTurn(
                tool_calls=[
                    ToolCall(
                        id="call_contact",
                        name="set_customer_contact",
                        args={"name": "Sam", "email": "sam@example.com"},
                    )
                ]
            ),
            ToolTurn(text="Nice to meet you, Sam.", tool_calls=[]),
        ],
        extract_route="conversation",
    )

    events = await _run_turn(
        tenant_id=tenant_id, conversation_id=conversation_id, provider=provider
    )
    contacts = [event for event in events if event.get("type") == "contact"]
    assert {"type": "contact", "name": "Sam"} in contacts
    # Email is owner-only (ticket 19): the customer surface never receives it.
    assert all("email" not in event for event in contacts)
    assert (
        await superuser_conn.fetchval(
            "select customer_ref from conversations where id = $1", conversation_id
        )
        == "Sam"
    )
