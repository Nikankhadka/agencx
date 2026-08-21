"""O-1: onboarding endpoints exercised at the API level.

Uses an OnboardingFakeProvider that synthesizes extraction updates from canned
profile data, one field per turn, so the API-level tests never call a real
model. Onboarding is text-only since O-1: every beat is satisfied by
extraction, so the walk is seven text turns and a selection payload is
rejected.
"""

from __future__ import annotations

import json
import time
import uuid
from collections.abc import AsyncIterator, Iterator
from typing import Any

import asyncpg
import httpx
import jwt
import pytest
import pytest_asyncio

from app.llm.dependency import get_embedder_dependency, get_llm_provider
from app.llm.provider import ChatMessage, SchemaT
from app.main import app
from app.shared import db
from app.shared.config import get_settings
from tests.conftest import _app_dsn_for
from tests.fakes import BaseFakeProvider, ZeroEmbedder

pytestmark = pytest.mark.db

TEST_JWT_SECRET = "test-only-supabase-jwt-secret-do-not-use-in-prod"  # noqa: S105


# One profile field per turn, in beat order. Each update carries only what the
# owner stated that turn; save_profile merges it into the accumulated draft.
_FAKE_UPDATES: list[dict[str, object]] = [
    {"profile": {"name": "Sam"}},
    {"profile": {"business_name": "Bytefix Repairs"}},
    {"profile": {"business_type": "a neighborhood phone repair shop"}},
    {"profile": {"headcount": "just me and one technician"}},
    {"profile": {"hours": "Mon-Fri 9-6"}},
    {"profile": {"services": "screen repairs, battery replacements"}},
    {"profile": {"contact": "555-0100"}},
]

_CHAT_REPLIES = [
    "Nice to meet you, Sam!",
    "Bytefix Repairs it is.",
    "A phone repair shop - got it.",
    "Team size noted.",
    "Hours noted.",
    "Services recorded.",
    "Contact details saved.",
]

# The full walk: seven text turns, one per lean beat.
_FULL_WALK: list[tuple[Any, ...]] = [
    ("text", "I'm Sam"),
    ("text", "we are Bytefix Repairs"),
    ("text", "we fix phones"),
    ("text", "just me and one tech"),
    ("text", "open weekdays 9 to 6"),
    ("text", "screen repairs and batteries"),
    ("text", "call 555-0100"),
]


class OnboardingFakeProvider(BaseFakeProvider):
    """Synthesizes extraction updates from canned data, one profile field per
    extract() call until every field is captured."""

    def __init__(self) -> None:
        self._update_idx = 0
        self._chat_idx = 0

    async def extract(
        self, *, system_prompt: str, user_input: str, schema: type[SchemaT]
    ) -> SchemaT:
        if self._update_idx < len(_FAKE_UPDATES):
            data = _FAKE_UPDATES[self._update_idx]
            self._update_idx += 1
            return schema.model_validate(data)
        return schema.model_validate({})

    async def chat(self, messages: list[ChatMessage]) -> str:
        reply = _CHAT_REPLIES[self._chat_idx % len(_CHAT_REPLIES)]
        self._chat_idx += 1
        return reply

    async def chat_stream(self, messages: list[ChatMessage]) -> AsyncIterator[str]:
        reply = _CHAT_REPLIES[self._chat_idx % len(_CHAT_REPLIES)]
        self._chat_idx += 1
        mid = len(reply) // 2
        yield reply[:mid]
        yield reply[mid:]


class OffTopicFakeProvider(BaseFakeProvider):
    """Always reports the message as off-topic, collecting nothing."""

    async def extract(
        self, *, system_prompt: str, user_input: str, schema: type[SchemaT]
    ) -> SchemaT:
        return schema.model_validate(
            {
                "off_topic": True,
                "meta_reply": "I'm here to help you set up your business.",
                "next_question": "What's your name?",
            }
        )

    async def chat(self, messages: list[ChatMessage]) -> str:
        return "I'm here to help you set up your business. What's your name?"


