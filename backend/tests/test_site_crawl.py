"""Unit tests for bounded site crawling (no Postgres, no network).

The FakeReader stands in for the SSRF-guarded fetch. These tests define the
crawl contract: pages combined into one document with headings and sources,
per-page and total caps enforced, repeated lines removed across pages,
near-duplicate content skipped, blocked pages tolerated, and a hard deadline.
"""

from __future__ import annotations

import asyncio

import pytest

from app.ingestion.site import CrawlResult, crawl_site

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
        self.active = 0
        self.max_active = 0

    async def read(self, url: str) -> bytes:
        self.reads.append(url)
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        try:
            await asyncio.sleep(self.delays.get(url, 0))
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
        "https://shop.example/about",
        "https://shop.example/services",
        "https://shop.example/pricing",
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
    assert result.skipped["budget"] >= 1


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
