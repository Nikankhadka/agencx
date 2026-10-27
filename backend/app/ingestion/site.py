"""Bounded, nav-first site discovery.

A pasted business URL names a site, not a page. Reading only the homepage
throws away the services list, the price list and the opening hours that the
owner's customers actually ask about, so ingestion discovers a small set of
high-signal pages before it sends anything to a model.

Discovery is deliberately cheap and bounded. It reads the homepage once, takes
the links the site's own navigation and header offer, then ordinary body links,
and only falls back to the sitemap when neither names a page that sells
something. Every URL is normalised, kept on the same site, filtered through a
junk blocklist, checked against robots.txt, de-duplicated by path, ranked by
what a customer usually needs, and capped. Fetching those pages is crawl_site's
job in the same module.

The WebReader seam exists so a later optional per-page fallback (a rendering
reader) can be slotted in without changing discovery, extraction, or the
callers. Nothing here knows about a business vertical; the ranking keywords are
generic page names.
"""

from __future__ import annotations

import asyncio
import logging
import re
import xml.etree.ElementTree as ET
from collections import Counter
from collections.abc import Collection, Iterable
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

from selectolax.parser import HTMLParser, Node

from app.ingestion.extract import (
    PageBlocked,
    PageExtraction,
    dedupe_lines,
    extract_page,
    is_near_duplicate,
    is_pricing_page,
)
from app.ingestion.url import AllowedTarget, fetch_page

logger = logging.getLogger("app.ingestion.site")

DEFAULT_MAX_PAGES = 10
DEFAULT_MAX_CHARS = 11_500
DEFAULT_CONCURRENCY = 6
DEFAULT_TIMEOUT_S = 10.0
_PAGE_MAX_CHARS = 4_000
_PRICING_PAGE_MAX_CHARS = 6_000
_MAX_SITEMAPS = 10
_MAX_SITEMAP_URLS = 1_000
_MAX_SITEMAP_DEPTH = 2
# A sitemap that lists one page per item can otherwise fill the whole page
# budget with siblings under a single first path segment.
_SITEMAP_PREFIX_CAP = 2

# Generic page names, in the order a customer usually needs them. A path token
# or an anchor-text token matching a group's keywords gives that page its
# priority. Nothing here names a trade, so tenant two onboards by config alone.
# What the business sells comes first: the review and the assistant are built
# from those pages, and every page spent on about-us copy is a page not read
# for a menu or a price.
_PRIORITY_KEYWORDS: tuple[set[str], ...] = (
    {
        "services",
        "service",
        "treatments",
        "menu",
        "menus",
        "pricing",
        "prices",
        "price",
        "rates",
        "what",
        "repairs",
    },
    {"about", "story", "team", "who", "mission"},
    {
        "contact",
        "location",
        "locations",
        "hours",
        "opening",
        "find",
        "visit",
        "directions",
    },
    {"faq", "faqs", "questions", "answers"},
    {"policies", "policy", "shipping", "returns", "warranty", "payment", "refunds"},
    {"booking", "book", "appointment", "appointments", "schedule", "reserve", "enquire"},
)

# The pre-29 table, kept only for the probe's comparison run.
_LEGACY_PRIORITY_KEYWORDS: tuple[set[str], ...] = (
    {"about", "story", "team", "who", "mission"},
    {"services", "service", "treatments", "treatment", "solutions", "repairs", "what"},
    {"pricing", "prices", "price", "rates", "rate", "menu", "menus", "cost", "costs", "quote"},
    {
        "contact",
        "location",
        "locations",
        "hours",
        "opening",
        "find",
        "visit",
        "directions",
    },
    {"faq", "faqs", "questions", "answers"},
    {"policies", "policy", "shipping", "returns", "warranty", "payment", "refunds"},
    {"booking", "book", "appointment", "appointments", "schedule", "reserve", "enquire"},
)

# Whole path segments that never carry knowledge a customer should be answered
# from. Test/sample pages are included because a staging page left linked from
# a live site is worse than a missing page: it teaches the assistant fiction.
_JUNK_SEGMENTS = {
    "account",
    "api",
    "author",
    "blog",
    "cart",
    "career",
    "careers",
    "cdn-cgi",
    "checkout",
    "demo",
    "feed",
    "feeds",
    "gallery",
    "login",
    "news",
    "privacy",
    "rss",
    "sample",
    "samples",
    "search",
    "signin",
    "signup",
    "slider",
    "slides",
    "tag",
    "tags",
    "tandc",
    "tcs",
    "terms",
    "test",
    "tests",
    "testing",
    "tnc",
    "wp-admin",
    "wp-json",
    "wp-login",
    "xmlrpc",
}

