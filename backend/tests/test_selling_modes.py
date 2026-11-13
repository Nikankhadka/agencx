"""32 slice A: selling-mode inference, confirmation, and stored config.

The inference is a pure keyword scorer, so most of this file is unit-level and
needs no database. The route tests at the bottom drive the three
``/api/onboarding/selling-mode`` endpoints against the real app, because what
they pin - the one-statement write, the 422 vocabulary, and the stored-config
summary - is only true of the wiring, not of the pure functions.
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
from pydantic import ValidationError

from app.features.onboarding import service as onboarding_service
from app.features.onboarding.selling_modes import (
    LABEL_DEFAULTS,
    Mode,
    SellingMode,
    SourceMaterial,
    infer_selling_mode,
    normalize_selling_mode,
    summary_for,
)
from app.llm.dependency import get_embedder_dependency, get_llm_provider
from app.main import app
from app.onboarding.agent import OnboardingRecord, progress
from app.shared import db
from app.shared.config import get_settings
from tests.conftest import _app_dsn_for
from tests.fakes import BaseFakeProvider, ZeroEmbedder

TEST_JWT_SECRET = "test-only-supabase-jwt-secret-do-not-use-in-prod"  # noqa: S105

# The four samples the ticket names, written as the surface of a real source
# rather than as keyword soup - each has to win on content, not on one word the
# scorer was told to look for.
MENU_SOURCE = (
    "Sababa Kitchen. Our menu: falafel wrap $12, chicken shawarma $15, "
    "hummus $9. Order online for pickup or delivery. Eat in or takeaway."
)
SERVICE_SOURCE = (
    "Fresh Cuts barber studio. Services: haircut 30 minutes, beard trim 15 "
    "minutes, hot towel shave 45 minutes. Book now, appointments available."
)
QUOTE_SOURCE = (
    "Northside Cleaning. We look after homes and offices. Prices are custom, so "
    "request a quote or get a free estimate. We arrange a site visit first."
)
PRODUCT_SOURCE = (
    "Harbour Supply store. Shop our products: work gloves, tape measures, safety "
    "glasses. Add to cart, free shipping over $80."
)

ALL_MODES = ["orders", "bookings", "quotes", "products"]


# --- inference ---------------------------------------------------------------


def test_a_menu_source_infers_orders() -> None:
    suggestion = infer_selling_mode(SourceMaterial(source_text=MENU_SOURCE))
    assert suggestion.mode == "orders"
    assert suggestion.confidence == "high"
    assert suggestion.capabilities.sell == ["orders"]


def test_a_service_list_with_durations_infers_bookings() -> None:
    suggestion = infer_selling_mode(SourceMaterial(source_text=SERVICE_SOURCE))
    assert suggestion.mode == "bookings"
    assert suggestion.confidence == "high"
    assert suggestion.capabilities.schedule == "slot"


def test_quote_phrases_infer_quotes() -> None:
    suggestion = infer_selling_mode(SourceMaterial(source_text=QUOTE_SOURCE))
    assert suggestion.mode == "quotes"
    assert suggestion.confidence == "high"
    assert suggestion.capabilities.acceptance == "owner"


def test_a_product_grid_infers_products() -> None:
    suggestion = infer_selling_mode(SourceMaterial(source_text=PRODUCT_SOURCE))
    assert suggestion.mode == "products"
    assert suggestion.confidence == "high"
    assert suggestion.capabilities.stock == "counted"


def test_an_ambiguous_source_offers_two_candidate_modes() -> None:
    """Two equally strong nav signals: return both and ask which is primary."""
    suggestion = infer_selling_mode(
        SourceMaterial(source_text="Order online for pickup. Book now for appointments.")
    )
    assert suggestion.confidence == "medium"
    assert len(suggestion.candidates) == 2
    assert set(suggestion.candidates) == {"orders", "bookings"}
    assert suggestion.mode in suggestion.candidates


def test_no_source_offers_all_four_modes() -> None:
    suggestion = infer_selling_mode(SourceMaterial())
    assert suggestion.confidence == "low"
    assert suggestion.candidates == ALL_MODES
    # A low-confidence suggestion still carries a usable bundle, so the card can
    # render the four choices without a second call.
    assert suggestion.mode == "orders"
    assert suggestion.capabilities.sell == ["orders"]


def test_a_business_type_alone_is_not_enough_to_be_confident() -> None:
    """Business type is the weak signal the ticket names - it never wins alone."""
    suggestion = infer_selling_mode(
        SourceMaterial(profile={"business_type": "a neighbourhood cafe"})
    )
    assert suggestion.confidence == "low"
    assert suggestion.candidates == ALL_MODES


def test_evidence_names_the_signals_it_scored() -> None:
    suggestion = infer_selling_mode(SourceMaterial(source_text=MENU_SOURCE))
    evidence = "\n".join(suggestion.evidence)
    assert '"order online"' in evidence
    assert "your website" in evidence
    # Every entry names a phrase that is actually in the source, so a wrong guess
    # is explainable to the owner instead of merely asserted at them.
    assert all(entry.startswith('"') for entry in suggestion.evidence)


def test_an_offering_list_can_carry_the_inference() -> None:
    """A document's offerings reach the scorer even with no nav text."""
    suggestion = infer_selling_mode(
        SourceMaterial(
            profile={"business_name": "Fresh Cuts"},
            offerings=("haircut 30 minutes", "beard trim 15 minutes"),
        )
    )
    assert suggestion.mode == "bookings"


