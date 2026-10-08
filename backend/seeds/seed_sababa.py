"""Tenant 3 seed: Sabbaba, a Middle Eastern restaurant (Spring St, Bondi Junction).

The menu and knowledge text come from the source menu document (8 October 2026),
held as data in ``seeds/sabbaba/`` (``menu.py`` and ``knowledge.py``). Photos are
Cloudinary URLs from ``seeds/sabbaba/images.json``. Prices are the document's own
integer cents; an item the document marks "price not confirmed" seeds with
``price_cents=None`` and no pricing rule, and every priced item gets exactly one
``each`` rule.

A handful of console conversations (open, escalated with contact captured, and
closed with a resolved escalation) seed alongside, so a standalone re-seed
leaves the Chats surface with realistic history and not an empty list.

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
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
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

# --- Conversations -----------------------------------------------------------
#
# The Chats console history for a standalone re-seed. Explicit timestamps keep
# ordering and cost attribution deterministic, and every answer is grounded in
# the seeded knowledge docs - the traces show what a real transcript leaves
# behind (search_knowledge chunks, inspection verdicts, contact capture, an
# open escalation for the queue and a resolved one with an owner reply).


def sabbaba_conversations(now: datetime) -> list[dict[str, Any]]:
    return [
        {
            "customer_ref": "Ravi",
            "status": "closed",
            "created_at": now - timedelta(days=3, hours=3),
            "messages": [
                ("customer", "How much is the Super Plate?", None, None, 0),
                (
                    "assistant",
                    "The Super Plate is $37.00 - it comes with a choice of two "
                    "proteins, four seasonal salads and two dips, with pita. Would "
                    "you like to see the rest of the plates and bowls?",
                    "draft",
                    {
                        "inspection": {
                            "grounding": {
                                "passed": True,
                                "reason": "Price and contents match the plates price list.",
                            },
                            "policy": {"passed": True, "reason": "Warm, offers a next step."},
                        }
                    },
                    11,
                ),
            ],
            "tool_calls": [
                {
                    "on_message_index": 1,
                    "tool_name": "search_knowledge",
                    "arguments": {"query": "Super Plate price"},
                    "result": {"chunks": ["menu-plates.md#price-list"]},
                    "success": True,
                    "latency_ms": 29,
                }
            ],
            "escalation": None,
        },
        {
            "customer_ref": "Priya",
            "status": "closed",
            "created_at": now - timedelta(days=4, hours=2),
            "messages": [
                (
                    "customer",
                    "Does the lentil, quinoa and haloumi salad have dairy?",
                    None,
                    None,
                    0,
                ),
                (
                    "assistant",
                    "Yes - the halloumi in that salad is dairy (milk). The allergen "
                    "notes are read from the shop's menus and have not been "
                    "confirmed by the kitchen, so please ask the team if you need "
                    "certainty. Would you like me to pass that question on?",
                    "draft",
                    {
                        "inspection": {
                            "grounding": {
                                "passed": True,
                                "reason": "Milk (halloumi) is listed in the salad's ingredients.",
                            },
                            "policy": {
                                "passed": True,
                                "reason": "Keeps the not-confirmed caveat; guarantees nothing.",
                            },
                        }
                    },
                    13,
                ),
            ],
            "tool_calls": [
                {
                    "on_message_index": 1,
                    "tool_name": "search_knowledge",
                    "arguments": {"query": "lentil quinoa haloumi salad dairy"},
                    "result": {
                        "chunks": [
                            "allergens-and-dietary.md#allergen-notes",
                            "menu-salads.md#price-list",
                        ]
                    },
                    "success": True,
                    "latency_ms": 41,
                }
            ],
            "escalation": None,
        },
        {
            "customer_ref": "Elena",
            "status": "open",
            "created_at": now - timedelta(days=1, hours=5),
            "messages": [
                (
                    "customer",
                    "What time do you open, and can I order for pickup?",
                    None,
                    None,
                    0,
                ),
                (
                    "assistant",
                    "Sabbaba is open every day from 6:00 am to 8:00 pm. Breakfast "
                    "runs from 6:15 am and pita pockets, plates and bowls start at "
                    "11:00 am. I can't take orders here, but you can order on Uber "
                    "Eats, DoorDash or the Hey You app, or phone the shop [1].",
                    "draft",
                    {
                        "inspection": {
                            "grounding": {
                                "passed": True,
                                "reason": "Hours and channels match about-hours-contact.md.",
                            }
                        }
                    },
                    12,
                ),
            ],
            "tool_calls": [
                {
                    "on_message_index": 1,
                    "tool_name": "search_knowledge",
                    "arguments": {"query": "opening hours and how to order"},
                    "result": {
                        "chunks": [
                            "about-hours-contact.md#hours",
                            "about-hours-contact.md#ordering-and-policies",
                        ]
                    },
                    "success": True,
                    "latency_ms": 35,
                }
            ],
            "escalation": None,
        },
        {
            "customer_ref": "Maya T",
            "customer_email": "maya.t@example.com",
            "status": "escalated",
            "created_at": now - timedelta(hours=9),
            "messages": [
                (
                    "customer",
                    "We need lunch for 25 people delivered to our office on Friday "
                    "around noon. Can you cater that?",
                    None,
                    None,
                    0,
                ),
                (
                    "assistant",
                    "That's a catering request I can't confirm from here, so I've "
                    "passed it to the Sabbaba team. Could I grab your name and email "
                    "so they know who to reach out to?",
                    "escalation",
                    {
                        "inspection": {
                            "grounding": {
                                "passed": True,
                                "reason": "No catering detail claimed; handoff offered.",
                            }
                        }
                    },
                    9,
                ),
                ("customer", "Maya T, maya.t@example.com", None, None, 27),
                (
                    "assistant",
                    "Thanks, Maya. The team has your details and will be in touch "
                    "about the Friday lunch.",
                    "draft",
                    {
                        "inspection": {
                            "grounding": {
                                "passed": True,
                                "reason": "Stores the contact; makes no timing promise.",
                            }
                        }
                    },
                    35,
                ),
            ],
            "tool_calls": [
                {
                    "on_message_index": 1,
                    "tool_name": "create_escalation",
                    "arguments": {
                        "reason": "Catering request",
                        "summary": "Lunch for 25 delivered on Friday",
                        "intent": "offer",
                    },
                    "result": {"escalated": True},
                    "success": True,
                    "latency_ms": 24,
                },
                {
                    "on_message_index": 3,
                    "tool_name": "set_customer_contact",
                    "arguments": {"name": "Maya T", "email": "maya.t@example.com"},
                    "result": {"stored": True},
                    "success": True,
                    "latency_ms": 18,
                },
            ],
            "escalation": {
                "reason": "Catering request for 25 people, Friday delivery",
                "summary": "Lunch for 25 delivered on Friday, wants confirmation",
                "intent": "offer",
                "status": "open",
            },
        },
        {
            "customer_ref": "Dan K",
            "status": "closed",
            "created_at": now - timedelta(days=5),
            "messages": [
                (
                    "customer",
                    "My Uber Eats delivery came with the wrong salad and no pita. "
                    "Pretty disappointing.",
                    None,
                    None,
                    0,
                ),
                (
                    "assistant",
                    "I'm sorry to hear that - I've passed it to the Sabbaba team so "
                    "they can look into what happened with your delivery.",
                    "escalation",
                    {
                        "inspection": {
                            "grounding": {
                                "passed": True,
                                "reason": "Empathy and handoff; no facts invented.",
                            }
                        }
                    },
                    8,
                ),
                (
                    "human_agent",
                    "Hi Dan, Aniket from Sabbaba here. Sorry about the mix-up - "
                    "we've added a credit to your next order. Thanks for letting us "
                    "know.",
                    None,
                    None,
                    30,
                ),
            ],
            "tool_calls": [],
            "escalation": {
                "reason": "Wrong items in a delivery order",
                "summary": "Wrong salad and missing pita on an Uber Eats order",
                "intent": "support",
                "status": "resolved",
            },
        },
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


async def _seed_conversations(tenant_id: UUID) -> None:
    async with db.tenant_context(tenant_id, "tenant_admin") as conn:
        await _helpers.seed_conversations(conn, tenant_id, sabbaba_conversations(datetime.now(UTC)))


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

        await _seed_conversations(tenant_id)
        print("seeded conversations, tool calls, costs and escalations")

        return tenant_id


def main() -> None:
    tenant_id = asyncio.run(seed())
    print(f"done: tenant_id={tenant_id}")


if __name__ == "__main__":
    main()
