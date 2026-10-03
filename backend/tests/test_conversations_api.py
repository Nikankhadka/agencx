"""T-031: GET /api/conversations (list + detail), the tenant-admin
Conversations tab. Same JWT pattern as test_escalations_api.py.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import asyncpg
import httpx
import jwt
import pytest
import pytest_asyncio

from app.main import app
from app.shared import db
from app.shared.config import get_settings
from tests.conftest import _app_dsn_for

pytestmark = pytest.mark.db

TEST_JWT_SECRET = "test-only-supabase-jwt-secret-do-not-use-in-prod"  # noqa: S105


@pytest.fixture(autouse=True)
def _supabase_jwt_secret_env() -> Iterator[None]:
    original = os.environ.get("SUPABASE_JWT_SECRET")
    os.environ["SUPABASE_JWT_SECRET"] = TEST_JWT_SECRET
    get_settings.cache_clear()
    yield
    if original is None:
        os.environ.pop("SUPABASE_JWT_SECRET", None)
    else:
        os.environ["SUPABASE_JWT_SECRET"] = original
    get_settings.cache_clear()


@pytest_asyncio.fixture
async def client(migrated_db: str) -> AsyncIterator[httpx.AsyncClient]:
    await db.create_pool(dsn=_app_dsn_for(migrated_db), min_size=1, max_size=4)
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac
    finally:
        await db.close_pool()


def _make_token(user_id: uuid.UUID) -> str:
    now = int(time.time())
    payload = {"sub": str(user_id), "aud": "authenticated", "iat": now, "exp": now + 3600}
    return jwt.encode(payload, TEST_JWT_SECRET, algorithm="HS256")


async def _signup_tenant_admin(client: httpx.AsyncClient) -> tuple[str, uuid.UUID]:
    user_id = uuid.uuid4()
    token = _make_token(user_id)
    slug = f"conversations-api-{uuid.uuid4().hex[:8]}"
    response = await client.post(
        "/api/tenants",
        json={"slug": slug, "name": "Conversations API Test Co"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    return token, uuid.UUID(response.json()["tenant_id"])


async def _seed_conversation(
    conn: asyncpg.Connection[Any],
    tenant_id: uuid.UUID,
    *,
    status: str = "open",
    customer_ref: str | None = None,
    customer_email: str | None = None,
) -> uuid.UUID:
    conversation_id: uuid.UUID = await conn.fetchval(
        "insert into conversations (tenant_id, status, customer_ref, customer_email) "
        "values ($1, $2, $3, $4) returning id",
        tenant_id,
        status,
        customer_ref,
        customer_email,
    )
    return conversation_id


async def test_list_conversations_returns_only_this_tenants_rows(
    client: httpx.AsyncClient, superuser_conn: asyncpg.Connection[Any]
) -> None:
    token, tenant_id = await _signup_tenant_admin(client)
    other_token, other_tenant_id = await _signup_tenant_admin(client)

    conversation_id = await _seed_conversation(superuser_conn, tenant_id, customer_ref="cust-1")
    await superuser_conn.execute(
        "insert into messages (tenant_id, conversation_id, role, content) "
        "values ($1, $2, 'customer', 'hi'), ($1, $2, 'assistant', 'hello')",
        tenant_id,
        conversation_id,
    )
    await _seed_conversation(superuser_conn, other_tenant_id)

    response = await client.get("/api/conversations", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    body = response.json()["items"]
    assert len(body) == 1
    assert body[0]["id"] == str(conversation_id)
    assert body[0]["customer_ref"] == "cust-1"
    assert body[0]["message_count"] == 2

    other_response = await client.get(
        "/api/conversations", headers={"Authorization": f"Bearer {other_token}"}
    )
    assert len(other_response.json()["items"]) == 1


async def test_list_conversations_filters_by_status(
    client: httpx.AsyncClient, superuser_conn: asyncpg.Connection[Any]
) -> None:
    token, tenant_id = await _signup_tenant_admin(client)
    await _seed_conversation(superuser_conn, tenant_id, status="open")
    escalated_id = await _seed_conversation(superuser_conn, tenant_id, status="escalated")

    response = await client.get(
        "/api/conversations?status=escalated", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    body = response.json()["items"]
    assert len(body) == 1
    assert body[0]["id"] == str(escalated_id)


async def test_list_conversations_surfaces_the_open_escalation(
    client: httpx.AsyncClient, superuser_conn: asyncpg.Connection[Any]
) -> None:
    """pending_summary/pending_since must describe the same open escalation
    needs_attention is derived from - all three are correlated subqueries
    against the same row and must never disagree (service.py's own claim)."""
    token, tenant_id = await _signup_tenant_admin(client)
    conversation_id = await _seed_conversation(superuser_conn, tenant_id, customer_ref="cust-1")
    escalation_created_at = await superuser_conn.fetchval(
        "insert into escalations (tenant_id, conversation_id, reason, summary) "
        "values ($1, $2, 'price_provenance', 'Wants a price for catering Friday') "
        "returning created_at",
        tenant_id,
        conversation_id,
    )

    response = await client.get("/api/conversations", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    row = response.json()["items"][0]
    assert row["needs_attention"] is True
    assert row["pending_summary"] == "Wants a price for catering Friday"
    assert datetime.fromisoformat(row["pending_since"]) == escalation_created_at


# --- RF-14: filtering, searching, paging, and counts over the whole queue ---


async def _list(client: httpx.AsyncClient, token: str, **params: Any) -> dict[str, Any]:
    response = await client.get("/api/conversations", params=params, headers=_auth(token))
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


async def _seed_message(
    conn: asyncpg.Connection[Any],
    tenant_id: uuid.UUID,
    conversation_id: uuid.UUID,
    *,
    role: str = "customer",
    content: str = "hi",
    created_at: datetime | None = None,
) -> None:
    await conn.execute(
        "insert into messages (tenant_id, conversation_id, role, content, created_at) "
        "values ($1, $2, $3, $4, $5)",
        tenant_id,
        conversation_id,
        role,
        content,
        created_at or datetime.now(UTC),
    )


async def _seed_escalation(
    conn: asyncpg.Connection[Any],
    tenant_id: uuid.UUID,
    conversation_id: uuid.UUID,
    *,
    summary: str = "asked for a price",
    status: str = "open",
) -> None:
    await conn.execute(
        "insert into escalations (tenant_id, conversation_id, reason, summary, status) "
        "values ($1, $2, 'price_provenance', $3, $4)",
        tenant_id,
        conversation_id,
        summary,
        status,
    )


async def test_list_conversations_returns_the_items_total_and_counts(
    client: httpx.AsyncClient, superuser_conn: asyncpg.Connection[Any]
) -> None:
    token, tenant_id = await _signup_tenant_admin(client)
    await _seed_conversation(superuser_conn, tenant_id, customer_ref="cust-1")

    body = await _list(client, token)
    assert set(body) == {"items", "total", "counts"}
    assert isinstance(body["items"], list)
    assert body["total"] == 1
    assert set(body["counts"]) == {"all", "needs_you", "unread", "human"}


async def test_needs_you_is_an_open_escalation_or_a_taken_over_thread(
    client: httpx.AsyncClient, superuser_conn: asyncpg.Connection[Any]
) -> None:
    token, tenant_id = await _signup_tenant_admin(client)
    await _seed_conversation(superuser_conn, tenant_id, customer_ref="plain")
    human_id = await _seed_conversation(
        superuser_conn, tenant_id, status="human", customer_ref="human"
    )
    escalated_id = await _seed_conversation(superuser_conn, tenant_id, customer_ref="escalated")
    await _seed_escalation(superuser_conn, tenant_id, escalated_id, summary="wants a price")
    resolved_id = await _seed_conversation(superuser_conn, tenant_id, customer_ref="resolved")
    await _seed_escalation(
        superuser_conn, tenant_id, resolved_id, summary="old news", status="resolved"
    )

    body = await _list(client, token, filter="needs_you")
    assert {row["id"] for row in body["items"]} == {str(human_id), str(escalated_id)}
    assert body["total"] == 2
    assert body["counts"]["needs_you"] == 2


async def test_human_filter_returns_only_taken_over_threads(
    client: httpx.AsyncClient, superuser_conn: asyncpg.Connection[Any]
) -> None:
    token, tenant_id = await _signup_tenant_admin(client)
    human_id = await _seed_conversation(superuser_conn, tenant_id, status="human")
    await _seed_conversation(superuser_conn, tenant_id, status="open")

    body = await _list(client, token, filter="human")
    assert {row["id"] for row in body["items"]} == {str(human_id)}
    assert body["total"] == 1


async def test_unread_filter_reuses_the_rf18_predicate(
    client: httpx.AsyncClient, superuser_conn: asyncpg.Connection[Any]
) -> None:
    token, tenant_id = await _signup_tenant_admin(client)
    unread_id = await _seed_conversation(superuser_conn, tenant_id, customer_ref="unread")
    await _seed_message(superuser_conn, tenant_id, unread_id)
    read_id = await _seed_conversation(superuser_conn, tenant_id, customer_ref="read")
    await _seed_message(
        superuser_conn,
        tenant_id,
        read_id,
        created_at=datetime.now(UTC) - timedelta(minutes=5),
    )
    await superuser_conn.execute(
        "update conversations set owner_read_at = now() where id = $1", read_id
    )
    assistant_only_id = await _seed_conversation(
        superuser_conn, tenant_id, customer_ref="assistant"
    )
    await _seed_message(superuser_conn, tenant_id, assistant_only_id, role="assistant")

    body = await _list(client, token, filter="unread")
    assert {row["id"] for row in body["items"]} == {str(unread_id)}
    assert body["total"] == 1
    assert body["counts"]["unread"] == 1


async def test_handler_is_derived_from_status(
    client: httpx.AsyncClient, superuser_conn: asyncpg.Connection[Any]
) -> None:
    token, tenant_id = await _signup_tenant_admin(client)
    assistant_id = await _seed_conversation(superuser_conn, tenant_id, status="open")
    human_id = await _seed_conversation(superuser_conn, tenant_id, status="human")

    body = await _list(client, token)
    handlers = {row["id"]: row["handler"] for row in body["items"]}
    assert handlers[str(assistant_id)] == "assistant"
    assert handlers[str(human_id)] == "human"


async def test_counts_cover_the_whole_dataset_and_match_the_active_filter(
    client: httpx.AsyncClient, superuser_conn: asyncpg.Connection[Any]
) -> None:
    token, tenant_id = await _signup_tenant_admin(client)
    # Unread open, no escalation.
    unread_open_id = await _seed_conversation(superuser_conn, tenant_id)
    await _seed_message(superuser_conn, tenant_id, unread_open_id)
    # Needs you via an open escalation, and unread too.
    escalated_id = await _seed_conversation(superuser_conn, tenant_id)
    await _seed_message(superuser_conn, tenant_id, escalated_id)
    await _seed_escalation(superuser_conn, tenant_id, escalated_id)
    # Needs you via human status; read, so not unread.
    human_id = await _seed_conversation(superuser_conn, tenant_id, status="human")
    await _seed_message(
        superuser_conn,
        tenant_id,
        human_id,
        created_at=datetime.now(UTC) - timedelta(minutes=5),
    )
    await superuser_conn.execute(
        "update conversations set owner_read_at = now() where id = $1", human_id
    )
    # Read open, no escalation: in all only.
    read_open_id = await _seed_conversation(superuser_conn, tenant_id)
    await _seed_message(
        superuser_conn,
        tenant_id,
        read_open_id,
        created_at=datetime.now(UTC) - timedelta(minutes=5),
    )
    await superuser_conn.execute(
        "update conversations set owner_read_at = now() where id = $1", read_open_id
    )

    body = await _list(client, token)
    assert body["counts"] == {"all": 4, "needs_you": 2, "unread": 2, "human": 1}
    for label in ("all", "needs_you", "unread", "human"):
        page = await _list(client, token, filter=label)
        assert page["total"] == page["counts"][label], label


async def test_the_queue_and_its_counts_never_show_another_tenant(
    client: httpx.AsyncClient, superuser_conn: asyncpg.Connection[Any]
) -> None:
    token, tenant_id = await _signup_tenant_admin(client)
    other_token, other_tenant_id = await _signup_tenant_admin(client)

    mine_id = await _seed_conversation(superuser_conn, tenant_id, customer_ref="mine")
    await _seed_message(superuser_conn, tenant_id, mine_id)
    await _seed_escalation(superuser_conn, tenant_id, mine_id)

    other_human_id = await _seed_conversation(
        superuser_conn, other_tenant_id, status="human", customer_ref="theirs-human"
    )
    other_escalated_id = await _seed_conversation(
        superuser_conn, other_tenant_id, customer_ref="theirs-escalated"
    )
    await _seed_message(superuser_conn, other_tenant_id, other_escalated_id)
    await _seed_escalation(superuser_conn, other_tenant_id, other_escalated_id)

    body = await _list(client, token)
    assert {row["id"] for row in body["items"]} == {str(mine_id)}
    assert body["total"] == 1
    assert body["counts"] == {"all": 1, "needs_you": 1, "unread": 1, "human": 0}

    other_body = await _list(client, other_token)
    assert {row["id"] for row in other_body["items"]} == {
        str(other_human_id),
        str(other_escalated_id),
    }
    assert other_body["total"] == 2
    assert other_body["counts"]["all"] == 2


async def test_search_ignores_a_leading_hash_on_the_reference(
    client: httpx.AsyncClient, superuser_conn: asyncpg.Connection[Any]
) -> None:
    token, tenant_id = await _signup_tenant_admin(client)
    conversation_id = await _seed_conversation(superuser_conn, tenant_id)
    fragment = str(conversation_id).replace("-", "")[:8]

    plain = await _list(client, token, q=fragment)
    hashed = await _list(client, token, q=f"#{fragment}")
    assert str(conversation_id) in {row["id"] for row in plain["items"]}
    assert str(conversation_id) in {row["id"] for row in hashed["items"]}


async def test_the_queue_filters_searches_and_pages_over_the_whole_dataset(
    client: httpx.AsyncClient, superuser_conn: asyncpg.Connection[Any]
) -> None:
    """Past 200 rows, a page bound must not look like a complete answer."""
    token, tenant_id = await _signup_tenant_admin(client)

    # 205 conversations, newest first (i=1 is the most recent). Each carries a
    # customer message stamped at the conversation's own created_at so
    # last_activity_at is explicit and the ordering is deterministic.
    await superuser_conn.execute(
        "insert into conversations (tenant_id, customer_ref, created_at) "
        "select $1, 'bulk-' || lpad(i::text, 4, '0'), "
        "       now() - (i::text || ' minutes')::interval "
        "from generate_series(1, 205) as i",
        tenant_id,
    )
    await superuser_conn.execute(
        "insert into messages (tenant_id, conversation_id, role, content, created_at) "
        "select c.tenant_id, c.id, 'customer', 'hello', c.created_at "
        "from conversations c where c.tenant_id = $1",
        tenant_id,
    )
    # The old unresolved issue: the oldest activity, so it sorts past page 1.
    old_id = await superuser_conn.fetchval(
        "insert into conversations (tenant_id, customer_ref, created_at) "
        "values ($1, 'old-needs-you', now() - interval '400 days') returning id",
        tenant_id,
    )
    await _seed_message(
        superuser_conn,
        tenant_id,
        old_id,
        created_at=datetime.now(UTC) - timedelta(days=400),
    )
    await _seed_escalation(superuser_conn, tenant_id, old_id, summary="forgotten refund")

    first = await _list(client, token, filter="all", limit=50, offset=0)
    assert first["total"] == 206
    assert len(first["items"]) == 50
    assert str(old_id) not in {row["id"] for row in first["items"]}

    # "Load more": the offset that covers the old issue returns it.
    last = await _list(client, token, filter="all", limit=50, offset=200)
    assert str(old_id) in {row["id"] for row in last["items"]}

    # Search by name across the whole dataset, not just page 1.
    by_name = await _list(client, token, q="bulk-0200")
    assert [row["customer_ref"] for row in by_name["items"]] == ["bulk-0200"]
    assert by_name["total"] == 1

    # Search by a conversation-reference fragment for a row off page 1.
    target_id = await superuser_conn.fetchval(
        "select id from conversations where tenant_id = $1 and customer_ref = $2",
        tenant_id,
        "bulk-0200",
    )
    fragment = str(target_id).replace("-", "")[:8]
    by_ref = await _list(client, token, q=fragment)
    assert str(target_id) in {row["id"] for row in by_ref["items"]}

    # Needs you reaches the old escalation regardless of the page bound.
    needs = await _list(client, token, filter="needs_you")
    assert {row["id"] for row in needs["items"]} == {str(old_id)}


async def _unread_of(client: httpx.AsyncClient, token: str, conversation_id: uuid.UUID) -> bool:
    response = await client.get("/api/conversations", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    items = response.json()["items"]
    return bool(next(row for row in items if row["id"] == str(conversation_id))["unread"])


async def test_unread_tracks_customer_messages_after_the_read_marker(
    client: httpx.AsyncClient, superuser_conn: asyncpg.Connection[Any]
) -> None:
    """RF-18: unread is a customer message newer than owner_read_at, or no marker
    yet. Opening the thread (POST .../read) clears it; a later customer message
    makes it unread again."""
    token, tenant_id = await _signup_tenant_admin(client)
    conversation_id = await _seed_conversation(superuser_conn, tenant_id, customer_ref="cust-1")
    await superuser_conn.execute(
        "insert into messages (tenant_id, conversation_id, role, content, created_at) "
        "values ($1, $2, 'customer', 'hi', now() - interval '2 minutes')",
        tenant_id,
        conversation_id,
    )

    # No marker yet, so the older customer message still counts as unread.
    assert await _unread_of(client, token, conversation_id) is True

    read = await client.post(f"/api/conversations/{conversation_id}/read", headers=_auth(token))
    assert read.status_code == 204
    assert await _unread_of(client, token, conversation_id) is False

    # A customer message after the marker flips it back to unread. Assistant
    # messages never do.
    await superuser_conn.execute(
        "insert into messages (tenant_id, conversation_id, role, content, created_at) "
        "values ($1, $2, 'assistant', 'hello', now() + interval '1 minute'), "
        "       ($1, $2, 'customer', 'are you there?', now() + interval '2 minutes')",
        tenant_id,
        conversation_id,
    )
    assert await _unread_of(client, token, conversation_id) is True


async def test_mark_read_is_idempotent_and_never_moves_backwards(
    client: httpx.AsyncClient, superuser_conn: asyncpg.Connection[Any]
) -> None:
    token, tenant_id = await _signup_tenant_admin(client)
    conversation_id = await _seed_conversation(superuser_conn, tenant_id)

    first = await client.post(f"/api/conversations/{conversation_id}/read", headers=_auth(token))
    assert first.status_code == 204
    first_marker = await superuser_conn.fetchval(
        "select owner_read_at from conversations where id = $1", conversation_id
    )
    assert first_marker is not None

    second = await client.post(f"/api/conversations/{conversation_id}/read", headers=_auth(token))
    assert second.status_code == 204
    second_marker = await superuser_conn.fetchval(
        "select owner_read_at from conversations where id = $1", conversation_id
    )
    assert second_marker >= first_marker


async def test_read_state_is_scoped_to_its_own_tenant(
    client: httpx.AsyncClient, superuser_conn: asyncpg.Connection[Any]
) -> None:
    token, _tenant_id = await _signup_tenant_admin(client)
    other_token, other_tenant_id = await _signup_tenant_admin(client)
    other_conversation = await _seed_conversation(superuser_conn, other_tenant_id)
    await superuser_conn.execute(
        "insert into messages (tenant_id, conversation_id, role, content) "
        "values ($1, $2, 'customer', 'hi')",
        other_tenant_id,
        other_conversation,
    )

    # One tenant cannot mark another's conversation read.
    response = await client.post(
        f"/api/conversations/{other_conversation}/read", headers=_auth(token)
    )
    assert response.status_code == 404
    assert (
        await superuser_conn.fetchval(
            "select owner_read_at from conversations where id = $1", other_conversation
        )
        is None
    )
    # And it is still unread for the tenant that owns it.
    assert await _unread_of(client, other_token, other_conversation) is True

    missing = await client.post(f"/api/conversations/{uuid.uuid4()}/read", headers=_auth(token))
    assert missing.status_code == 404


async def test_mark_read_requires_auth(client: httpx.AsyncClient) -> None:
    response = await client.post(f"/api/conversations/{uuid.uuid4()}/read")
    assert response.status_code == 401


async def test_get_conversation_detail_includes_tool_calls_verdicts_and_cost(
    client: httpx.AsyncClient, superuser_conn: asyncpg.Connection[Any]
) -> None:
    token, tenant_id = await _signup_tenant_admin(client)
    conversation_id = await _seed_conversation(superuser_conn, tenant_id, customer_ref="cust-2")

    await superuser_conn.execute(
        "insert into messages (tenant_id, conversation_id, role, content) "
        "values ($1, $2, 'customer', 'where is my order?')",
        tenant_id,
        conversation_id,
    )
    assistant_message_id: uuid.UUID = await superuser_conn.fetchval(
        "insert into messages (tenant_id, conversation_id, role, content, agent_node, metadata) "
        "values ($1, $2, 'assistant', 'it is on its way', 'order_status', $3) returning id",
        tenant_id,
        conversation_id,
        json.dumps({"inspection": {"grounding": {"passed": True, "reason": ""}}}),
    )
    await superuser_conn.execute(
        "insert into tool_calls (tenant_id, message_id, tool_name, arguments, result, success, "
        "latency_ms) values ($1, $2, 'lookup_order_or_ticket', $3, $4, true, 42)",
        tenant_id,
        assistant_message_id,
        json.dumps({"ref_code": "R-1001"}),
        json.dumps({"found": True, "status": "shipped"}),
    )
    await superuser_conn.execute(
        "insert into cost_logs (tenant_id, conversation_id, model, input_tokens, output_tokens, "
        "cost_usd) values ($1, $2, 'gpt-4o-mini', 100, 20, 0.5)",
        tenant_id,
        conversation_id,
    )

    response = await client.get(
        f"/api/conversations/{conversation_id}", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["customer_ref"] == "cust-2"
    assert body["total_cost_usd"] == 0.5
    assert len(body["messages"]) == 2

    assistant_message = next(m for m in body["messages"] if m["role"] == "assistant")
    assert assistant_message["agent_node"] == "order_status"
    assert assistant_message["metadata"]["inspection"]["grounding"]["passed"] is True
    assert assistant_message["cost_usd"] == 0.5
    assert len(assistant_message["tool_calls"]) == 1
    assert assistant_message["tool_calls"][0]["tool_name"] == "lookup_order_or_ticket"
    assert assistant_message["tool_calls"][0]["arguments"] == {"ref_code": "R-1001"}
    assert assistant_message["tool_calls"][0]["success"] is True

    customer_message = next(m for m in body["messages"] if m["role"] == "customer")
    assert customer_message["cost_usd"] is None
    assert customer_message["tool_calls"] == []


async def test_get_conversation_detail_exposes_customer_email(
    client: httpx.AsyncClient, superuser_conn: asyncpg.Connection[Any]
) -> None:
    """The email captured at escalation rides only on the owner detail. The
    queue list still labels by name, so its summary payload must not carry it."""
    token, tenant_id = await _signup_tenant_admin(client)
    conversation_id = await _seed_conversation(
        superuser_conn,
        tenant_id,
        customer_ref="cust-3",
        customer_email="cust3@example.com",
    )

    detail = await client.get(
        f"/api/conversations/{conversation_id}", headers={"Authorization": f"Bearer {token}"}
    )
    assert detail.status_code == 200
    assert detail.json()["customer_email"] == "cust3@example.com"

    listed = await client.get("/api/conversations", headers={"Authorization": f"Bearer {token}"})
    assert listed.status_code == 200
    summary = next(row for row in listed.json()["items"] if row["id"] == str(conversation_id))
    assert "customer_email" not in summary


async def test_get_conversation_detail_cross_tenant_is_404(
    client: httpx.AsyncClient, superuser_conn: asyncpg.Connection[Any]
) -> None:
    token, _tenant_id = await _signup_tenant_admin(client)
    _other_token, other_tenant_id = await _signup_tenant_admin(client)
    conversation_id = await _seed_conversation(superuser_conn, other_tenant_id)

    response = await client.get(
        f"/api/conversations/{conversation_id}", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 404


async def test_list_conversations_requires_auth(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/conversations")
    assert response.status_code == 401


# --- C-6: takeover, handback, and the human's own words --------------------


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _status_of(conn: asyncpg.Connection[Any], conversation_id: uuid.UUID) -> str:
    return str(
        await conn.fetchval("select status from conversations where id = $1", conversation_id)
    )


async def _roles_and_text(
    conn: asyncpg.Connection[Any], conversation_id: uuid.UUID
) -> list[tuple[str, str]]:
    rows = await conn.fetch(
        "select role, content from messages where conversation_id = $1 order by created_at, id",
        conversation_id,
    )
    return [(r["role"], r["content"]) for r in rows]


async def test_takeover_and_handback_move_the_conversation_and_leave_stamps(
    client: httpx.AsyncClient, superuser_conn: asyncpg.Connection[Any]
) -> None:
    token, tenant_id = await _signup_tenant_admin(client)
    conversation_id = await _seed_conversation(superuser_conn, tenant_id)

    assert (
        await client.post(f"/api/conversations/{conversation_id}/takeover", headers=_auth(token))
    ).status_code == 204
    assert await _status_of(superuser_conn, conversation_id) == "human"

    assert (
        await client.post(f"/api/conversations/{conversation_id}/handback", headers=_auth(token))
    ).status_code == 204
    assert await _status_of(superuser_conn, conversation_id) == "open"

    # The transcript says who was speaking, and from when.
    assert await _roles_and_text(superuser_conn, conversation_id) == [
        ("system", "You took over this conversation"),
        ("system", "Handed back to Agencx"),
    ]


async def test_takeover_is_idempotent_and_never_stamps_twice(
    client: httpx.AsyncClient, superuser_conn: asyncpg.Connection[Any]
) -> None:
    token, tenant_id = await _signup_tenant_admin(client)
    conversation_id = await _seed_conversation(superuser_conn, tenant_id)

    first = await client.post(
        f"/api/conversations/{conversation_id}/takeover", headers=_auth(token)
    )
    second = await client.post(
        f"/api/conversations/{conversation_id}/takeover", headers=_auth(token)
    )
    assert first.status_code == 204
    assert second.status_code == 409
    assert len(await _roles_and_text(superuser_conn, conversation_id)) == 1


async def test_a_limit_stopped_conversation_cannot_be_taken_over(
    client: httpx.AsyncClient, superuser_conn: asyncpg.Connection[Any]
) -> None:
    """A cap is a hard stop - taking it over would quietly reopen a
    conversation the tenant is not paying to continue."""
    token, tenant_id = await _signup_tenant_admin(client)
    conversation_id = await _seed_conversation(superuser_conn, tenant_id, status="escalated")

    response = await client.post(
        f"/api/conversations/{conversation_id}/takeover", headers=_auth(token)
    )
    assert response.status_code == 409
    assert await _status_of(superuser_conn, conversation_id) == "escalated"


async def test_reply_needs_the_conversation_taken_over_first(
    client: httpx.AsyncClient, superuser_conn: asyncpg.Connection[Any]
) -> None:
    """Two voices in one thread, neither aware of the other mid-turn, is worse
    than making the owner press one button first."""
    token, tenant_id = await _signup_tenant_admin(client)
    conversation_id = await _seed_conversation(superuser_conn, tenant_id)

    too_early = await client.post(
        f"/api/conversations/{conversation_id}/reply",
        json={"message": "Hi, it's Sam."},
        headers=_auth(token),
    )
    assert too_early.status_code == 409

    await client.post(f"/api/conversations/{conversation_id}/takeover", headers=_auth(token))
    accepted = await client.post(
        f"/api/conversations/{conversation_id}/reply",
        json={"message": "Hi, it's Sam."},
        headers=_auth(token),
    )
    assert accepted.status_code == 204
    assert ("human_agent", "Hi, it's Sam.") in await _roles_and_text(
        superuser_conn, conversation_id
    )


async def test_takeover_is_scoped_to_its_own_tenant(
    client: httpx.AsyncClient, superuser_conn: asyncpg.Connection[Any]
) -> None:
    token, tenant_id = await _signup_tenant_admin(client)
    _, other_tenant_id = await _signup_tenant_admin(client)
    other_conversation = await _seed_conversation(superuser_conn, other_tenant_id)

    response = await client.post(
        f"/api/conversations/{other_conversation}/takeover", headers=_auth(token)
    )
    assert response.status_code == 409
    assert await _status_of(superuser_conn, other_conversation) == "open"


async def _seed_transcript(
    conn: asyncpg.Connection[Any], tenant_id: uuid.UUID, conversation_id: uuid.UUID
) -> None:
    """One assistant turn with everything that hangs off a conversation:
    messages, a tool call, an escalation and a cost_logs row."""
    message_id: uuid.UUID = await conn.fetchval(
        "insert into messages (tenant_id, conversation_id, role, content) "
        "values ($1, $2, 'customer', 'my number is 0400 000 000'), "
        "       ($1, $2, 'assistant', 'thanks') returning id",
        tenant_id,
        conversation_id,
    )
    await conn.execute(
        "insert into tool_calls (tenant_id, message_id, tool_name, arguments, success) "
        "values ($1, $2, 'lookup', '{}', true)",
        tenant_id,
        message_id,
    )
    await conn.execute(
        "insert into escalations (tenant_id, conversation_id, reason, summary) "
        "values ($1, $2, 'price_provenance', 'asked for a price')",
        tenant_id,
        conversation_id,
    )
    await conn.execute(
        "insert into cost_logs (tenant_id, conversation_id, model, input_tokens, output_tokens, "
        "cost_usd) values ($1, $2, 'gpt-4o-mini', 10, 5, 0.1)",
        tenant_id,
        conversation_id,
    )


async def _rows_for(conn: asyncpg.Connection[Any], conversation_id: uuid.UUID) -> dict[str, int]:
    return {
        "conversations": await conn.fetchval(
            "select count(*) from conversations where id = $1", conversation_id
        ),
        "messages": await conn.fetchval(
            "select count(*) from messages where conversation_id = $1", conversation_id
        ),
        "tool_calls": await conn.fetchval(
            "select count(*) from tool_calls tc join messages m on m.id = tc.message_id "
            "where m.conversation_id = $1",
            conversation_id,
        ),
        "escalations": await conn.fetchval(
            "select count(*) from escalations where conversation_id = $1", conversation_id
        ),
    }


async def test_delete_conversation_removes_the_transcript_and_keeps_the_cost(
    client: httpx.AsyncClient, superuser_conn: asyncpg.Connection[Any]
) -> None:
    token, tenant_id = await _signup_tenant_admin(client)
    doomed = await _seed_conversation(superuser_conn, tenant_id)
    kept = await _seed_conversation(superuser_conn, tenant_id)
    await _seed_transcript(superuser_conn, tenant_id, doomed)
    await _seed_transcript(superuser_conn, tenant_id, kept)

    response = await client.delete(f"/api/conversations/{doomed}", headers=_auth(token))
    assert response.status_code == 204

    assert await _rows_for(superuser_conn, doomed) == {
        "conversations": 0,
        "messages": 0,
        "tool_calls": 0,
        "escalations": 0,
    }
    # Its cost row survives, detached: unit economics do not depend on the chat text.
    assert (
        await superuser_conn.fetchval(
            "select count(*) from cost_logs where tenant_id = $1 and conversation_id is null",
            tenant_id,
        )
        == 1
    )
    # A sibling conversation is untouched.
    assert await _rows_for(superuser_conn, kept) == {
        "conversations": 1,
        "messages": 2,
        "tool_calls": 1,
        "escalations": 1,
    }
    gone = await client.get(f"/api/conversations/{doomed}", headers=_auth(token))
    assert gone.status_code == 404


async def test_delete_conversation_with_a_quote_is_refused(
    client: httpx.AsyncClient, superuser_conn: asyncpg.Connection[Any]
) -> None:
    token, tenant_id = await _signup_tenant_admin(client)
    quoted = await _seed_conversation(superuser_conn, tenant_id)
    await _seed_transcript(superuser_conn, tenant_id, quoted)
    await superuser_conn.execute(
        "insert into quotes (tenant_id, conversation_id, line_items, subtotal_cents, total_cents) "
        "values ($1, $2, '[]', 1000, 1000)",
        tenant_id,
        quoted,
    )

    response = await client.delete(f"/api/conversations/{quoted}", headers=_auth(token))
    assert response.status_code == 409
    assert response.headers["content-type"] == "application/problem+json"
    assert "quote" in response.json()["detail"].lower()

    # Nothing moved: not the conversation, not its messages, not the quote.
    assert await _rows_for(superuser_conn, quoted) == {
        "conversations": 1,
        "messages": 2,
        "tool_calls": 1,
        "escalations": 1,
    }
    assert (
        await superuser_conn.fetchval(
            "select count(*) from quotes where conversation_id = $1", quoted
        )
        == 1
    )


async def test_the_app_role_still_cannot_delete_quotes(
    client: httpx.AsyncClient, superuser_conn: asyncpg.Connection[Any]
) -> None:
    """Negative control for the 409 above: the refusal exists because quotes are
    tamper-proof, so prove the revoke in 0006 is still in force rather than
    silently re-granted later."""
    _, tenant_id = await _signup_tenant_admin(client)
    conversation_id = await _seed_conversation(superuser_conn, tenant_id)
    await superuser_conn.execute(
        "insert into quotes (tenant_id, conversation_id, line_items, subtotal_cents, total_cents) "
        "values ($1, $2, '[]', 1000, 1000)",
        tenant_id,
        conversation_id,
    )

    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        async with db.tenant_context(str(tenant_id), "tenant_admin") as conn:
            await conn.execute("delete from quotes where tenant_id = $1", tenant_id)


async def test_delete_conversation_is_scoped_to_its_own_tenant(
    client: httpx.AsyncClient, superuser_conn: asyncpg.Connection[Any]
) -> None:
    token, _ = await _signup_tenant_admin(client)
    _, other_tenant_id = await _signup_tenant_admin(client)
    other_conversation = await _seed_conversation(superuser_conn, other_tenant_id)
    await _seed_transcript(superuser_conn, other_tenant_id, other_conversation)

    response = await client.delete(f"/api/conversations/{other_conversation}", headers=_auth(token))
    assert response.status_code == 404
    assert (await _rows_for(superuser_conn, other_conversation))["messages"] == 2

    missing = await client.delete(f"/api/conversations/{uuid.uuid4()}", headers=_auth(token))
    assert missing.status_code == 404


async def test_delete_conversation_requires_auth(client: httpx.AsyncClient) -> None:
    response = await client.delete(f"/api/conversations/{uuid.uuid4()}")
    assert response.status_code == 401
