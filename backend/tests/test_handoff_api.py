"""RF-11: POST /api/chat/handoff - the deterministic customer-initiated handoff.

The visible "Ask for a person" control must record the same escalation row the
assistant's ``create_escalation`` tool would and stream the same handoff reply,
without depending on the model choosing the tool. These tests drive the HTTP
boundary directly (no live provider); the assistant tool path's own behavior
stays covered in ``test_escalation_agent.py``, and ticket 19's one-ask logic in
``app/agents/escalation.py`` is reused, not re-implemented.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator
from typing import Any

import asyncpg
import httpx
import pytest
import pytest_asyncio

from app.agents.escalation import HANDOFF_MESSAGE, contact_ask, handoff_message
from app.main import app
from app.retrieval.rerank import Reranker
from app.retrieval.types import RetrievedChunk
from app.shared import db
from tests.conftest import _app_dsn_for

pytestmark = pytest.mark.db


@pytest_asyncio.fixture
async def client(migrated_db: str) -> AsyncIterator[httpx.AsyncClient]:
    await db.create_pool(dsn=_app_dsn_for(migrated_db), min_size=1, max_size=4)
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac
    finally:
        await db.close_pool()


def _parse_sse(text: str) -> list[dict[str, Any]]:
    return [
        json.loads(line.removeprefix("data: "))
        for line in text.splitlines()
        if line.startswith("data: ")
    ]


def _types(events: list[dict[str, Any]]) -> list[str]:
    return [event["type"] for event in events]


async def _seed_tenant(
    conn: asyncpg.Connection[Any], *, slug: str, status: str = "active"
) -> uuid.UUID:
    tenant_id: uuid.UUID = await conn.fetchval(
        "insert into tenants (slug, name, status) values ($1, 'Handoff Test Co', $2) returning id",
        slug,
        status,
    )
    await conn.execute("insert into tenant_config (tenant_id) values ($1)", tenant_id)
    return tenant_id


async def _seed_conversation(
    conn: asyncpg.Connection[Any],
    tenant_id: uuid.UUID,
    *,
    status: str = "open",
    name: str | None = None,
    email: str | None = None,
) -> uuid.UUID:
    conversation_id: uuid.UUID = await conn.fetchval(
        "insert into conversations (tenant_id, status, customer_ref, customer_email) "
        "values ($1, $2, $3, $4) returning id",
        tenant_id,
        status,
        name,
        email,
    )
    return conversation_id


async def test_handoff_unknown_slug_is_404(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/api/chat/handoff", json={"slug": f"no-such-{uuid.uuid4().hex[:8]}"}
    )
    assert response.status_code == 404


async def test_handoff_wrong_tenant_conversation_is_404(
    client: httpx.AsyncClient, superuser_conn: asyncpg.Connection[Any]
) -> None:
    slug_a = f"handoff-a-{uuid.uuid4().hex[:8]}"
    slug_b = f"handoff-b-{uuid.uuid4().hex[:8]}"
    tenant_a = await _seed_tenant(superuser_conn, slug=slug_a)
    await _seed_tenant(superuser_conn, slug=slug_b)
    conversation_id = await _seed_conversation(superuser_conn, tenant_a)

    response = await client.post(
        "/api/chat/handoff",
        json={"slug": slug_b, "conversation_id": str(conversation_id)},
    )
    assert response.status_code == 404


async def test_handoff_creates_an_open_escalation_and_asks_once(
    client: httpx.AsyncClient, superuser_conn: asyncpg.Connection[Any]
) -> None:
    """No conversation id: the endpoint creates one (a customer may want a
    person before typing), records one open escalation, and streams the
    deterministic handoff reply with the one contact ask."""
    slug = f"handoff-{uuid.uuid4().hex[:8]}"
    await _seed_tenant(superuser_conn, slug=slug)

    response = await client.post("/api/chat/handoff", json={"slug": slug})
    assert response.status_code == 200
    events = _parse_sse(response.text)
    assert _types(events) == ["conversation", "refusal", "handoff", "done"]

    conversation_id = uuid.UUID(events[0]["conversation_id"])
    assert events[1]["text"] == handoff_message(name_known=False, email_known=False)
    assert contact_ask(name_known=False, email_known=False) in events[1]["text"]

    row = await superuser_conn.fetchrow(
        "select reason, status from escalations where conversation_id = $1", conversation_id
    )
    assert row is not None
    assert row["reason"] == "human_requested"
    assert row["status"] == "open"
    conversation_status = await superuser_conn.fetchval(
        "select status from conversations where id = $1", conversation_id
    )
    assert conversation_status == "open"


async def test_handoff_with_complete_contact_omits_the_ask_and_leaks_no_detail(
    client: httpx.AsyncClient, superuser_conn: asyncpg.Connection[Any]
) -> None:
    slug = f"handoff-known-{uuid.uuid4().hex[:8]}"
    tenant_id = await _seed_tenant(superuser_conn, slug=slug)
    conversation_id = await _seed_conversation(
        superuser_conn, tenant_id, name="Sam", email="sam@example.com"
    )

    response = await client.post(
        "/api/chat/handoff",
        json={"slug": slug, "conversation_id": str(conversation_id)},
    )
    assert response.status_code == 200
    events = _parse_sse(response.text)
    assert _types(events) == ["conversation", "refusal", "handoff", "done"]
    assert events[1]["text"] == HANDOFF_MESSAGE
    # Contact is owner-only (ticket 19): neither half may ride the stream.
    assert "sam@example.com" not in response.text
    assert "Sam" not in response.text


async def test_a_second_handoff_does_not_duplicate_or_ask_again(
    client: httpx.AsyncClient, superuser_conn: asyncpg.Connection[Any]
) -> None:
    slug = f"handoff-twice-{uuid.uuid4().hex[:8]}"
    await _seed_tenant(superuser_conn, slug=slug)

    first = await client.post("/api/chat/handoff", json={"slug": slug})
    conversation_id = _parse_sse(first.text)[0]["conversation_id"]

    second = await client.post(
        "/api/chat/handoff",
        json={"slug": slug, "conversation_id": conversation_id},
    )
    assert second.status_code == 200
    second_events = _parse_sse(second.text)
    # Already open: no second reply and no second ask, only the handoff signal
    # that starts the client's human-reply poll.
    assert _types(second_events) == ["conversation", "handoff", "done"]

    count = await superuser_conn.fetchval(
        "select count(*) from escalations where conversation_id = $1",
        uuid.UUID(conversation_id),
    )
    assert count == 1


async def test_handoff_on_human_conversation_does_not_create_a_new_handoff(
    client: httpx.AsyncClient, superuser_conn: asyncpg.Connection[Any]
) -> None:
    slug = f"handoff-human-{uuid.uuid4().hex[:8]}"
    tenant_id = await _seed_tenant(superuser_conn, slug=slug)
    conversation_id = await _seed_conversation(superuser_conn, tenant_id, status="human")

    response = await client.post(
        "/api/chat/handoff",
        json={"slug": slug, "conversation_id": str(conversation_id)},
    )
    assert response.status_code == 200
    assert _types(_parse_sse(response.text)) == ["conversation", "handoff", "done"]
    assert (
        await superuser_conn.fetchval(
            "select count(*) from escalations where conversation_id = $1", conversation_id
        )
        == 0
    )
    assert (
        await superuser_conn.fetchval(
            "select status from conversations where id = $1", conversation_id
        )
        == "human"
    )


async def test_handoff_on_escalated_conversation_is_not_reopened(
    client: httpx.AsyncClient, superuser_conn: asyncpg.Connection[Any]
) -> None:
    slug = f"handoff-escalated-{uuid.uuid4().hex[:8]}"
    tenant_id = await _seed_tenant(superuser_conn, slug=slug)
    conversation_id = await _seed_conversation(superuser_conn, tenant_id, status="escalated")

    response = await client.post(
        "/api/chat/handoff",
        json={"slug": slug, "conversation_id": str(conversation_id)},
    )
    assert response.status_code == 200
    assert _types(_parse_sse(response.text)) == ["conversation", "escalated", "done"]
    assert (
        await superuser_conn.fetchval(
            "select count(*) from escalations where conversation_id = $1", conversation_id
        )
        == 0
    )
    assert (
        await superuser_conn.fetchval(
            "select status from conversations where id = $1", conversation_id
        )
        == "escalated"
    )


def test_assistant_tool_and_handoff_endpoint_share_one_writer() -> None:
    """The row writer is shared, so the two paths cannot drift: both
    module namespaces resolve ``record_escalation`` to the same function."""
    from app.agents import agent_node, escalation
    from app.features.chat import controller as chat_controller

    # vars() rather than attribute access: mypy's no-implicit-reexport treats a
    # module's imported names as non-exported, but the wiring is exactly what
    # this test pins.
    assert vars(agent_node)["record_escalation"] is escalation.record_escalation
    assert vars(chat_controller)["record_escalation"] is escalation.record_escalation


class _NoopReranker(Reranker):
    async def rerank(
        self, *, query: str, candidates: list[RetrievedChunk], top_k: int
    ) -> list[RetrievedChunk]:
        return candidates[:top_k]


async def test_assistant_tool_and_handoff_endpoint_write_the_same_row(
    client: httpx.AsyncClient, superuser_conn: asyncpg.Connection[Any]
) -> None:
    """Behavioral half of the shared-writer claim: the assistant's tool path
    and the deterministic endpoint produce identical escalation rows for the
    same reason."""
    from app.agents.graph import build_graph
    from app.agents.state import AgentState, GraphContext
    from app.llm.provider import ToolCall, ToolTurn
    from tests.fakes import ToolAwareFakeProvider, ZeroEmbedder

    slug = f"handoff-parity-{uuid.uuid4().hex[:8]}"
    tenant_id = await _seed_tenant(superuser_conn, slug=slug)
    tool_conversation = await _seed_conversation(superuser_conn, tenant_id)

    provider = ToolAwareFakeProvider(
        tool_call_sequence=[
            ToolTurn(
                tool_calls=[
                    ToolCall(
                        id="call_e",
                        name="create_escalation",
                        args={"reason": "human_requested"},
                    )
                ]
            )
        ],
        stream_text="",
        extract_route="escalation",
    )
    state: AgentState = {
        "conversation_id": str(tool_conversation),
        "tenant_id": str(tenant_id),
        "messages": [{"role": "customer", "content": "I want to talk to a person"}],
        "route": None,
        "route_confidence": None,
        "retrieved_chunks": [],
        "selections": [],
        "engine_quote": None,
        "draft_response": "",
        "inspection": None,
        "escalated": False,
    }
    await build_graph().ainvoke(
        state,
        context=GraphContext(
            tenant_id=tenant_id,
            provider=provider,
            embedder=ZeroEmbedder(),
            reranker=_NoopReranker(),
        ),
    )

    response = await client.post("/api/chat/handoff", json={"slug": slug})
    endpoint_conversation = uuid.UUID(_parse_sse(response.text)[0]["conversation_id"])

    async def row(conversation_id: uuid.UUID) -> dict[str, Any]:
        found = await superuser_conn.fetchrow(
            "select reason, summary, intent, status from escalations where conversation_id = $1",
            conversation_id,
        )
        assert found is not None
        return dict(found)

    assert await row(tool_conversation) == await row(endpoint_conversation)
