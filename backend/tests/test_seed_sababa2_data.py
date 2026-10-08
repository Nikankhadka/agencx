"""Sabbaba 2 seed data invariants - pure data, no database.

Two contracts: every fact is synced from the source Sabbaba seed (menu,
prices, dietary labels, media, orders), and the assembled prompt the seed
produces fits the raised fast-path budgets with comfortable margin. The
second is the reason this tenant exists - a silent slip back over the line
turns the demo slow again, so it is pinned here and again post-seed in
test_seed_sababa2.py.
"""

from __future__ import annotations

import uuid

import pytest

from app.ingestion.chunker import chunk_prose
from app.services.context_package import (
    _CONTRACT_OVERHEAD_CHARS,
    ActiveOffering,
    ActiveOfferingCategory,
    _profile_text,
    format_offerings,
)
from app.services.retrieval import (
    ANSWER_RESERVE_TOKENS,
    estimate_tokens,
    fits_fast_path,
)
from app.shared.config import get_settings
from seeds.sababa2.knowledge import KNOWLEDGE_DOCS, RATINGS_MD
from seeds.sababa2.menu import SUMMARIES
from seeds.sabbaba.menu import MENU as SOURCE_MENU
from seeds.seed_sababa2 import (
    CATALOG_ITEMS,
    MEDIA,
    ORDER_ITEMS,
    PRICING_RULES,
    SABABA2_PROFILE,
)

NAMES = [name for name, _, _, _ in CATALOG_ITEMS]
PRICES = {name: price for name, _, price, _ in CATALOG_ITEMS}
SOURCE_PRICES = {name: price for items in SOURCE_MENU.values() for name, _, price in items}

# .env.example's raised values: the Groq-safe 7500/1500 defaults cannot carry
# a 96-item catalog.
FAST_PATH_BUDGET = 11500
CATALOG_BUDGET = 5500
# The margin the seed is sized for: at least this many tokens under budget.
MIN_MARGIN = 1000


def test_catalog_is_the_full_source_menu_in_document_order() -> None:
    source_items = [
        (name, price, category)
        for category, items in SOURCE_MENU.items()
        for name, _, price in items
    ]
    catalog_items = [
        (name, price, category)
        for name, _, price, categories in CATALOG_ITEMS
        for category in categories
    ]
    assert catalog_items == source_items
    assert len(CATALOG_ITEMS) == 96


def test_catalog_descriptions_are_the_authored_summaries() -> None:
    assert {name: description for name, description, _, _ in CATALOG_ITEMS} == {
        name: SUMMARIES[name] for name in NAMES
    }


def test_summaries_cover_every_item_and_stay_terse() -> None:
    assert set(SUMMARIES) == set(NAMES) == set(SOURCE_PRICES)
    assert all(len(summary) <= 35 for summary in SUMMARIES.values())
    assert all(
        summary.strip() == summary and summary.endswith(".") for summary in SUMMARIES.values()
    )


def test_names_and_rule_codes_are_unique() -> None:
    assert len({name.casefold() for name in NAMES}) == len(NAMES)
    codes = [code for code, _, _, _ in PRICING_RULES]
    assert len(set(codes)) == len(codes)


def test_every_priced_item_has_exactly_one_each_rule_and_no_other_rules() -> None:
    priced = {name: price for name, price in PRICES.items() if price is not None}
    assert {label: cents for _, label, cents, _ in PRICING_RULES} == priced
    assert len(PRICING_RULES) == len(priced)
    assert {unit for _, _, _, unit in PRICING_RULES} == {"each"}


def test_prices_match_the_source_document() -> None:
    assert PRICES == SOURCE_PRICES
    assert PRICES["Plate"] == 3000
    assert PRICES["Super Plate"] == 3700
    assert PRICES["Sabbaba Pita Pocket"] == 1490
    assert PRICES["Falafel, 6 pieces"] == 890


def test_unconfirmed_prices_are_unpriced_with_no_rule() -> None:
    unpriced = {name for name, price in PRICES.items() if price is None}
    assert unpriced == {"Chunky Egg and Tender Greens Bagel", "Caramel Cookie"}
    assert unpriced.isdisjoint(label for _, label, _, _ in PRICING_RULES)


def test_orders_reference_real_offerings() -> None:
    assert {item for items in ORDER_ITEMS for item in items} <= set(NAMES)


def test_profile_is_the_source_identity_with_the_clones_name() -> None:
    assert SABABA2_PROFILE["business_name"] == "Sabbaba 2"
    assert SABABA2_PROFILE["contact"] == "owner@sababa2.dev"
    assert SABABA2_PROFILE["hours"] == "Monday to Sunday 6:00 am to 8:00 pm"
    assert SABABA2_PROFILE["customer_voice_preset"] == "warm_casual"