_NON_PAGE_EXTENSIONS = {
    ".css",
    ".csv",
    ".doc",
    ".docx",
    ".gif",
    ".gz",
    ".ico",
    ".jpeg",
    ".jpg",
    ".js",
    ".json",
    ".mp3",
    ".mp4",
    ".pdf",
    ".png",
    ".ppt",
    ".pptx",
    ".rar",
    ".rss",
    ".svg",
    ".txt",
    ".webp",
    ".xls",
    ".xlsx",
    ".xml",
    ".zip",
}

_TRACKING_PARAMS = {
    "fbclid",
    "gclid",
    "mc_cid",
    "mc_eid",
    "msclkid",
    "ref",
    "source",
}

_SOURCE_RANK = {"home": 0, "nav": 1, "body": 2, "sitemap": 3}

# The pre-29 ordering, kept only for the probe's comparison run: the sitemap was
# a step of its own before body links, and it was always fetched.
_LEGACY_SOURCE_RANK = {"home": 0, "nav": 1, "sitemap": 2, "body": 3}

# A page's path names the same page as one already selected when one token set
# sits inside the other (a city variant of the same page) or when the sets
# overlap this much, under the same first segment and the same depth. Cheap and
# conservative: the content-level check in extract.py is the one that catches
# city duplicates.
_PATH_DUPLICATE_THRESHOLD = 0.7


class WebReader(Protocol):
    """One page read. A rendering fallback can implement this later."""

    async def read(self, url: str) -> bytes: ...


@dataclass(frozen=True)
class HttpReader:
    """The default reader: the SSRF-guarded fetch in app.ingestion.url.

    ``allowed_targets`` exists only for the deterministic local fixture used by
    E2E tests (a compose-internal host); it never broadens a public fetch.
    """

    allowed_targets: Collection[AllowedTarget] = ()

    async def read(self, url: str) -> bytes:
        if self.allowed_targets:
            return await fetch_page(url, allowed_targets=self.allowed_targets)
        return await fetch_page(url)


@dataclass(frozen=True)
class DiscoveredPage:
    url: str
    priority: int
    source: str


@dataclass(frozen=True)
class DiscoveryResult:
    homepage: str
    homepage_html: bytes
    pages: list[DiscoveredPage]
    considered: int
    skipped: dict[str, int]
    # Used by the crawl's thin-result fallback: the sitemap is fetched only
    # after the nav/body read proves too small, so discovery cannot return the
    # URLs it deliberately did not fetch.
    robots_text: str = ""
    sitemap_checked: bool = False


def normalize_url(value: str, *, base: str | None = None) -> str | None:
    """An absolute http(s) URL with fragments, default ports and tracking noise
    removed, or None when the value is not a page we would fetch.

    ``index.html``/``index.php`` collapse to their directory so a site that
    links both forms is not crawled twice.
    """
    resolved = urljoin(base, value.strip()) if base else value.strip()
    try:
        parts = urlsplit(resolved)
    except ValueError:
        return None
    scheme = parts.scheme.lower()
    if scheme not in {"http", "https"}:
        return None
    try:
        host = (parts.hostname or "").lower().rstrip(".")
        port = parts.port
    except ValueError:
        return None
    if not host:
        return None
    netloc = host
    if port is not None and not (
        (scheme == "http" and port == 80) or (scheme == "https" and port == 443)
    ):
        netloc = f"{host}:{port}"
    path = re.sub(r"/{2,}", "/", parts.path or "/")
    path = re.sub(r"/index\.(?:html?|php)$", "/", path, flags=re.IGNORECASE)
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")
    query = sorted(
        (key, item)
        for key, item in parse_qsl(parts.query, keep_blank_values=True)
        if not key.lower().startswith("utm_") and key.lower() not in _TRACKING_PARAMS
    )
    return urlunsplit((scheme, netloc, path, urlencode(query), ""))


def site_key(url: str) -> str:
    """The host a URL belongs to, treating ``www.`` as the same site.

    A homepage that redirects to its www form would otherwise yield a
    navigation full of links discovery rejects as a different host.
    """
    host = (urlsplit(url).hostname or "").lower().rstrip(".")
    return host.removeprefix("www.")


def _keyword_tokens(*values: str) -> set[str]:
    """Casefolded word tokens from paths, URLs and anchor text."""
    return {
        token for value in values for token in re.split(r"[^a-z0-9]+", value.casefold()) if token
    }


def page_priority(url: str, label: str = "") -> int:
    """The generic customer-need tier of a page, 0 (home) through 99 (other).

    ``label`` is the anchor text the owner wrote for the link. A page named
    after the business rather than the need - ``/our-work``, ``/what-we-do`` -
    still ranks by what the owner called it, so the path tokens and the label
    tokens are unioned.
    """
    path = urlsplit(url).path
    if path in {"", "/"}:
        return 0
    tokens = _keyword_tokens(path, label)
    for priority, keywords in enumerate(_PRIORITY_KEYWORDS, start=1):
        if tokens & keywords:
            return priority
    return 99


