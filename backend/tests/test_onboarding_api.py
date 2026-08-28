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
from pathlib import Path
from typing import Any

import asyncpg
import httpx
import jwt
import pytest
import pytest_asyncio

from app.features.onboarding.controller import _find_url
from app.features.tenants.slug import suggested_slug
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
    {"profile": {"abn": "51 824 753 556"}},
    {"profile": {"gst": "yes"}},
]

_CHAT_REPLIES = [
    "Nice to meet you, Sam!",
    "Bytefix Repairs it is.",
    "A phone repair shop - got it.",
    "Team size noted.",
    "Hours noted.",
    "Services recorded.",
    "Contact details saved.",
    "ABN saved.",
    "GST noted.",
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
    ("text", "yes, 51 824 753 556"),
    ("text", "yes we are"),
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
    # The beats land on the optional website/documents ask ("knowledge"); one
    # "skip" answers it and advances to confirm.
    await _walk(client, token)
    await _send(client, {"Authorization": f"Bearer {token}"}, text="skip")


def _page_slug(tenant_id: uuid.UUID) -> str:
    return f"page-{tenant_id.hex[:12]}"


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


async def test_every_beat_still_accepts_typed_text(client: httpx.AsyncClient) -> None:
    """O-6: chips are an accelerator, never a gate. Every beat keeps ``kind``
    "text", so the pill renders on all of them and a typed answer is always a
    way through - which is also what keeps the one-tool extraction loop the
    single path into the draft."""
    token, _tenant_id = await _signup_tenant_admin(client)
    headers = {"Authorization": f"Bearer {token}"}

    for step in _FULL_WALK[:-1]:
        body = await _send(client, headers, text=step[1])
        assert body["input"]["kind"] == "text"
        assert body["input"]["cta_label"] is None


async def test_chipped_beats_offer_their_shortcuts(client: httpx.AsyncClient) -> None:
    """O-6: the beats the prototype chips are the beats that carry chips here.

    Ported from agencx-prototype-v6.html: `otpVerified()` (Just me / Got a team),
    `handlePricing()` (Yes / No, not yet on the ABN) and `handleAbn()`'s GST
    follow-up.
    """
    token, _tenant_id = await _signup_tenant_admin(client)
    headers = {"Authorization": f"Bearer {token}"}

    def labels(body: dict[str, Any]) -> list[str]:
        return [c["label"] for c in body["input"]["chips"]]

    # Two beats in: the team-size question offers the prototype's two chips.
    await _send(client, headers, text=_FULL_WALK[0][1])
    await _send(client, headers, text=_FULL_WALK[1][1])
    body = await _send(client, headers, text=_FULL_WALK[2][1])
    assert body["stage"] == "headcount"
    assert labels(body) == ["Just me", "Got a team"]
    # A chipped beat invites typing past the chips, never blocks it.
    assert body["input"]["placeholder"] == "or type…"

    await _send(client, headers, text=_FULL_WALK[3][1])
    body = await _send(client, headers, text=_FULL_WALK[4][1])
    assert body["stage"] == "services"
    assert body["input"]["chips"] == []

    body = await _send(client, headers, text=_FULL_WALK[5][1])
    assert body["stage"] == "contact"
    # The phone chip swaps the composer rather than submitting its label, and
    # the email chip's label is the client's to fill from its own session.
    assert labels(body) == ["Phone number"]
    assert body["input"]["chips"][0]["widget"] == "phone"
    assert body["input"]["suggest_owner_email"] is True

    body = await _send(client, headers, text=_FULL_WALK[6][1])
    assert body["stage"] == "abn"
    assert labels(body) == ["Yes", "No, not yet"]
    assert body["input"]["chips"][0]["widget"] == "masked"
    assert body["input"]["mask"] == "XX XXX XXX XXX"
    assert body["input"]["prefix"] == "ABN"

    body = await _send(client, headers, text=_FULL_WALK[7][1])
    assert body["stage"] == "gst"
    assert labels(body) == ["Yes", "Not yet"]


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


def test_suggested_slug_is_a_shareable_handle() -> None:
    assert suggested_slug("Bytefix Repairs") == "bytefix-repairs"
    assert suggested_slug("Café & Co.") == "cafe-co"


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


async def test_knowledge_ask_then_skip_advances_to_confirm(
    client: httpx.AsyncClient,
) -> None:
    """The website/documents ask is optional, not a gate: after the seven beats
    the interview pauses on a ``knowledge`` stage with a text composer, and one
    "skip" answers it so confirm becomes available."""
    token, _tenant_id = await _signup_tenant_admin(client)
    headers = {"Authorization": f"Bearer {token}"}

    body: dict[str, Any] = {}
    for step in _FULL_WALK:
        body = await _send(client, headers, text=step[1])

    # Profile complete -> the offer fires, and the stage is the non-blocking ask.
    assert body["stage"] == "knowledge"
    assert body["can_confirm"] is False
    assert body["input"]["kind"] == "text"

    final = await _send(client, headers, text="skip")
    assert final["stage"] == "confirm"
    assert final["can_confirm"] is True
    assert final["input"] is None


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
    assert confirm.json() == {"tenant_id": str(tenant_id), "slug": "bytefix-repairs"}

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
        "select business_name, slug from tenants where id = $1", tenant_id
    )
    assert tenant_row is not None
    assert tenant_row["business_name"] == "Bytefix Repairs"
    assert tenant_row["slug"] == "bytefix-repairs"

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
        "abn": "51 824 753 556",
        "gst": "yes",
    }
    await superuser_conn.execute("delete from tenants where id = $1", tenant_id)


