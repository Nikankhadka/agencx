"""The Sabbaba seed script, run against wren_test with a stub embedder.

Mirrors test_seed_tenant1.py: ``seed()`` reuses whatever pool already
exists, so pointing a pool at wren_test first exercises the exact code
path the real ``python -m seeds.seed_sababa`` entrypoint uses, without
loading a real embedding model.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

import asyncpg
import pytest
import pytest_asyncio

from app.features.escalations.service import RESOLUTION_STAMP
from app.shared import db
from seeds.sabbaba.knowledge import KNOWLEDGE_DOCS
from seeds.seed_sababa import (
    CATALOG_ITEMS,
    MEDIA,
    ORDER_ITEMS,
    PRICING_RULES,
    SABABA_PROFILE,
    SLUG,
    TENANT_NAME,
    sabbaba_conversations,
    seed,
)
from tests.conftest import _app_dsn_for
from tests.fakes import ZeroEmbedder

pytestmark = pytest.mark.db


@pytest_asyncio.fixture
async def app_pool(migrated_db: str) -> AsyncIterator[None]:
    await db.create_pool(dsn=_app_dsn_for(migrated_db), min_size=1, max_size=4)
    try:
        yield
    finally:
        await db.close_pool()


async def test_seed_creates_tenant_with_expected_counts(app_pool: None) -> None:
    tenant_id = await seed(embedder=ZeroEmbedder())

    async with db.tenant_context(tenant_id, "tenant_admin") as conn:
        slug = await conn.fetchval("select slug from tenants where id = $1", tenant_id)
        assert slug == SLUG

        catalog_count = await conn.fetchval(
            "select count(*) from offerings where tenant_id = $1", tenant_id
        )
        assert catalog_count == len(CATALOG_ITEMS)

        rules_count = await conn.fetchval(
            "select count(*) from pricing_rules where tenant_id = $1", tenant_id
        )
        assert rules_count == len(PRICING_RULES)

        orders_count = await conn.fetchval(
            "select count(*) from orders where tenant_id = $1", tenant_id
        )
        assert orders_count == len(ORDER_ITEMS) == 5

        ready_docs = await conn.fetchval(
            "select count(*) from documents where tenant_id = $1 and status = 'ready'", tenant_id
        )
        assert ready_docs == len(KNOWLEDGE_DOCS) + 1  # knowledge docs + synthetic catalog doc

        chunk_count = await conn.fetchval(
            "select count(*) from knowledge_chunks where tenant_id = $1", tenant_id
        )
        assert chunk_count > len(CATALOG_ITEMS)  # catalog chunks + at least the prose chunks


async def test_seed_is_idempotent(app_pool: None, superuser_conn: asyncpg.Connection[Any]) -> None:
    first_id = await seed(embedder=ZeroEmbedder())
    second_id = await seed(embedder=ZeroEmbedder())

    assert first_id != second_id  # re-seeding recreates the tenant with a fresh id

    count = await superuser_conn.fetchval("select count(*) from tenants where slug = $1", SLUG)
    assert count == 1  # the first tenant was wiped, not left behind

    leftover_catalog = await superuser_conn.fetchval(
        "select count(*) from offerings where tenant_id = $1", first_id
    )
    assert leftover_catalog == 0  # cascaded away with the first tenant


async def test_seed_pre_onboards_the_tenant(
    app_pool: None, superuser_conn: asyncpg.Connection[Any]
) -> None:
    tenant_id = await seed(embedder=ZeroEmbedder())

    row = await superuser_conn.fetchrow(
        "select t.business_name, c.config "
        "from tenants t join tenant_config c on c.tenant_id = t.id where t.id = $1",
        tenant_id,
    )
    assert row is not None
    assert row["business_name"] == TENANT_NAME

    config = json.loads(row["config"])
    assert config["customer_voice"] == {"preset": "warm_casual", "custom_style": None}
    assert config["onboarding"]["completed"] is True
    assert config["onboarding"]["version"] == 4
    assert config["onboarding"]["draft"] == SABABA_PROFILE
    assert config["profile"] == SABABA_PROFILE


async def test_seed_takes_the_lean_tool_default(
    app_pool: None, superuser_conn: asyncpg.Connection[Any]
) -> None:
    """D-2: sababa writes no enabled_tools, like lumident - only bytefix opts in."""
    tenant_id = await seed(embedder=ZeroEmbedder())
    row = await superuser_conn.fetchrow(
        "select enabled_tools from tenant_config where tenant_id = $1", tenant_id
    )
    assert row is not None
    lean = ["search_knowledge", "create_escalation"]
    assert json.loads(row["enabled_tools"]) == lean


async def test_seeded_offerings_carry_the_documents_prices(app_pool: None) -> None:
    """The money rule, seed-side: prices are the document's integer cents, and
    the two items it marks "price not confirmed" seed with no price at all."""
    tenant_id = await seed(embedder=ZeroEmbedder())

    async with db.tenant_context(tenant_id, "tenant_admin") as conn:
        rows = await conn.fetch(
            "select name, price_cents from offerings where tenant_id = $1", tenant_id
        )
    by_name = {r["name"]: r["price_cents"] for r in rows}
    assert by_name["Plate"] == 3000
    assert by_name["Bowl"] == 2700
    assert by_name["Pita Pocket"] == 2000
    assert by_name["Super Plate"] == 3700
    assert by_name["Falafel, 6 pieces"] == 890
    assert by_name["Sabbaba Pita Pocket"] == 1490
    assert by_name["Chunky Egg and Tender Greens Bagel"] is None
    assert by_name["Caramel Cookie"] is None


async def test_priced_offerings_and_pricing_rules_pair_one_to_one(app_pool: None) -> None:
    tenant_id = await seed(embedder=ZeroEmbedder())

    async with db.tenant_context(tenant_id, "tenant_admin") as conn:
        offerings = await conn.fetch(
            "select name, price_cents from offerings where tenant_id = $1", tenant_id
        )
        rules = await conn.fetch(
            "select code, label, unit_amount_cents, unit from pricing_rules where tenant_id = $1",
            tenant_id,
        )
    priced = {r["name"]: r["price_cents"] for r in offerings if r["price_cents"] is not None}
    assert {r["unit"] for r in rules} == {"each"}
    assert len(rules) == len(priced)  # exactly one rule per priced offering
    assert {r["label"]: r["unit_amount_cents"] for r in rules} == priced
    # The Sabbaba seed's first conversation quotes the Super Plate by this code.
    assert {r["code"]: r["unit_amount_cents"] for r in rules}["super-plate"] == 3700


async def test_seed_writes_the_greeting_and_starter_questions(app_pool: None) -> None:
    tenant_id = await seed(embedder=ZeroEmbedder())

    async with db.tenant_context(tenant_id, "tenant_admin") as conn:
        config = json.loads(
            await conn.fetchval("select config from tenant_config where tenant_id = $1", tenant_id)
        )
    customer = config["customer"]
    assert "I can walk you through the menu" in customer["greeting"]
    assert customer["starter_questions"] == [
        "Which dishes are vegan or gluten free?",
        "What are your most popular items?",
        "What time do you open?",
    ]
    assert config["profile"]["hours"] == "Monday to Sunday 6:00 am to 8:00 pm"


async def test_seed_writes_the_cover_and_one_photo_per_listed_offering(app_pool: None) -> None:
    tenant_id = await seed(embedder=ZeroEmbedder())

    async with db.tenant_context(tenant_id, "tenant_admin") as conn:
        covers = await conn.fetchval(
            "select count(*) from tenant_media where tenant_id = $1 and role = 'cover'", tenant_id
        )
        photos = await conn.fetch(
            "select o.name, m.url from tenant_media m join offerings o on o.id = m.offering_id "
            "where m.tenant_id = $1 and m.role = 'offering'",
            tenant_id,
        )
    assert covers == 1
    assert {row["name"]: row["url"] for row in photos} == {
        name: media["url"] for name, media in MEDIA["offerings"].items()
    }


async def test_seed_writes_conversations_across_states(app_pool: None) -> None:
    """A standalone re-seed leaves the Chats console with history: knowledge
    answers, a live queue row, and a resolved complaint with a contact."""
    tenant_id = await seed(embedder=ZeroEmbedder())

    async with db.tenant_context(tenant_id, "tenant_admin") as conn:
        conversations = await conn.fetch(
            "select customer_ref, customer_email, status from conversations where tenant_id = $1",
            tenant_id,
        )
        message_count = await conn.fetchval(
            "select count(*) from messages where tenant_id = $1", tenant_id
        )
        tool_names = {
            row["tool_name"]
            for row in await conn.fetch(
                "select tool_name from tool_calls where tenant_id = $1", tenant_id
            )
        }
        cost_count = await conn.fetchval(
            "select count(*) from cost_logs where tenant_id = $1", tenant_id
        )
        escalations = await conn.fetch(
            "select status, summary, intent, resolved_at from escalations where tenant_id = $1",
            tenant_id,
        )

    specs = sabbaba_conversations(datetime.now(UTC))
    assert len(conversations) == len(specs) == 5
    assert {row["status"] for row in conversations} == {"closed", "open", "escalated"}

    # Every spec message plus the resolved escalation's owner-only stamp.
    stamps = sum(1 for spec in specs if (spec["escalation"] or {}).get("status") == "resolved")
    assert message_count == sum(len(spec["messages"]) for spec in specs) + stamps
    # One cost row per assistant turn.
    assert cost_count == sum(1 for spec in specs for m in spec["messages"] if m[0] == "assistant")
    assert tool_names == {"search_knowledge", "create_escalation", "set_customer_contact"}

    by_status = {row["status"]: row for row in escalations}
    assert set(by_status) == {"open", "resolved"}
    assert by_status["open"]["resolved_at"] is None
    assert by_status["open"]["summary"] == "Lunch for 25 delivered on Friday, wants confirmation"
    assert by_status["open"]["intent"] == "offer"
    assert by_status["resolved"]["resolved_at"] is not None

    escalated = next(row for row in conversations if row["status"] == "escalated")
    assert escalated["customer_ref"] == "Maya T"
    assert escalated["customer_email"] == "maya.t@example.com"


async def test_resolved_escalation_stamps_before_the_human_reply(app_pool: None) -> None:
    tenant_id = await seed(embedder=ZeroEmbedder())

    async with db.tenant_context(tenant_id, "tenant_admin") as conn:
        conv_id = await conn.fetchval(
            "select conversation_id from escalations where tenant_id = $1 and status = 'resolved'",
            tenant_id,
        )
        assert conv_id is not None
        transcript = await conn.fetch(
            "select role, content from messages where conversation_id = $1 order by created_at, id",
            conv_id,
        )

    roles_and_text = [(row["role"], row["content"]) for row in transcript]
    assert ("system", RESOLUTION_STAMP) in roles_and_text
    stamp_index = roles_and_text.index(("system", RESOLUTION_STAMP))
    human_index = next(i for i, (role, _) in enumerate(roles_and_text) if role == "human_agent")
    assert stamp_index < human_index