def _legacy_page_priority(url: str) -> int:
    """Pre-29 ranking, path tokens only - probe comparison only."""
    path = urlsplit(url).path
    if path in {"", "/"}:
        return 0
    tokens = _keyword_tokens(path)
    for priority, keywords in enumerate(_LEGACY_PRIORITY_KEYWORDS, start=1):
        if tokens & keywords:
            return priority
    return 99


def is_junk(url: str) -> bool:
    """True for pages no owner wants their agent answering from."""
    path = urlsplit(url).path
    extension = path[path.rfind(".") :].lower() if "." in path.rsplit("/", 1)[-1] else ""
    if extension in _NON_PAGE_EXTENSIONS:
        return True
    raw_segments = [segment for segment in path.casefold().split("/") if segment]
    # Split hyphenated variants too: /privacy-policy and /terms-and-conditions
    # are the same junk as /privacy and /terms, while whole-segment names such
    # as wp-admin are checked as written.
    tokens = {token for segment in raw_segments for token in re.split(r"[_.-]+", segment) if token}
    if any(segment in _JUNK_SEGMENTS for segment in raw_segments) or tokens & _JUNK_SEGMENTS:
        return True
    # A slider's individual slides and a staging page's test-* variants are
    # path variants of something that should never be read.
    staging_prefixes = ("slide-", "slider-", "test-", "sample-", "demo-")
    if any(segment.startswith(staging_prefixes) for segment in raw_segments):
        return True
    return False


def _link_label(anchor: Node) -> str:
    """The anchor's visible text, whitespace collapsed so it tokenises cleanly."""
    return " ".join(anchor.text(separator=" ", strip=True).split())


def extract_links(
    html: bytes, base_url: str
) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    """(navigation links, other body links) in document order, each as
    ``(url, anchor label)``.

    Navigation and header links come first because they are the site owner's
    own idea of what matters. Body links are a fallback for sites that never
    use those elements, not the first frontier. The label travels with the URL
    because it is the owner's own words for the page: a site that names the
    page ``/our-work`` still writes "Services" in the menu.
    """
    tree = HTMLParser(html)
    navigation: list[tuple[str, str]] = []
    seen_navigation: set[str] = set()
    for anchor in tree.css("nav a[href], header a[href]"):
        href = (anchor.attributes.get("href") or "").strip()
        url = normalize_url(href, base=base_url)
        if url is not None and url not in seen_navigation:
            seen_navigation.add(url)
            navigation.append((url, _link_label(anchor)))
    body: list[tuple[str, str]] = []
    seen_body: set[str] = set()
    for anchor in tree.css("a[href]"):
        href = (anchor.attributes.get("href") or "").strip()
        url = normalize_url(href, base=base_url)
        if url is None or url in seen_navigation or url in seen_body:
            continue
        seen_body.add(url)
        body.append((url, _link_label(anchor)))
    return navigation, body


def parse_sitemap(body: bytes) -> tuple[list[str], list[str]]:
    """(page URLs, child sitemap URLs) from either sitemap shape.

    Namespaces are stripped rather than assumed so both the standard sitemap
    namespace and the image/video extensions parse.
    """
    try:
        root = ET.fromstring(body)
    except ET.ParseError:
        return [], []
    tag = root.tag.rsplit("}", 1)[-1].casefold()
    container_tag = "sitemap" if tag == "sitemapindex" else "url" if tag == "urlset" else ""
    if not container_tag:
        return [], []

    def local_name(node: ET.Element) -> str:
        return node.tag.rsplit("}", 1)[-1].casefold()

    locations: list[str] = []
    for container in root:
        if local_name(container) != container_tag:
            continue
        for child in container:
            if local_name(child) == "loc" and (child.text or "").strip():
                locations.append((child.text or "").strip())
                break
    return (locations, []) if tag == "urlset" else ([], locations)


async def _robots(reader: WebReader, homepage: str) -> tuple[RobotFileParser | None, str]:
    """The site's robots.txt, or (None, "") when it has none.

    A missing robots.txt is permission, not an error; a robots.txt that cannot
    be fetched for any other reason is treated the same way, matching the
    standard's "unavailable means allow" rule.
    """
    parts = urlsplit(homepage)
    robots_url = urlunsplit((parts.scheme, parts.netloc, "/robots.txt", "", ""))
    try:
        body = await reader.read(robots_url)
    except ValueError:
        return None, ""
    text = body.decode("utf-8", errors="replace")
    parser = RobotFileParser()
    parser.parse(text.splitlines())
    return parser, text


def _robots_sitemaps(text: str) -> list[str]:
    return [
        line.split(":", 1)[1].strip()
        for line in text.splitlines()
        if line.lower().startswith("sitemap:") and ":" in line
    ]


async def _sitemap_children(reader: WebReader, sitemap_url: str) -> tuple[list[str], list[str]]:
    try:
        return parse_sitemap(await reader.read(sitemap_url))
    except ValueError:
        return [], []


