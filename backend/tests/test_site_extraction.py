"""Unit tests for hybrid page extraction (no Postgres, no network).

Trafilatura runs for real; the recall-selection test monkeypatches only the
two-pass seam so the choice between standard and recall text is deterministic.
"""

from __future__ import annotations

import pytest

from app.ingestion import extract
from app.ingestion.extract import (
    PageBlocked,
    dedupe_lines,
    detect_blocked,
    extract_page,
    inclusive_text,
    is_near_duplicate,
    is_pricing_page,
)

_BODY = (
    "Northside Repairs is a family-run phone and laptop repair shop on the "
    "north side. Walk-ins are welcome, most screen repairs are finished the "
    "same day, and every repair carries a twelve month warranty. Bring the "
    "device in or send a message describing the fault before you travel."
)

_JSON_LD = """
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "LocalBusiness",
  "name": "Northside Repairs",
  "telephone": "+61 2 5550 1234",
  "email": "hello@northside.example",
  "address": {
    "streetAddress": "12 High Street",
    "addressLocality": "Sydney",
    "addressRegion": "NSW",
    "postalCode": "2000",
    "addressCountry": "AU"
  },
  "openingHoursSpecification": [
    {"dayOfWeek": ["Monday", "Tuesday"], "opens": "09:00", "closes": "17:00"}
  ],
  "priceRange": "$$",
  "menu": "https://northside.example/menu"
}
</script>
"""


def _page(body: str, *, title: str = "Northside Repairs", head: str = "") -> bytes:
    return (
        f"<html><head><title>{title}</title>{head}</head><body><main>{body}</main></body></html>"
    ).encode()


def test_json_ld_and_visible_blocks_become_business_facts() -> None:
    html = _page(
        f"<h1>Northside Repairs</h1><p>{_BODY}</p>"
        '<div id="contact"><p>Call +61 2 5550 1234</p><p>12 High Street, Sydney</p></div>',
        head=_JSON_LD,
    )

    result = extract_page(html, url="https://northside.example/contact")

    assert result.title == "Northside Repairs"
    assert "## Business details" in result.text
    assert "Phone: +61 2 5550 1234" in result.text
    assert "Address: 12 High Street, Sydney, NSW, 2000, AU" in result.text
    assert "Hours: Monday, Tuesday: 09:00-17:00" in result.text
    assert "Price range: $$" in result.text
    assert "Menu: https://northside.example/menu" in result.text
    assert "Call +61 2 5550 1234" in result.text


def test_pricing_page_uses_inclusive_text_when_it_keeps_more_prices() -> None:
    html = _page(
        f"<h1>Menu</h1><p>{_BODY}</p>"
        '<div class="products">'
        '<a href="/p/1">Flat white $4.50</a>'
        '<a href="/p/2">Avocado toast $12</a>'
        '<a href="/p/3">Big breakfast $24</a>'
        "</div>"
    )

    result = extract_page(html, url="https://northside.example/menu")

    assert result.used_inclusive is True
    assert "$4.50" in result.text
    assert "$24" in result.text
    assert "Big breakfast" in result.text


def test_inclusive_text_keeps_link_prices() -> None:
    html = _page(
        f"<h1>Menu</h1><p>{_BODY}</p>"
        '<div><a href="/p/1">Flat white $4.50</a><a href="/p/2">Big breakfast $24</a></div>'
    )
    text = inclusive_text(html)
    assert "Flat white $4.50" in text
    assert "Big breakfast $24" in text


def test_recall_pass_runs_when_standard_is_short_and_recovers_contact(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[bool] = []

    def fake_trafilatura(html: bytes, url: str, *, recall: bool) -> str:
        calls.append(recall)
        if recall:
            return (
                "Northside Repairs. Call us on 0400 000 000 or visit 12 High Street. "
                "We are open Monday to Friday, nine to five, and Saturday mornings. "
                "Walk-ins are welcome and most screen repairs are finished the same day. "
                "Every repair carries a twelve month warranty, and we can order parts "
                "for less common models before you travel across town."
            )
        return "Northside Repairs."

    monkeypatch.setattr(extract, "_trafilatura", fake_trafilatura)
    html = _page("<h1>Northside Repairs</h1>")

    result = extract_page(html, url="https://northside.example/")

    assert calls == [False, True]
    assert result.used_recall is True
    assert "0400 000 000" in result.text


def test_standard_text_is_kept_when_recall_adds_nothing() -> None:
    html = _page(f"<h1>Northside Repairs</h1><p>{_BODY}</p><h2>Hours</h2><p>Mon-Fri 9-5</p>")
    result = extract_page(html, url="https://northside.example/about")
    assert result.used_recall is False
    assert "## Hours" in result.text


@pytest.mark.parametrize(
    "title,body",
    [
        ("Just a moment...", "Checking your browser before accessing the site."),
        ("Robot Challenge Screen", "Please verify you are human."),
        ("Northside Repairs", "Enable JavaScript and cookies to continue."),
    ],
)
def test_captcha_and_challenge_pages_are_rejected(title: str, body: str) -> None:
    html = _page(f"<p>{body}</p>", title=title)
    assert detect_blocked(html) is not None
    with pytest.raises(PageBlocked, match="bot challenge"):
        extract_page(html, url="https://northside.example/")


def test_thin_pages_are_rejected_even_with_a_200_response() -> None:
    html = _page("<p>Hi there.</p>")
    with pytest.raises(PageBlocked, match="too little"):
        extract_page(html, url="https://northside.example/")


def test_css_like_contact_block_is_not_a_fact() -> None:
    html = _page(
        f"<h1>Northside Repairs</h1><p>{_BODY}</p>"
        '<div id="contact">.contact-box { color: red; padding: 4px; }</div>'
    )
    result = extract_page(html, url="https://northside.example/")
    assert not any(".contact-box" in fact for fact in result.facts)


def test_dedupe_lines_threads_seen_text_across_pages() -> None:
    seen: set[str] = set()
    first = dedupe_lines(
        "A sentence long enough to be repeated across pages.\nShort unique line", seen
    )
    second = dedupe_lines(
        "A sentence long enough to be repeated across pages.\nAnother short line", seen
    )

    assert "A sentence long enough" in first
    assert "Short unique line" in first
    assert "A sentence long enough" not in second
    assert "Another short line" in second


def test_near_duplicate_detects_city_copy_and_keeps_unrelated_pages() -> None:
    city_a = (
        "We are the north side's phone repair specialists. We replace screens, "
        "batteries and charge ports, and every repair carries a twelve month "
        "warranty. Walk in or book ahead and we will have the part ready. "
    ) * 4
    city_b = city_a.replace("north side", "south side").replace("book ahead", "call ahead")

    assert is_near_duplicate(city_a, city_b)
    assert not is_near_duplicate(city_a, "Our cafe serves breakfast and lunch daily. " * 8)


def test_pricing_page_detection_is_path_based() -> None:
    assert is_pricing_page("https://shop.example/menu")
    assert is_pricing_page("https://shop.example/services/prices")
    assert not is_pricing_page("https://shop.example/about")
