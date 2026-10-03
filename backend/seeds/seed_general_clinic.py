"""Tenant 4 seed: Wellspring Medical Centre, a general medical practice.

The fourth demo business for the RF-17 four-business walkthrough: a general
medical practice, kept deliberately distinct from the other seeded verticals,
so the domain-agnostic invariant is proved by identical code across four
different businesses with configuration-only differences. Detail here is
illustrative demo data, not a real fee schedule.

Idempotent: re-running wipes and recreates tenant 'wellspring' from scratch.
Standalone staging use (non-destructive to the other tenants)::

    docker compose run --rm \
      -e DATABASE_URL='<pooler url, port 5432>' \
      backend python -m seeds.seed_general_clinic

``make seed`` (the full demo world) also calls :func:`seed`, so local dev gets
bytefix + lumident + sababa + wellspring together.

Usage: ``uv run python -m seeds.seed_general_clinic``
"""

from __future__ import annotations

import asyncio
from uuid import UUID, uuid4

from app.llm.embedder import Embedder, get_embedder
from app.shared import db
from app.shared.config import get_settings
from seeds import _helpers

SLUG = "wellspring"
TENANT_NAME = "Wellspring Medical Centre"

# Pre-onboarded profile - the demo world lands in the console, not the
# interview, so the seed writes the same end-state a real confirm produces
# (via _helpers.insert_tenant_core's profile arg).
WELLSPRING_PROFILE = {
    "owner_display_name": "Dr. Priya Raman",
    "business_name": TENANT_NAME,
    "business_type": "general medical practice",
    "headcount": "9",
    "hours": "Monday to Friday 8am to 6pm, Saturday 9am to 1pm",
    "services": [
        "General consultations",
        "Health assessments",
        "Vaccinations",
        "Chronic disease management",
        "Minor procedures",
        "Travel medicine",
    ],
    "contact": "owner@wellspring.dev",
    "abn": "none",
    "gst": "no",
    # W-9: the voice beat is part of the interview now, so a pre-onboarded
    # tenant carries the same end-state a real confirm leaves behind.
    "customer_voice_preset": "warm_casual",
    "customer_voice_custom_style": "",
}

# --- offerings: consultations, preventive care and in-room procedures -------

CATALOG_ITEMS: list[tuple[str, str, int | None, list[str]]] = [
    (
        "Standard Consultation",
        "A standard GP consultation of up to 15 minutes",
        8500,
        ["Consultations"],
    ),
    (
        "Long Consultation",
        "An extended GP consultation of up to 30 minutes",
        14000,
        ["Consultations"],
    ),
    (
        "Health Assessment",
        "A comprehensive preventive health assessment",
        21000,
        ["Preventive care"],
    ),
    (
        "Childhood Vaccination",
        "Routine childhood immunisation, no out-of-pocket cost",
        0,
        ["Preventive care"],
    ),
    (
        "Travel Medicine Consult",
        "Pre-travel advice, vaccines and medication planning",
        9500,
        ["Preventive care"],
    ),
    (
        "Skin Check",
        "A full-body skin cancer check",
        12000,
        ["Preventive care"],
    ),
    (
        "Minor Procedure",
        "A small in-room procedure such as a biopsy or a suture",
        18000,
        ["Procedures"],
    ),
    (
        "Wound Dressing",
        "A professional wound cleaning and dressing change",
        4500,
        ["Procedures"],
    ),
    (
        "Ear Syringe",
        "Ear wax removal by microsuction or syringing",
        6000,
        ["Procedures"],
    ),
]

# --- pricing_rules: one per flat-priced offering ----------------------------

PRICING_RULES: list[tuple[str, str, int, str]] = [
    ("standard-consultation", "Standard GP consultation", 8500, "each"),
    ("long-consultation", "Long GP consultation", 14000, "each"),
    ("health-assessment", "Comprehensive health assessment", 21000, "each"),
    ("childhood-vaccination", "Childhood immunisation", 0, "flat"),
    ("travel-medicine-consult", "Travel medicine consultation", 9500, "each"),
    ("skin-check", "Full-body skin check", 12000, "each"),
    ("minor-procedure", "Minor in-room procedure", 18000, "each"),
    ("wound-dressing", "Wound dressing change", 4500, "each"),
    ("ear-syringe", "Ear wax removal", 6000, "each"),
]

ORDER_STATUSES = ["scheduled", "confirmed", "completed", "cancelled", "no_show"]

SERVICES_AND_FEES_MD = """# Services and Fees

## Consultations

A standard consultation is $85 and runs up to 15 minutes - enough for one
or two concerns, a repeat prescription, or a referral. If your visit needs
more time, we book a long consultation at $140, which runs up to 30 minutes
and suits multiple issues or a new complex problem. Fees are payable on the
day and we can process a Medicare rebate on the spot.

## Preventive Care

A comprehensive health assessment is $210 and includes a full review of your
history, risk factors and screening needs, with a written plan at the end.
A full-body skin check is $120. Routine childhood immunisations are offered
at no out-of-pocket cost to families. A travel medicine consultation is $95
and covers destination-specific vaccines, malaria prevention and a medical
kit list; any vaccines given are charged at cost on the day.

## Procedures

A minor procedure such as a biopsy, a small excision or a suture is $180,
including a follow-up dressing review. A wound dressing change is $45, and
ear wax removal by microsuction or syringing is $60. If a procedure turns
out to be more involved than expected, we will pause and discuss a revised
fee with you before continuing.
"""

