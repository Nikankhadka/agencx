"""T-044: Escalation agent tests - tool-driven agent node calls
create_escalation tool, escalation node creates DB rows.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator
from typing import Any

import asyncpg
import pytest

from app.agents.escalation import HANDOFF_MESSAGE, contact_ask, handoff_message
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


def _initial_state(*, tenant_id: uuid.UUID, conversation_id: uuid.UUID) -> AgentState:
    return {
        "conversation_id": str(conversation_id),
        "tenant_id": str(tenant_id),
        "messages": [{"role": "customer", "content": "I want to talk to a human"}],
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
    await db.create_pool(dsn=_app_dsn_for(migrated_db), min_size=1, max_size=4)
    yield
    await db.close_pool()


async def _seed_tenant_with_conversation(
    conn: asyncpg.Connection[Any],
) -> tuple[uuid.UUID, uuid.UUID]:
    tenant_id: uuid.UUID = await conn.fetchval(
        "insert into tenants (slug, name) values ($1, 'Escalation Test Co') returning id",
        f"escalation-{uuid.uuid4().hex[:8]}",
    )
    await conn.execute("insert into tenant_config (tenant_id) values ($1)", tenant_id)
    conversation_id: uuid.UUID = await conn.fetchval(
        "insert into conversations (tenant_id) values ($1) returning id", tenant_id
    )
    return tenant_id, conversation_id


def _escalation_provider(*, reason: str, intent: str | None = None) -> ToolAwareFakeProvider:
    args: dict[str, Any] = {"reason": reason}
    if intent is not None:
        args["intent"] = intent
    return ToolAwareFakeProvider(
        tool_call_sequence=[
            ToolTurn(
                tool_calls=[
                    ToolCall(id="call_e", name="create_escalation", args=args),
                ]
            ),
        ],
        stream_text="",
        extract_route="escalation",
    )


def test_handoff_message_is_the_exact_specified_string() -> None:
    """W-9 box 6 (slice 1.4): the ticket specifies this literal string, apostrophe
    included. The other tests in this file compare a draft response against
    ``handoff_message(...)`` (which is built from this constant), so they would
    still pass if the constant's text changed to anything at all - this is the
    one place "exact" is pinned against a literal copy, so a future edit to the
    constant fails a test instead of silently redefining what "exact" means.

    The apostrophe below is U+2019 (right single quote), not ASCII U+0027,
    matching the byte actually shipped in app/agents/escalation.py.
    """
    expected = "I’ve forwarded your query to the business. They can reply to you here."
    assert HANDOFF_MESSAGE == expected


async def test_escalation_records_the_handoff_and_leaves_the_chat_open(
    superuser_conn: asyncpg.Connection[Any],
) -> None:
    """C-5's core claim: escalating notifies a human without ending the chat."""
    tenant_id, conversation_id = await _seed_tenant_with_conversation(superuser_conn)
    graph = build_graph()
    context = GraphContext(
        tenant_id=tenant_id,
        provider=_escalation_provider(reason="customer_request"),
        embedder=ZeroEmbedder(),
        reranker=NoopReranker(),
    )
    final_state = await graph.ainvoke(
        _initial_state(tenant_id=tenant_id, conversation_id=conversation_id), context=context
    )
    assert final_state["escalated"] is True
    assert final_state["draft_response"] == handoff_message(name_known=False, email_known=False)
    escalation_row = await superuser_conn.fetchrow(
        "select reason, status from escalations where conversation_id = $1", conversation_id
    )
    assert escalation_row is not None
    assert escalation_row["reason"] == "customer_request"
    assert escalation_row["status"] == "open"
    conversation_status = await superuser_conn.fetchval(
        "select status from conversations where id = $1", conversation_id
    )
    assert conversation_status == "open"


async def test_escalation_is_scoped_to_its_own_tenant(
    superuser_conn: asyncpg.Connection[Any],
) -> None:
    tenant_a, conversation_a = await _seed_tenant_with_conversation(superuser_conn)
    tenant_b, conversation_b = await _seed_tenant_with_conversation(superuser_conn)
    graph = build_graph()
    context = GraphContext(
        tenant_id=tenant_a,
        provider=_escalation_provider(reason="low_confidence"),
        embedder=ZeroEmbedder(),
        reranker=NoopReranker(),
    )
    await graph.ainvoke(
        _initial_state(tenant_id=tenant_a, conversation_id=conversation_a), context=context
    )
    status_b = await superuser_conn.fetchval(
        "select status from conversations where id = $1", conversation_b
    )
    assert status_b == "open"
    escalations_for_b = await superuser_conn.fetchval(
        "select count(*) from escalations where conversation_id = $1", conversation_b
    )
    assert escalations_for_b == 0


