"""Demo world seed: all five tenants, auth users, membership, and realistic
conversations/escalations/costs - the data the demo surfaces show.

Run with ``make dev && make seed`` (or ``./scripts/dev.sh --seed``). It is
wipe-and-recreate idempotent: re-running resets the whole demo world to a
known state.

Structure (mirrors seeds/seed_tenant1_phoneshop.py's pattern):

1. Bytefix (Tenant 1) via ``seed_tenant1_phoneshop.seed`` - its existing
   wipe+recreate (config, 15 items, 12 rules, 20 orders, 3 docs). All five
   tenants are seeded already-onboarded (profile + business_name + persona
   + completed onboarding record), so the demo world lands in the console,
   not the interview.
2. Five GoTrue auth users (find-or-create by email), via an injected
   ``create_auth_user`` callable so tests run GoTrue-free with deterministic
   UUIDs. The default calls the GoTrue Admin API (POST /auth/v1/admin/users
   with a service_role bearer, email_confirm=true).
3. Lumident Dental (Tenant 2, slug ``lumident``, pure demo data, explicitly
   NOT the T-037 generalization proof which has its own ticket). Distinct
   brand accent + dental-language customer config, ~8 catalog items, ~6
   pricing rules, ~6 appointment orders, 2 knowledge docs.
3b. Sabbaba (Tenant 3, slug ``sababa``) and Wellspring Medical Centre (Tenant
   4, slug ``wellspring``), each via its own standalone seed module so the
   same module seeds staging without touching the other tenants. Sabbaba
   brings its own conversations with it.
3d. Sabbaba 2 (Tenant 5, slug ``sababa2``) via ``seed_sababa2``: Sabbaba's
   business and full menu with summarized catalog copy, sized so the whole
   prompt takes the fast path. The seed fails loudly if it would not.
4. Membership rows: ``users`` (role='owner') for each tenant's owner;
   ``platform_admins`` for the founder. Tenant wipe cascades users;
   platform_admins is delete-then-insert by user_id for idempotency.
5. Conversations for bytefix, lumident and wellspring (Sabbaba and Sabbaba 2
   seed their own),
   with explicit ``created_at`` (``now()`` is constant within one transaction
   and ``tenant_context`` is one transaction, so every insert sets created_at
   explicitly - spread over the past 7 days, messages 5-30s apart so
   list/transcript ordering and the cost attribution lateral join all behave).
   5 for bytefix (2 closed, 1 open, 2 escalated), 2 for lumident and 2 for
   wellspring. Tool calls on 3 assistant messages, inspection verdicts in
   messages.metadata (the shape TraceTree.tsx renders), cost_logs placed just
   after each assistant message's created_at, and 3 escalations (open,
   claimed, resolved with a trailing human_agent message) respecting the
   0011 partial unique index.

Domain-agnosticism is data-side only: bytefix, lumident, sababa, sababa2 and
wellspring run identical code and differ only in tenant_config + uploaded
knowledge - no vertical branches anywhere (the hard rule). Sabbaba 2 is the
deliberate same-vertical clone: its data proves the fast-path budget, not a
new vertical.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import httpx

from app.llm.embedder import Embedder, get_embedder
from app.shared import db
from app.shared.config import get_settings
from seeds import (
    _helpers,
    seed_general_clinic,
    seed_sababa,
    seed_sababa2,
    seed_tenant1_phoneshop,
)
from seeds.supabase_keys import mint_key

# Demo identities (password ``wren-demo`` for all; 6+ chars satisfies GoTrue's
# default minimum). Kept here as the single source of truth for the demo
# banner, docs/archive/DEMO.md, and the tests' fake create_auth_user.
BYTEFIX_OWNER_EMAIL = "owner@bytefix.dev"
LUMIDENT_OWNER_EMAIL = "owner@lumident.dev"
SABABA_OWNER_EMAIL = "owner@sababa.dev"
SABABA2_OWNER_EMAIL = "owner@sababa2.dev"
WELLSPRING_OWNER_EMAIL = "owner@wellspring.dev"
FOUNDER_EMAIL = "founder@wren.dev"
DEMO_PASSWORD = "wren-demo"

# Lumident (Tenant 2) - a dental practice. Pure demo data.
LUMIDENT_SLUG = "lumident"
LUMIDENT_NAME = "Lumident Dental"

# Pre-onboarded profile (same end-state as a real confirm, written by
# _helpers.insert_tenant_core's profile arg) - the demo world lands in the
# console, not the interview.
LUMIDENT_PROFILE = {
    "owner_display_name": "Dr. Sarah Mitchell",
    "business_name": LUMIDENT_NAME,
    "business_type": "family dental practice",
    "headcount": "6",
    "hours": "Monday to Friday 8am to 5pm, Saturday 9am to 12pm",
    "services": ["General dentistry", "Cleanings", "Fillings", "Crowns"],
    "contact": "owner@lumident.dev",
    "abn": "none",
    "gst": "no",
    # W-9: the voice beat is part of the interview now, so a pre-onboarded
    # tenant carries the same end-state a real confirm leaves behind.
    "customer_voice_preset": "warm_casual",
    "customer_voice_custom_style": "",
}

LUMIDENT_CATALOG: list[tuple[str, str, int | None, list[str]]] = [
    (
        "New Patient Exam",
        "Comprehensive exam, oral cancer screening, treatment plan",
        9500,
        ["Exams & Cleanings"],
    ),
    ("Standard Cleaning", "Routine professional cleaning and polish", 12000, ["Exams & Cleanings"]),
    (
        "Deep Cleaning (Per Quadrant)",
        "Scaling and root planing, one quadrant",
        35000,
        ["Exams & Cleanings"],
    ),
    (
        "Tooth-Colored Filling",
        "Composite resin filling, one surface",
        25000,
        ["Restorative"],
    ),
    ("Dental Crown", "Porcelain-fused-to-metal crown, one tooth", 110000, ["Restorative"]),
    ("Root Canal", "Endodontic treatment, one tooth", 95000, ["Restorative"]),
    (
        "In-Office Whitening",
        "Single-session professional whitening",
        45000,
        ["Cosmetic & Emergency"],
    ),
    (
        "Emergency Visit",
        "Same-day pain or trauma assessment",
        15000,
        ["Cosmetic & Emergency"],
    ),
]

LUMIDENT_PRICING_RULES: list[tuple[str, str, int, str]] = [
    ("new-patient-exam", "New patient comprehensive exam", 9500, "each"),
    ("standard-cleaning", "Routine cleaning and polish", 12000, "each"),
    ("deep-cleaning-quadrant", "Deep cleaning - one quadrant", 35000, "each"),
    ("filling-composite", "Tooth-colored composite filling - one surface", 25000, "each"),
    ("filling-additional-surface", "Each additional surface on the same tooth", 9000, "each"),
    ("crown-pfm", "Porcelain-fused-to-metal crown", 110000, "each"),
    ("root-canal", "Root canal therapy - one tooth", 95000, "each"),
    ("whitening-inoffice", "In-office whitening session", 45000, "flat"),
]

APPOINTMENT_STATUSES = ["scheduled", "confirmed", "completed", "cancelled", "no_show"]

LUMIDENT_SERVICES_MD = """# Dental Services

