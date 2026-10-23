"""Unit tests for bounded site discovery (no Postgres, no network).

A FakeReader stands in for the SSRF-guarded fetch, so these tests define the
selection contract: nav first, sitemap second, junk and off-site links out,
robots respected, near-duplicate paths collapsed, page cap enforced.
"""

from __future__ import annotations

import pytest

from app.ingestion import site
from app.ingestion.site import (
    DiscoveryResult,
    discover_pages,
    extract_links,
    normalize_url,
    page_priority,
    parse_sitemap,
    site_key,
)


class FakeReader:
    def __init__(self, pages: dict[str, bytes]) -> None:
        self.pages = pages
        self.reads: list[str] = []

    async def read(self, url: str) -> bytes:
        self.reads.append(url)
        try:
            return self.pages[url]
        except KeyError as exc:
            raise ValueError(f"could not read this URL (HTTP 404) {url}") from exc


_HOME = b"""<!doctype html><html><head><title>Northside</title></head><body>
<header><nav>
  <a href="/about">About</a>
  <a href="/services">Services</a>
  <a href="/pricing">Pricing</a>
  <a href="/contact">Contact</a>
  <a href="/blog">Blog</a>
  <a href="/test-page">Test page</a>
  <a href="/private">Private</a>
  <a href="https://other.example/contact">Another site</a>
  <a href="#top">Top</a>
</nav></header>
<main>
  <a href="/hours">Hours</a>
  <a href="/about">About again</a>
</main>
</body></html>"""

_ROBOTS = b"""User-agent: *
Disallow: /private
Sitemap: https://shop.example/sitemap.xml
"""

_SITEMAP_INDEX = b"""<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <sitemap><loc>https://shop.example/sitemap-pages.xml</loc></sitemap>
</sitemapindex>"""

_SITEMAP_PAGES = b"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://shop.example/services/phone-repair</loc></url>
  <url><loc>https://shop.example/faq</loc></url>
  <url><loc>https://shop.example/contact</loc></url>
  <url><loc>https://shop.example/services/phone-repair-austin</loc></url>
  <url><loc>https://shop.example/services/phone-repair-austin-tx</loc></url>
  <url><loc>https://other.example/services</loc></url>
