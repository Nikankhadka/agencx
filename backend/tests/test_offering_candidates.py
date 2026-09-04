"""E-6: the Services rows, and the money rule they are built to respect.

No model runs on this path, so the guarantee is stronger than "the gate checks
it": a price on the Booking page is a *slice* of a line the owner wrote and
saved. These tests pin that property, not just the happy shape.
"""

from __future__ import annotations

from typing import Any

from app.features.business import offering_candidates as offerings


def _record(sections: list[dict[str, str]], status: str = "ready") -> dict[str, Any]:
    return {"status": status, "sections": sections}


def test_a_price_list_becomes_rows_with_the_owners_own_figures() -> None:
    rows = offerings.derive(
        [
            _record(
                [
                    {
                        "heading": "Prices",
                        "body": (
                            "Shawarma plate - $16 · Pickup\n"
                            "Catering box (feeds 15) - from $285\n"
                            "Mixed plate - $19"
                        ),
                    }
                ]
            )
        ]
    )
    assert rows == [
        {"name": "Shawarma plate", "price": "$16 · Pickup"},
        {"name": "Catering box (feeds 15)", "price": "from $285"},
        {"name": "Mixed plate", "price": "$19"},
    ]


def test_every_rendered_price_is_verbatim_in_the_source() -> None:
    """The money rule, as a property. Whatever the input, the price text on the
    page must appear character for character in the owner's own line - which is
    what makes it impossible for this path to round, convert or invent one."""
    body = (
        "Screen repair  $89.50 (most models)\n"
        "Battery replacement: AUD 65\n"
        "  * Diagnostic - free\n"
        "Water damage assessment — $49.99 up front\n"
        "Bulk discount: ten dollars off five or more\n"
    )
    rows = offerings.derive([_record([{"heading": "Prices", "body": body}])])
    assert rows, "expected the price list to produce rows"
    for row in rows:
        if row["price"] is not None:
            assert row["price"] in body, f"price {row['price']!r} is not verbatim in the source"
        assert str(row["name"]) in body


def test_rounding_is_impossible_because_nothing_recomputes() -> None:
    """$16.50 must never come back as $17 - the classic failure the structuring
    money guard exists for. Here the figure is never parsed into a number that
    could be re-rendered, so the assertion is on the exact string."""
    rows = offerings.derive([_record([{"heading": "Prices", "body": "Half plate - $16.50"}])])
    assert rows == [{"name": "Half plate", "price": "$16.50"}]


def test_offerings_without_a_price_still_list() -> None:
    rows = offerings.derive(
        [_record([{"heading": "What we offer", "body": "Screen repairs\nBattery replacements"}])]
    )
    assert rows == [
        {"name": "Screen repairs", "price": None},
        {"name": "Battery replacements", "price": None},
    ]


def test_only_the_offering_headings_are_read() -> None:
    """About, Hours and Policies describe the business, not what it sells. A
    sentence about opening hours is not a service row."""
    rows = offerings.derive(
        [
            _record(
                [
                    {"heading": "About", "body": "A phone repair shop in Bondi."},
                    {"heading": "Hours", "body": "Mon-Fri 9 to 6"},
                    {"heading": "Policies", "body": "Deposit of $50 on large jobs."},
                    {"heading": "What we offer", "body": "Screen repairs"},
                ]
            )
        ]
    )
    assert rows == [{"name": "Screen repairs", "price": None}]


def test_a_draft_the_owner_has_not_saved_is_not_published() -> None:
    """O-3 holds a source as a draft until the owner reads it back and saves it.
    An unreviewed draft reaching a customer-facing page would defeat that."""
    assert (
        offerings.derive(
            [_record([{"heading": "Prices", "body": "Screen repair $89"}], status="draft")]
        )
        == []
    )


def test_the_same_service_from_two_sources_lists_once() -> None:
    menu = _record([{"heading": "Prices", "body": "Screen repair - $89"}])
    price_list = _record([{"heading": "What we offer", "body": "Screen repair"}])
    assert offerings.derive([menu, price_list]) == [{"name": "Screen repair", "price": "$89"}]


def test_a_priced_mention_upgrades_a_bare_one() -> None:
    """The headings arrive in reading order, so "What we offer" (bare names) is
    read before "Prices" (the same names with figures). First-wins de-duplication
    threw every price away and left a Services list with no prices on it - which
    is what the screenshot of the real page showed."""
    rows = offerings.derive(
        [
            _record(
                [
                    {"heading": "What we offer", "body": "Shawarma plate\nMixed plate"},
                    {"heading": "Prices", "body": "Shawarma plate - $16 · Pickup"},
                ]
            )
        ]
    )
    assert rows == [
        {"name": "Shawarma plate", "price": "$16 · Pickup"},
        {"name": "Mixed plate", "price": None},
    ]


def test_prose_is_not_mistaken_for_a_row() -> None:
    """A wall of text under "What we offer" is a description, not a list. The
    length ceiling is what keeps it off the page as a giant unreadable row."""
    paragraph = (
        "We have been repairing phones in the neighbourhood for eleven years and "
        "we pride ourselves on same-day turnaround for almost every model we see, "
        "including the older handsets other shops turn away."
    )
    assert offerings.derive([_record([{"heading": "What we offer", "body": paragraph}])]) == []


def test_a_bare_total_keeps_its_whole_line() -> None:
    """A line that is only a figure has no name to show; dropping the name and
    rendering an empty title would be worse than keeping the line."""
    rows = offerings.derive([_record([{"heading": "Prices", "body": "$285"}])])
    assert rows == [{"name": "$285", "price": None}]


def test_a_qualifier_belongs_to_the_price_not_the_name() -> None:
    """ "Catering box - from $285" is one price, not a service called
    "Catering box - from". The prototype renders it "From $285"."""
    rows = offerings.derive(
        [
            _record(
                [
                    {
                        "heading": "Prices",
                        "body": (
                            "Catering box - from $285\n"
                            "Callout starting at $90\n"
                            "Repairs up to $300\n"
                        ),
                    }
                ]
            )
        ]
    )
    assert rows == [
        {"name": "Catering box", "price": "from $285"},
        {"name": "Callout", "price": "starting at $90"},
        {"name": "Repairs", "price": "up to $300"},
    ]


def test_no_knowledge_means_no_rows() -> None:
    assert offerings.derive([]) == []
    assert offerings.derive([_record([])]) == []


def test_normalize_name_handles_unicode_punctuation_and_spacing() -> None:
    assert offerings.normalize_name("  Café—Menu!  ") == "café menu"


def test_long_comma_and_semicolon_lists_become_rows() -> None:
    record = _record(
        [
            {"heading": "What we offer", "body": "Coffee, Salads, Pita bowls, Catering box"},
            {
                "heading": "Prices",
                "body": "Coffee $5; Salads $12; Pita bowls $16.50; Catering box $285",
            },
        ]
    )
    assert offerings.derive([record]) == [
        {"name": "Coffee", "price": "$5"},
        {"name": "Salads", "price": "$12"},
        {"name": "Pita bowls", "price": "$16.50"},
        {"name": "Catering box", "price": "$285"},
    ]
