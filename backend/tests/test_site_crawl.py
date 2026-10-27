"""Unit tests for bounded site crawling (no Postgres, no network).

The FakeReader stands in for the SSRF-guarded fetch. These tests define the
crawl contract: pages combined into one document with headings and sources,
per-page and total caps enforced, repeated lines removed across pages,
near-duplicate content skipped, blocked pages tolerated, and a hard deadline.
"""

from __future__ import annotations

import asyncio

import pytest

from app.ingestion import site
from app.ingestion.site import CrawlResult, crawl_site


def test_crawl_defaults_keep_the_ten_page_budget_and_read_six_at_a_time() -> None:
    """29: one pasted URL is still 10 pages and 11,500 characters - the speed
    comes from reading six at once under a 10s deadline, not from a bigger
    document."""
    assert site.DEFAULT_MAX_PAGES == 10
    assert site.DEFAULT_MAX_CHARS == 11_500
    assert site.DEFAULT_CONCURRENCY == 6
    assert site.DEFAULT_TIMEOUT_S == 10.0


_ABOUT = (
    b"<html><head><title>About</title></head><body><main>"
    b"<p>Northside Repairs has served the same suburb for fifteen years. "
    b"We are a family business, we explain the fault before we start, "
    b"and we never replace a part that does not need replacing. "
    b"Every repair carries a ninety day warranty.</p>"
    b"<p>Copyright 2026 Northside Repairs. All rights reserved.</p>"
    b"</main></body></html>"
)

_SERVICES = (
    b"<html><head><title>Services</title></head><body><main>"
    b"<p>Screen replacement, battery replacement, charging port repair, "
    b"camera repair, speaker repair and data recovery. Bring the device in "
    b"and we will diagnose it while you wait. Most repairs are ready the same "
    b"day, and every one is tested before you collect it.</p>"
    b"<p>Copyright 2026 Northside Repairs. All rights reserved.</p>"
    b"</main></body></html>"
)

_PRICING = (
    b"<html><head><title>Pricing</title></head><body><main>"
    b"<p>Battery replacement costs $49. Screen replacement costs $89. "
    b"Charging port repair costs $69. Diagnostic checks are free. "
    b"We quote before we start, and the price you are quoted is the price "
    b"you pay when you collect the device.</p>"
    b"<p>Copyright 2026 Northside Repairs. All rights reserved.</p>"
    b"</main></body></html>"
)

_CONTACT = (
    b"<html><head><title>Contact</title></head><body><main>"
    b"<p>Call us on 555-0100, email hello@northside.example, "
    b"or visit 12 High Street on weekdays between nine and six. "
    b"Weekend drop-offs are welcome, and we will message you when the "
    b"repair is ready to collect. Parking is available behind the shop.</p>"
    b"<p>Copyright 2026 Northside Repairs. All rights reserved.</p>"
    b"</main></body></html>"
)


class FakeReader:
    def __init__(
        self,
        pages: dict[str, bytes],
        *,
        delays: dict[str, float] | None = None,
    ) -> None:
        self.pages = pages
        self.delays = delays or {}
        self.reads: list[str] = []
        self.cancelled: list[str] = []
        self.active = 0
        self.max_active = 0

    async def read(self, url: str) -> bytes:
        self.reads.append(url)
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        try:
            try:
                await asyncio.sleep(self.delays.get(url, 0))
            except asyncio.CancelledError:
                self.cancelled.append(url)
                raise
            try:
                return self.pages[url]
            except KeyError as exc:
                raise ValueError(f"could not read this URL (HTTP 404) {url}") from exc
        finally:
            self.active -= 1


def _reader(**overrides: bytes) -> FakeReader:
    pages = {
        "https://shop.example/": _nav("/about", "/services", "/pricing", "/contact"),
        "https://shop.example/robots.txt": b"User-agent: *\n",
        "https://shop.example/about": _ABOUT,
        "https://shop.example/services": _SERVICES,
        "https://shop.example/pricing": _PRICING,
        "https://shop.example/contact": _CONTACT,
    }
    pages.update(overrides)
    return FakeReader(pages)