async def _sitemap_urls(
    reader: WebReader, homepage: str, robots_text: str, *, max_urls: int = _MAX_SITEMAP_URLS
) -> list[str]:
    """Page URLs from robots.txt sitemaps and the conventional sitemap paths.

    Sitemap indexes are followed two levels deep and capped in both documents
    and URLs, so a large site cannot turn discovery into a full crawl.
    """
    parts = urlsplit(homepage)
    root = urlunsplit((parts.scheme, parts.netloc, "/", "", ""))
    seeds = _robots_sitemaps(robots_text)
    seeds.extend(urljoin(root, name) for name in ("sitemap.xml", "sitemap_index.xml"))
    queue: list[str] = []
    seen_sitemaps: set[str] = set()
    for seed in seeds:
        normalized = normalize_url(seed, base=root)
        if normalized is not None and site_key(normalized) == site_key(homepage):
            if normalized not in seen_sitemaps:
                seen_sitemaps.add(normalized)
                queue.append(normalized)

    pages: list[str] = []
    depth = 0
    processed = 0
    while queue and depth <= _MAX_SITEMAP_DEPTH and len(pages) < max_urls:
        batch = queue[: max(0, _MAX_SITEMAPS - processed)]
        if not batch:
            break
        queue = queue[len(batch) :]
        processed += len(batch)
        results = await asyncio.gather(
            *(_sitemap_children(reader, sitemap_url) for sitemap_url in batch)
        )
        for page_urls, child_sitemaps in results:
            for page_url in page_urls:
                normalized = normalize_url(page_url, base=root)
                if (
                    normalized is not None
                    and site_key(normalized) == site_key(homepage)
                    and normalized not in pages
                ):
                    pages.append(normalized)
                    if len(pages) >= max_urls:
                        break
            for child in child_sitemaps:
                normalized = normalize_url(child, base=root)
                if (
                    normalized is not None
                    and site_key(normalized) == site_key(homepage)
                    and normalized not in seen_sitemaps
                ):
                    seen_sitemaps.add(normalized)
                    queue.append(normalized)
        depth += 1
    return pages


def _path_tokens(url: str) -> set[str]:
    path = urlsplit(url).path.casefold()
    return {token for token in re.split(r"[/_.-]+", path) if token}


def _near_duplicate_path(url: str, selected: Iterable[str]) -> bool:
    tokens = _path_tokens(url)
    if not tokens:
        return False
    path = urlsplit(url).path.casefold().strip("/")
    first_segment = path.split("/", 1)[0]
    depth = path.count("/")
    for other in selected:
        other_path = urlsplit(other).path.casefold().strip("/")
        # A parent section page and its child are different pages; only compare
        # siblings at the same depth.
        if not other_path or other_path.split("/", 1)[0] != first_segment:
            continue
        if other_path.count("/") != depth:
            continue
        other_tokens = _path_tokens(other)
        intersection = len(tokens & other_tokens)
        if not intersection:
            continue
        union = len(tokens | other_tokens)
        # A city variant is the same page plus a qualifier, so one token set
        # sits inside the other. A shared directory prefix is not a duplicate:
        # /offers/x-services and /offers/x-pricing are two pages of one site.
        subset = intersection == min(len(tokens), len(other_tokens))
        if subset or intersection / union >= _PATH_DUPLICATE_THRESHOLD:
            return True
    return False


def _page_offers(candidate: str, label: str, homepage: str) -> bool:
    """True when a linked page is a same-site, readable page that sells."""
    normalized = normalize_url(candidate, base=homepage)
    if normalized is None:
        return False
    if site_key(normalized) != site_key(homepage) or is_junk(normalized):
        return False
    return page_priority(normalized, label) == 1


def _consider_link(
    link: str,
    *,
    source: str,
    label: str,
    homepage: str,
    robots: RobotFileParser | None,
    source_rank: dict[str, int],
    legacy_discovery: bool,
    candidates: dict[str, DiscoveredPage],
    skipped: Counter[str],
) -> None:
    """Filter one link and merge it into the candidate set."""
    normalized = normalize_url(link, base=homepage)
    if normalized is None:
        skipped["invalid_url"] += 1
        return
    if site_key(normalized) != site_key(homepage):
        skipped["other_site"] += 1
        return
    if is_junk(normalized):
        skipped["junk"] += 1
        return
    if robots is not None and not robots.can_fetch("*", normalized):
        skipped["robots"] += 1
        return
    existing = candidates.get(normalized)
    if existing is not None:
        if source_rank[source] < source_rank[existing.source]:
            candidates[normalized] = DiscoveredPage(
                url=normalized,
                priority=existing.priority,
                source=source,
            )
        return
    if normalized == homepage:
        priority = 0
    elif legacy_discovery:
        priority = _legacy_page_priority(normalized)
    else:
        priority = page_priority(normalized, label)
    candidates[normalized] = DiscoveredPage(
        url=normalized,
        priority=priority,
        source=source,
    )