# --- labels ------------------------------------------------------------------


def test_labels_fill_every_missing_key() -> None:
    config = normalize_selling_mode(mode="orders", capabilities=None, labels={})
    assert config.labels == {
        **LABEL_DEFAULTS,
        **{
            "item": "Dish",
            "items": "Menu",
            "work": "Orders",
            "add_item": "Add a dish",
            "time": "Prep time",
            "sold_out": "Sold out today",
            "action": "Order",
        },
    }


def test_a_partial_label_map_keeps_the_mode_presets_and_the_defaults() -> None:
    config = normalize_selling_mode(
        mode="orders", capabilities=None, labels={"items": "Treatments"}
    )
    assert config.labels["items"] == "Treatments"
    assert config.labels["work"] == "Orders"
    assert config.labels["item"] == "Dish"


def test_an_unknown_label_key_is_dropped() -> None:
    config = normalize_selling_mode(
        mode="orders", capabilities=None, labels={"items": "Menu", "nonsense": "x"}
    )
    assert "nonsense" not in config.labels
    assert set(config.labels) == set(LABEL_DEFAULTS)


def test_label_values_are_coerced_to_strings() -> None:
    config = normalize_selling_mode(mode="orders", capabilities=None, labels={"items": 42})
    assert config.labels["items"] == "42"


# --- the summary -------------------------------------------------------------


def test_the_summary_is_built_from_the_stored_config() -> None:
    orders = normalize_selling_mode(mode="orders", capabilities=None, labels={})
    assert summary_for(orders).startswith("Your assistant will take orders")
    assert "menu" in summary_for(orders)
    assert summary_for(orders).endswith("You can change this later.")

    renamed = normalize_selling_mode(
        mode="orders",
        capabilities={"stock": "counted"},
        labels={"items": "Treatments", "item": "Treatment"},
    )
    summary = summary_for(renamed)
    assert "treatments" in summary
    assert "keep a count of your treatments" in summary
    assert summary != summary_for(orders)


def test_a_stored_config_round_trips_through_the_model() -> None:
    config = normalize_selling_mode(mode="quotes", capabilities=None, labels={})
    assert SellingMode.model_validate(config.model_dump()) == config