def _nav(*paths: str) -> bytes:
    links = "".join(f'<a href="{path}">{path}</a>' for path in paths)
    return (
        f"<html><head><title>Northside Repairs</title></head><body>"
        f"<header><nav>{links}</nav></header><main>"
        f"<p>We repair phones and laptops for the whole neighbourhood. "
        f"Our technicians handle screens, batteries, charging ports and water "
        f"damage, and every repair is checked before it goes back to you. "
        f"Most repairs are ready the same day.</p>"
        f"</main></body></html>"
    ).encode()


async def test_crawl_combines_pages_with_headings_and_sources() -> None:
    reader = _reader()

    result = await crawl_site("https://shop.example/", reader=reader)

    assert isinstance(result, CrawlResult)
    assert result.homepage == "https://shop.example/"
    assert result.title == "Northside Repairs"
    assert [page.url for page in result.pages] == [
        "https://shop.example/",
        "https://shop.example/pricing",
        "https://shop.example/services",
        "https://shop.example/about",
        "https://shop.example/contact",
    ]
    assert result.text.startswith("## Northside Repairs\nSource: https://shop.example/\n\n")
    assert "## About\nSource: https://shop.example/about" in result.text
    assert "## Pricing\nSource: https://shop.example/pricing" in result.text
    assert "Battery replacement costs $49." in result.text
    assert result.discovered == 5
    assert result.selected == 5
    assert result.timed_out is False
    # The homepage body is read once and reused from discovery.
    assert reader.reads.count("https://shop.example/") == 1


async def test_crawl_keeps_the_total_document_below_the_budget() -> None:
    body = "We repair phones and laptops every weekday. " * 120
    pages = {
        "https://shop.example/": _nav("/about", "/services"),
        "https://shop.example/robots.txt": b"User-agent: *\n",
        "https://shop.example/about": (
            f"<html><head><title>About</title></head><body><main><p>{body}</p></main></body></html>"
        ).encode(),
        "https://shop.example/services": (
            f"<html><head><title>Services</title></head><body><main><p>{body}</p>"
            f"</main></body></html>"
        ).encode(),
    }
    reader = FakeReader(pages)

    result = await crawl_site("https://shop.example/", reader=reader, max_chars=400)

    assert len(result.text) <= 400
    assert len(result.pages) == 1
    # The pages that could not fit are cancelled at the budget, so they are
    # never fetched and never recorded as a skip or a failure.
    assert "timeout" not in result.skipped
    assert result.timed_out is False


async def test_crawl_removes_lines_repeated_across_pages() -> None:
    reader = _reader()

    result = await crawl_site("https://shop.example/", reader=reader)

    footer = "Copyright 2026 Northside Repairs. All rights reserved."
    assert result.text.count(footer) == 1


async def test_crawl_skips_a_near_duplicate_page() -> None:
    body = (
        "<p>We repair phones and laptops for the whole neighbourhood. "
        "Our technicians handle screens, batteries, charging ports and water "
        "damage, and every repair is checked before it goes back to you. "
        "Most repairs are ready the same day.</p>"
    )
    home = (
        b"<html><head><title>Northside Repairs</title></head><body>"
        b'<header><nav><a href="/about">About</a>'
        b'<a href="/our-story">Our story</a></nav></header>'
        b"<main><p>Welcome to Northside Repairs. Bring your device in for a "
        b"free quote. We open at nine each weekday and close at six, and we "
        b"are closed on public holidays. Parking is available behind the "
        b"shop, and the bus stops directly outside.</p></main></body></html>"
    )
    pages = {
        "https://shop.example/": home,
        "https://shop.example/robots.txt": b"User-agent: *\n",
        "https://shop.example/about": (
            "<html><head><title>About Northside</title></head><body><main>"
            f"{body}</main></body></html>"
        ).encode(),
        "https://shop.example/our-story": (
            f"<html><head><title>Our Story</title></head><body><main>{body}</main></body></html>"
        ).encode(),
    }
    reader = FakeReader(pages)

    result = await crawl_site("https://shop.example/", reader=reader, max_pages=3)

    urls = [page.url for page in result.pages]
    assert urls == ["https://shop.example/", "https://shop.example/about"]
    assert result.skipped["duplicate_content"] == 1


