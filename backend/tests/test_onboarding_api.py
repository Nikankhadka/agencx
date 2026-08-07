"""T-006 / T-042: onboarding endpoints exercised at the API level.

Uses an OnboardingFakeProvider that synthesizes onboarding tool calls from
canned draft data, one section per turn, so the API-level tests never call
a real model.
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
from app.llm.provider import ChatMessage, ToolCall, ToolSpec, ToolTurn
from app.main import app
from app.shared import db
from app.shared.config import get_settings
from tests.conftest import _app_dsn_for
from tests.fakes import BaseFakeProvider, ZeroEmbedder

pytestmark = pytest.mark.db

TEST_JWT_SECRET = "test-only-supabase-jwt-secret-do-not-use-in-prod"  # noqa: S105


_FAKE_TOOLS: list[tuple[str, dict[str, object]]] = [
    ("save_identity", {"description": "A neighborhood phone repair shop."}),
    ("save_tone", {"tone": "friendly"}),
    (
        "save_services",
        {
            "items": [
                {
                    "name": "Screen repair",
                    "description": "Cracked screens",
                    "price_dollars": 89.5,
                }
            ]
        },
    ),
    (
        "save_pricing_rules",
        {
            "rules": [
                {
                    "code": "rush-fee",
                    "label": "Rush service",
                    "unit_amount_dollars": 25.0,
                    "unit": "flat",
                }
            ]
        },
    ),
    ("save_escalation", {"threshold": 0.6}),
]

_CHAT_REPLIES = [
    "I've captured your business description. How should the assistant sound?",
    "Friendly tone noted! What services do you offer?",
    "Services recorded. Any pricing rules?",
    "Pricing rules saved. When should the assistant escalate?",
    "Escalation threshold set. Ready to confirm?",
    "All sections captured - you can confirm now.",
]


class OnboardingFakeProvider(BaseFakeProvider):
    """Synthesizes tool calls from canned data, one section per chat_with_tools
    call until all sections are captured."""

    def __init__(self) -> None:
        self._tool_idx = 0
        self._chat_idx = 0

    async def chat(self, messages: list[ChatMessage]) -> str:
        reply = _CHAT_REPLIES[self._chat_idx % len(_CHAT_REPLIES)]
        self._chat_idx += 1
        return reply

    async def chat_with_tools(
        self,
        *,
        messages: list[ChatMessage],
        tools: list[ToolSpec],
        tool_choice: str = "auto",
    ) -> ToolTurn:
        if self._tool_idx < len(_FAKE_TOOLS):
            name, args = _FAKE_TOOLS[self._tool_idx]
            self._tool_idx += 1
            return ToolTurn(
                tool_calls=[
                    ToolCall(
                        id=f"call_{self._tool_idx}",
                        name=name,
                        args=args,
                    ),
                ],
            )
        return ToolTurn()


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


async def _walk_to_confirm(client: httpx.AsyncClient, token: str) -> None:
    headers = {"Authorization": f"Bearer {token}"}
    replies = [
        "we fix phones",
        "keep it friendly",
        "screen repairs for $89.50",
        "rush fee is $25",
        "escalate when unsure",
        "ready",
    ]
    for reply in replies:
        response = await client.post(
            "/api/onboarding/message", json={"text": reply}, headers=headers
        )
        assert response.status_code == 200, response.text


async def test_fresh_tenant_starts_at_identity(client: httpx.AsyncClient) -> None:
    token, _tenant_id = await _signup_tenant_admin(client)
    response = await client.get(
        "/api/onboarding/state", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["stage"] == "identity"
    assert body["completed"] is False
    assert body["draft"] == {}


async def test_message_captures_identity_and_advances_stage(client: httpx.AsyncClient) -> None:
    token, _tenant_id = await _signup_tenant_admin(client)
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.post(
        "/api/onboarding/message", json={"text": "we fix phones"}, headers=headers
    )
    assert response.status_code == 200
    body = response.json()
    assert body["stage"] == "tone"
    description = body["draft"]["identity"]["description"]
    assert description == "A neighborhood phone repair shop."

    resumed = await client.get("/api/onboarding/state", headers=headers)
    assert resumed.json()["stage"] == "tone"


async def test_full_flow_confirm_writes_tenant_config_and_catalog(
    client: httpx.AsyncClient, superuser_conn: asyncpg.Connection[Any]
) -> None:
    token, tenant_id = await _signup_tenant_admin(client)
    headers = {"Authorization": f"Bearer {token}"}
    await _walk_to_confirm(client, token)

    state = await client.get("/api/onboarding/state", headers=headers)
    assert state.json()["stage"] == "confirm"

    confirm = await client.post("/api/onboarding/confirm", headers=headers)
    assert confirm.status_code == 200
    body = confirm.json()
    assert body["catalog_items_created"] == 1
    assert body["pricing_rules_created"] == 1

    config_row = await superuser_conn.fetchrow(
        "select system_prompt, tone, escalation_threshold from tenant_config where tenant_id = $1",
        tenant_id,
    )
    assert config_row is not None
    assert "phone repair shop" in config_row["system_prompt"]
    assert config_row["tone"] == "friendly"
    assert config_row["escalation_threshold"] == pytest.approx(0.6)

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
        json={"text": "we fix phones"},
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
    assert "done" in types