async def test_confirm_writes_no_catalog_or_pricing_rows(
    client: httpx.AsyncClient, superuser_conn: asyncpg.Connection[Any]
) -> None:
    """O-1 captures a profile, not a priced catalog - prices come from uploads."""
    token, tenant_id = await _signup_tenant_admin(client)
    await _walk_to_confirm(client, token)
    await client.post(
        "/api/onboarding/confirm",
        json={"slug": _page_slug(tenant_id)},
        headers={"Authorization": f"Bearer {token}"},
    )

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
    token, tenant_id = await _signup_tenant_admin(client)
    headers = {"Authorization": f"Bearer {token}"}
    await _walk_to_confirm(client, token)

    first = await client.post(
        "/api/onboarding/confirm", json={"slug": _page_slug(tenant_id)}, headers=headers
    )
    assert first.status_code == 200
    second = await client.post("/api/onboarding/confirm", headers=headers)
    assert second.status_code == 409


async def test_confirm_refuses_a_taken_business_page_address(
    client: httpx.AsyncClient, superuser_conn: asyncpg.Connection[Any]
) -> None:
    token, _tenant_id = await _signup_tenant_admin(client)
    await superuser_conn.execute(
        "insert into tenants (slug, name) values ('bytefix-repairs', 'Existing business')"
    )
    await _walk_to_confirm(client, token)

    response = await client.post(
        "/api/onboarding/confirm", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "That page address is already taken. Choose another."
    await superuser_conn.execute("delete from tenants where slug = 'bytefix-repairs'")


async def test_message_at_confirm_stage_is_conflict(client: httpx.AsyncClient) -> None:
    token, tenant_id = await _signup_tenant_admin(client)
    headers = {"Authorization": f"Bearer {token}"}
    await _walk_to_confirm(client, token)

    # Confirm, then try to send another message.
    await client.post(
        "/api/onboarding/confirm", json={"slug": _page_slug(tenant_id)}, headers=headers
    )
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


# --- URL turn (O-3 site-as-shortcut) ------------------------------------------


class UrlFakeProvider(BaseFakeProvider):
    """Returns a URL-shaped extraction: the page states business_type/services/
    hours. No chat is needed - the URL turn's reply is a server-synthesized
    read-back."""

    async def extract(
        self, *, system_prompt: str, user_input: str, schema: type[SchemaT]
    ) -> SchemaT:
        return schema.model_validate(
            {
                "profile": {
                    "business_type": "phone repair shop",
                    "services": "screen repairs, battery replacements",
                    "hours": "Mon-Fri 9-6",
                }
            }
        )

    async def chat(self, messages: list[ChatMessage]) -> str:
        return ""

    async def chat_stream(self, messages: list[ChatMessage]) -> AsyncIterator[str]:
        if False:
            yield ""


@pytest.fixture
def uploads_tmp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("UPLOADS_DIR", str(tmp_path))
    get_settings.cache_clear()
    return tmp_path


def _patch_fetch(monkeypatch: pytest.MonkeyPatch, html: bytes) -> None:
    async def fake_fetch(url: str, *, client: httpx.AsyncClient | None = None) -> bytes:
        return html

    monkeypatch.setattr("app.features.knowledge.service.fetch_page", fake_fetch)


_CANNED_URL_HTML = (
    b"<html><head><title>Bytefix</title></head>"
    b"<body><main>Phone repair shop. Screen repairs and batteries. "
    b"Open weekdays 9 to 6.</main></body></html>"
)


async def test_url_message_scrapes_ingests_and_reads_back(
    client: httpx.AsyncClient,
    uploads_tmp: Path,
    superuser_conn: asyncpg.Connection[Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token, tenant_id = await _signup_tenant_admin(client)
    headers = {"Authorization": f"Bearer {token}"}
    app.dependency_overrides[get_llm_provider] = lambda: UrlFakeProvider()
    _patch_fetch(monkeypatch, _CANNED_URL_HTML)
    try:
        body = await _send(client, headers, text="https://bytefix.example.com")
    finally:
        app.dependency_overrides.pop(get_llm_provider, None)

    # The page pre-filled the profile fields the read-back covers.
    assert body["draft"]["business_type"] == "phone repair shop"
    assert body["draft"]["services"] == "screen repairs, battery replacements"
    assert body["draft"]["hours"] == "Mon-Fri 9-6"

    assistant_msgs = [m["content"] for m in body["history"] if m["role"] == "assistant"]
    assert any("Here's what I've got from your site" in m for m in assistant_msgs)

    # The site became a ready 'website' document.
    doc = await superuser_conn.fetchrow(
        "select doc_type, status, filename from documents where tenant_id = $1",
        tenant_id,
    )
    assert doc is not None
    assert doc["doc_type"] == "website"
    assert doc["status"] == "ready"
    assert doc["filename"] == "https://bytefix.example.com"


async def test_url_message_scrape_failure_falls_back(
    client: httpx.AsyncClient, uploads_tmp: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    token, _tenant_id = await _signup_tenant_admin(client)
    headers = {"Authorization": f"Bearer {token}"}
    app.dependency_overrides[get_llm_provider] = lambda: UrlFakeProvider()

    async def fail_fetch(url: str, *, client: httpx.AsyncClient | None = None) -> bytes:
        raise ValueError("no extractable content at this URL")

    monkeypatch.setattr("app.features.knowledge.service.fetch_page", fail_fetch)
    try:
        body = await _send(client, headers, text="https://empty.example.com")
    finally:
        app.dependency_overrides.pop(get_llm_provider, None)

    # Nothing captured, and the owner gets the calm line - which offers the other
    # two ways in and says knowledge can wait. Onboarding is never blocked on it.
    assert body["draft"] == {}
    assistant_msgs = [m["content"] for m in body["history"] if m["role"] == "assistant"]
    assert any("couldn't read that page" in m for m in assistant_msgs)
    assert any("Settings > Knowledge" in m for m in assistant_msgs)


async def test_url_message_survives_an_unreachable_host(
    client: httpx.AsyncClient, uploads_tmp: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A dead link is a transport error, not a ValueError, at the httpx layer.
    It has to reach the owner as the same calm line, never as a 500."""
    token, _tenant_id = await _signup_tenant_admin(client)
    headers = {"Authorization": f"Bearer {token}"}
    app.dependency_overrides[get_llm_provider] = lambda: UrlFakeProvider()

    async def unreachable(url: str, *, client: httpx.AsyncClient | None = None) -> bytes:
        raise ValueError("could not read this URL (ConnectError)")

    monkeypatch.setattr("app.features.knowledge.service.fetch_page", unreachable)
    try:
        body = await _send(client, headers, text="please read https://nope.invalid/")
    finally:
        app.dependency_overrides.pop(get_llm_provider, None)

    assistant_msgs = [m["content"] for m in body["history"] if m["role"] == "assistant"]
    assert any("couldn't read that page" in m for m in assistant_msgs)


async def test_url_stream_leads_with_the_reading_stamp(
    client: httpx.AsyncClient, uploads_tmp: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The 'Reading your site' stamp covers the scrape, so it must be the first
    event on the wire - emitted before the fetch, not after it."""
    token, _tenant_id = await _signup_tenant_admin(client)
    headers = {"Authorization": f"Bearer {token}"}
    app.dependency_overrides[get_llm_provider] = lambda: UrlFakeProvider()
    _patch_fetch(monkeypatch, _CANNED_URL_HTML)
    try:
        async with client.stream(
            "POST",
            "/api/onboarding/message/stream",
            json={"text": "https://bytefix.example.com"},
            headers=headers,
        ) as resp:
            assert resp.status_code == 200
            events: list[dict[str, Any]] = []
            async for line in resp.aiter_lines():
                if line.startswith("data: "):
                    events.append(json.loads(line[6:]))
    finally:
        app.dependency_overrides.pop(get_llm_provider, None)

    assert events[0] == {"type": "progress", "stage": "reading_site"}
    assert [e["type"] for e in events].count("progress") == 1
    reply = next(e for e in events if e["type"] == "reply")
    assert "Here's what I've got from your site" in reply["text"]


def test_find_url_extracts_http_url_and_strips_punctuation() -> None:
    assert _find_url("check https://bytefix.example.com, thanks") == "https://bytefix.example.com"
    assert _find_url("https://bytefix.example.com.") == "https://bytefix.example.com"


def test_find_url_ignores_prose_and_bare_domains() -> None:
    assert _find_url("we fix phones") is None
    assert _find_url("open weekdays 9 to 5.30pm") is None
    # A bare host with no path stays prose: too easy to trip on a sentence.
    assert _find_url("see bytefix.example.com") is None


def test_find_url_accepts_a_bare_domain_that_carries_a_path() -> None:
    """O-7: an owner pastes what the address bar shows them, which is usually
    scheme-less. Before O-7 that fell through to an ordinary text turn and the
    page was never fetched at all - the link looked ignored."""
    assert _find_url("ubereats.com/store/sababa") == "https://ubereats.com/store/sababa"
    assert _find_url("www.bytefix.example.com") == "https://www.bytefix.example.com"
    assert _find_url("have a look at bytefix.example.com/menu") == (
        "https://bytefix.example.com/menu"
    )


def test_find_url_never_reads_a_price_as_a_link() -> None:
    """The guard the loose match has to survive: money and ratings contain both
    a dot and a slash, and onboarding is full of them."""
    assert _find_url("$16.50 a plate") is None
    assert _find_url("we charge 16.50/plate for catering") is None
    assert _find_url("it is 3.5/5 stars") is None
    assert _find_url("email me at sam@shop.example") is None
