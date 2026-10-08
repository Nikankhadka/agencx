"""Sabbaba seed data invariants - pure data, no database.

The menu and knowledge text are the source menu document's own, so these pin
the shape the seed and the hard rules depend on (integer cents, one ``each``
rule per priced offering, document-ordered categories) plus a handful of
figures read straight off the document.
"""

from __future__ import annotations

from seeds.sabbaba.knowledge import KNOWLEDGE_DOCS, RATINGS_MD
from seeds.sabbaba.menu import MENU
from seeds.seed_sababa import CATALOG_ITEMS, MEDIA, ORDER_ITEMS, PRICING_RULES, SABABA_PROFILE

NAMES = [name for name, _, _, _ in CATALOG_ITEMS]
PRICES = {name: price for name, _, price, _ in CATALOG_ITEMS}

CATEGORIES = [
    "Pita Pockets",
    "Plates",
    "Bowls",
    "Salads",
    "Sides",
    "Dips and Extras",
    "Breakfast",
    "Coffee and Hot Drinks",
    "Cold Drinks",
    "Sweets",
]


def test_categories_follow_the_document_and_each_item_has_one() -> None:
    assert list(MENU) == CATEGORIES
    assert all(len(items) > 0 for items in MENU.values())
    assert [categories for _, _, _, categories in CATALOG_ITEMS] == [
        [category] for category, items in MENU.items() for _ in items
    ]
    assert len(CATALOG_ITEMS) == sum(len(items) for items in MENU.values()) == 96


def test_names_and_rule_codes_are_unique() -> None:
    assert len({name.casefold() for name in NAMES}) == len(NAMES)
    codes = [code for code, _, _, _ in PRICING_RULES]
    assert len(set(codes)) == len(codes)


def test_every_priced_item_has_exactly_one_each_rule_and_no_other_rules() -> None:
    priced = {name: price for name, price in PRICES.items() if price is not None}
    assert {label: cents for _, label, cents, _ in PRICING_RULES} == priced
    assert len(PRICING_RULES) == len(priced)
    assert {unit for _, _, _, unit in PRICING_RULES} == {"each"}
    assert all(isinstance(cents, int) and cents >= 0 for cents in priced.values())


def test_unconfirmed_prices_are_unpriced_with_no_rule() -> None:
    unpriced = {name for name, price in PRICES.items() if price is None}
    assert unpriced == {"Chunky Egg and Tender Greens Bagel", "Caramel Cookie"}
    assert unpriced.isdisjoint(label for _, label, _, _ in PRICING_RULES)


def test_prices_read_off_the_document() -> None:
    assert PRICES["Plate"] == 3000
    assert PRICES["Bowl"] == 2700
    assert PRICES["Pita Pocket"] == 2000
    assert PRICES["Super Plate"] == 3700
    assert PRICES["Falafel, 6 pieces"] == 890
    assert PRICES["Sabbaba Pita Pocket"] == 1490
    assert PRICES["Babyccino"] == 100
    assert PRICES["Lamb Shish (side)"] == 2190
    rule_codes = {code: cents for code, _, cents, _ in PRICING_RULES}
    # The Sabbaba seed's first conversation quotes the Super Plate by this code.
    assert rule_codes["super-plate"] == 3700


def test_the_seasonal_salads_list_is_not_an_offering() -> None:
    assert "Seasonal salads list" not in NAMES
    assert {"Cauliflower and Avocado Salad", "Tabouli", "Pickles"} <= set(NAMES)


def test_orders_reference_real_offerings() -> None:
    assert {item for items in ORDER_ITEMS for item in items} <= set(NAMES)


def test_profile_matches_the_document() -> None:
    assert SABABA_PROFILE["hours"] == "Monday to Sunday 6:00 am to 8:00 pm"
    assert SABABA_PROFILE["business_type"] == "Middle Eastern restaurant"
    assert SABABA_PROFILE["contact"] == "owner@sababa.dev"  # demo address, not the shop's phone


def test_knowledge_docs_are_typed_and_cover_every_section() -> None:
    by_name = {filename: (doc_type, text) for filename, doc_type, text in KNOWLEDGE_DOCS}
    assert len(by_name) == len(KNOWLEDGE_DOCS)
    assert by_name["about-hours-contact.md"][0] == "faq"
    assert by_name["allergens-and-dietary.md"][0] == "policy"
    assert by_name["ratings.md"][0] == "faq"
    price_lists = {f: text for f, (t, text) in by_name.items() if t == "price_list"}
    assert len(price_lists) == len(CATEGORIES)
    for category, items in MENU.items():
        text = price_lists[f"menu-{category.lower().replace(' ', '-')}.md"]
        for name, _, cents in items:
            expected = (
                "price not confirmed" if cents is None else f"${cents // 100}.{cents % 100:02d}"
            )
            assert f"- {name}: {expected}" in text


def test_about_doc_states_the_documents_discrepancies_as_is() -> None:
    about = KNOWLEDGE_DOCS[0][2]
    for stated in (
        "77 Spring St",
        "91 Spring St",
        "71 Spring St",
        "0493 872 535",
        "(02) 9369 5599",
    ):
        assert stated in about
    assert "cannot take or place orders" in about
    for channel in ("Uber Eats", "DoorDash", "Hey You"):
        assert channel in about


def test_allergen_doc_keeps_the_kitchen_caveat_and_dietary_lists() -> None:
    text = dict((f, t) for f, _, t in KNOWLEDGE_DOCS)["allergens-and-dietary.md"]
    assert "not been confirmed by the kitchen" in text
    assert "Tabouli contains bulgur, which is wheat" in text
    assert "Whether they share a fryer with other foods is not published" in text
    assert "{dietary_lists}" not in text  # the label lists were filled in
    vegan = next(p for p in text.split("\n\n") if p.startswith("Vegan on the menu:"))
    gluten_free = next(p for p in text.split("\n\n") if p.startswith("Gluten free on the menu:"))
    assert "Tabouli" in vegan and "Falafel, 12 pieces" in vegan
    assert "Tabouli" not in gluten_free  # the document says "Not gluten free"
    assert "Crunchy Edamame Salad" in gluten_free and "Garlic Aioli" in gluten_free


def test_ratings_doc_is_dated_to_the_snapshot() -> None:
    assert "8 October 2026" in RATINGS_MD
    assert "3.8 out of 5 from 190 ratings" in RATINGS_MD


def test_no_em_dash_anywhere_in_the_data() -> None:
    texts = [d for _, d, _, _ in CATALOG_ITEMS] + [t for _, _, t in KNOWLEDGE_DOCS] + NAMES
    em_dash = chr(0x2014)
    assert not any(em_dash in text for text in texts)


def test_photo_manifest_points_at_real_offerings_on_cloudinary_only() -> None:
    assert set(MEDIA["offerings"]) <= set(NAMES)
    assert len(MEDIA["offerings"]) >= 40
    for media in [MEDIA["cover"], *MEDIA["offerings"].values()]:
        assert media["url"].startswith("https://res.cloudinary.com/")
        assert media["public_id"].startswith("demo/sabbaba/")