async def test_crawl_reports_a_blocked_page_and_keeps_the_rest() -> None:
    blocked = (
        b"<html><head><title>Contact</title></head><body><main>"
        b"<p>Access denied. This page is protected by a robot challenge. "
        b"Please enable JavaScript and cookies to continue.</p>"
        b"</main></body></html>"
    )
    reader = _reader(**{"https://shop.example/contact": blocked})

    result = await crawl_site("https://shop.example/", reader=reader)

    assert "https://shop.example/contact" not in [page.url for page in result.pages]
    assert result.skipped["blocked"] == 1
    assert "## Services" in result.text


async def test_crawl_raises_when_nothing_is_extractable() -> None:
    blocked = (
        b"<html><head><title>Northside</title></head><body><main>"
        b"<p>Access denied. This page is protected by a robot challenge.</p>"
        b"</main></body></html>"
    )
    reader = FakeReader(
        {
            "https://shop.example/": blocked,
            "https://shop.example/robots.txt": b"User-agent: *\n",
        }
    )

    with pytest.raises(ValueError, match="no extractable content"):
        await crawl_site("https://shop.example/", reader=reader)


async def test_crawl_applies_per_page_caps_with_a_larger_pricing_cap() -> None:
    long_about = "We are a family business and we explain every fault. " * 160
    long_pricing = "Battery replacement costs $49. Screen replacement costs $89. " * 160
    pages = {
        "https://shop.example/": _nav("/about", "/pricing"),
        "https://shop.example/robots.txt": b"User-agent: *\n",
        "https://shop.example/about": (
            "<html><head><title>About</title></head><body><main>"
            f"<p>{long_about}</p></main></body></html>"
        ).encode(),
        "https://shop.example/pricing": (
            "<html><head><title>Pricing</title></head><body><main>"
            f"<p>{long_pricing}</p></main></body></html>"
        ).encode(),
    }
    reader = FakeReader(pages)

    result = await crawl_site("https://shop.example/", reader=reader, max_pages=3)

    by_url = {page.url: page.chars for page in result.pages}
    assert 3_900 <= by_url["https://shop.example/about"] <= 4_000
    assert 5_900 <= by_url["https://shop.example/pricing"] <= 6_000
    assert len(result.text) <= 11_500


async def test_crawl_reads_at_most_six_pages_at_once_by_default() -> None:
    """29: the default fan-out is six page reads in flight, not one after the
    other - the wall clock on a ten-page site is two rounds, not ten."""
    paths = [f"/page-{index}" for index in range(12)]
    links = "".join(f'<a href="{path}">Page {index}</a>' for index, path in enumerate(paths))
    home = f"<html><body><header><nav>{links}</nav></header></body></html>".encode()
    pages: dict[str, bytes] = {
        "https://shop.example/": home,
        "https://shop.example/robots.txt": b"User-agent: *\n",
    }
    delays: dict[str, float] = {}
    for index, path in enumerate(paths):
        body = f"We repair phones, laptops and tablets, number {index}. " * 20
        pages[f"https://shop.example{path}"] = (
            f"<html><head><title>Page {index}</title></head><body><main><p>{body}</p>"
            f"</main></body></html>"
        ).encode()
        delays[f"https://shop.example{path}"] = 0.05
    reader = FakeReader(pages, delays=delays)

    result = await crawl_site("https://shop.example/", reader=reader)

    assert reader.max_active <= 6
    assert reader.max_active > 1
    assert len(result.pages) <= 10


async def test_crawl_never_exceeds_the_total_budget_at_defaults() -> None:
    """29: ten pages of long copy still land inside the 11,500-character
    contract; the per-page caps alone do not add up to it."""
    paths = [f"/page-{index}" for index in range(9)]
    links = "".join(f'<a href="{path}">Page {index}</a>' for index, path in enumerate(paths))
    home = f"<html><body><header><nav>{links}</nav></header></body></html>".encode()
    pages: dict[str, bytes] = {
        "https://shop.example/": home,
        "https://shop.example/robots.txt": b"User-agent: *\n",
    }
    for index, path in enumerate(paths):
        body = f"Line {index} of the services page. " * 200
        pages[f"https://shop.example{path}"] = (
            f"<html><head><title>Page {index}</title></head><body><main><p>{body}</p>"
            f"</main></body></html>"
        ).encode()
    reader = FakeReader(pages)

    result = await crawl_site("https://shop.example/", reader=reader)

    assert len(result.text) <= 11_500
    assert len(result.pages) >= 2