def test_knowledge_docs_are_typed_and_cover_every_section() -> None:
    by_name = {filename: (doc_type, text) for filename, doc_type, text in KNOWLEDGE_DOCS}
    assert len(by_name) == len(KNOWLEDGE_DOCS) == 13
    assert by_name["about-hours-contact.md"][0] == "faq"
    assert by_name["allergens-and-dietary.md"][0] == "policy"
    assert by_name["ratings.md"][0] == "faq"
    price_lists = {f: text for f, (t, text) in by_name.items() if t == "price_list"}
    assert len(price_lists) == len(SOURCE_MENU) == 10
    for category, items in SOURCE_MENU.items():
        text = price_lists[f"menu-{category.lower().replace(' ', '-')}.md"]
        for name, _, cents in items:
            expected = (
                "price not confirmed" if cents is None else f"${cents // 100}.{cents % 100:02d}"
            )
            assert f"- {name}: {expected}" in text


def test_condensed_prose_keeps_the_facts_and_caveats() -> None:
    by_name = {filename: " ".join(text.split()) for filename, _, text in KNOWLEDGE_DOCS}
    about = by_name["about-hours-contact.md"]
    for stated in ("77 Spring St", "91 Spring St", "71 Spring St", "0493 872 535"):
        assert stated in about
    assert "cannot take or place orders" in about
    for channel in ("Uber Eats", "DoorDash", "Hey You"):
        assert channel in about
    assert "Hey You prices listed on 8 October 2026" in about

    allergens = by_name["allergens-and-dietary.md"]
    assert "not been confirmed by the kitchen" in allergens
    assert "Tabouli contains bulgur, which is wheat" in allergens
    assert "share a fryer with other foods is not published" in allergens
    assert "Vegan on the menu:" in allergens
    assert "Gluten free on the menu:" in allergens
    assert "{dietary_lists}" not in allergens


def test_ratings_are_condensed_to_the_snapshot() -> None:
    assert "8 October 2026" in RATINGS_MD
    assert "3.8 out of 5 from 190 ratings" in RATINGS_MD
    assert "Uber Eats breakfast listing: 4.7 out of 5" in RATINGS_MD
    # Only the five most-liked items survive; the rest of the per-item paragraph
    # is the condensed-away part.
    ratings = " ".join(RATINGS_MD.split())
    assert "Plate 90 percent from 996 ratings" in ratings
    assert ratings.count(" percent from ") == 5
    assert "Garlic Aioli" not in RATINGS_MD


def test_media_is_the_full_source_manifest() -> None:
    # Every manifest photo belongs to a kept offering (the full menu is kept).
    assert set(MEDIA["offerings"]) <= set(NAMES)
    assert len(MEDIA["offerings"]) == 44
    assert MEDIA["cover"]["public_id"] == "demo/sabbaba/cover"
    for media in [MEDIA["cover"], *MEDIA["offerings"].values()]:
        assert media["url"].startswith("https://res.cloudinary.com/")
        assert media["public_id"].startswith("demo/sabbaba/")


def test_no_em_dash_anywhere_in_the_data() -> None:
    texts = (
        [d for _, d, _, _ in CATALOG_ITEMS]
        + [t for _, _, t in KNOWLEDGE_DOCS]
        + list(SUMMARIES.values())
        + NAMES
    )
    em_dash = chr(0x2014)
    assert not any(em_dash in text for text in texts)


def test_prompt_fits_the_fast_path_with_margin(monkeypatch: pytest.MonkeyPatch) -> None:
    """The assembled prompt (contract + profile + catalog + chunked corpus)
    fits the raised budgets with MIN_MARGIN tokens to spare."""
    monkeypatch.setenv("CORPUS_FAST_PATH_MAX_TOKENS", str(FAST_PATH_BUDGET))
    monkeypatch.setenv("CATALOG_INLINE_MAX_TOKENS", str(CATALOG_BUDGET))
    get_settings.cache_clear()
    try:
        corpus_chars = sum(
            len(chunk.content)
            for filename, _, text in KNOWLEDGE_DOCS
            for chunk in chunk_prose(text, source=filename)
        )
        assert corpus_chars > 0

        offerings = [
            ActiveOffering(
                id=str(uuid.uuid5(uuid.NAMESPACE_DNS, name)),
                name=name,
                description=description,
                category=categories[0],
                price_cents=price,
                categories=[
                    ActiveOfferingCategory(
                        id=str(position), name=category, position=position, is_primary=True
                    )
                    for position, category in enumerate(categories)
                ],
            )
            for position, (name, description, price, categories) in enumerate(CATALOG_ITEMS)
        ]
        catalog_chars = len(format_offerings(offerings))
        profile_chars = len(_profile_text(SABABA2_PROFILE))
        overhead = _CONTRACT_OVERHEAD_CHARS + profile_chars + catalog_chars

        catalog_tokens = estimate_tokens(catalog_chars)
        assert catalog_tokens <= CATALOG_BUDGET, catalog_tokens
        assert fits_fast_path(corpus_chars=corpus_chars, overhead_chars=overhead)

        needed = estimate_tokens(corpus_chars + overhead) + ANSWER_RESERVE_TOKENS
        assert FAST_PATH_BUDGET - needed >= MIN_MARGIN, needed
    finally:
        get_settings.cache_clear()