def _rank_pages(
    candidates: dict[str, DiscoveredPage],
    *,
    source_rank: dict[str, int],
    max_pages: int,
    sitemap_depth_first: bool = False,
) -> tuple[list[DiscoveredPage], Counter[str]]:
    """Rank candidates and keep the bounded, near-duplicate-free selection.

    ``sitemap_depth_first`` is the thin-result fallback: a sitemap-sourced
    candidate is ranked by path depth before its tier, so a deep item page
    cannot outrank a shallow page of the same site. Untiered nav/body pages
    still come last. A flat sitemap has one depth, so its tier order is
    unchanged. Selected sitemap pages are also capped per first path segment,
    because a sitemap that lists one page per item can otherwise fill every
    remaining slot with siblings.
    """
    skipped: Counter[str] = Counter()

    def rank_key(page: DiscoveredPage) -> tuple[int, int, int, int, int, str]:
        path = urlsplit(page.url).path
        depth = path.count("/")
        if sitemap_depth_first and page.source == "sitemap":
            return (depth, page.priority, source_rank[page.source], depth, len(page.url), page.url)
        return (page.priority, source_rank[page.source], 0, depth, len(page.url), page.url)

    ranked = sorted(candidates.values(), key=rank_key)
    selected: list[DiscoveredPage] = []
    selected_by_priority: dict[int, list[str]] = {}
    selected_prefixes: Counter[str] = Counter()
    for page in ranked:
        if len(selected) >= max_pages:
            skipped["page_cap"] += 1
            continue
        prefix = urlsplit(page.url).path.strip("/").split("/", 1)[0].casefold()
        if (
            sitemap_depth_first
            and page.source == "sitemap"
            and selected_prefixes[prefix] >= _SITEMAP_PREFIX_CAP
        ):
            skipped["prefix_cap"] += 1
            continue
        # Only compare within a tier: a phone-repair page and its prices page
        # share most of their path but serve different customer needs.
        if page.priority != 0 and _near_duplicate_path(
            page.url, selected_by_priority.get(page.priority, [])
        ):
            skipped["duplicate_path"] += 1
            continue
        selected.append(page)
        selected_by_priority.setdefault(page.priority, []).append(page.url)
        if page.source == "sitemap":
            selected_prefixes[prefix] += 1
    return selected, skipped


async def discover_pages(
    url: str,
    *,
    reader: WebReader | None = None,
    max_pages: int = DEFAULT_MAX_PAGES,
    legacy_discovery: bool = False,
) -> DiscoveryResult:
    """Discover the bounded, ranked set of pages worth reading for ``url``.

    Raises ValueError when the homepage itself is unfetchable or robots.txt
    forbids reading it - both are owner-facing fetch failures, never a crawl
    that silently returns nothing.

    ``legacy_discovery`` restores the pre-29 selection exactly (eager sitemap,
    sitemap before body, path-only priorities) so the probe can put both
    selections on the same URL. It exists only for that comparison.

    ponytail: one flag, probe-only, no per-behaviour switches. Ceiling: two
    ranking paths to keep honest while the evidence table is open. Delete this
    branch, ``_LEGACY_*`` tables and the ``legacy_discovery`` parameters once
    the table in ``docs/agencx/evidence/onboarding-source-2026-10/`` is filed.
    """
    reader = reader or HttpReader()
    homepage = normalize_url(url)
    if homepage is None:
        raise ValueError("unsupported URL scheme; only absolute http and https URLs are allowed")
    homepage_html = await reader.read(homepage)

    robots, robots_text = await _robots(reader, homepage)
    if robots is not None and not robots.can_fetch("*", homepage):
        raise ValueError("this site's robots.txt does not allow it to be read")

    navigation, body = extract_links(homepage_html, homepage)
    source_rank = _LEGACY_SOURCE_RANK if legacy_discovery else _SOURCE_RANK
    sitemap_checked = False

    if legacy_discovery:
        sitemap_pages = await _sitemap_urls(reader, homepage, robots_text)
        sitemap_checked = True
        feed: list[tuple[str, str, str]] = [
            (homepage, "home", ""),
            *((link, "nav", label) for link, label in navigation),
            *((link, "sitemap", "") for link in sitemap_pages),
            *((link, "body", label) for link, label in body),
        ]
    else:
        # The sitemap is a fallback, not a step. When the owner's own menu
        # already names a page that sells something, the sitemap can only add
        # latency to a turn that already has what it came for. A result that
        # turns out too thin is handled by the crawl, which can still fall
        # back after seeing the pages.
        offers = any(_page_offers(link, label, homepage) for link, label in (*navigation, *body))
        sitemap_pages = [] if offers else await _sitemap_urls(reader, homepage, robots_text)
        sitemap_checked = not offers
        feed = [
            (homepage, "home", ""),
            *((link, "nav", label) for link, label in navigation),
            *((link, "body", label) for link, label in body),
            *((link, "sitemap", "") for link in sitemap_pages),
        ]

    skipped: Counter[str] = Counter()
    candidates: dict[str, DiscoveredPage] = {}
    for link, source, label in feed:
        _consider_link(
            link,
            source=source,
            label=label,
            homepage=homepage,
            robots=robots,
            source_rank=source_rank,
            legacy_discovery=legacy_discovery,
            candidates=candidates,
            skipped=skipped,
        )

    selected, select_skipped = _rank_pages(candidates, source_rank=source_rank, max_pages=max_pages)
    skipped.update(select_skipped)

    logger.info(
        "site discovered homepage=%s considered=%d selected=%d skipped=%s",
        homepage,
        len(candidates),
        len(selected),
        dict(skipped),
    )
    return DiscoveryResult(
        homepage=homepage,
        homepage_html=homepage_html,
        pages=selected,
        considered=len(candidates),
        skipped=dict(skipped),
        robots_text=robots_text,
        sitemap_checked=sitemap_checked,
    )