async def test_crawl_limits_concurrent_page_reads() -> None:
    pages = {
        "https://shop.example/": _nav("/about", "/services", "/pricing", "/contact"),
        "https://shop.example/robots.txt": b"User-agent: *\n",
        "https://shop.example/about": _ABOUT,
        "https://shop.example/services": _SERVICES,
        "https://shop.example/pricing": _PRICING,
        "https://shop.example/contact": _CONTACT,
    }
    reader = FakeReader(
        pages,
        delays={
            "https://shop.example/about": 0.05,
            "https://shop.example/services": 0.05,
            "https://shop.example/pricing": 0.05,
            "https://shop.example/contact": 0.05,
        },
    )

    await crawl_site("https://shop.example/", reader=reader, concurrency=2)

    assert reader.max_active <= 2


async def test_crawl_deadline_keeps_pages_that_finished() -> None:
    pages = {
        "https://shop.example/": _nav("/about", "/services", "/pricing"),
        "https://shop.example/robots.txt": b"User-agent: *\n",
        "https://shop.example/about": _ABOUT,
        "https://shop.example/services": _SERVICES,
        "https://shop.example/pricing": _PRICING,
    }
    reader = FakeReader(
        pages,
        delays={
            "https://shop.example/about": 5,
            "https://shop.example/services": 5,
            "https://shop.example/pricing": 5,
        },
    )

    result = await crawl_site("https://shop.example/", reader=reader, timeout_s=0.5)

    assert result.timed_out is True
    assert result.skipped["timeout"] == 3
    assert [page.url for page in result.pages] == ["https://shop.example/"]
    assert "## Northside Repairs" in result.text


async def test_crawl_caps_a_hostile_page_count_at_ten() -> None:
    """29: a site that links four hundred pages still costs ten page reads -
    discovery caps the selection, and the crawl reads only what was selected."""
    paths = [f"/service-{index}" for index in range(60)]
    links = "".join(f'<a href="{path}">Service {index}</a>' for index, path in enumerate(paths))
    home = f"<html><body><header><nav>{links}</nav></header></body></html>".encode()
    pages: dict[str, bytes] = {
        "https://shop.example/": home,
        "https://shop.example/robots.txt": b"User-agent: *\n",
    }
    for index, path in enumerate(paths):
        pages[f"https://shop.example{path}"] = (
            f"<html><body><main><p>Service {index} is available every weekday.</p>"
            f"</main></body></html>"
        ).encode()
    reader = FakeReader(pages)

    result = await crawl_site("https://shop.example/", reader=reader)

    assert result.discovered >= 60
    assert result.selected == 10
    assert len(result.pages) <= 10
    assert result.skipped["page_cap"] > 0


def _sitemap(*paths: str) -> bytes:
    locations = "".join(f"<url><loc>{path}</loc></url>" for path in paths)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        f"{locations}</urlset>"
    ).encode()


def _long_page(title: str, sentence: str, repeats: int) -> bytes:
    return (
        f"<html><head><title>{title}</title></head><body><main>"
        f"<p>{sentence * repeats}</p></main></body></html>"
    ).encode()


def _home_with_nav(sentence: str, repeats: int, *paths: str) -> bytes:
    links = "".join(f'<a href="{path}">Services</a>' for path in paths)
    return (
        f"<html><head><title>Northside Repairs</title></head><body>"
        f"<header><nav>{links}</nav></header>"
        f"<main><p>{sentence * repeats}</p></main></body></html>"
    ).encode()


async def test_crawl_stops_at_the_budget_and_cancels_the_slow_sibling() -> None:
    """29: a fast page that fills the character budget ends the crawl. The
    in-flight sibling that would only add latency is cancelled - not waited
    for, and not recorded as a timeout or a failure."""
    home = (
        f"<html><head><title>Northside Repairs</title></head><body>"
        f'<header><nav><a href="/services">Services</a>'
        f'<a href="/about">About</a></nav></header><main>'
        f"<p>{'We repair phones and laptops every weekday. ' * 40}</p>"
        f"</main></body></html>"
    ).encode()
    pages = {
        "https://shop.example/": home,
        "https://shop.example/robots.txt": b"User-agent: *\n",
        "https://shop.example/services": _SERVICES,
        "https://shop.example/about": _ABOUT,
    }
    reader = FakeReader(
        pages,
        delays={
            "https://shop.example/services": 0.01,
            "https://shop.example/about": 5.0,
        },
    )
    loop = asyncio.get_running_loop()
    started = loop.time()

    result = await crawl_site("https://shop.example/", reader=reader, max_chars=600)

    elapsed = loop.time() - started
    assert elapsed < 1.0
    assert "https://shop.example/about" in reader.cancelled
    assert result.timed_out is False
    assert "timeout" not in result.skipped
    assert len(result.text) <= 600


