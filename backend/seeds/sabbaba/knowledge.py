"""Sabbaba knowledge documents, as of 8 October 2026.

The prose is the source menu document's own text (about, hours, contact,
policies, allergens, ratings), lightly reflowed into markdown. The price lists
and the dietary-label lists are built from ``MENU`` so they cannot drift from
the offerings the seed writes.

``KNOWLEDGE_DOCS`` is ``(filename, doc_type, markdown)`` rows for
``_helpers.ingest_documents``.
"""

from __future__ import annotations

import re

from seeds.sabbaba.menu import MENU

ABOUT_MD = """# About Sabbaba, Spring St, Bondi Junction

## About

Sabbaba is a fast-casual Middle Eastern and Israeli restaurant. The menu is built around
falafel, pita pockets, plates, bowls, salads, dips and grilled meats, and the shop also
serves breakfast bagels, coffee and sweets. Its Google listing describes it as Middle
Eastern street food, like pita, dips and grilled meats, in a laid-back cafe. Many items are
labelled vegetarian or vegan on the menu. Sabbaba has other locations, including Bondi
Beach. This assistant answers for the Spring Street shop in Bondi Junction. The other
locations are not set up here.

## Hours

Opening hours on the Google listing are 6:00 am to 8:00 pm every day.

Ordering hours on Uber Eats: breakfast menu 6:15 am to 11:00 am, main menu 11:00 am to
8:00 pm. DoorDash lists the same breakfast hours.

On the Hey You app, bagels are available from 6:15 am, salads from 10:00 am, and pita
pockets, plates, bowls and sides from 11:00 am.

Public holiday hours are not listed.

## Location and contact

The shop is on Spring Street, Bondi Junction NSW 2022, in the Eastgate Bondi Junction
shopping centre. Uber Eats and DoorDash list 77 Spring St. Google lists 91 Spring St. Some
directories list 71 Spring St.

Phone: 0493 872 535 (Google listing). An older number, (02) 9369 5599, appears on some
directories.

Website: sabbaba.com.au.

## Ordering and policies

This assistant cannot take or place orders. Customers can order on Uber Eats, DoorDash or
the Hey You app, or phone the shop. The assistant can pass a request on to the business.

The assistant has no live information such as stock or special offers, and it does not
search the web.

Prices are the Hey You prices listed in the menu. Where an item is not on Hey You, the Uber
Eats listed price is used and the item says so. Delivery apps list higher prices for some
items.

Vegetarian, vegan and gluten free labels are the ones shown on the shop's menus. Halal
status is not stated on the shop's listings.
"""

ALLERGENS_MD = """# Allergen and dietary information

## Allergen notes

Allergen notes on each menu item are read from the ingredients listed on the shop's public
menus. They have not been confirmed by the kitchen. Where ingredients are not listed, the
allergens are not known.

The names used are wheat (gluten), milk, egg, soy, sesame, peanut, fish, crustacean,
mollusc, lupin, tree nuts and sulphites. No public information covers peanut, crustacean,
mollusc, lupin or sulphites for this shop.

Falafel and chips are fried. Whether they share a fryer with other foods is not published.
Cross-contact between foods in the kitchen is not published.

Tabouli contains bulgur, which is wheat, so vegan items with tabouli are not gluten free.

Halloumi, cheese, sour cream and tzatziki are dairy (milk).

Tahini, babaganoush, hummus and falafel contain sesame.

## Dietary labels

Vegetarian, vegan and gluten free labels are the ones shown on the shop's menus. Halal
status is not stated on the shop's listings. The lists below are the items carrying each
label on the menu; an item not listed has no such label. Allergen notes are not confirmed
by the kitchen.

{dietary_lists}

## Food safety

No public food safety inspection result or penalty record for this shop has been confirmed
as of 8 October 2026. Questions about hygiene and food safety go to the business.
"""

