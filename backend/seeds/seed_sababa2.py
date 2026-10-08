"""Tenant 5 seed: Sabbaba 2, the fast-path clone of Sabbaba.

Same business, same 96-item menu, same categories, same Cloudinary photos,
same console conversations - with the catalog copy summarized to one line per
item and the knowledge prose condensed, so the whole prompt (contract +
profile + catalog + corpus) fits the configured fast-path budget and every
customer turn runs the 2-call path instead of hybrid retrieval. The two
budget values it needs are raised in .env.example; the seed's final check
fails loudly if the environment would not actually route this tenant to the
fast path.

Everything factual is synced from the source: prices, allergen notes and
dietary labels come from ``seeds/sabbaba/menu.py``, the knowledge builders
read the same MENU, and the conversations are the source seed's own specs
(via ``sabbaba_conversations``). Only ``seeds/sababa2/menu.py``'s summaries
are authored, and its import guard keeps them covering exactly the source
menu.

Idempotent: re-running wipes and recreates tenant 'sababa2' from scratch.
Standalone staging use (non-destructive to the other tenants)::

    docker compose run --rm \
      -e DATABASE_URL='<pooler url, port 5432>' \
      backend python -m seeds.seed_sababa2

``make seed`` (the full demo world) also calls :func:`seed`, so local dev
gets bytefix + lumident + sababa + sababa2 + wellspring together.

Usage: ``uv run python -m seeds.seed_sababa2``
"""

from __future__ import annotations

import asyncio
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from app.llm.embedder import Embedder, get_embedder
from app.services.context_package import _CONTRACT_OVERHEAD_CHARS, build_package
from app.services.retrieval import ANSWER_RESERVE_TOKENS, corpus_chars, estimate_tokens
from app.shared import db
from app.shared.config import get_settings
from seeds import _helpers
from seeds.sababa2.knowledge import KNOWLEDGE_DOCS
from seeds.sababa2.menu import SUMMARIES
from seeds.sabbaba.menu import MENU
from seeds.seed_sababa import sabbaba_conversations

# The source tenant's committed photo manifest, reused whole: the clone keeps
# every offering, so every photo has an item to attach to (no new uploads).
MEDIA = json.loads((Path(__file__).parent / "sabbaba" / "images.json").read_text())

SLUG = "sababa2"
TENANT_NAME = "Sabbaba 2"

# Same demo profile as Sabbaba, with the clone's own name and contact. The
# owner name, hours, services and voice are the source's, so the two tenants
# differ only where a real clone would.
SABABA2_PROFILE = {
    "owner_display_name": "Aniket",
    "business_name": TENANT_NAME,
    "business_type": "Middle Eastern restaurant",
    "headcount": "8",
    "hours": "Monday to Sunday 6:00 am to 8:00 pm",
    "services": [
        "Pita pockets",
        "Plates",
        "Bowls",
        "Salads",
        "Sides",
        "Dips and extras",
        "Breakfast",
        "Coffee and hot drinks",
        "Cold drinks",
        "Sweets",
    ],
    "contact": "owner@sababa2.dev",
    "abn": "none",
    "gst": "no",
    "customer_voice_preset": "warm_casual",
    "customer_voice_custom_style": "",
}

# --- offerings: the full source menu, summarized copy -------------------------

CATALOG_ITEMS: list[tuple[str, str, int | None, list[str]]] = [
    (name, SUMMARIES[name], price_cents, [category])
    for category, items in MENU.items()
    for name, _, price_cents in items
]

# --- pricing_rules: one per priced offering; unpriced items get none ---------