@pytest.fixture(autouse=True)
def _supabase_jwt_secret_env() -> Iterator[None]:
    import os

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
    fake = OnboardingFakeProvider()
    app.dependency_overrides[get_llm_provider] = lambda: fake
    app.dependency_overrides[get_embedder_dependency] = ZeroEmbedder
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac
    finally:
        app.dependency_overrides.pop(get_llm_provider, None)
        app.dependency_overrides.pop(get_embedder_dependency, None)
        await db.close_pool()


def _make_token(user_id: uuid.UUID) -> str:
    now = int(time.time())
    payload = {
        "sub": str(user_id),
        "aud": "authenticated",
        "iat": now,
        "exp": now + 3600,
    }
    return jwt.encode(payload, TEST_JWT_SECRET, algorithm="HS256")


async def _signup_tenant_admin(client: httpx.AsyncClient) -> tuple[str, uuid.UUID]:
    user_id = uuid.uuid4()
    token = _make_token(user_id)
    slug = f"onboard-{uuid.uuid4().hex[:8]}"
    response = await client.post(
        "/api/tenants",
        json={"slug": slug, "name": "Onboarding Test Co"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    return token, uuid.UUID(response.json()["tenant_id"])


async def _send(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    *,
    text: str | None = None,
    selection: dict[str, object] | None = None,
) -> dict[str, Any]:
    payload: dict[str, object] = {"text": text} if text is not None else {"selection": selection}
    response = await client.post("/api/onboarding/message", json=payload, headers=headers)
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


async def _walk(
    client: httpx.AsyncClient, token: str, steps: list[tuple[Any, ...]] | None = None
) -> None:
    headers = {"Authorization": f"Bearer {token}"}
    for step in steps or _FULL_WALK:
        await _send(client, headers, text=step[1])


async def _walk_to_confirm(client: httpx.AsyncClient, token: str) -> None:
    await _walk(client, token)


async def test_fresh_tenant_starts_at_name(client: httpx.AsyncClient) -> None:
    token, _tenant_id = await _signup_tenant_admin(client)
    response = await client.get(
        "/api/onboarding/state", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["stage"] == "name"
    assert body["completed"] is False
    assert body["draft"] == {}
    assert body["history"] == []
    assert body["can_confirm"] is False
    assert body["input"]["kind"] == "text"


async def test_every_beat_renders_the_text_pill(client: httpx.AsyncClient) -> None:
    """O-1: the interview is text-only, so no beat ever asks for a chip."""
    token, _tenant_id = await _signup_tenant_admin(client)
    headers = {"Authorization": f"Bearer {token}"}

    for step in _FULL_WALK[:-1]:
        body = await _send(client, headers, text=step[1])
        assert body["input"]["kind"] == "text"
        assert body["input"]["chips"] == []
        assert body["input"]["mask"] is None
        assert body["input"]["cta_label"] is None


async def test_message_captures_name_and_advances_stage(client: httpx.AsyncClient) -> None:
    token, _tenant_id = await _signup_tenant_admin(client)
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.post(
        "/api/onboarding/message", json={"text": "I'm Sam"}, headers=headers
    )
    assert response.status_code == 200
    body = response.json()
    assert body["stage"] == "business_name"
    assert body["draft"]["name"] == "Sam"

    resumed = await client.get("/api/onboarding/state", headers=headers)
    assert resumed.json()["stage"] == "business_name"


async def test_draft_accumulates_across_turns(client: httpx.AsyncClient) -> None:
    """US-1: each turn merges its fields; nothing captured earlier is lost."""
    token, _tenant_id = await _signup_tenant_admin(client)
    headers = {"Authorization": f"Bearer {token}"}

    await _send(client, headers, text="I'm Sam")
    body = await _send(client, headers, text="we are Bytefix Repairs")

    assert body["draft"] == {"name": "Sam", "business_name": "Bytefix Repairs"}


async def test_resume_returns_history_and_draft_in_place(client: httpx.AsyncClient) -> None:
    """US-4: a returning owner picks up where they left off, nothing re-asked."""
    token, _tenant_id = await _signup_tenant_admin(client)
    headers = {"Authorization": f"Bearer {token}"}
    await _walk(client, token, _FULL_WALK[:3])

    state = await client.get("/api/onboarding/state", headers=headers)
    body = state.json()

    assert body["stage"] == "headcount"
    assert body["draft"]["name"] == "Sam"
    assert body["draft"]["business_name"] == "Bytefix Repairs"
    user_messages = [m["content"] for m in body["history"] if m["role"] == "user"]
    assert user_messages == ["I'm Sam", "we are Bytefix Repairs", "we fix phones"]


async def test_off_topic_message_is_not_persisted(client: httpx.AsyncClient) -> None:
    token, _tenant_id = await _signup_tenant_admin(client)
    headers = {"Authorization": f"Bearer {token}"}
    app.dependency_overrides[get_llm_provider] = lambda: OffTopicFakeProvider()
    try:
        response = await client.post(
            "/api/onboarding/message", json={"text": "hi"}, headers=headers
        )
        assert response.status_code == 200
        assert response.json()["draft"] == {}
    finally:
        app.dependency_overrides.pop(get_llm_provider, None)

    state = await client.get("/api/onboarding/state", headers=headers)
    body = state.json()
    assert body["draft"] == {}
    assert body["stage"] == "name"


async def test_selection_payload_is_conflict(client: httpx.AsyncClient) -> None:
    """O-1 retired the chip path; the payload stays in the contract until E-1."""
    token, _tenant_id = await _signup_tenant_admin(client)
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.post(
        "/api/onboarding/message",
        json={"selection": {"beat": "headcount", "values": ["team"]}},
        headers=headers,
    )
    assert response.status_code == 409
    assert "text-only" in response.json()["detail"]


async def test_message_requires_exactly_one_of_text_or_selection(
    client: httpx.AsyncClient,
) -> None:
    token, _tenant_id = await _signup_tenant_admin(client)
    headers = {"Authorization": f"Bearer {token}"}
    both = await client.post(
        "/api/onboarding/message",
        json={"text": "hi", "selection": {"beat": "headcount", "values": ["team"]}},
        headers=headers,
    )
    assert both.status_code == 422
    neither = await client.post("/api/onboarding/message", json={}, headers=headers)
    assert neither.status_code == 422


async def test_full_flow_confirm_writes_profile(
    client: httpx.AsyncClient, superuser_conn: asyncpg.Connection[Any]
) -> None:
    token, tenant_id = await _signup_tenant_admin(client)
    headers = {"Authorization": f"Bearer {token}"}
    await _walk_to_confirm(client, token)

    state = await client.get("/api/onboarding/state", headers=headers)
    body = state.json()
    assert body["stage"] == "confirm"
    assert body["can_confirm"] is True
    assert body["input"] is None

    confirm = await client.post("/api/onboarding/confirm", headers=headers)
    assert confirm.status_code == 200
    assert confirm.json() == {"tenant_id": str(tenant_id)}

    config_row = await superuser_conn.fetchrow(
        "select system_prompt, tone, escalation_threshold from tenant_config where tenant_id = $1",
        tenant_id,
    )
    assert config_row is not None
    # The identity sentence carries both the name and the captured type.
    assert "Bytefix Repairs" in config_row["system_prompt"]
    assert "phone repair shop" in config_row["system_prompt"]
    # O-1 no longer sets these from the interview - they keep schema defaults.
    assert config_row["tone"] == "friendly"
    assert config_row["escalation_threshold"] == pytest.approx(0.5)

    tenant_row = await superuser_conn.fetchrow(
        "select business_name from tenants where id = $1", tenant_id
    )
    assert tenant_row is not None
    assert tenant_row["business_name"] == "Bytefix Repairs"

    profile = await superuser_conn.fetchval(
        "select config->'profile' from tenant_config where tenant_id = $1", tenant_id
    )
    assert json.loads(profile) == {
        "name": "Sam",
        "business_name": "Bytefix Repairs",
        "business_type": "a neighborhood phone repair shop",
        "headcount": "just me and one technician",
        "hours": "Mon-Fri 9-6",
        "services": "screen repairs, battery replacements",
        "contact": "555-0100",
    }


async def test_confirm_writes_no_catalog_or_pricing_rows(
    client: httpx.AsyncClient, superuser_conn: asyncpg.Connection[Any]
) -> None:
    """O-1 captures a profile, not a priced catalog - prices come from uploads."""
    token, tenant_id = await _signup_tenant_admin(client)
    await _walk_to_confirm(client, token)
    await client.post("/api/onboarding/confirm", headers={"Authorization": f"Bearer {token}"})

    items = await superuser_conn.fetchval(
        "select count(*) from catalog_items where tenant_id = $1", tenant_id
    )
    rules = await superuser_conn.fetchval(
        "select count(*) from pricing_rules where tenant_id = $1", tenant_id
    )
    assert items == 0
    assert rules == 0


async def test_confirm_before_complete_is_conflict(client: httpx.AsyncClient) -> None:
    token, _tenant_id = await _signup_tenant_admin(client)
    response = await client.post(
        "/api/onboarding/confirm", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 409


async def test_double_confirm_is_conflict(client: httpx.AsyncClient) -> None:
    token, _tenant_id = await _signup_tenant_admin(client)
    headers = {"Authorization": f"Bearer {token}"}
    await _walk_to_confirm(client, token)

    first = await client.post("/api/onboarding/confirm", headers=headers)
    assert first.status_code == 200
    second = await client.post("/api/onboarding/confirm", headers=headers)
    assert second.status_code == 409


async def test_message_at_confirm_stage_is_conflict(client: httpx.AsyncClient) -> None:
    token, _tenant_id = await _signup_tenant_admin(client)
    headers = {"Authorization": f"Bearer {token}"}
    await _walk_to_confirm(client, token)

    # Confirm, then try to send another message.
    await client.post("/api/onboarding/confirm", headers=headers)
    response = await client.post(
        "/api/onboarding/message", json={"text": "anything"}, headers=headers
    )
    assert response.status_code == 409


async def test_sse_endpoint_returns_reply(client: httpx.AsyncClient) -> None:
    token, _tenant_id = await _signup_tenant_admin(client)
    headers = {"Authorization": f"Bearer {token}"}

    async with client.stream(
        "POST",
        "/api/onboarding/message/stream",
        json={"text": "I'm Sam"},
        headers=headers,
    ) as resp:
        assert resp.status_code == 200
        events: list[dict[str, object]] = []
        async for line in resp.aiter_lines():
            if line.startswith("data: "):
                events.append(json.loads(line[6:]))
    types = [e["type"] for e in events]
    assert "progress" in types
    assert "reply" in types
    assert "state" in types
    assert "done" in types
    tokens = [e for e in events if e["type"] == "token"]
    assert tokens, "stream must emit token deltas"
    token_texts: list[str] = []
    for token_event in tokens:
        text = token_event["text"]
        assert isinstance(text, str)
        token_texts.append(text)
    reply_event = next(e for e in events if e["type"] == "reply")
    assert "".join(token_texts) == reply_event["text"]
    state_event = next(e for e in events if e["type"] == "state")
    state_draft = state_event["draft"]
    assert isinstance(state_draft, dict)
    assert state_draft["name"] == "Sam"
    assert state_event["completed"] is False
    # The SSE state event carries the current beat key, matching /state's shape.
    assert state_event["stage"] == "business_name"