</urlset>"""


def _reader(*, include_private: bool = True) -> FakeReader:
    pages = {
        "https://shop.example/": _HOME,
        "https://shop.example/robots.txt": _ROBOTS,
        "https://shop.example/sitemap.xml": _SITEMAP_INDEX,
        "https://shop.example/sitemap-pages.xml": _SITEMAP_PAGES,
        "https://shop.example/about": b"<html><body>About</body></html>",
        "https://shop.example/services": b"<html><body>Services</body></html>",
        "https://shop.example/pricing": b"<html><body>Pricing</body></html>",
        "https://shop.example/contact": b"<html><body>Contact</body></html>",
        "https://shop.example/hours": b"<html><body>Hours</body></html>",
        "https://shop.example/faq": b"<html><body>FAQ</body></html>",
        "https://shop.example/services/phone-repair": b"<html><body>Repairs</body></html>",
        "https://shop.example/services/phone-repair-austin": b"<html><body>Austin</body></html>",
        "https://shop.example/services/phone-repair-austin-tx": (
            b"<html><body>Austin TX</body></html>"
        ),
    }
    if include_private:
        pages["https://shop.example/private"] = b"<html><body>Private</body></html>"
    return FakeReader(pages)


async def test_discovery_prefers_nav_then_sitemap_and_excludes_junk() -> None:
    reader = _reader()
    result = await discover_pages("https://shop.example/", reader=reader)

    assert isinstance(result, DiscoveryResult)
    urls = [page.url for page in result.pages]
    assert urls == [
        "https://shop.example/",
        "https://shop.example/about",
        "https://shop.example/services",
        "https://shop.example/services/phone-repair",
        "https://shop.example/pricing",
        "https://shop.example/contact",
        "https://shop.example/hours",
        "https://shop.example/faq",
    ]
    assert result.pages[0].source == "home"
    assert result.pages[1].source == "nav"
    assert next(page for page in result.pages if page.url.endswith("/faq")).source == "sitemap"
    assert result.skipped["junk"] == 2
    assert result.skipped["other_site"] >= 1
    assert result.skipped["robots"] == 1
    assert result.skipped["duplicate_path"] == 2


async def test_discovery_honours_the_page_cap() -> None:
    links = "".join(f'<a href="/service-{index}">Service {index}</a>' for index in range(15))
    pages = {
        "https://shop.example/": f"<html><body><nav>{links}</nav></body></html>".encode(),
    }
    reader = FakeReader(pages)

    result = await discover_pages("https://shop.example/", reader=reader, max_pages=4)

    assert len(result.pages) == 4
    assert result.pages[0].url == "https://shop.example/"
    assert result.skipped["page_cap"] > 0


async def test_discovery_keeps_a_pasted_subpath_as_the_home_page() -> None:
    """A URL that is not the root still names the page the owner meant, so it
    keeps priority 0 and leads the document instead of ranking as "other"."""
    pages = {
        "https://shop.example/landing": (
            b'<html><body><nav><a href="/about">About</a>'
            b'<a href="/services">Services</a></nav></body></html>'
        ),
        "https://shop.example/about": b"<html><body>About</body></html>",
        "https://shop.example/services": b"<html><body>Services</body></html>",
    }
    result = await discover_pages("https://shop.example/landing", reader=FakeReader(pages))

    assert result.pages[0].url == "https://shop.example/landing"
    assert result.pages[0].priority == 0


async def test_discovery_raises_when_robots_blocks_the_homepage() -> None:
    reader = FakeReader(
        {
            "https://shop.example/": b"<html><body>Home</body></html>",
            "https://shop.example/robots.txt": b"User-agent: *\nDisallow: /\n",
        }
    )
    with pytest.raises(ValueError, match="robots"):
        await discover_pages("https://shop.example/", reader=reader)


async def test_sitemap_index_is_followed_and_offsite_sitemaps_ignored() -> None:
    reader = FakeReader(
        {
            "https://shop.example/": b"<html><body>Home</body></html>",
            "https://shop.example/robots.txt": b"",
            "https://shop.example/sitemap.xml": _SITEMAP_INDEX,
            "https://shop.example/sitemap-pages.xml": _SITEMAP_PAGES,
        }
    )
    result = await discover_pages("https://shop.example/", reader=reader)
    urls = [page.url for page in result.pages]
    assert "https://shop.example/faq" in urls
    assert "https://shop.example/services/phone-repair" in urls
    assert "https://other.example/services" not in urls


def test_parse_sitemap_reads_urls_and_child_sitemaps() -> None:
    pages, children = parse_sitemap(_SITEMAP_PAGES)
    assert "https://shop.example/faq" in pages
    assert children == []

    pages, children = parse_sitemap(_SITEMAP_INDEX)
    assert pages == []
    assert children == ["https://shop.example/sitemap-pages.xml"]


def test_parse_sitemap_ignores_image_locations() -> None:
    body = b"""<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
        xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">
      <url><loc>https://shop.example/menu</loc>
        <image:image><image:loc>https://shop.example/menu.jpg</image:loc></image:image>
      </url>
    </urlset>"""
    pages, _children = parse_sitemap(body)
    assert pages == ["https://shop.example/menu"]


def test_normalize_url_removes_fragments_tracking_and_index_files() -> None:
    assert normalize_url("HTTPS://Shop.Example/about/?utm_source=x&q=1#team") == (
        "https://shop.example/about?q=1"
    )
    assert normalize_url("https://shop.example/about/index.html") == "https://shop.example/about"
    assert normalize_url("https://shop.example/index.php") == "https://shop.example/"
    assert normalize_url("mailto:owner@shop.example") is None
    assert normalize_url("/about", base="https://shop.example/") == "https://shop.example/about"


def test_site_key_treats_www_as_the_same_site() -> None:
    assert site_key("https://www.shop.example/about") == "shop.example"
    assert site_key("https://shop.example/about") == "shop.example"


def test_page_priority_follows_customer_need() -> None:
    assert page_priority("https://shop.example/") == 0
    assert page_priority("https://shop.example/about") == 1
    assert page_priority("https://shop.example/treatments") == 2
    assert page_priority("https://shop.example/menu") == 3
    assert page_priority("https://shop.example/opening-hours") == 4
    assert page_priority("https://shop.example/faq") == 5
    assert page_priority("https://shop.example/warranty") == 6
    assert page_priority("https://shop.example/book") == 7
    assert page_priority("https://shop.example/whatever") == 99


def test_extract_links_separates_navigation_from_body() -> None:
    navigation, body = extract_links(_HOME, "https://shop.example/")
    assert "https://shop.example/about" in navigation
    assert "https://shop.example/hours" in body
    assert "https://shop.example/about" not in body


def test_is_junk_blocks_assets_staging_and_slider_fragments() -> None:
    assert site.is_junk("https://shop.example/blog/post")
    assert site.is_junk("https://shop.example/test-page")
    assert site.is_junk("https://shop.example/sample-menu")
    assert site.is_junk("https://shop.example/images/logo.png")
    assert site.is_junk("https://shop.example/slider-home")
    assert not site.is_junk("https://shop.example/testimonials")
    assert not site.is_junk("https://shop.example/services")


def test_near_duplicate_path_keeps_different_services() -> None:
    selected = ["https://shop.example/services/phone-repair"]
    assert not site._near_duplicate_path("https://shop.example/services/laptop-repair", selected)
    assert site._near_duplicate_path("https://shop.example/services/phone-repair-austin", selected)
