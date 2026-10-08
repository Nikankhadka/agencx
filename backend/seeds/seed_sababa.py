"""Tenant 3 seed: Sabbaba, a Middle Eastern restaurant (Spring St, Bondi Junction).

The menu and knowledge text come from the source menu document (8 October 2026),
held as data in ``seeds/sabbaba/`` (``menu.py`` and ``knowledge.py``). Photos are
Cloudinary URLs from ``seeds/sabbaba/images.json``. Prices are the document's own
integer cents; an item the document marks "price not confirmed" seeds with
``price_cents=None`` and no pricing rule, and every priced item gets exactly one
``each`` rule.

Idempotent: re-running wipes and recreates tenant 'sababa' from scratch.
Standalone staging use (non-destructive to the other tenants)::

    docker compose run --rm \
      -e DATABASE_URL='<pooler url, port 5432>' \
      backend python -m seeds.seed_sababa

``make seed`` (the full demo world) also calls :func:`seed`, so local dev
gets bytefix + lumident + sababa together.

Usage: ``uv run python -m seeds.seed_sababa``
"""

from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path
from uuid import UUID, uuid4

from app.llm.embedder import Embedder, get_embedder
from app.shared import db
from app.shared.config import get_settings
from seeds import _helpers
from seeds.sabbaba.knowledge import KNOWLEDGE_DOCS
from seeds.sabbaba.menu import MENU

# Cloudinary photo manifest written by scripts/seed_sabbaba_images.py. Items
# without a photo are simply absent (the storefront shows a letter tile).
MEDIA = json.loads((Path(__file__).parent / "sabbaba" / "images.json").read_text())

SLUG = "sababa"
TENANT_NAME = "Sabbaba"

# Pre-onboarded profile - the demo world lands in the console, not the
# interview, so the seed writes the same end-state a real confirm produces
# (via _helpers.insert_tenant_core's profile arg). Owner name and headcount
# are demo placeholders; hours and services follow the menu document.
SABABA_PROFILE = {
    "owner_display_name": "Noa",
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
    "contact": "owner@sababa.dev",
    "abn": "none",
    "gst": "no",
    # W-9: the voice beat is part of the interview now, so a pre-onboarded
    # tenant carries the same end-state a real confirm leaves behind.
    "customer_voice_preset": "warm_casual",
    "customer_voice_custom_style": "",
}

# --- offerings: one per menu item, in document order -------------------------

CATALOG_ITEMS: list[tuple[str, str, int | None, list[str]]] = [
    (name, description, price_cents, [category])
    for category, items in MENU.items()
    for name, description, price_cents in items
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

# Demo console orders: item names are real menu offerings.
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
        # Third vertical, same code: the restaurant takes the lean column
        # default (search + escalate) like lumident, so enabled_tools stays
        # unwritten here - only bytefix opts into the commerce tools (D-2).
        brand={"display_name": TENANT_NAME, "accent": "#C2410C"},
        config={
            "customer": {
                "greeting": (
                    "Hi! Welcome to Sabbaba. I can walk you through the menu, "
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
        profile=SABABA_PROFILE,
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
                    f"SAB-{4001 + i}",
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
        await _helpers.ingest_documents(
            conn,
            tenant_id,
            KNOWLEDGE_DOCS,
            embedder,
        )


async def seed(embedder: Embedder | None = None) -> UUID:
    """Seed (or re-seed) the Sabbaba tenant. Returns the tenant id."""
    async with _helpers.seed_pool():
        async with db.tenant_context(None, "platform_admin") as conn:
            await _helpers.wipe_tenant(conn, SLUG)

        tenant_id = uuid4()
        await _seed_core(tenant_id)
        print(f"seeded core data for tenant {tenant_id} (slug={SLUG})")

        resolved_embedder = embedder or get_embedder(get_settings())
        await _seed_knowledge(tenant_id, resolved_embedder)
        print("ingested knowledge documents and catalog items")

        return tenant_id


def main() -> None:
    tenant_id = asyncio.run(seed())
    print(f"done: tenant_id={tenant_id}")


if __name__ == "__main__":
    main()