## Cleanings and Prevention

A standard professional cleaning is recommended every six months and includes
a full polish and a review of your home-care routine. For patients with
periodontal concerns, we offer deep cleanings (scaling and root planing) done
one quadrant at a time, usually across two visits. New patients start with a
comprehensive exam that includes an oral cancer screening and a personalized
treatment plan, so you know exactly what you need before anything is scheduled.

## Restorative Care

We place tooth-colored composite fillings for cavities, matched to your natural
shade. A single-surface filling is one price, and each additional surface on the
same tooth is a smaller add-on. For teeth that need more structural support, we
place porcelain-fused-to-metal crowns, which take two visits: a prep visit with
a temporary, then a final cementation once the lab finishes the crown.

## Cosmetic and Emergency

Our in-office whitening is a single one-hour session that lifts several shades
in one visit. For dental emergencies - severe pain, a knocked-out tooth, or a
broken crown - we keep same-day slots open every day; call ahead and we will fit
you in. Emergency visits cover the assessment and pain relief; further treatment
is quoted separately.
"""

LUMIDENT_FAQ_MD = """# Frequently Asked Questions

## Do you take walk-in emergencies?

Yes. We reserve same-day emergency slots every day for severe pain, trauma, or
a knocked-out tooth. Call ahead so we can prepare, but we will see you even if
you cannot reach us first. Save a knocked-out tooth in milk or saliva and bring
it with you - it can often be re-implanted within an hour.

