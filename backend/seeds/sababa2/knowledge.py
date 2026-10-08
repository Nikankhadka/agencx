"""Sabbaba 2 knowledge documents: the source Sabbaba text, condensed.

Same 13 documents, same filenames and document types as the source seed, so
citations and the ingestion pipeline see the identical shape. The prose is
tightened (the source's repeated price-basis block lives once in the About
doc; the ratings doc drops its bulky per-item paragraph) and the price lists
and dietary-label lists are built from ``seeds.sabbaba.menu.MENU`` - the
same source the offerings come from - so the facts cannot drift.

Why condense at all: this tenant's whole corpus travels in the fast-path
prompt on every turn, and the prompt budget covers the catalog too (see
``seeds/seed_sababa2.py`` and .env.example's context-budget block).
"""

from __future__ import annotations

from seeds.sabbaba.knowledge import dietary_lists_md
from seeds.sabbaba.menu import MENU

ABOUT_MD = """# About Sabbaba 2, Spring St, Bondi Junction

## About

Sabbaba is a fast-casual Middle Eastern and Israeli restaurant. The menu is
built around falafel, pita pockets, plates, bowls, salads, dips and grilled
meats, and the shop also serves breakfast bagels, coffee and sweets. Many
items are labelled vegetarian or vegan. Sabbaba has other locations; this
assistant answers for the Spring Street shop in Bondi Junction only.

## Hours

Opening hours are 6:00 am to 8:00 pm every day. Uber Eats and DoorDash list
breakfast 6:15 am to 11:00 am and the main menu 11:00 am to 8:00 pm. On the
Hey You app, bagels start at 6:15 am, salads at 10:00 am, and pita pockets,
plates, bowls and sides at 11:00 am. Public holiday hours are not listed.

## Location and contact

The shop is on Spring Street, Bondi Junction NSW 2022, in the Eastgate Bondi
Junction shopping centre. Listings disagree on the number: Uber Eats and
DoorDash say 77 Spring St, Google says 91 Spring St, and some directories
say 71 Spring St. Phone: 0493 872 535 (Google listing); an older number,
(02) 9369 5599, appears on some directories. Website: sabbaba.com.au.

## Ordering and policies

This assistant cannot take or place orders. Customers can order on Uber Eats,
DoorDash or the Hey You app, or phone the shop; the assistant can pass a
request on to the business. It has no live information such as stock or
special offers, and it does not search the web.

Prices are the Hey You prices listed on 8 October 2026. Where an item is not
on Hey You, the Uber Eats listed price is used and the item says so, and
delivery apps list higher prices for some items. Vegetarian, vegan and gluten
free labels are the ones shown on the shop's menus. Halal status is not
stated on the shop's listings.
"""

ALLERGENS_MD = """# Allergen and dietary information

## Allergen notes

Allergen notes on each menu item are read from the ingredients listed on the
shop's public menus and have not been confirmed by the kitchen. Where
ingredients are not listed, the allergens are not known. The names used are
wheat (gluten), milk, egg, soy, sesame, peanut, fish, crustacean, mollusc,
lupin, tree nuts and sulphites; no public information covers peanut,
crustacean, mollusc, lupin or sulphites for this shop. Falafel and chips are
fried, and whether they share a fryer with other foods is not published.
Cross-contact between foods in the kitchen is not published. Tabouli contains
bulgur, which is wheat, so vegan items with tabouli are not gluten free.
Halloumi, cheese, sour cream and tzatziki are dairy (milk). Tahini,
babaganoush, hummus and falafel contain sesame.

## Dietary labels

Vegetarian, vegan and gluten free labels are the ones shown on the shop's
menus. Halal status is not stated on the shop's listings. The lists below are
the items carrying each label on the menu; an item not listed has no such
label. Allergen notes are not confirmed by the kitchen.

{dietary_lists}

## Food safety

No public food safety inspection result or penalty record for this shop has
been confirmed as of 8 October 2026. Questions about hygiene and food safety
go to the business.
"""

RATINGS_MD = """# Ratings snapshot (8 October 2026)

Google: 3.8 out of 5 from 190 ratings.

Uber Eats main menu listing: 4.6 out of 5 from more than 3,000 ratings.

Uber Eats breakfast listing: 4.7 out of 5 from more than 2,000 ratings.

These ratings are a snapshot taken on 8 October 2026 and may have changed.
"""

# One short availability note per category, from the source document's own
# section notes. Categories the source leaves unannotated simply have none.
SECTION_NOTES: dict[str, str] = {
    "Pita Pockets": "Pita pockets, plates and bowls are available from 11:00 am.",
    "Plates": "Pita pockets, plates and bowls are available from 11:00 am.",
    "Bowls": "Pita pockets, plates and bowls are available from 11:00 am.",
    "Salads": "Salad boxes are available from 10:00 am.",
    "Sides": "Sides are available from 11:00 am.",
    "Breakfast": "Breakfast and coffee are served from 6:15 am.",
    "Coffee and Hot Drinks": "Breakfast and coffee are served from 6:15 am.",
}


def _dollars(cents: int) -> str:
    return f"${cents // 100}.{cents % 100:02d}"


def price_list_md(category: str, items: list[tuple[str, str, int | None]]) -> str:
    """One section's price list: name and price per line, from the seeded offerings.

    The shared price basis lives once in the About document instead of being
    repeated in every section, which is most of what keeps this corpus small
    enough for the fast path.
    """
    lines = []
    for name, description, price_cents in items:
        price = "price not confirmed" if price_cents is None else _dollars(price_cents)
        source = " (Uber Eats price)" if "Price source: Uber Eats" in description else ""
        lines.append(f"- {name}: {price}{source}")
    notes = [SECTION_NOTES.get(category, "")]
    if any(price_cents is None for _, _, price_cents in items):
        notes.append("An item shown as price not confirmed has no confirmed price yet.")
    intro = " ".join(note for note in notes if note)
    return f"# {category} price list\n\n{intro}\n\n" + "\n".join(lines) + "\n"


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
