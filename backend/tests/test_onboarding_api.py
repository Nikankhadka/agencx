"""T-006 / T-042 / T-054: onboarding endpoints exercised at the API level.

Uses an OnboardingFakeProvider that synthesizes onboarding extraction updates
from canned draft data, one section per turn, so the API-level tests never
call a real model. Chip beats are exercised through the deterministic
selection path (no LLM involved).
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


# The text beats the fake provider feeds, in beat order. business updates are
# cumulative (stateful extraction re-emits the full section), so the
# hours_contact update repeats the name and team size captured earlier.
_FAKE_UPDATES: list[dict[str, object]] = [
    {"business": {"name": "Bytefix Repairs"}},
    {"identity": {"description": "A neighborhood phone repair shop."}},
    {
        "business": {
            "name": "Bytefix Repairs",
            "is_team": True,
            "hours": "Mon-Fri 9-6",
            "contact": "555-0100",
        }
    },
    {
        "services": {
            "items": [
                {
                    "name": "Screen repair",
                    "description": "Cracked screens",
                    "price_dollars": 89.5,
                }
            ]
        },
    },
    {
        "pricing_rules": {
            "rules": [
                {
                    "code": "rush-fee",
                    "label": "Rush service",
                    "unit_amount_dollars": 25.0,
                    "unit": "flat",
                }
            ]
        },
    },
]

_CHAT_REPLIES = [
    "Nice to meet you, Bytefix Repairs!",
    "I've captured your business description.",
    "Hours and contact noted.",
    "Services recorded.",
    "Pricing rules saved.",
]

# The full walk: text beats (LLM extraction) interleaved with chip selections
# in beat order.
_FULL_WALK: list[tuple[Any, ...]] = [
    ("text", "we are Bytefix Repairs"),
    ("selection", "team", ["team"]),
    ("text", "we fix phones"),
    ("selection", "readback", ["confirm"]),
    ("text", "open weekdays, call 555-0100"),
    ("text", "screen repairs are $89.50"),
    ("text", "rush fee is $25"),
    ("selection", "business_number", ["none"]),
    ("selection", "tax_registered", ["yes"]),
    ("selection", "payment_mode", ["DIRECT"]),
    ("selection", "payment_terms", ["full_before"]),
    ("selection", "inbound_channels", ["website", "phone"]),
    ("selection", "tone", ["friendly"]),
    ("selection", "escalation_posture", ["balanced"]),
]


class OnboardingFakeProvider(BaseFakeProvider):
    """Synthesizes extraction updates from canned data, one section per
    extract() call until all sections are captured."""

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
                "meta_reply": "I'm Wren.",
                "next_question": "What is your business?",
            }
        )

    async def chat(self, messages: list[ChatMessage]) -> str:
        return "I'm Wren. What is your business?"


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
        if step[0] == "text":
            await _send(client, headers, text=step[1])
        else:
            await _send(client, headers, selection={"beat": step[1], "values": step[2]})


async def _walk_to_confirm(client: httpx.AsyncClient, token: str) -> None:
    await _walk(client, token)


async def test_fresh_tenant_starts_at_business_name(client: httpx.AsyncClient) -> None:
    token, _tenant_id = await _signup_tenant_admin(client)
    response = await client.get(
        "/api/onboarding/state", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["stage"] == "business_name"
    assert body["completed"] is False
    assert body["draft"] == {}
    assert body["history"] == []
    assert body["can_confirm"] is False
    assert body["input"]["kind"] == "text"


async def test_message_captures_business_name_and_advances_stage(client: httpx.AsyncClient) -> None:
    token, _tenant_id = await _signup_tenant_admin(client)
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.post(
        "/api/onboarding/message", json={"text": "we are Bytefix Repairs"}, headers=headers
    )
    assert response.status_code == 200
    body = response.json()
    assert body["stage"] == "team"
    assert body["draft"]["business"]["name"] == "Bytefix Repairs"

    resumed = await client.get("/api/onboarding/state", headers=headers)
    assert resumed.json()["stage"] == "team"


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
    assert body["stage"] == "business_name"


async def test_selection_updates_draft_and_history(client: httpx.AsyncClient) -> None:
    token, _tenant_id = await _signup_tenant_admin(client)
    headers = {"Authorization": f"Bearer {token}"}
    await _send(client, headers, text="we are Bytefix Repairs")

    body = await _send(client, headers, selection={"beat": "team", "values": ["team"]})
    assert body["stage"] == "description"
    assert body["draft"]["business"]["is_team"] is True
    assert body["input"]["kind"] == "text"
    user_messages = [m["content"] for m in body["history"] if m["role"] == "user"]
    assert any("We're a team" in m for m in user_messages)


async def test_stale_selection_is_conflict(client: httpx.AsyncClient) -> None:
    token, _tenant_id = await _signup_tenant_admin(client)
    headers = {"Authorization": f"Bearer {token}"}
    # current beat is business_name; a team selection is stale.
    response = await client.post(
        "/api/onboarding/message",
        json={"selection": {"beat": "team", "values": ["team"]}},
        headers=headers,
    )
    assert response.status_code == 409


async def test_message_requires_exactly_one_of_text_or_selection(
    client: httpx.AsyncClient,
) -> None:
    token, _tenant_id = await _signup_tenant_admin(client)
    headers = {"Authorization": f"Bearer {token}"}
    both = await client.post(
        "/api/onboarding/message",
        json={"text": "hi", "selection": {"beat": "team", "values": ["team"]}},
        headers=headers,
    )
    assert both.status_code == 422
    neither = await client.post("/api/onboarding/message", json={}, headers=headers)
    assert neither.status_code == 422


async def test_kyc_beat_appears_only_for_platform(client: httpx.AsyncClient) -> None:
    token, _tenant_id = await _signup_tenant_admin(client)
    headers = {"Authorization": f"Bearer {token}"}
    await _walk(client, token, _FULL_WALK[:9])  # through tax_registered

    body = await _send(client, headers, selection={"beat": "payment_mode", "values": ["PLATFORM"]})
    assert body["stage"] == "kyc"
    assert body["input"]["kind"] == "cta"
    assert body["input"]["cta_label"] == "Start ID check"

    body = await _send(client, headers, selection={"beat": "kyc", "values": ["skip"]})
    assert body["stage"] == "payment_terms"
    assert body["draft"]["kyc"]["skipped"] is True


async def test_direct_payment_skips_kyc(client: httpx.AsyncClient) -> None:
    token, _tenant_id = await _signup_tenant_admin(client)
    headers = {"Authorization": f"Bearer {token}"}
    await _walk(client, token, _FULL_WALK[:9])

    body = await _send(client, headers, selection={"beat": "payment_mode", "values": ["DIRECT"]})
    assert body["stage"] == "payment_terms"


async def test_deposit_terms_asks_for_percentage(client: httpx.AsyncClient) -> None:
    token, _tenant_id = await _signup_tenant_admin(client)
    headers = {"Authorization": f"Bearer {token}"}
    await _walk(client, token, _FULL_WALK[:9])
    await _send(client, headers, selection={"beat": "payment_mode", "values": ["DIRECT"]})

    body = await _send(client, headers, selection={"beat": "payment_terms", "values": ["deposit"]})
    assert body["stage"] == "deposit_pct"

    body = await _send(client, headers, selection={"beat": "deposit_pct", "values": ["20"]})
    assert body["stage"] == "inbound_channels"
    assert body["draft"]["payment"]["deposit_pct"] == 20


async def test_full_flow_confirm_writes_tenant_config_and_catalog(
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
    result = confirm.json()
    assert result["catalog_items_created"] == 1
    assert result["pricing_rules_created"] == 1

    config_row = await superuser_conn.fetchrow(
        "select system_prompt, tone, escalation_threshold from tenant_config where tenant_id = $1",
        tenant_id,
    )
    assert config_row is not None
    assert "phone repair shop" in config_row["system_prompt"]
    assert config_row["tone"] == "friendly"
    assert config_row["escalation_threshold"] == pytest.approx(0.5)

    tenant_row = await superuser_conn.fetchrow(
        "select business_name, payment_processing_mode from tenants where id = $1", tenant_id
    )
    assert tenant_row is not None
    assert tenant_row["business_name"] == "Bytefix Repairs"
    assert tenant_row["payment_processing_mode"] == "DIRECT"

    business_name = await superuser_conn.fetchval(
        "select config->'business'->>'name' from tenant_config where tenant_id = $1", tenant_id
    )
    assert business_name == "Bytefix Repairs"

    item_row = await superuser_conn.fetchrow(
        "select name, price_cents from catalog_items where tenant_id = $1", tenant_id
    )
    assert item_row is not None
    assert item_row["name"] == "Screen repair"
    assert item_row["price_cents"] == 8950

    rule_row = await superuser_conn.fetchrow(
        "select code, unit_amount_cents from pricing_rules where tenant_id = $1",
        tenant_id,
    )
    assert rule_row is not None
    assert rule_row["code"] == "rush-fee"
    assert rule_row["unit_amount_cents"] == 2500

    catalog_doc = await superuser_conn.fetchrow(
        "select id, status from documents where tenant_id = $1 and doc_type = 'catalog'",
        tenant_id,
    )
    assert catalog_doc is not None
    assert catalog_doc["status"] == "ready"
    chunk_row = await superuser_conn.fetchrow(
        "select content, metadata from knowledge_chunks where document_id = $1",
        catalog_doc["id"],
    )
    assert chunk_row is not None
    assert "Screen repair" in chunk_row["content"]


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
        json={"text": "we are Bytefix Repairs"},
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
    business = state_draft["business"]
    assert isinstance(business, dict)
    assert business["name"] == "Bytefix Repairs"
    assert state_event["completed"] is False
    # The client needs the current beat key to submit a chip selection after a
    # text turn, so the SSE state event carries it (matching /state's shape).
    assert state_event["stage"] == "team"