## How often should I get a cleaning?

Every six months for most patients. Patients with gum disease or a history of
heavy buildup may be advised to come every three to four months instead. Your
hygienist will tell you what interval fits your mouth, not a generic schedule.

## Does whitening damage enamel?

Professional in-office whitening does not damage enamel when done correctly. You
may experience temporary sensitivity for a day or two, which resolves on its
own. We do not recommend over-the-counter kits for patients with existing
sensitivity without a quick consult first.

## What if I am anxious about the dentist?

We are used to nervous patients and will never rush you. Tell us at booking and
we will schedule extra time, explain each step before we do it, and offer breaks
whenever you need them. Sedation options are available for longer procedures if
you and the dentist agree they are appropriate.
"""

CreateAuthUser = Callable[[str, str], Awaitable[UUID]]


# --- GoTrue Admin API: the default create_auth_user (tests inject a fake) -------


def _gotrue_service_token() -> str:
    """The bearer GoTrue's Admin API accepts.

    Prefer the real ``SUPABASE_SERVICE_ROLE_KEY`` when set: hosted projects
    that sign sessions with asymmetric keys (ES256/RS256) reject a locally
    minted HS256 service token with 401, and the real key is the only way in
    (same reason the deployed backend presents it - deploy.md step 1). Local
    dev has no service role key and mints from the symmetric JWT secret, which
    is what local GoTrue expects.
    """
    settings = get_settings()
    if settings.supabase_service_role_key:
        return settings.supabase_service_role_key
    if settings.supabase_jwt_secret:
        return mint_key("service_role", settings.supabase_jwt_secret)
    return ""


def _make_gotrue_create_auth_user() -> CreateAuthUser:
    """Build the default create_auth_user from settings (GoTrue Admin API).

    Find-or-create by email: list existing admin users first (the demo has
    very few), return the id on a match, otherwise POST a new confirmed user.
    The Admin API is used instead of direct auth-schema SQL because the auth
    schema is GoTrue-owned and version-drifting - hand-inserting rows requires
    bcrypt-via-pgcrypto, instance_id, aud, role, identities rows, etc. and is
    the classic source of "seeded user can't log in" breakage.
    """
    settings = get_settings()
    base = settings.supabase_url.rstrip("/")
    service_token = _gotrue_service_token()
    if not base or not service_token:
        raise RuntimeError(
            "SUPABASE_URL plus either SUPABASE_SERVICE_ROLE_KEY or "
            "SUPABASE_JWT_SECRET must be set to seed demo auth users "
            "(run scripts/demo.sh, or inject create_auth_user in tests)."
        )
    headers = {
        "Authorization": f"Bearer {service_token}",
        "apikey": service_token,
        "Content-Type": "application/json",
    }

    async def create_auth_user(email: str, password: str) -> UUID:
        async with httpx.AsyncClient(timeout=30) as client:
            # Find existing by email (admin list). Handle both the
            # {"users": [...]} object shape and the bare-array shape GoTrue
            # has used across versions.
            found = await _gotrue_find_user_by_email(client, base, headers, email)
            if found is not None:
                return found
            resp = await client.post(
                f"{base}/auth/v1/admin/users",
                json={"email": email, "password": password, "email_confirm": True},
                headers=headers,
            )
            if resp.status_code in (200, 201):
                return UUID(str(resp.json()["id"]))
            # A concurrent create (or a stale list cache) can race; re-scan
            # before giving up so a rerun during a partial failure still wins.
            found = await _gotrue_find_user_by_email(client, base, headers, email)
            if found is not None:
                return found
            resp.raise_for_status()
            raise RuntimeError(  # pragma: no cover - raise_for_status covers it
                f"unexpected GoTrue admin create response: {resp.status_code}"
            )

    return create_auth_user


async def _gotrue_find_user_by_email(
    client: httpx.AsyncClient,
    base: str,
    headers: dict[str, str],
    email: str,
) -> UUID | None:
    page = 1
    while True:
        resp = await client.get(
            f"{base}/auth/v1/admin/users",
            params={"page": page, "per_page": 1000},
            headers=headers,
        )
        resp.raise_for_status()
        data = resp.json()
        users = data.get("users", []) if isinstance(data, dict) else data
        for user in users:
            if user.get("email") == email and user.get("id"):
                return UUID(str(user["id"]))
        # Stop when no more pages.
        if isinstance(data, dict):
            if not data.get("has_next") or not users:
                break
        elif not users:
            break
        page += 1
    return None


# --- Lumident (Tenant 2) --------------------------------------------------------


async def _seed_lumident_core() -> UUID:
    tenant_id = uuid4()
    await _helpers.insert_tenant_core(
        tenant_id=tenant_id,
        slug=LUMIDENT_SLUG,
        name=LUMIDENT_NAME,
        brand={"display_name": LUMIDENT_NAME, "accent": "#2C7A7B"},
        config={
            "customer": {
                "greeting": (
                    "Hello, and welcome to Lumident Dental. I can help you "
                    "understand a treatment, estimate a procedure's cost, or "
                    "check an upcoming appointment - how can I help?"
                ),
                "starter_questions": [
                    "How much is a standard cleaning?",
                    "What does a tooth-colored filling cost?",
                    "Do you take walk-in emergencies?",
                ],
            }
        },
        business_name=LUMIDENT_NAME,
        profile=LUMIDENT_PROFILE,
    )

    async with db.tenant_context(tenant_id, "tenant_admin") as conn:
        await _helpers.insert_offerings(conn, tenant_id, LUMIDENT_CATALOG)
        await _helpers.insert_pricing_rules(conn, tenant_id, LUMIDENT_PRICING_RULES)
        await _helpers.insert_orders(
            conn,
            tenant_id,
            [
                (
                    f"APPT-{3001 + i}",
                    "appointment",
                    f"patient-{i + 1}",
                    APPOINTMENT_STATUSES[i % len(APPOINTMENT_STATUSES)],
                    {"provider": "dr-lumident", "duration_min": 45},
                )
                for i in range(6)
            ],
        )
    return tenant_id


async def _seed_lumident_knowledge(tenant_id: UUID, embedder: Embedder) -> None:
    async with db.tenant_context(tenant_id, "tenant_admin") as conn:
        await _helpers.ingest_documents(
            conn,
            tenant_id,
            [
                ("services.md", "other", LUMIDENT_SERVICES_MD),
                ("faq.md", "faq", LUMIDENT_FAQ_MD),
            ],
            embedder,
        )


# --- Membership: users + platform_admins ---------------------------------------


async def _seed_membership(
    bytefix_id: UUID,
    bytefix_owner: UUID,
    lumident_id: UUID,
    lumident_owner: UUID,
    sababa_id: UUID,
    sababa_owner: UUID,
    sababa2_id: UUID,
    sababa2_owner: UUID,
    wellspring_id: UUID,
    wellspring_owner: UUID,
    founder: UUID,
) -> None:
    # A tenant wipe cascades its membership rows, but a previous partial seed
    # may have left the same auth user attached to a different stale tenant.
    # `users.id` is the auth.users id and is globally unique, so remove that
    # old membership through the tenant-scoped policy before recreating the
    # demo ownership rows. This keeps a rerun safe without broad service-role
    # writes to the users table.
    user_tenants: dict[UUID, UUID] = {}
    async with db.tenant_context(None, "platform_admin") as conn:
        for user_id in (
            bytefix_owner,
            lumident_owner,
            sababa_owner,
            sababa2_owner,
            wellspring_owner,
        ):
            tenant_id = await conn.fetchval("select tenant_id from users where id = $1", user_id)
            if tenant_id is not None:
                user_tenants[user_id] = tenant_id
    for user_id, tenant_id in user_tenants.items():
        async with db.tenant_context(tenant_id, "tenant_admin") as conn:
            await conn.execute("delete from users where id = $1", user_id)

    async with db.tenant_context(bytefix_id, "tenant_admin") as conn:
        await conn.execute(
            "insert into users (id, tenant_id, role) values ($1, $2, 'owner')",
            bytefix_owner,
            bytefix_id,
        )
    async with db.tenant_context(lumident_id, "tenant_admin") as conn:
        await conn.execute(
            "insert into users (id, tenant_id, role) values ($1, $2, 'owner')",
            lumident_owner,
            lumident_id,
        )
    async with db.tenant_context(sababa_id, "tenant_admin") as conn:
        await conn.execute(
            "insert into users (id, tenant_id, role) values ($1, $2, 'owner')",
            sababa_owner,
            sababa_id,
        )
    async with db.tenant_context(sababa2_id, "tenant_admin") as conn:
        await conn.execute(
            "insert into users (id, tenant_id, role) values ($1, $2, 'owner')",
            sababa2_owner,
            sababa2_id,
        )
    async with db.tenant_context(wellspring_id, "tenant_admin") as conn:
        await conn.execute(
            "insert into users (id, tenant_id, role) values ($1, $2, 'owner')",
            wellspring_owner,
            wellspring_id,
        )
    # platform_admins is not tenant-scoped and survives a tenant wipe, so
    # delete-then-insert by user_id for idempotency (matches test_auth_api's
    # _insert_platform_admin RLS-with-check pattern under platform_admin role).
    async with db.tenant_context(None, "platform_admin") as conn:
        await conn.execute("delete from platform_admins where user_id = $1", founder)
        await conn.execute("insert into platform_admins (user_id) values ($1)", founder)


# --- Conversations, messages, tool calls, costs, escalations -------------------
#
# The insert machinery lives in _helpers.seed_conversations (shared with the
# standalone tenant seeds); each tenant's specs are built here - except
# Sabbaba's, which its own seed module owns and seeds.


# Each conversation is seeded with explicit created_at timestamps so ordering
# and the cost lateral join (which brackets by created_at) are deterministic.
# A spec is inserted inside one tenant_context transaction.
def _bytefix_conversations(now: datetime) -> list[dict[str, Any]]:
    return [
        {
            "customer_ref": "alex.rivera",
            "status": "closed",
            "created_at": now - timedelta(days=7),
            "messages": [
                ("customer", "How much to replace the screen on a Galaxy S21?", None, None, 0),
                (
                    "assistant",
                    "A standard aftermarket screen replacement for the Galaxy S21 is $129, "
                    "or $179 if you'd prefer an original OEM display. Both are same-day. "
                    "Would you like me to put together a quote?",
                    "draft",
                    {
                        "inspection": {
                            "grounding": {
                                "passed": True,
                                "reason": (
                                    "Price figures match the pricing engine quote line items."
                                ),
                            },
                            "policy": {
                                "passed": True,
                                "reason": "Friendly, offers next step.",
                            },
                        }
                    },
                    12,
                ),
            ],
            "tool_calls": [
                {
                    "on_message_index": 1,
                    "tool_name": "get_quote_inputs",
                    "arguments": {"rule_codes": ["screen-repair-flagship-aftermarket"]},
                    "result": {
                        "line_items": [
                            {"code": "screen-repair-flagship-aftermarket", "quantity": 1}
                        ]
                    },
                    "success": True,
                    "latency_ms": 38,
                }
            ],
            "escalation": None,
        },
        {
            "customer_ref": "sam.lee",
            "status": "closed",
            "created_at": now - timedelta(days=5),
            "messages": [
                ("customer", "Is there a warranty on your repairs?", None, None, 0),
                (
                    "assistant",
                    "Yes - every repair is covered by a 90-day warranty against defects in parts "
                    "and workmanship [1]. If the same issue recurs within that window, we'll fix "
                    "it at no charge [1].",
                    "draft",
                    {
                        "inspection": {
                            "grounding": {
                                "passed": True,
                                "reason": "Both claims trace to the warranty section of policy.md.",
                            },
                            "injection": {
                                "passed": True,
                                "reason": "No injected instructions detected.",
                            },
                        }
                    },
                    15,
                ),
                ("customer", "Can I speak to a manager about a previous visit?", None, None, 22),
                (
                    "human_agent",
                    "Of course - I'll review your visit and call you back this afternoon. "
                    "Thanks for reaching out.",
                    None,
                    None,
                    30,
                ),
            ],
            "tool_calls": [
                {
                    "on_message_index": 1,
                    "tool_name": "search_knowledge",
                    "arguments": {"query": "warranty on repairs"},
                    "result": {"chunks": ["policy.md#warranty"]},
                    "success": True,
                    "latency_ms": 52,
                }
            ],
            "escalation": {"reason": "Customer asked to speak to a manager.", "status": "resolved"},
        },
        {
            "customer_ref": "jordan.patel",
            "status": "open",
            "created_at": now - timedelta(days=3),
            "messages": [
                ("customer", "Where's my repair? The ticket is R-1001.", None, None, 0),
                (
                    "assistant",
                    "I found it - repair R-1001 is currently in progress and we expect it to be "
                    "ready for pickup later today. We'll text you the moment it's finished.",
                    "draft",
                    {
                        "inspection": {
                            "grounding": {
                                "passed": True,
                                "reason": "Status matches the orders row.",
                            }
                        }
                    },
                    10,
                ),
            ],
            "tool_calls": [
                {
                    "on_message_index": 1,
                    "tool_name": "lookup_order_or_ticket",
                    "arguments": {"ref_code": "R-1001"},
                    "result": {
                        "found": True,
                        "ref_code": "R-1001",
                        "status": "in_progress",
                        "kind": "repair",
                    },
                    "success": True,
                    "latency_ms": 21,
                }
            ],
            "escalation": None,
        },
        {
            "customer_ref": "casey.nguyen",
            "status": "escalated",
            "created_at": now - timedelta(days=2),
            "messages": [
                ("customer", "I'd really like to talk to a human about this.", None, None, 0),
                (
                    "assistant",
                    "No problem - I'm handing you to a human teammate who'll follow up shortly. "
                    "Thanks for your patience.",
                    "escalation",
                    {
                        "inspection": {
                            "grounding": {"passed": True, "reason": "No factual claims to verify."}
                        }
                    },
                    8,
                ),
            ],
            "tool_calls": [],
            "escalation": {"reason": "Customer asked for a human.", "status": "open"},
        },
        {
            "customer_ref": "morgan.chen",
            "status": "escalated",
            "created_at": now - timedelta(days=1),
            "messages": [
                (
                    "customer",
                    "This is the third time my screen has broken after your repair. I'm furious.",
                    None,
                    None,
                    0,
                ),
                (
                    "assistant",
                    "I'm really sorry to hear that - that's frustrating, and "
                    "I want to make it right. "
                    "I'm escalating this to a senior technician right now so "
                    "we can look into what's "
                    "happening and get it sorted.",
                    "escalation",
                    {
                        "inspection": {
                            "grounding": {
                                "passed": True,
                                "reason": "Empathy + escalation, no facts invented.",
                            }
                        }
                    },
                    14,
                ),
            ],
            "tool_calls": [],
            "escalation": {
                "reason": "Angry repeat customer; sentiment-driven escalation.",
                "status": "claimed",
            },
        },
    ]


def _lumident_conversations(now: datetime) -> list[dict[str, Any]]:
    return [
        {
            "customer_ref": "patient.a",
            "status": "closed",
            "created_at": now - timedelta(days=4),
            "messages": [
                (
                    "customer",
                    "How much is a standard cleaning if I'm a new patient?",
                    None,
                    None,
                    0,
                ),
                (
                    "assistant",
                    "A standard cleaning is $120. As a new patient you'd also start with a $95 "
                    "comprehensive exam, which includes an oral cancer screening and a treatment "
                    "plan. Would you like me to quote both together?",
                    "draft",
                    {
                        "inspection": {
                            "grounding": {
                                "passed": True,
                                "reason": "Prices match the catalog and pricing engine.",
                            }
                        }
                    },
                    11,
                ),
            ],
            "tool_calls": [
                {
                    "on_message_index": 1,
                    "tool_name": "get_quote_inputs",
                    "arguments": {"rule_codes": ["standard-cleaning", "new-patient-exam"]},
                    "result": {
                        "line_items": [
                            {"code": "standard-cleaning", "quantity": 1},
                            {"code": "new-patient-exam", "quantity": 1},
                        ]
                    },
                    "success": True,
                    "latency_ms": 33,
                }
            ],
            "escalation": None,
        },
        {
            "customer_ref": "patient.b",
            "status": "open",
            "created_at": now - timedelta(days=2, hours=6),
            "messages": [
                ("customer", "Do you take walk-in emergencies?", None, None, 0),
                (
                    "assistant",
                    "Yes - we reserve same-day emergency slots every day for severe pain, trauma, "
                    "or a knocked-out tooth. Call ahead if you can, but we'll "
                    "see you either way [1].",
                    "draft",
                    {
                        "inspection": {
                            "grounding": {
                                "passed": True,
                                "reason": "Matches the FAQ's emergency entry.",
                            }
                        }
                    },
                    13,
                ),
            ],
            "tool_calls": [],
            "escalation": None,
        },
    ]


def _wellspring_conversations(now: datetime) -> list[dict[str, Any]]:
    return [
        {
            "customer_ref": "patient.c",
            "status": "closed",
            "created_at": now - timedelta(days=3, hours=9),
            "messages": [
                (
                    "customer",
                    "How much is a standard consultation, and what about a health assessment?",
                    None,
                    None,
                    0,
                ),
                (
                    "assistant",
                    "A standard consultation is $85. A comprehensive health "
                    "assessment is $210 and includes a full review of your history "
                    "and screening needs with a written plan. Want me to put both "
                    "together for you?",
                    "draft",
                    {
                        "inspection": {
                            "grounding": {
                                "passed": True,
                                "reason": "Prices match the catalog and pricing engine.",
                            }
                        }
                    },
                    11,
                ),
            ],
            "tool_calls": [
                {
                    "on_message_index": 1,
                    "tool_name": "get_quote_inputs",
                    "arguments": {"rule_codes": ["standard-consultation", "health-assessment"]},
                    "result": {
                        "line_items": [
                            {"code": "standard-consultation", "quantity": 1},
                            {"code": "health-assessment", "quantity": 1},
                        ]
                    },
                    "success": True,
                    "latency_ms": 31,
                }
            ],
            "escalation": None,
        },
        {
            "customer_ref": "patient.d",
            "status": "open",
            "created_at": now - timedelta(days=1, hours=8),
            "messages": [
                ("customer", "Are childhood vaccinations free?", None, None, 0),
                (
                    "assistant",
                    "Yes - routine childhood immunisations on the national schedule "
                    "are provided at no out-of-pocket cost to families. Travel or "
                    "occupational vaccines are not part of that schedule and are "
                    "charged separately [1].",
                    "draft",
                    {
                        "inspection": {
                            "grounding": {
                                "passed": True,
                                "reason": "Matches the FAQ's vaccination entry.",
                            }
                        }
                    },
                    12,
                ),
            ],
            "tool_calls": [],
            "escalation": None,
        },
    ]


# --- The top-level seed ---------------------------------------------------------


async def seed(
    embedder: Embedder | None = None,
    create_auth_user: CreateAuthUser | None = None,
) -> dict[str, UUID]:
    """Seed (or re-seed) the whole demo world. Returns the tenant + user ids.

    ``create_auth_user`` defaults to the GoTrue Admin API client built from
    ``settings``; tests inject a fake returning deterministic UUIDs so the
    full seed runs GoTrue-free.
    """
    async with _helpers.seed_pool():
        resolved_embedder = embedder or get_embedder(get_settings())
        user_factory = create_auth_user or _make_gotrue_create_auth_user()

        # 1. Bytefix (wipes + recreates tenant 'bytefix' with a fresh id).
        bytefix_id = await seed_tenant1_phoneshop.seed(embedder=resolved_embedder)
        print(f"seeded bytefix (tenant_id={bytefix_id})")

        # 2. Auth users (find-or-create by email).
        bytefix_owner = await user_factory(BYTEFIX_OWNER_EMAIL, DEMO_PASSWORD)
        lumident_owner = await user_factory(LUMIDENT_OWNER_EMAIL, DEMO_PASSWORD)
        sababa_owner = await user_factory(SABABA_OWNER_EMAIL, DEMO_PASSWORD)
        sababa2_owner = await user_factory(SABABA2_OWNER_EMAIL, DEMO_PASSWORD)
        wellspring_owner = await user_factory(WELLSPRING_OWNER_EMAIL, DEMO_PASSWORD)
        founder = await user_factory(FOUNDER_EMAIL, DEMO_PASSWORD)
        print(
            f"auth users: owner@bytefix={bytefix_owner} "
            f"owner@lumident={lumident_owner} owner@sababa={sababa_owner} "
            f"owner@sababa2={sababa2_owner} "
            f"owner@wellspring={wellspring_owner} founder={founder}"
        )

        # 3. Lumident (Tenant 2) - wipe + recreate, config + catalog + knowledge.
        async with db.tenant_context(None, "platform_admin") as conn:
            await _helpers.wipe_tenant(conn, LUMIDENT_SLUG)
        lumident_id = await _seed_lumident_core()
        await _seed_lumident_knowledge(lumident_id, resolved_embedder)
        print(f"seeded lumident (tenant_id={lumident_id})")

        # 3b. Sabbaba (Tenant 3) - wipe + recreate via its standalone seed so
        # the same module seeds staging without touching the other tenants.
        sababa_id = await seed_sababa.seed(embedder=resolved_embedder)
        print(f"seeded sababa (tenant_id={sababa_id})")

        # 3c. Wellspring (Tenant 4) - same standalone-seed pattern as sababa.
        wellspring_id = await seed_general_clinic.seed(embedder=resolved_embedder)
        print(f"seeded wellspring (tenant_id={wellspring_id})")

        # 3d. Sabbaba 2 (Tenant 5) - the fast-path clone; its seed asserts the
        # assembled prompt takes the whole-corpus fast path or fails loudly.
        sababa2_id = await seed_sababa2.seed(embedder=resolved_embedder)
        print(f"seeded sababa2 (tenant_id={sababa2_id})")

        # 4. Membership rows.
        await _seed_membership(
            bytefix_id,
            bytefix_owner,
            lumident_id,
            lumident_owner,
            sababa_id,
            sababa_owner,
            sababa2_id,
            sababa2_owner,
            wellspring_id,
            wellspring_owner,
            founder,
        )
        print("seeded membership (5 owners + 1 platform admin)")

        # 5. Conversations for the inline tenants, tool calls, costs,
        # escalations. Sabbaba and Sabbaba 2 brought their own above.
        now = datetime.now(UTC)
        async with db.tenant_context(bytefix_id, "tenant_admin") as conn:
            await _helpers.seed_conversations(conn, bytefix_id, _bytefix_conversations(now))
        async with db.tenant_context(lumident_id, "tenant_admin") as conn:
            await _helpers.seed_conversations(conn, lumident_id, _lumident_conversations(now))
        async with db.tenant_context(wellspring_id, "tenant_admin") as conn:
            await _helpers.seed_conversations(conn, wellspring_id, _wellspring_conversations(now))
        print(
            "seeded conversations (5 bytefix + 2 lumident + 2 wellspring), "
            "tool calls, costs, escalations"
        )

        print(
            "\ndemo world ready. Logins (password wren-demo):\n"
            f"  tenant console: http://localhost:3000/login  {BYTEFIX_OWNER_EMAIL}\n"
            f"  tenant console: http://localhost:3000/login  {LUMIDENT_OWNER_EMAIL}\n"
            f"  tenant console: http://localhost:3000/login  {SABABA_OWNER_EMAIL}\n"
            f"  tenant console: http://localhost:3000/login  {SABABA2_OWNER_EMAIL}\n"
            f"  tenant console: http://localhost:3000/login  {WELLSPRING_OWNER_EMAIL}\n"
            f"  platform:       http://localhost:3000/admin  {FOUNDER_EMAIL}\n"
            f"  customer pages: http://localhost:3000/bytefix, /lumident, /sababa, "
            f"/sababa2, /wellspring"
        )
        return {
            "bytefix_id": bytefix_id,
            "lumident_id": lumident_id,
            "sababa_id": sababa_id,
            "sababa2_id": sababa2_id,
            "wellspring_id": wellspring_id,
            "bytefix_owner": bytefix_owner,
            "lumident_owner": lumident_owner,
            "sababa_owner": sababa_owner,
            "sababa2_owner": sababa2_owner,
            "wellspring_owner": wellspring_owner,
            "founder": founder,
        }


def main() -> None:
    asyncio.run(seed())


if __name__ == "__main__":
    main()