@dataclass(frozen=True)
class CrawledPage:
    url: str
    title: str
    chars: int


@dataclass(frozen=True)
class CrawlResult:
    homepage: str
    title: str
    text: str
    pages: list[CrawledPage]
    discovered: int
    selected: int
    skipped: dict[str, int]
    timed_out: bool


def _truncate(text: str, limit: int) -> str:
    """Cut at a line or word boundary, never past ``limit``."""
    if limit <= 0:
        return ""
    if len(text) <= limit:
        return text
    head = text[:limit]
    for separator in ("\n", " "):
        trimmed = head.rsplit(separator, 1)[0].strip()
        if len(trimmed) >= limit // 2:
            return trimmed
    return head.strip()


def _fit_section(
    *,
    title: str,
    url: str,
    body: str,
    remaining: int,
    needs_separator: bool,
) -> str | None:
    """One page's section, clipped to the total budget, or None when it cannot
    contribute a useful amount."""
    header = f"## {' '.join(title.split())[:120]}\nSource: {url}\n\n"
    separator = 2 if needs_separator else 0
    available = remaining - separator - len(header)
    if available < 200:
        return None
    clipped = _truncate(body, available)
    if len(clipped) < 200:
        return None
    return f"{header}{clipped}"


_MIN_SECTION_BODY = 200
# The shortest possible section header: "## " + an empty title + "\nSource: "
# + the URL + "\n\n". A title only makes it longer, so this is the optimistic
# bound used to decide that no in-flight page can still fit.
_HEADER_MIN_CHARS = len("## ") + len("\nSource: ") + 2


@dataclass(frozen=True)
class _Document:
    text: str
    used: int
    pages: list[CrawledPage]
    title: str
    duplicates: int
    empty: int
    budget: int


def _assemble(
    pages: list[DiscoveredPage],
    extracted: dict[str, PageExtraction],
    *,
    max_chars: int,
    homepage: str,
) -> _Document:
    """Combine whichever of ``pages`` have been read into one document.

    Pure enough to run after every completed fetch: the caller passes the
    settled prefix, so a slow higher-ranked page cannot be skipped over.
    """
    parts: list[str] = []
    used = 0
    crawled: list[CrawledPage] = []
    seen_lines: set[str] = set()
    fingerprints: list[str] = []
    title = ""
    duplicates = empty = budget = 0
    for page in pages:
        extraction = extracted.get(page.url)
        if extraction is None:
            continue
        if page.url == homepage:
            title = extraction.title
        opening = f"{extraction.title}\n{extraction.text[:600]}"
        if any(is_near_duplicate(opening, other) for other in fingerprints):
            duplicates += 1
            continue
        fingerprints.append(opening)
        body = dedupe_lines(extraction.text, seen_lines)
        if not body.strip():
            empty += 1
            continue
        page_cap = _PRICING_PAGE_MAX_CHARS if is_pricing_page(page.url) else _PAGE_MAX_CHARS
        body = _truncate(body, page_cap)
        section = _fit_section(
            title=extraction.title,
            url=page.url,
            body=body,
            remaining=max_chars - used,
            needs_separator=bool(parts),
        )
        if section is None:
            budget += 1
            continue
        used += len(section) + (2 if parts else 0)
        parts.append(section)
        crawled.append(CrawledPage(url=page.url, title=extraction.title, chars=len(body)))
    return _Document(
        text="\n\n".join(parts),
        used=used,
        pages=crawled,
        title=title,
        duplicates=duplicates,
        empty=empty,
        budget=budget,
    )