# --- the defaults ------------------------------------------------------------


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("deposit_bps", 10001),
        ("deposit_bps", -1),
        ("lead_time_minutes", -1),
        ("delivery_fee_cents", -5000),
        ("delivery_radius_km", -1),
        ("hold_ttl_minutes", 0),
        ("owner_hold_ttl_minutes", 0),
        ("slot_increment_minutes", 0),
    ],
)
def test_a_default_outside_its_bound_is_rejected(key: str, value: int) -> None:
    """32: the ticket's own bounds, enforced where the value is written.

    Slice E divides by these (`total_cents * deposit_bps / 10000`) and steps the
    slot grid by `slot_increment_minutes`, so a stored out-of-range value is not
    a cosmetic problem - it is the number the ordering engine runs on.
    """
    with pytest.raises(ValidationError):
        normalize_selling_mode(mode="orders", capabilities=None, labels={}, defaults={key: value})


@pytest.mark.parametrize(
    ("key", "value", "expected"),
    [
        ("deposit_bps", 0, 0),
        ("deposit_bps", 10000, 10000),
        ("lead_time_minutes", 0, 0),
        ("delivery_fee_cents", 0, 0),
        ("delivery_radius_km", 0, 0),
        ("hold_ttl_minutes", 1, 1),
        ("owner_hold_ttl_minutes", 1, 1),
        ("slot_increment_minutes", 1, 1),
        # A JSON number arrives as a string often enough that the coercion is
        # part of the contract - bounded, not batch-rewritten.
        ("lead_time_minutes", "45", 45),
    ],
)
def test_a_default_on_its_bound_is_kept(key: str, value: Any, expected: int) -> None:
    config = normalize_selling_mode(
        mode="orders", capabilities=None, labels={}, defaults={key: value}
    )
    assert config.defaults[key] == expected


def test_a_null_default_is_a_validation_error_not_a_crash() -> None:
    """`{"defaults": {"lead_time_minutes": null}}` used to be `int(None)` - a 500."""
    with pytest.raises(ValidationError):
        normalize_selling_mode(
            mode="orders", capabilities=None, labels={}, defaults={"lead_time_minutes": None}
        )


def test_a_fractional_default_is_rejected_rather_than_truncated() -> None:
    with pytest.raises(ValidationError):
        normalize_selling_mode(
            mode="orders", capabilities=None, labels={}, defaults={"lead_time_minutes": 1.5}
        )


def test_a_default_timezone_must_be_a_real_zone() -> None:
    with pytest.raises(ValidationError):
        normalize_selling_mode(
            mode="orders", capabilities=None, labels={}, defaults={"timezone": "Mars/Olympus"}
        )

    config = normalize_selling_mode(
        mode="orders", capabilities=None, labels={}, defaults={"timezone": "Asia/Tokyo"}
    )
    assert config.defaults["timezone"] == "Asia/Tokyo"


# --- the interview stage -----------------------------------------------------


def _record(**overrides: Any) -> OnboardingRecord:
    payload: dict[str, Any] = {
        "version": 4,
        "draft": {"owner_display_name": "Sam"},
        "knowledge_pending": False,
    }
    payload.update(overrides)
    return OnboardingRecord.from_jsonb(payload)


def test_progress_asks_the_selling_mode_after_the_source_is_settled() -> None:
    stage, input_spec, can_confirm = progress(_record())
    assert stage == "selling_mode"
    assert input_spec is not None
    assert can_confirm is False


def test_progress_keeps_the_source_ask_ahead_of_the_selling_mode() -> None:
    stage, _input, _can_confirm = progress(_record(knowledge_pending=True))
    assert stage == "knowledge"


def test_progress_keeps_the_name_ahead_of_the_selling_mode() -> None:
    stage, _input, _can_confirm = progress(_record(draft={}, knowledge_pending=False))
    assert stage == "owner_display_name"


def test_progress_stops_asking_once_the_mode_is_confirmed() -> None:
    record = _record()
    record.selling_mode = normalize_selling_mode(
        mode="orders", capabilities=None, labels={}
    ).model_dump()
    stage, _input, _can_confirm = progress(record)
    # business_name is the first beat this record is missing, and the mode is
    # behind it now - asked exactly once.
    assert stage == "business_name"