async def test_sitemap_is_not_fetched_when_the_nav_result_is_rich() -> None:
    """29: a nav that carries an offerings page and enough text is not sent to
    the sitemap. The assertion is on the fetch: an unrequested sitemap cannot
    have changed the selection."""
    pages = {
        "https://shop.example/": _home_with_nav("We repair phones and laptops. ", 40, "/services"),
        "https://shop.example/robots.txt": (
            b"User-agent: *\nSitemap: https://shop.example/sitemap.xml\n"
        ),
        "https://shop.example/services": _long_page(
            "Services", "Screen and battery repairs while you wait. ", 40
        ),
        "https://shop.example/sitemap.xml": _sitemap("https://shop.example/menu"),
        "https://shop.example/menu": _long_page("Menu", "Extras and sides. ", 100),
    }
    reader = FakeReader(pages)

    result = await crawl_site("https://shop.example/", reader=reader, max_chars=2_000, max_pages=2)

    assert not [read for read in reader.reads if "sitemap" in read]
    assert "## Services" in result.text
    assert len(result.text) <= 2_000


async def test_sitemap_fires_on_a_thin_nav_result() -> None:
    """29: a nav that offers a page but gathers less than 60% of the document
    budget is thin, so the sitemap fallback fires and the crawl continues with
    the page that fills the remaining slot."""
    home = (
        b"<html><head><title>Northside Repairs</title></head><body>"
        b'<header><nav><a href="/services">Services</a>'
        b'<a href="/app">App</a></nav></header>'
        b"<main><p>We repair phones and laptops for the neighbourhood.</p>"
        b"</main></body></html>"
    )
    pages = {
        "https://shop.example/": home,
        "https://shop.example/robots.txt": (
            b"User-agent: *\nSitemap: https://shop.example/sitemap.xml\n"
        ),
        "https://shop.example/services": _long_page(
            "Services", "Screen repairs and battery swaps. ", 12
        ),
        "https://shop.example/app": _long_page("App", "Track your repair. ", 20),
        "https://shop.example/sitemap.xml": _sitemap("https://shop.example/menu"),
        "https://shop.example/menu": _long_page("Menu", "Peri peri chicken and sides. ", 100),
    }
    reader = FakeReader(pages)

    result = await crawl_site("https://shop.example/", reader=reader, max_chars=2_000, max_pages=3)

    assert "https://shop.example/sitemap.xml" in reader.reads
    assert "https://shop.example/menu" in [page.url for page in result.pages]
    assert len(result.text) <= 2_000


async def test_character_cap_holds_when_pages_are_cancelled_at_the_budget() -> None:
    """29: the character cap is a true cap, not an estimate. A page already
    received is clipped to the budget and the rest are cancelled."""
    pages = {
        "https://shop.example/": _long_page(
            "Northside Repairs", "We repair phones and laptops. ", 100
        ),
        "https://shop.example/robots.txt": b"User-agent: *\n",
        "https://shop.example/services": _long_page(
            "Services", "Screen replacements and battery swaps. ", 100
        ),
    }
    reader = FakeReader(pages)

    result = await crawl_site("https://shop.example/", reader=reader, max_chars=1_500)

    assert len(result.text) <= 1_500
    assert len(result.pages) == 1
    assert result.timed_out is False


