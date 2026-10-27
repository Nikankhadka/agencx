"""Unit tests for bounded site discovery (no Postgres, no network).

A FakeReader stands in for the SSRF-guarded fetch, so these tests define the
selection contract: the offerings page first, nav before body, the sitemap only
when nav and body offer nothing to sell, junk and off-site links out, robots
respected, near-duplicate paths collapsed, page cap enforced.
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


async def test_discovery_leads_with_offerings_and_never_reads_the_sitemap() -> None:
    """29: an owner's own services and pricing pages are what the review is
    built from, so they outrank about, and the sitemap is only a fallback. The
    assertion is on the fetch calls: a sitemap that is never requested cannot
    have influenced the result."""
    reader = _reader()
    result = await discover_pages("https://shop.example/", reader=reader)

    assert isinstance(result, DiscoveryResult)
    urls = [page.url for page in result.pages]
    assert urls == [
        "https://shop.example/",
        "https://shop.example/pricing",
        "https://shop.example/services",
        "https://shop.example/about",
        "https://shop.example/contact",
        "https://shop.example/hours",
    ]
    assert result.pages[0].source == "home"
    assert next(page for page in result.pages if page.url.endswith("/services")).source == "nav"
    assert result.skipped["junk"] == 2
    assert result.skipped["other_site"] >= 1
    assert result.skipped["robots"] == 1
    assert not [read for read in reader.reads if "sitemap" in read]


async def test_legacy_discovery_reproduces_the_pre_ticket_order() -> None:
    """29: the probe compares old against new on the same URL, so the old
    selection is still reachable - eager sitemap, sitemap before body, about
    ahead of services, and the pre-ticket priority numbers."""
    reader = _reader()
    result = await discover_pages("https://shop.example/", reader=reader, legacy_discovery=True)

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
    assert result.pages[1].source == "nav"
    assert next(page for page in result.pages if page.url.endswith("/faq")).source == "sitemap"
    assert result.skipped["junk"] == 2
    assert result.skipped["other_site"] >= 1
    assert result.skipped["robots"] == 1
    assert result.skipped["duplicate_path"] == 2
    assert "https://shop.example/sitemap.xml" in reader.reads


async def test_offerings_page_outranks_an_about_page() -> None:
    home = (
        b"<html><body><nav>"
        b'<a href="/about">About</a><a href="/treatments">Treatments</a>'
        b"</nav></body></html>"
    )
    pages = {
        "https://shop.example/": home,
        "https://shop.example/about": b"<html><body>About</body></html>",
        "https://shop.example/treatments": b"<html><body>Treatments</body></html>",
    }
    result = await discover_pages("https://shop.example/", reader=FakeReader(pages))

    assert [page.url for page in result.pages] == [
        "https://shop.example/",
        "https://shop.example/treatments",
        "https://shop.example/about",
    ]
    assert result.pages[1].priority == 1


async def test_nav_anchor_label_alone_promotes_a_page() -> None:
    """29: plenty of sites name the page after the business, not the need -
    ``/our-work``, ``/what-we-do``, ``/shop``. The anchor text is the owner's
    own words for that page, so it ranks with the path."""
    home = (
        b"<html><body><nav>"
        b'<a href="/our-work">Services and repairs</a>'
        b'<a href="/about">About</a>'
        b"</nav></body></html>"
    )
    pages = {
        "https://shop.example/": home,
        "https://shop.example/our-work": b"<html><body>Work</body></html>",
        "https://shop.example/about": b"<html><body>About</body></html>",
    }
    result = await discover_pages("https://shop.example/", reader=FakeReader(pages))

    urls = [page.url for page in result.pages]
    assert urls == [
        "https://shop.example/",
        "https://shop.example/our-work",
        "https://shop.example/about",
    ]
    assert result.pages[1].priority == 1


async def test_sitemap_is_read_when_no_page_offers_anything_to_sell() -> None:
    home = b'<html><body><nav><a href="/about">About</a></nav></body></html>'
    pages = {
        "https://shop.example/": home,
        "https://shop.example/robots.txt": _ROBOTS,
        "https://shop.example/sitemap.xml": _SITEMAP_INDEX,
        "https://shop.example/sitemap-pages.xml": _SITEMAP_PAGES,
        "https://shop.example/about": b"<html><body>About</body></html>",
        "https://shop.example/faq": b"<html><body>FAQ</body></html>",
        "https://shop.example/services/phone-repair": b"<html><body>Repairs</body></html>",
    }
    reader = FakeReader(pages)
    result = await discover_pages("https://shop.example/", reader=reader)

    assert "https://shop.example/sitemap.xml" in reader.reads
    sources = {page.url: page.source for page in result.pages}
    assert sources["https://shop.example/faq"] == "sitemap"
    assert sources["https://shop.example/services/phone-repair"] == "sitemap"


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
    assert page_priority("https://shop.example/about") == 2
    assert page_priority("https://shop.example/treatments") == 1
    assert page_priority("https://shop.example/menu") == 1
    assert page_priority("https://shop.example/opening-hours") == 3
    assert page_priority("https://shop.example/faq") == 4
    assert page_priority("https://shop.example/warranty") == 5
    assert page_priority("https://shop.example/book") == 6
    assert page_priority("https://shop.example/whatever") == 99


def test_page_priority_reads_the_anchor_label_too() -> None:
    """29: path tokens and anchor text tokens are unioned, casefolded."""
    assert page_priority("https://shop.example/our-work", "Our Services") == 1
    assert page_priority("https://shop.example/our-work", "Pricing") == 1
    assert page_priority("https://shop.example/our-work", "Get in touch") == 99
    assert page_priority("https://shop.example/contact", "Where to find us") == 3


def test_extract_links_separates_navigation_from_body() -> None:
    navigation, body = extract_links(_HOME, "https://shop.example/")
    assert ("https://shop.example/about", "About") in navigation
    assert ("https://shop.example/services", "Services") in navigation
    assert "https://shop.example/hours" in [url for url, _label in body]
    assert "https://shop.example/about" not in [url for url, _label in body]


def test_is_junk_blocks_assets_staging_and_slider_fragments() -> None:
    assert site.is_junk("https://shop.example/blog/post")
    assert site.is_junk("https://shop.example/test-page")
    assert site.is_junk("https://shop.example/sample-menu")
    assert site.is_junk("https://shop.example/images/logo.png")
    assert site.is_junk("https://shop.example/slider-home")
    assert site.is_junk("https://shop.example/privacy-policy")
    assert site.is_junk("https://shop.example/terms-and-conditions")
    assert site.is_junk("https://shop.example/tcs")
    assert site.is_junk("https://shop.example/wp-admin")
    assert not site.is_junk("https://shop.example/testimonials")
    assert not site.is_junk("https://shop.example/services")
    assert not site.is_junk("https://shop.example/dental-anxiety")


def test_near_duplicate_path_keeps_different_services() -> None:
    selected = ["https://shop.example/services/phone-repair"]
    assert not site._near_duplicate_path("https://shop.example/services/laptop-repair", selected)
    assert site._near_duplicate_path("https://shop.example/services/phone-repair-austin", selected)


def test_near_duplicate_path_keeps_siblings_sharing_a_long_prefix() -> None:
    """29: the offerings tier now holds services, menu and pricing together, so
    a site whose pages are one long shared file name (the fixture and its like)
    must not lose its services page as a "duplicate" of its pricing page."""
    selected = ["https://shop.example/example-business-pricing.html"]
    assert not site._near_duplicate_path(
        "https://shop.example/example-business-services.html", selected
    )