async def test_concurrent_escalations_on_same_conversation_do_not_duplicate(
    superuser_conn: asyncpg.Connection[Any],
) -> None:
    tenant_id, conversation_id = await _seed_tenant_with_conversation(superuser_conn)
    graph = build_graph()
    context = GraphContext(
        tenant_id=tenant_id,
        provider=_escalation_provider(reason="low_confidence"),
        embedder=ZeroEmbedder(),
        reranker=NoopReranker(),
    )
    await asyncio.gather(
        graph.ainvoke(
            _initial_state(tenant_id=tenant_id, conversation_id=conversation_id), context=context
        ),
        graph.ainvoke(
            _initial_state(tenant_id=tenant_id, conversation_id=conversation_id), context=context
        ),
    )
    open_escalations = await superuser_conn.fetchval(
        "select count(*) from escalations where conversation_id = $1 and status = 'open'",
        conversation_id,
    )
    assert open_escalations == 1
    status = await superuser_conn.fetchval(
        "select status from conversations where id = $1", conversation_id
    )
    assert status == "open"


# --- C-5: what happens *after* a handoff ------------------------------------


async def test_the_conversation_keeps_working_after_a_handoff(
    superuser_conn: asyncpg.Connection[Any],
) -> None:
    """Escalate, then ask something else on the same conversation and get a
    real answer.

    This is the failure C-5 exists to remove: one unanswerable question used to
    end a session that was working fine for everything else.
    """
    tenant_id, conversation_id = await _seed_tenant_with_conversation(superuser_conn)
    graph = build_graph()

    await graph.ainvoke(
        _initial_state(tenant_id=tenant_id, conversation_id=conversation_id),
        context=GraphContext(
            tenant_id=tenant_id,
            provider=_escalation_provider(reason="customer_request"),
            embedder=ZeroEmbedder(),
            reranker=NoopReranker(),
        ),
    )

    follow_up = _initial_state(tenant_id=tenant_id, conversation_id=conversation_id)
    follow_up["messages"] = [{"role": "customer", "content": "what are your hours?"}]
    second_state = await graph.ainvoke(
        follow_up,
        context=GraphContext(
            tenant_id=tenant_id,
            provider=ToolAwareFakeProvider(
                tool_call_sequence=[ToolTurn(text="We're open 9 to 5.", tool_calls=[])],
                stream_text="We're open 9 to 5.",
                extract_route="conversation",
            ),
            embedder=ZeroEmbedder(),
            reranker=NoopReranker(),
        ),
    )

    assert second_state["escalated"] is False
    assert second_state["draft_response"] == "We're open 9 to 5."
    assert (
        await superuser_conn.fetchval(
            "select status from conversations where id = $1", conversation_id
        )
        == "open"
    )


async def test_a_second_handoff_does_not_queue_a_duplicate_for_the_owner(
    superuser_conn: asyncpg.Connection[Any],
) -> None:
    """The chat continues, so it may hand off again - the owner should still
    see one open item, not one per attempt."""
    tenant_id, conversation_id = await _seed_tenant_with_conversation(superuser_conn)
    graph = build_graph()
    for reason in ("customer_request", "customer_request_again"):
        await graph.ainvoke(
            _initial_state(tenant_id=tenant_id, conversation_id=conversation_id),
            context=GraphContext(
                tenant_id=tenant_id,
                provider=_escalation_provider(reason=reason),
                embedder=ZeroEmbedder(),
                reranker=NoopReranker(),
            ),
        )
    open_rows = await superuser_conn.fetchval(
        "select count(*) from escalations where conversation_id = $1 and status = 'open'",
        conversation_id,
    )
    assert open_rows == 1


# --- intent + contact capture on the handoff ---------------------------------


async def test_escalation_row_carries_the_tool_intent(
    superuser_conn: asyncpg.Connection[Any],
) -> None:
    tenant_id, conversation_id = await _seed_tenant_with_conversation(superuser_conn)
    graph = build_graph()
    context = GraphContext(
        tenant_id=tenant_id,
        provider=_escalation_provider(reason="customer_request", intent="support"),
        embedder=ZeroEmbedder(),
        reranker=NoopReranker(),
    )
    final_state = await graph.ainvoke(
        _initial_state(tenant_id=tenant_id, conversation_id=conversation_id), context=context
    )
    assert final_state["intent"] == "support"
    assert final_state["action"] == "escalate"
    row_intent = await superuser_conn.fetchval(
        "select intent from escalations where conversation_id = $1", conversation_id
    )
    assert row_intent == "support"


async def test_unknown_tool_intent_still_escalates_and_writes_null(
    superuser_conn: asyncpg.Connection[Any],
) -> None:
    tenant_id, conversation_id = await _seed_tenant_with_conversation(superuser_conn)
    graph = build_graph()
    context = GraphContext(
        tenant_id=tenant_id,
        provider=_escalation_provider(reason="customer_request", intent="not-a-family"),
        embedder=ZeroEmbedder(),
        reranker=NoopReranker(),
    )
    final_state = await graph.ainvoke(
        _initial_state(tenant_id=tenant_id, conversation_id=conversation_id), context=context
    )
    assert final_state["escalated"] is True
    assert final_state.get("intent") is None
    row_intent = await superuser_conn.fetchval(
        "select intent from escalations where conversation_id = $1", conversation_id
    )
    assert row_intent is None