def _settled_prefix(
    selected: list[DiscoveredPage],
    extracted: dict[str, PageExtraction],
    in_flight: set[str],
) -> list[DiscoveredPage]:
    """The pages that can be placed before an earlier in-flight page lands."""
    ready: list[DiscoveredPage] = []
    for page in selected:
        if page.url in extracted:
            ready.append(page)
        elif page.url in in_flight:
            break
    return ready


def _budget_satisfied(
    document: _Document,
    *,
    in_flight: set[str],
    max_chars: int,
    max_pages: int,
) -> bool:
    """True when no in-flight page can add a useful section."""
    if document.used >= max_chars or len(document.pages) >= max_pages:
        return True
    if not in_flight:
        return True
    remaining = max_chars - document.used
    shortest_url = min(len(url) for url in in_flight)
    return remaining - 2 - _HEADER_MIN_CHARS - shortest_url < _MIN_SECTION_BODY


async def _pump(
    pages: list[DiscoveredPage],
    *,
    selected: list[DiscoveredPage],
    reader: WebReader,
    homepage: str,
    homepage_html: bytes,
    extracted: dict[str, PageExtraction],
    fetched: set[str],
    skipped: Counter[str],
    semaphore: asyncio.Semaphore,
    max_chars: int,
    max_pages: int,
    deadline: float,
    stop_early: bool,
) -> bool:
    """Read ``pages`` concurrently and fold completions into the document.

    Returns True when the deadline cancelled in-flight reads. A read cancelled
    because the budget is already satisfied is deliberately not counted: it
    never started, so it is neither a failure nor a skip reason.
    """
    loop = asyncio.get_running_loop()

    async def read(page: DiscoveredPage) -> PageExtraction:
        async with semaphore:
            html = homepage_html if page.url == homepage else await reader.read(page.url)
            return await asyncio.to_thread(extract_page, html, url=page.url)

    tasks: dict[asyncio.Task[PageExtraction], str] = {
        asyncio.create_task(read(page)): page.url for page in pages if page.url not in fetched
    }
    pending = set(tasks)
    timed_out = False
    while pending:
        in_flight = {tasks[task] for task in pending}
        document = _assemble(
            _settled_prefix(selected, extracted, in_flight),
            extracted,
            max_chars=max_chars,
            homepage=homepage,
        )
        if stop_early and _budget_satisfied(
            document, in_flight=in_flight, max_chars=max_chars, max_pages=max_pages
        ):
            break
        remaining_s = deadline - loop.time()
        if remaining_s <= 0:
            timed_out = True
            break
        done, pending = await asyncio.wait(
            pending, timeout=remaining_s, return_when=asyncio.FIRST_COMPLETED
        )
        if not done:
            timed_out = True
            break
        for task in done:
            url = tasks[task]
            fetched.add(url)
            try:
                extracted[url] = task.result()
            except asyncio.CancelledError:
                continue
            except PageBlocked as exc:
                skipped["blocked"] += 1
                logger.info("crawl page blocked url=%s reason=%s", url, exc)
            except ValueError as exc:
                skipped["fetch_failed"] += 1
                logger.info("crawl page unreadable url=%s reason=%s", url, exc)
            except Exception:  # noqa: BLE001 - one bad page must not lose the site
                skipped["extract_failed"] += 1
                logger.exception("crawl page extraction failed url=%s", url)

    if pending:
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
        if timed_out:
            skipped["timeout"] += len(pending)
    return timed_out


def _parse_robots(text: str) -> RobotFileParser | None:
    if not text:
        return None
    parser = RobotFileParser()
    parser.parse(text.splitlines())
    return parser


def _is_thin(
    document: _Document,
    selected: list[DiscoveredPage],
    extracted: dict[str, PageExtraction],
    *,
    max_chars: int,
) -> bool:
    """True when the nav/body read is not worth trusting as the whole site."""
    offerings_read = any(page.priority == 1 and page.url in extracted for page in selected)
    return not offerings_read or document.used * 10 < max_chars * 6


async def _expand_from_sitemaps(
    discovery: DiscoveryResult,
    *,
    reader: WebReader,
    max_pages: int,
) -> tuple[list[DiscoveredPage], Counter[str]]:
    """Re-rank the nav/body selection together with the sitemap pages."""
    robots = _parse_robots(discovery.robots_text)
    candidates = {page.url: page for page in discovery.pages}
    skipped: Counter[str] = Counter()
    for link in await _sitemap_urls(reader, discovery.homepage, discovery.robots_text):
        _consider_link(
            link,
            source="sitemap",
            label="",
            homepage=discovery.homepage,
            robots=robots,
            source_rank=_SOURCE_RANK,
            legacy_discovery=False,
            candidates=candidates,
            skipped=skipped,
        )
    selected, select_skipped = _rank_pages(
        candidates,
        source_rank=_SOURCE_RANK,
        max_pages=max_pages,
        sitemap_depth_first=True,
    )
    skipped.update(select_skipped)
    return selected, skipped


