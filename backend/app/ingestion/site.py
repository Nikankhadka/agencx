"""Bounded, nav-first site discovery.

A pasted business URL names a site, not a page. Reading only the homepage
throws away the services list, the price list and the opening hours that the
owner's customers actually ask about, so ingestion discovers a small set of
high-signal pages before it sends anything to a model.

Discovery is deliberately cheap and bounded. It reads the homepage once, takes
the links the site's own navigation and header offer, then falls back to the
sitemap and finally to ordinary body links. Every URL is normalised, kept on
the same site, filtered through a junk blocklist, checked against robots.txt,
de-duplicated by path, ranked by what a customer usually needs, and capped.
Fetching those pages is crawl_site's job in the same module.

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

from selectolax.parser import HTMLParser

from app.ingestion.url import AllowedTarget, fetch_page

logger = logging.getLogger("app.ingestion.site")

DEFAULT_MAX_PAGES = 10
_MAX_SITEMAPS = 10
_MAX_SITEMAP_URLS = 1_000
_MAX_SITEMAP_DEPTH = 2

# Generic page names, in the order a customer usually needs them. A path token
# matching a group's keywords gives that page its priority. Nothing here names
# a trade, so tenant two onboards by config alone.
_PRIORITY_KEYWORDS: tuple[set[str], ...] = (
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
    "terms",
    "test",
    "tests",
    "testing",
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

_SOURCE_RANK = {"home": 0, "nav": 1, "sitemap": 2, "body": 3}

# A page's path is near-identical to one already selected when its token sets
# overlap this much under the same first segment. Cheap and conservative: the
# content-level check in extract.py is the one that catches city duplicates.
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


def page_priority(url: str) -> int:
    """The generic customer-need tier of a page, 0 (home) through 99 (other)."""
    path = urlsplit(url).path
    if path in {"", "/"}:
        return 0
    tokens = {token for token in re.split(r"[/_.-]+", path.casefold()) if token}
    for priority, keywords in enumerate(_PRIORITY_KEYWORDS, start=1):
        if tokens & keywords:
            return priority
    return 99


def is_junk(url: str) -> bool:
    """True for pages no owner wants their agent answering from."""
    path = urlsplit(url).path
    extension = path[path.rfind(".") :].lower() if "." in path.rsplit("/", 1)[-1] else ""
    if extension in _NON_PAGE_EXTENSIONS:
        return True
    segments = [segment for segment in path.casefold().split("/") if segment]
    if any(segment in _JUNK_SEGMENTS for segment in segments):
        return True
    # A slider's individual slides and a staging page's test-* variants are
    # path variants of something that should never be read.
    staging_prefixes = ("slide-", "slider-", "test-", "sample-", "demo-")
    if any(segment.startswith(staging_prefixes) for segment in segments):
        return True
    return False


def extract_links(html: bytes, base_url: str) -> tuple[list[str], list[str]]:
    """(navigation links, other body links) in document order.

    Navigation and header links come first because they are the site owner's
    own idea of what matters. Body links are a fallback for sites that never
    use those elements, not the first frontier.
    """
    tree = HTMLParser(html)
    navigation: list[str] = []
    seen_navigation: set[str] = set()
    for anchor in tree.css("nav a[href], header a[href]"):
        href = (anchor.attributes.get("href") or "").strip()
        url = normalize_url(href, base=base_url)
        if url is not None and url not in seen_navigation:
            seen_navigation.add(url)
            navigation.append(url)
    body: list[str] = []
    seen_body: set[str] = set()
    for anchor in tree.css("a[href]"):
        href = (anchor.attributes.get("href") or "").strip()
        url = normalize_url(href, base=base_url)
        if url is None or url in seen_navigation or url in seen_body:
            continue
        seen_body.add(url)
        body.append(url)
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
        containment = intersection / min(len(tokens), len(other_tokens))
        # Containment catches the city variant whose extra token would
        # otherwise dilute plain Jaccard below the threshold.
        if max(intersection / union, containment) >= _PATH_DUPLICATE_THRESHOLD:
            return True
    return False


async def discover_pages(
    url: str,
    *,
    reader: WebReader | None = None,
    max_pages: int = DEFAULT_MAX_PAGES,
) -> DiscoveryResult:
    """Discover the bounded, ranked set of pages worth reading for ``url``.

    Raises ValueError when the homepage itself is unfetchable or robots.txt
    forbids reading it - both are owner-facing fetch failures, never a crawl
    that silently returns nothing.
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
    sitemap_pages = await _sitemap_urls(reader, homepage, robots_text)

    skipped: Counter[str] = Counter()
    candidates: dict[str, DiscoveredPage] = {}

    def consider(link: str, source: str) -> None:
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
            if _SOURCE_RANK[source] < _SOURCE_RANK[existing.source]:
                candidates[normalized] = DiscoveredPage(
                    url=normalized,
                    priority=existing.priority,
                    source=source,
                )
            return
        candidates[normalized] = DiscoveredPage(
            url=normalized, priority=page_priority(normalized), source=source
        )

    consider(homepage, "home")
    for link in navigation:
        consider(link, "nav")
    for link in sitemap_pages:
        consider(link, "sitemap")
    for link in body:
        consider(link, "body")

    ranked = sorted(
        candidates.values(),
        key=lambda page: (
            page.priority,
            _SOURCE_RANK[page.source],
            urlsplit(page.url).path.count("/"),
            len(page.url),
            page.url,
        ),
    )
    selected: list[DiscoveredPage] = []
    selected_by_priority: dict[int, list[str]] = {}
    for page in ranked:
        if len(selected) >= max_pages:
            skipped["page_cap"] += 1
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
    )