def test_a_completed_record_never_reopens_the_selling_mode() -> None:
    """A tenant that went live before this stage existed keeps working."""
    stage, _input, can_confirm = progress(
        _record(
            completed=True,
            draft={
                "owner_display_name": "Sam",
                "business_name": "Bytefix",
                "business_type": "phone repair",
                "headcount": "just me",
                "hours": "Mon-Fri 9-5",
                "services": ["screen repair"],
                "customer_voice_preset": "warm and casual",
                "contact": "owner@bytefix.dev",
                "abn": "none",
                "gst": "no",
            },
        )
    )
    assert stage == "confirm"
    # `completed` is what makes confirm un-offerable; the point of this test is
    # that the interview is not sent back for a question it never asked.
    assert can_confirm is False


def test_the_selling_mode_survives_a_jsonb_round_trip() -> None:
    record = _record()
    config = normalize_selling_mode(mode="products", capabilities=None, labels={})
    record.selling_mode = config.model_dump()
    restored = OnboardingRecord.from_jsonb(record.to_jsonb())
    assert restored.selling_mode == record.selling_mode
    assert restored.version == 4


# --- the routes --------------------------------------------------------------


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
    app.dependency_overrides[get_llm_provider] = BaseFakeProvider
    app.dependency_overrides[get_embedder_dependency] = ZeroEmbedder
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac
    finally:
        app.dependency_overrides.pop(get_llm_provider, None)
        app.dependency_overrides.pop(get_embedder_dependency, None)
        await db.close_pool()


def _token(user_id: uuid.UUID) -> str:
    now = int(time.time())
    payload = {"sub": str(user_id), "aud": "authenticated", "iat": now, "exp": now + 3600}
    return jwt.encode(payload, TEST_JWT_SECRET, algorithm="HS256")