def _thin_site(
    *,
    menu_items: int = 0,
    content: dict[str, bytes] | None = None,
    fillers: int = 6,
) -> dict[str, bytes]:
    """A nav that sells but reads thin, with a sitemap behind it.

    The nav names one offerings page and enough untiered filler pages to hit
    the page cap; the homepage and the offerings page are short, so the crawl
    sees a thin result and asks the sitemap for more.
    """
    filler_links = "".join(f'<a href="/page-{index}">Page {index}</a>' for index in range(fillers))
    pages: dict[str, bytes] = {
        "https://shop.example/": (
            f"<html><head><title>Northside Repairs</title></head><body>"
            f'<header><nav><a href="/services">Services</a>{filler_links}</nav></header>'
            f"<main><p>{'We repair phones and laptops. ' * 10}</p></main></body></html>"
        ).encode(),
        "https://shop.example/robots.txt": (
            b"User-agent: *\nSitemap: https://shop.example/sitemap.xml\n"
        ),
        "https://shop.example/services": _long_page("Services", "Screen and battery repairs. ", 10),
    }
    for index in range(fillers):
        pages[f"https://shop.example/page-{index}"] = _long_page(
            f"Page {index}", f"Page {index} has details. ", 20
        )
    sitemap = [f"https://shop.example/menu-item/{index}" for index in range(1, menu_items + 1)]
    sitemap.extend((content or {}).keys())
    pages["https://shop.example/sitemap.xml"] = _sitemap(*sitemap)
    for index in range(1, menu_items + 1):
        pages[f"https://shop.example/menu-item/{index}"] = _long_page(
            f"Menu item {index}", f"Menu item {index} description. ", 10
        )
    pages.update(content or {})
    return pages


async def test_sitemap_fallback_caps_one_path_prefix_and_fills_with_content() -> None:
    """29: a sitemap that lists hundreds of one-item pages must not spend the
    whole budget on one prefix. The fallback reads at most two pages from the
    same first path segment and fills the rest from the other pages."""
    pages = _thin_site(
        menu_items=8,
        content={
            "https://shop.example/about": _long_page(
                "About", "We have repaired phones here since 2009. ", 10
            ),
            "https://shop.example/contact": _long_page(
                "Contact", "Call us or visit the shop on High Street. ", 10
            ),
        },
    )
    reader = FakeReader(pages)

    result = await crawl_site("https://shop.example/", reader=reader, max_pages=8)

    urls = [page.url for page in result.pages]
    assert len([url for url in urls if "/menu-item/" in url]) == 2
    assert "https://shop.example/about" in urls
    assert "https://shop.example/contact" in urls
    assert result.skipped["prefix_cap"] == 6


async def test_sitemap_fallback_keeps_the_tier_order_on_a_flat_sitemap() -> None:
    """29: a sitemap that is a flat list of real pages is unaffected. Nothing
    is deeper than one segment, so the tier still decides the order."""
    pages = _thin_site(
        content={
            "https://shop.example/menu": _long_page("Menu", "Chicken and sides. ", 15),
            "https://shop.example/pricing": _long_page(
                "Pricing", "Mains from twelve dollars. ", 15
            ),
            "https://shop.example/faq": _long_page("FAQ", "Common questions. ", 15),
            "https://shop.example/warranty": _long_page("Warranty", "Ninety days. ", 15),
            "https://shop.example/book": _long_page("Book", "Book an appointment. ", 15),
        },
        fillers=3,
    )
    reader = FakeReader(pages)

    result = await crawl_site("https://shop.example/", reader=reader, max_pages=5)

    assert [page.url for page in result.pages] == [
        "https://shop.example/",
        "https://shop.example/services",
        "https://shop.example/menu",
        "https://shop.example/pricing",
        "https://shop.example/faq",
    ]


async def test_character_cap_holds_after_the_sitemap_fallback() -> None:
    """29: the fallback's extra reads still land inside the character budget."""
    long_body = "".join(f"<p>We repair phones, item {index}.</p>" for index in range(200))
    pages = _thin_site(
        menu_items=8,
        content={
            "https://shop.example/about": (
                f"<html><head><title>About</title></head><body><main>{long_body}"
                f"</main></body></html>"
            ).encode(),
            "https://shop.example/contact": (
                f"<html><head><title>Contact</title></head><body><main>{long_body}"
                f"</main></body></html>"
            ).encode(),
        },
    )
    reader = FakeReader(pages)

    result = await crawl_site("https://shop.example/", reader=reader, max_pages=8, max_chars=1_200)

    assert len(result.text) <= 1_200
    assert result.timed_out is False