async def test_known_contact_handoff_omits_the_ask(
    superuser_conn: asyncpg.Connection[Any],
) -> None:
    tenant_id, conversation_id = await _seed_tenant_with_conversation(superuser_conn)
    await superuser_conn.execute(
        "update conversations set customer_ref = 'Sam', customer_email = 'sam@example.com' "
        "where id = $1",
        conversation_id,
    )
    graph = build_graph()
    context = GraphContext(
        tenant_id=tenant_id,
        provider=_escalation_provider(reason="customer_request"),
        embedder=ZeroEmbedder(),
        reranker=NoopReranker(),
    )
    final_state = await graph.ainvoke(
        _initial_state(tenant_id=tenant_id, conversation_id=conversation_id), context=context
    )
    assert final_state["draft_response"] == HANDOFF_MESSAGE


async def test_contact_set_in_the_same_turn_omits_the_ask(
    superuser_conn: asyncpg.Connection[Any],
) -> None:
    """The flags are run-local: storing contact before the handoff in one turn
    is enough to suppress the ask in that same reply."""
    tenant_id, conversation_id = await _seed_tenant_with_conversation(superuser_conn)
    provider = ToolAwareFakeProvider(
        tool_call_sequence=[
            ToolTurn(
                tool_calls=[
                    ToolCall(
                        id="call_c",
                        name="set_customer_contact",
                        args={"name": "Sam", "email": "sam@example.com"},
                    ),
                ]
            ),
            ToolTurn(
                tool_calls=[
                    ToolCall(
                        id="call_e",
                        name="create_escalation",
                        args={"reason": "customer_request"},
                    )
                ]
            ),
        ],
        stream_text="",
        extract_route="escalation",
    )
    graph = build_graph()
    context = GraphContext(
        tenant_id=tenant_id,
        provider=provider,
        embedder=ZeroEmbedder(),
        reranker=NoopReranker(),
    )
    final_state = await graph.ainvoke(
        _initial_state(tenant_id=tenant_id, conversation_id=conversation_id), context=context
    )
    assert final_state["draft_response"] == HANDOFF_MESSAGE
    row = await superuser_conn.fetchrow(
        "select customer_ref, customer_email from conversations where id = $1",
        conversation_id,
    )
    assert row is not None
    assert row["customer_ref"] == "Sam"
    assert row["customer_email"] == "sam@example.com"


async def test_replying_with_a_name_after_a_handoff_stores_it_and_does_not_hand_off_again(
    superuser_conn: asyncpg.Connection[Any],
) -> None:
    """The customer answers the contact ask ("Jordan") and the model, seeing a
    handoff in the transcript, calls create_escalation again. That duplicate
    must not re-stream the handoff text and its ask, and must leave the model
    free to store the name."""
    tenant_id, conversation_id = await _seed_tenant_with_conversation(superuser_conn)
    graph = build_graph()

    async def stream_turn(provider: ToolAwareFakeProvider, message: str) -> list[dict[str, Any]]:
        state = _initial_state(tenant_id=tenant_id, conversation_id=conversation_id)
        state["messages"] = [{"role": "customer", "content": message}]
        context = GraphContext(
            tenant_id=tenant_id,
            provider=provider,
            embedder=ZeroEmbedder(),
            reranker=NoopReranker(),
        )
        stream = graph.astream(state, context=context, stream_mode="custom")
        return [event async for event in stream]

    first_events = await stream_turn(
        _escalation_provider(reason="customer_request"), "I'd like to speak to a real person"
    )
    first_text = " ".join(str(event.get("text", "")) for event in first_events)
    assert {"type": "handoff"} in first_events
    assert handoff_message(name_known=False, email_known=False) in first_text

    reply = "Thanks Jordan - the team will pick this up here."
    provider = ToolAwareFakeProvider(
        tool_call_sequence=[
            ToolTurn(
                tool_calls=[
                    ToolCall(
                        id="call_e", name="create_escalation", args={"reason": "customer_request"}
                    )
                ]
            ),
            ToolTurn(
                tool_calls=[
                    ToolCall(id="call_c", name="set_customer_contact", args={"name": "Jordan"})
                ]
            ),
            ToolTurn(text=reply, tool_calls=[]),
        ],
        stream_text=reply,
        extract_route="conversation",
    )
    events = await stream_turn(provider, "Jordan")

    text = " ".join(str(event.get("text", "")) for event in events)
    assert {"type": "handoff"} not in events
    assert HANDOFF_MESSAGE not in text
    assert contact_ask(name_known=False, email_known=False) not in text
    assert reply in text
    tool_events = [event for event in events if event.get("type") == "tool_call"]
    assert [(e["name"], e["result"]) for e in tool_events] == [
        ("create_escalation", {"escalated": False, "already_open": True}),
        ("set_customer_contact", {"stored": True}),
    ]
    assert "already_open" in provider.tool_call_messages[1][-1]["content"]
    assert (
        await superuser_conn.fetchval(
            "select customer_ref from conversations where id = $1", conversation_id
        )
        == "Jordan"
    )
    assert (
        await superuser_conn.fetchval(
            "select count(*) from escalations where conversation_id = $1 and status = 'open'",
            conversation_id,
        )
        == 1
    )