CLINIC_POLICIES_MD = """# Clinic Policies

## Appointments and Cancellations

Appointments can be booked online or by phone. If you cannot make your
appointment, please let us know at least two hours ahead so we can offer the
slot to someone else. Missed appointments without notice may incur a small
non-attendance fee, which we waive for genuine emergencies. Urgent same-day
appointments are kept open every morning for existing patients.

## Fees and Medicare

Our fees are listed in full on our services and fees page, and the Medicare
rebate you receive depends on the item billed. We offer bulk billing for
children under 16 and for concession card holders on standard weekday
consultations. Payment is due on the day by card or cash. If you are
experiencing financial hardship, please speak with our reception team in
confidence - we would rather find a way to see you than have cost be a
barrier.

## Results and Follow-up

We will contact you when your results are ready. Our reception team cannot
give results over the phone; a nurse or doctor will call you, or book you a
short follow-up appointment if the result needs discussion. Please allow up
to three business days for routine results and longer for specialised tests.
If you have not heard from us within a week, call and we will chase it.

## Privacy

Your medical record is confidential and stored securely. We only share
information with other health professionals involved in your care, or where
required by law. You can request a copy of your record or ask us to correct
it at any time. Our full privacy policy is available at reception.
"""

FAQ_MD = """# Frequently Asked Questions

## Do I need an appointment?

Yes for routine care - booking ahead keeps your wait short. We also keep
same-day appointments open every morning for urgent problems such as a
sudden illness, an injury or a wound that needs attention. Call as early as
you can and we will fit you in.

## Are childhood vaccinations free?

Routine childhood immunisations on the national schedule are provided at no
out-of-pocket cost to families. Vaccines needed for travel or for
occupational reasons are not part of that schedule and are charged
separately - ask at your consultation and we will give you the exact cost.

## Can I get a repeat prescription without an appointment?

For most regular medications, yes, if you have been seen here in the last
twelve months and your review is up to date. Some medicines need a
consultation first. Send us the request through the clinic and we will tell
you which applies.

## Do you see children and families?

Yes. We see patients of all ages, from newborns through to older adults. We
offer bulk billing for children under 16 on standard consultations, and we
keep our waiting room calm and family-friendly.

## What should I bring to my first visit?

Bring a photo ID, your Medicare card, a list of your current medications and
any recent test results or specialist letters you have. If you are
transferring from another practice, ask them to send your records across or
bring a summary with you.
"""


async def _seed_core(tenant_id: UUID) -> None:
    await _helpers.insert_tenant_core(
        tenant_id=tenant_id,
        slug=SLUG,
        name=TENANT_NAME,
        # Fourth vertical, same code: the clinic takes the lean column default
        # (search + escalate) like lumident and sababa, so enabled_tools stays
        # unwritten here - only bytefix opts into the commerce tools (D-2).
        brand={"display_name": TENANT_NAME, "accent": "#3A6EA5"},
        config={
            "customer": {
                "greeting": (
                    "Hello and welcome to Wellspring Medical Centre. I can "
                    "answer questions about our services and fees, help you "
                    "understand what an appointment involves, or put you in "
                    "touch with the clinic - how can I help?"
                ),
                "starter_questions": [
                    "How much is a standard consultation?",
                    "Are childhood vaccinations free?",
                    "How do I get my test results?",
                ],
            }
        },
        business_name=TENANT_NAME,
        profile=WELLSPRING_PROFILE,
    )

    async with db.tenant_context(tenant_id, "tenant_admin") as conn:
        await _helpers.insert_offerings(conn, tenant_id, CATALOG_ITEMS)
        await _helpers.insert_pricing_rules(conn, tenant_id, PRICING_RULES)
        await _helpers.insert_orders(
            conn,
            tenant_id,
            [
                (
                    f"APP-{5001 + i}",
                    "booking",
                    f"patient-{i + 1}",
                    ORDER_STATUSES[i % len(ORDER_STATUSES)],
                    {"provider": "dr-raman", "duration_min": 15},
                )
                for i in range(6)
            ],
        )


async def _seed_knowledge(tenant_id: UUID, embedder: Embedder) -> None:
    async with db.tenant_context(tenant_id, "tenant_admin") as conn:
        await _helpers.ingest_documents(
            conn,
            tenant_id,
            [
                ("services-and-fees.md", "price_list", SERVICES_AND_FEES_MD),
                ("clinic-policies.md", "policy", CLINIC_POLICIES_MD),
                ("faq.md", "faq", FAQ_MD),
            ],
            embedder,
        )


async def seed(embedder: Embedder | None = None) -> UUID:
    """Seed (or re-seed) the Wellspring tenant. Returns the tenant id."""
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