async def _owner(client: httpx.AsyncClient) -> tuple[dict[str, str], uuid.UUID]:
    token = _token(uuid.uuid4())
    response = await client.post(
        "/api/tenants",
        json={"slug": f"selling-{uuid.uuid4().hex[:8]}", "name": "Selling Mode Co"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    return {"Authorization": f"Bearer {token}"}, uuid.UUID(response.json()["tenant_id"])


async def _settle_source(tenant_id: uuid.UUID, draft: dict[str, Any] | None = None) -> None:
    """Put the record where the selling-mode stage is the next thing asked.

    Written through the same checkpoint the interview uses, so the routes read
    exactly what a real interview would have left behind.
    """
    await onboarding_service.save_record(
        tenant_id=tenant_id,
        record={
            "version": 4,
            "draft": draft or {"owner_display_name": "Sam"},
            "knowledge_pending": False,
            "completed": False,
        },
    )


def _caps(mode: Mode = "orders", **overrides: Any) -> dict[str, Any]:
    preset = normalize_selling_mode(mode=mode, capabilities=None, labels={})
    return {**preset.capabilities.model_dump(), **overrides}


async def _ordering(tenant_id: uuid.UUID) -> dict[str, Any] | None:
    async with db.tenant_context(tenant_id, "tenant_admin") as conn:
        raw = await conn.fetchval(
            "select config->'ordering' from tenant_config where tenant_id = $1", tenant_id
        )
    if raw is None:
        return None
    parsed = json.loads(raw) if isinstance(raw, str) else raw
    assert isinstance(parsed, dict)
    return parsed


@pytest.mark.db
async def test_the_suggestion_route_answers_before_anything_is_stored(
    client: httpx.AsyncClient,
) -> None:
    headers, tenant_id = await _owner(client)
    await _settle_source(
        tenant_id,
        {
            "owner_display_name": "Sam",
            "business_name": "Sababa Kitchen",
            "business_type": "a neighbourhood cafe",
            "services": ["falafel wrap", "chicken shawarma"],
        },
    )

    response = await client.get("/api/onboarding/selling-mode/suggestion", headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["mode"] in ALL_MODES
    assert body["confidence"] in {"high", "medium", "low"}
    assert isinstance(body["evidence"], list)
    assert body["config"] is None
    assert body["summary"]


@pytest.mark.db
async def test_the_confirmation_writes_the_record_and_the_config_in_one_step(
    client: httpx.AsyncClient,
) -> None:
    headers, tenant_id = await _owner(client)
    await _settle_source(tenant_id)

    response = await client.post(
        "/api/onboarding/selling-mode",
        json={
            "mode": "orders",
            "capabilities": _caps("orders"),
            "labels": {"items": "Menu"},
        },
        headers=headers,
    )
    assert response.status_code == 200, response.text
    state = response.json()
    # The confirmation advances the cursor with no model call: the next beat is
    # asked in the reply the client renders.
    assert state["stage"] != "selling_mode"
    assert state["history"][-1]["role"] == "assistant"
    assert "?" in state["history"][-1]["content"]

    stored = await _ordering(tenant_id)
    assert stored is not None
    assert stored["mode"] == "orders"
    assert stored["capabilities"]["stock"] == "flag"
    assert stored["labels"]["items"] == "Menu"
    # `items` was the only label given, so every other key is a real default.
    assert stored["labels"]["work"] == "Orders"
    assert stored["labels"]["sold_out"] == "Sold out today"
    assert stored["defaults"]["hold_ttl_minutes"] == 15

    record = await onboarding_service.load_record(tenant_id=tenant_id)
    assert OnboardingRecord.from_jsonb(record).selling_mode is not None


@pytest.mark.db
async def test_a_correction_rewrites_the_config_and_leaves_orders_alone(
    client: httpx.AsyncClient, superuser_conn: asyncpg.Connection[Any]
) -> None:
    headers, tenant_id = await _owner(client)
    await _settle_source(tenant_id)
    first = await client.post(
        "/api/onboarding/selling-mode",
        json={"mode": "orders", "capabilities": _caps("orders"), "labels": {}},
        headers=headers,
    )
    assert first.status_code == 200, first.text
    before = await _ordering(tenant_id)
    assert before is not None and before["capabilities"]["sell"] == ["orders"]

    response = await client.post(
        "/api/onboarding/selling-mode",
        json={"mode": "bookings", "capabilities": _caps("bookings"), "labels": {}},
        headers=headers,
    )
    assert response.status_code == 200, response.text

    after = await _ordering(tenant_id)
    assert after is not None
    assert after["capabilities"]["sell"] == ["bookings"]
    assert after["capabilities"]["schedule"] == "slot"
    assert after["labels"]["items"] == "Services"
    assert after["labels"]["work"] == "Bookings"

    orders = await superuser_conn.fetchval(
        "select count(*) from orders where tenant_id = $1", tenant_id
    )
    assert orders == 0


@pytest.mark.db
async def test_an_owner_set_default_lands_on_the_stored_config(
    client: httpx.AsyncClient,
) -> None:
    """32: the card's "how long does an order take?" row writes the real default.

    Only the key the row owns is meant to move; the rest of the block keeps the
    module constant.
    """
    headers, tenant_id = await _owner(client)
    await _settle_source(tenant_id)
    response = await client.post(
        "/api/onboarding/selling-mode",
        json={
            "mode": "orders",
            "capabilities": _caps("orders"),
            "labels": {},
            "defaults": {"lead_time_minutes": 45},
        },
        headers=headers,
    )
    assert response.status_code == 200, response.text

    stored = await _ordering(tenant_id)
    assert stored is not None
    assert stored["defaults"]["lead_time_minutes"] == 45
    assert stored["defaults"]["hold_ttl_minutes"] == 15

    # The card reads it back from the same payload, not from a client constant.
    state = await client.get("/api/onboarding/selling-mode", headers=headers)
    assert state.json()["config"]["defaults"]["lead_time_minutes"] == 45


@pytest.mark.db
async def test_the_confirm_stage_reads_the_stored_config_back(
    client: httpx.AsyncClient,
) -> None:
    """32: the sentence the owner approves is the row, not the inference.

    The confirm screen renders its summary from `config.ordering`, so a
    correction made on the card changes the sentence the go-live button sits
    under - and a stage with nothing stored answers null rather than quietly
    showing the guess.
    """
    headers, tenant_id = await _owner(client)
    empty = await client.get("/api/onboarding/state", headers=headers)
    assert empty.json()["stage"] == "owner_display_name"
    assert empty.json()["selling_mode"] is None

    await _settle_source(
        tenant_id,
        {
            "owner_display_name": "Sam",
            "business_name": "Fresh Cuts",
            "business_type": "barber studio",
            "headcount": "just me",
            "hours": "Mon-Fri 9-6",
            "services": ["haircut"],
            "customer_voice_preset": "warm_casual",
            "contact": "555-0100",
            "abn": "none",
            "gst": "no",
        },
    )
    # No mode yet, so the interview is still asking for it - not at confirm.
    assert (await client.get("/api/onboarding/state", headers=headers)).json()["stage"] == (
        "selling_mode"
    )

    correction = {"mode": "bookings", "capabilities": _caps("bookings"), "labels": {}}
    await client.post("/api/onboarding/selling-mode", json=correction, headers=headers)
    at_confirm = (await client.get("/api/onboarding/state", headers=headers)).json()
    assert at_confirm["stage"] == "confirm"
    assert at_confirm["can_confirm"] is True
    assert at_confirm["selling_mode"]["mode"] == "bookings"
    assert "take bookings for your services" in at_confirm["selling_mode"]["summary"]

    # The card is edited again on the confirm screen: one statement rewrites
    # config.ordering, and the next read of the screen names the new config.
    orders = {"mode": "orders", "capabilities": _caps("orders"), "labels": {}}
    await client.post("/api/onboarding/selling-mode", json=orders, headers=headers)
    edited = (await client.get("/api/onboarding/state", headers=headers)).json()
    assert edited["stage"] == "confirm"
    assert "take orders from your menu" in edited["selling_mode"]["summary"]
    assert edited["selling_mode"]["summary"] != at_confirm["selling_mode"]["summary"]


@pytest.mark.db
async def test_the_get_route_is_404_free_and_reads_the_stored_config(
    client: httpx.AsyncClient,
) -> None:
    headers, tenant_id = await _owner(client)
    empty = await client.get("/api/onboarding/selling-mode", headers=headers)
    assert empty.status_code == 200
    assert empty.json()["config"] is None
    assert empty.json()["summary"] is None

    await client.post(
        "/api/onboarding/selling-mode",
        json={"mode": "orders", "capabilities": _caps("orders"), "labels": {}},
        headers=headers,
    )
    stored = await client.get("/api/onboarding/selling-mode", headers=headers)
    assert stored.status_code == 200
    assert stored.json()["config"]["mode"] == "orders"
    assert "menu" in stored.json()["summary"]

    # The summary is a read of the stored config, so editing the config edits
    # the sentence - it is never composed from the request that wrote it.
    async with db.tenant_context(tenant_id, "tenant_admin") as conn:
        await conn.execute(
            "update tenant_config set config = jsonb_set(config, "
            "'{ordering,labels,items}', '\"Treatments\"'::jsonb, true) "
            "where tenant_id = $1",
            tenant_id,
        )
    edited = await client.get("/api/onboarding/selling-mode", headers=headers)
    assert "treatments" in edited.json()["summary"].lower()
    assert edited.json()["summary"] != stored.json()["summary"]


@pytest.mark.db
@pytest.mark.parametrize(
    "body",
    [
        {"mode": "cafe", "capabilities": _caps(), "labels": {}},
        {"mode": "orders", "capabilities": _caps(sell=[]), "labels": {}},
        {"mode": "orders", "capabilities": _caps(schedule="whenever"), "labels": {}},
        {"mode": "orders", "capabilities": _caps(fulfillment=[]), "labels": {}},
        {"mode": "orders", "capabilities": _caps(), "labels": {}, "defaults": {"nonsense": 1}},
        # 32: the bounds the ticket states for the same names. A null used to
        # reach `int(None)` and answer 500 on an owner route.
        {
            "mode": "orders",
            "capabilities": _caps(),
            "labels": {},
            "defaults": {"lead_time_minutes": None},
        },
        {
            "mode": "orders",
            "capabilities": _caps(),
            "labels": {},
            "defaults": {"deposit_bps": 999999},
        },
        {
            "mode": "orders",
            "capabilities": _caps(),
            "labels": {},
            "defaults": {"timezone": "Mars/Olympus"},
        },
    ],
    ids=[
        "bad-mode",
        "empty-sell",
        "bad-axis",
        "empty-fulfillment",
        "unknown-default",
        "null-default",
        "out-of-range-default",
        "bad-timezone",
    ],
)
async def test_bad_input_is_rejected_with_422(
    client: httpx.AsyncClient, body: dict[str, Any]
) -> None:
    headers, tenant_id = await _owner(client)
    await _settle_source(tenant_id)
    response = await client.post("/api/onboarding/selling-mode", json=body, headers=headers)
    assert response.status_code == 422, response.text
    # The rejected field is named, so the card can say which row is wrong.
    if "defaults" in body:
        assert "defaults" in response.text
    assert await _ordering(tenant_id) is None


@pytest.mark.db
async def test_a_retried_confirmation_leaves_one_history_pair_and_one_ask(
    client: httpx.AsyncClient,
) -> None:
    """32: the card's write is a POST the client may have to retry.

    The body is the whole action, so a second identical POST must return the
    state the first one produced - one transcript pair, one next question -
    rather than appending "Got it" again from an already-advanced cursor.
    """
    headers, tenant_id = await _owner(client)
    await _settle_source(tenant_id)
    body = {"mode": "orders", "capabilities": _caps("orders"), "labels": {}}

    first = await client.post("/api/onboarding/selling-mode", json=body, headers=headers)
    assert first.status_code == 200, first.text
    retried = await client.post("/api/onboarding/selling-mode", json=body, headers=headers)
    assert retried.status_code == 200, retried.text

    state = retried.json()
    assert state["history"] == first.json()["history"]
    assert [entry["role"] for entry in state["history"]] == ["user", "assistant"]
    assert state["history"][0]["content"] == "Orders"
    # One ask, and it is the next beat's - not two copies of the same question.
    assert state["history"][1]["content"] == "Got it. What does the business go by?"

    stored = await _ordering(tenant_id)
    assert stored is not None and stored["mode"] == "orders"


@pytest.mark.db
async def test_the_confirm_gate_needs_a_selling_mode(client: httpx.AsyncClient) -> None:
    """32: no tenant goes live without the ordering block every later screen reads."""
    headers, tenant_id = await _owner(client)
    await _settle_source(
        tenant_id,
        {
            "owner_display_name": "Sam",
            "business_name": "Bytefix",
            "business_type": "phone repair",
            "headcount": "just me",
            "hours": "Mon-Fri 9-5",
            "services": ["screen repair"],
            "customer_voice_preset": "warm_casual",
            "contact": "owner@bytefix.dev",
            "abn": "none",
            "gst": "no",
        },
    )
    blocked = await client.post("/api/onboarding/confirm", json={}, headers=headers)
    assert blocked.status_code == 409
    assert "customers buy" in blocked.json()["detail"]

    await client.post(
        "/api/onboarding/selling-mode",
        json={"mode": "orders", "capabilities": _caps("orders"), "labels": {}},
        headers=headers,
    )
    # An explicit address: the suggestion for "Bytefix" is a slug another test
    # in this session already claimed, and a taken slug is a different 409.
    allowed = await client.post(
        "/api/onboarding/confirm",
        json={"slug": f"selling-{tenant_id.hex[:12]}"},
        headers=headers,
    )
    assert allowed.status_code == 200, allowed.text


@pytest.mark.db
async def test_the_me_route_carries_the_ordering_block(client: httpx.AsyncClient) -> None:
    headers, _tenant_id = await _owner(client)
    before = await client.get("/api/tenants/me", headers=headers)
    assert before.status_code == 200
    assert before.json()["ordering"] == {}

    await client.post(
        "/api/onboarding/selling-mode",
        json={"mode": "quotes", "capabilities": _caps("quotes"), "labels": {}},
        headers=headers,
    )
    after = await client.get("/api/tenants/me", headers=headers)
    assert after.json()["ordering"]["mode"] == "quotes"
    assert after.json()["ordering"]["labels"]["work"] == "Requests"