def _rule_code(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


PRICING_RULES: list[tuple[str, str, int, str]] = [
    (_rule_code(name), name, price_cents, "each")
    for name, _, price_cents, _ in CATALOG_ITEMS
    if price_cents is not None
]

ORDER_STATUSES = ["pending", "in_progress", "ready_for_pickup", "completed", "cancelled"]

# Same demo orders as Sabbaba; every item name is on the full menu.
ORDER_ITEMS: list[list[str]] = [
    ["Sabbaba Pita Pocket"],
    ["Falafel Plate", "Hot Chips"],
    ["Chicken Shish Bowl"],
    ["Larnaca Pita Pocket", "Housemade Lemonade"],
    ["Super Plate"],
]


async def _seed_core(tenant_id: UUID) -> None:
    await _helpers.insert_tenant_core(
        tenant_id=tenant_id,
        slug=SLUG,
        name=TENANT_NAME,
        # Same lean column default as Sabbaba (search + escalate, D-2).
        brand={"display_name": TENANT_NAME, "accent": "#C2410C"},
        config={
            "customer": {
                "greeting": (
                    "Hi! Welcome to Sabbaba 2. I can walk you through the menu, "
                    "help with dietary and allergen questions, or tell you about "
                    "the shop - what would you like to know?"
                ),
                "starter_questions": [
                    "Which dishes are vegan or gluten free?",
                    "What are your most popular items?",
                    "What time do you open?",
                ],
            }
        },
        business_name=TENANT_NAME,
        profile=SABABA2_PROFILE,
    )

    async with db.tenant_context(tenant_id, "tenant_admin") as conn:
        await _helpers.insert_offerings(conn, tenant_id, CATALOG_ITEMS)
        await _helpers.insert_media(conn, tenant_id, MEDIA["cover"], MEDIA["offerings"])
        await _helpers.insert_pricing_rules(conn, tenant_id, PRICING_RULES)
        await _helpers.insert_orders(
            conn,
            tenant_id,
            [
                (
                    f"SAB2-{4001 + i}",
                    "order",
                    f"customer-{i + 1}",
                    ORDER_STATUSES[i % len(ORDER_STATUSES)],
                    {"items": items},
                )
                for i, items in enumerate(ORDER_ITEMS)
            ],
        )


async def _seed_knowledge(tenant_id: UUID, embedder: Embedder) -> None:
    async with db.tenant_context(tenant_id, "tenant_admin") as conn:
        await _helpers.ingest_documents(conn, tenant_id, KNOWLEDGE_DOCS, embedder)


async def _seed_conversations(tenant_id: UUID) -> None:
    async with db.tenant_context(tenant_id, "tenant_admin") as conn:
        await _helpers.seed_conversations(conn, tenant_id, sabbaba_conversations(datetime.now(UTC)))


async def _assert_fast_path(tenant_id: UUID) -> None:
    """The point of this tenant: prove the assembled prompt takes the fast path.

    Raises if it does not, with the measured numbers and the two env vars to
    check - a silently-hybrid seed would look exactly like a slow demo.
    """
    async with db.tenant_context(tenant_id, "tenant_admin") as conn:
        package = await build_package(conn, tenant_id)
        total_chars = await corpus_chars(conn, tenant_id)

    catalog_chars = len(package.offerings_text())
    overhead = _CONTRACT_OVERHEAD_CHARS + len(package.profile_text()) + catalog_chars
    needed = estimate_tokens(total_chars + overhead) + ANSWER_RESERVE_TOKENS
    settings = get_settings()
    if not package.fast_path or not package.catalog_inline:
        raise RuntimeError(
            "sababa2 did not take the whole-corpus fast path: "
            f"fast_path={package.fast_path} catalog_inline={package.catalog_inline} "
            f"corpus_chars={total_chars} catalog_tokens={estimate_tokens(catalog_chars)} "
            f"needed_tokens={needed} budget={settings.corpus_fast_path_max_tokens}. "
            "Raise CORPUS_FAST_PATH_MAX_TOKENS / CATALOG_INLINE_MAX_TOKENS (see "
            ".env.example) or shrink the seed data."
        )
    print(
        f"sabbaba2 takes the fast path: {len(package.chunks)} corpus chunks, "
        f"corpus_chars={total_chars}, catalog_tokens={estimate_tokens(catalog_chars)}, "
        f"needed_tokens={needed}, budget={settings.corpus_fast_path_max_tokens}, "
        f"margin={settings.corpus_fast_path_max_tokens - needed}"
    )


async def seed(embedder: Embedder | None = None) -> UUID:
    """Seed (or re-seed) the Sabbaba 2 tenant. Returns the tenant id."""
    async with _helpers.seed_pool():
        async with db.tenant_context(None, "platform_admin") as conn:
            await _helpers.wipe_tenant(conn, SLUG)

        tenant_id = uuid4()
        await _seed_core(tenant_id)
        print(f"seeded core data for tenant {tenant_id} (slug={SLUG})")

        resolved_embedder = embedder or get_embedder(get_settings())
        await _seed_knowledge(tenant_id, resolved_embedder)
        print("ingested knowledge documents and catalog items")

        await _seed_conversations(tenant_id)
        print("seeded conversations, tool calls, costs and escalations")

        await _assert_fast_path(tenant_id)

        return tenant_id


async def link_owner(tenant_id: UUID) -> None:
    """Attach owner@sababa2.dev to the tenant so the console login lands on it.

    Without a ``users`` row the login falls into signup and onboards a stray
    tenant, which is what a standalone re-seed (the wipe cascades the old
    membership) used to cause. ``seed_demo`` does the same for the whole demo
    world; imported here, not at module level, because it imports this module.
    """
    from seeds.seed_demo import DEMO_PASSWORD, SABABA2_OWNER_EMAIL, _make_gotrue_create_auth_user

    owner_id = await _make_gotrue_create_auth_user()(SABABA2_OWNER_EMAIL, DEMO_PASSWORD)
    async with _helpers.seed_pool():
        async with db.tenant_context(None, "platform_admin") as conn:
            old = await conn.fetchval("select tenant_id from users where id = $1", owner_id)
        if old is not None:
            async with db.tenant_context(old, "tenant_admin") as conn:
                await conn.execute("delete from users where id = $1", owner_id)
        async with db.tenant_context(tenant_id, "tenant_admin") as conn:
            await conn.execute(
                "insert into users (id, tenant_id, role) values ($1, $2, 'owner')",
                owner_id,
                tenant_id,
            )
    print(f"linked {SABABA2_OWNER_EMAIL} (password {DEMO_PASSWORD}) as owner of {SLUG}")


def main() -> None:
    tenant_id = asyncio.run(seed())
    asyncio.run(link_owner(tenant_id))
    print(f"done: tenant_id={tenant_id}")


if __name__ == "__main__":
    main()