RATINGS_MD = """# Ratings snapshot (8 October 2026)

Google: 3.8 out of 5 from 190 ratings.

Uber Eats main menu listing: 4.6 out of 5 from more than 3,000 ratings.

Uber Eats breakfast listing: 4.7 out of 5 from more than 2,000 ratings.

Uber Eats shows the share of customers who liked an item. Items with 50 or more ratings:
Plate 90 percent liked from 996 ratings. Pita Pocket 88 percent from 1,068. Sabbaba Pita
Pocket 89 percent from 556. Super Plate 84 percent from 535. Six Falafel 89 percent from
447. Sweet Potato Chips 88 percent from 418. Soft Drink Can 93 percent from 270. Vine
Leaves 85 percent from 181. Tunisian Pita Pocket 84 percent from 172. Algerian Pita Pocket
88 percent from 98. Chocolate Brownie 87 percent from 74. Garlic Aioli 94 percent from 74.
Pita White 94 percent from 57. Chips and Dips Share Pack 89 percent from 56.

These ratings are a snapshot taken on 8 October 2026 and may have changed.
"""

PRICE_BASIS = (
    "Prices are the Hey You prices listed on 8 October 2026. For items not on Hey You, the "
    "Uber Eats listed price is used and the item says so. Delivery apps list higher prices "
    "for some items."
)

# Availability and list notes the source document states for a section.
SECTION_NOTES: dict[str, str] = {
    "Pita Pockets": "Pita pockets, plates and bowls are available from 11:00 am.",
    "Plates": "Pita pockets, plates and bowls are available from 11:00 am.",
    "Bowls": "Pita pockets, plates and bowls are available from 11:00 am.",
    "Salads": (
        "Salad boxes are available from 10:00 am. Seasonal salads listed on Uber Eats, each "
        "priced below: Cauliflower and Avocado Salad, Pickles, Tabouli, Red Cabbage, Crunchy "
        "Edamame, Lentil, Quinoa and Haloumi."
    ),
    "Sides": "Sides are available from 11:00 am.",
    "Breakfast": "Breakfast and coffee are served from 6:15 am.",
    "Coffee and Hot Drinks": "Breakfast and coffee are served from 6:15 am.",
}


def _dollars(cents: int) -> str:
    return f"${cents // 100}.{cents % 100:02d}"


def price_list_md(category: str, items: list[tuple[str, str, int | None]]) -> str:
    """One section's price list: name and price per line, from the seeded offerings."""
    lines = []
    for name, description, price_cents in items:
        price = "price not confirmed" if price_cents is None else _dollars(price_cents)
        source = " (Uber Eats price)" if "Price source: Uber Eats" in description else ""
        lines.append(f"- {name}: {price}{source}")
    notes = [SECTION_NOTES.get(category, ""), PRICE_BASIS]
    if any(price_cents is None for _, _, price_cents in items):
        notes.append("An item shown as price not confirmed has no confirmed price yet.")
    intro = " ".join(note for note in notes if note)
    return f"# {category} price list\n\n{intro}\n\n" + "\n".join(lines) + "\n"


# Label -> pattern over an item's own description. "Not gluten free" (Tabouli) is a
# negation, not a label.
_DIETARY_LABELS: dict[str, str] = {
    "Vegan": r"\bvegan\b",
    "Vegetarian": r"\bvegetarian\b",
    "Gluten free": r"(?<!Not )\bgluten free\b",
}


def dietary_lists_md() -> str:
    """Items carrying each dietary label on the menu, read from their descriptions."""
    parts = []
    for label, pattern in _DIETARY_LABELS.items():
        names = [
            name
            for items in MENU.values()
            for name, description, _ in items
            if re.search(pattern, description, re.IGNORECASE)
        ]
        parts.append(f"{label} on the menu: " + "; ".join(names) + ".")
    return "\n\n".join(parts)


KNOWLEDGE_DOCS: list[tuple[str, str, str]] = [
    ("about-hours-contact.md", "faq", ABOUT_MD),
    ("allergens-and-dietary.md", "policy", ALLERGENS_MD.format(dietary_lists=dietary_lists_md())),
    ("ratings.md", "faq", RATINGS_MD),
    *(
        (
            f"menu-{category.lower().replace(' ', '-')}.md",
            "price_list",
            price_list_md(category, items),
        )
        for category, items in MENU.items()
    ),
]