async def crawl_site(
    url: str,
    *,
    reader: WebReader | None = None,
    max_pages: int = DEFAULT_MAX_PAGES,
    max_chars: int = DEFAULT_MAX_CHARS,
    concurrency: int = DEFAULT_CONCURRENCY,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    legacy_discovery: bool = False,
) -> CrawlResult:
    """Read a bounded set of pages and combine them into one model-sized document.

    At most ``concurrency`` pages are fetched and extracted at once, each page
    is capped (6,000 chars for pricing/menu, 4,000 otherwise), repeated lines
    are removed across pages, and the combined text never exceeds
    ``max_chars``. The crawl consumes reads as they complete and stops as soon
    as the page or character budget is full, so a slow sibling cannot stretch
    a turn once the document is complete. The total crawl has a hard deadline.

    ``legacy_discovery`` is the probe's comparison switch; see
    ``discover_pages``. It also keeps the pre-29 wait-for-every-read shape so
    the probe compares the new crawl with the old one, not with itself.

    Raises ValueError when no page produced readable content.
    """
    reader = reader or HttpReader()
    loop = asyncio.get_running_loop()
    started = loop.time()
    deadline = started + timeout_s
    try:
        async with asyncio.timeout(timeout_s):
            discovery = await discover_pages(
                url,
                reader=reader,
                max_pages=max_pages,
                legacy_discovery=legacy_discovery,
            )
    except TimeoutError as exc:
        raise ValueError("could not read this URL (timeout)") from exc

    skipped: Counter[str] = Counter(discovery.skipped)
    extracted: dict[str, PageExtraction] = {}
    fetched: set[str] = set()
    semaphore = asyncio.Semaphore(max(1, concurrency))
    selected = discovery.pages

    async def pump(pages: list[DiscoveredPage], *, stop_early: bool) -> bool:
        return await _pump(
            pages,
            selected=selected,
            reader=reader,
            homepage=discovery.homepage,
            homepage_html=discovery.homepage_html,
            extracted=extracted,
            fetched=fetched,
            skipped=skipped,
            semaphore=semaphore,
            max_chars=max_chars,
            max_pages=max_pages,
            deadline=deadline,
            stop_early=stop_early,
        )

    if legacy_discovery:
        timed_out = await pump(selected, stop_early=False)
    else:
        # Tiered pages first: the untiered body tail is the first thing to
        # replace if the result turns out thin, so it is not read until the
        # sitemap fallback has had its chance.
        timed_out = await pump([page for page in selected if page.priority != 99], stop_early=True)
        if not timed_out:
            document = _assemble(
                selected, extracted, max_chars=max_chars, homepage=discovery.homepage
            )
            # The fallback protects coverage on a site with more pages than the
            # budget: if discovery never hit the cap it already read every page
            # the nav and body offered, and a sitemap would only add latency.
            if (
                len(discovery.pages) >= max_pages
                and _is_thin(document, selected, extracted, max_chars=max_chars)
                and not discovery.sitemap_checked
            ):
                selected, sitemap_skipped = await _expand_from_sitemaps(
                    discovery, reader=reader, max_pages=max_pages
                )
                skipped.update(sitemap_skipped)
                document = _assemble(
                    selected, extracted, max_chars=max_chars, homepage=discovery.homepage
                )
            slots = max(0, max_pages - len(fetched))
            unread = [page for page in selected if page.url not in fetched][:slots]
            if unread and not _budget_satisfied(
                document,
                in_flight={page.url for page in unread},
                max_chars=max_chars,
                max_pages=max_pages,
            ):
                timed_out = await pump(unread, stop_early=True)

    document = _assemble(selected, extracted, max_chars=max_chars, homepage=discovery.homepage)
    skipped["duplicate_content"] += document.duplicates
    skipped["empty"] += document.empty
    skipped["budget"] += document.budget

    if not document.pages:
        raise ValueError("no extractable content at this URL")

    text = document.text
    # The budget is applied before the model calls; this assertion is the
    # invariant, not an estimate.
    if len(text) > max_chars:
        text = _truncate(text, max_chars)
    title = document.title or document.pages[0].title
    logger.debug("site crawl pages=%s", [page.url for page in document.pages])
    logger.info(
        "site crawl homepage=%s pages_discovered=%d pages_selected=%d pages_read=%d "
        "pages_skipped=%d blocked=%d robots_skipped=%d chars=%d timed_out=%s reasons=%s",
        discovery.homepage,
        discovery.considered,
        len(selected),
        len(document.pages),
        sum(skipped.values()),
        skipped.get("blocked", 0),
        skipped.get("robots", 0),
        len(text),
        timed_out,
        dict(skipped),
    )
    return CrawlResult(
        homepage=discovery.homepage,
        title=title,
        text=text,
        pages=document.pages,
        discovered=discovery.considered,
        selected=len(selected),
        skipped=dict(skipped),
        timed_out=timed_out,
    )
