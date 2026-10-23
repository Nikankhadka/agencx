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
DEFAULT_CONCURRENCY = 3
DEFAULT_TIMEOUT_S = 30.0
_PAGE_MAX_CHARS = 4_000
_PRICING_PAGE_MAX_CHARS = 6_000
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
            url=normalized,
            priority=0 if normalized == homepage else page_priority(normalized),
            source=source,
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


async def crawl_site(
    url: str,
    *,
    reader: WebReader | None = None,
    max_pages: int = DEFAULT_MAX_PAGES,
    max_chars: int = DEFAULT_MAX_CHARS,
    concurrency: int = DEFAULT_CONCURRENCY,
    timeout_s: float = DEFAULT_TIMEOUT_S,
) -> CrawlResult:
    """Read a bounded set of pages and combine them into one model-sized document.

    At most ``concurrency`` pages are fetched and extracted at once, each page
    is capped (6,000 chars for pricing/menu, 4,000 otherwise), repeated lines
    are removed across pages, and the combined text never exceeds
    ``max_chars``. The total crawl has a hard deadline so an owner's turn can
    never hang on a slow site.

    Raises ValueError when no page produced readable content.
    """
    reader = reader or HttpReader()
    loop = asyncio.get_running_loop()
    started = loop.time()
    try:
        async with asyncio.timeout(timeout_s):
            discovery = await discover_pages(url, reader=reader, max_pages=max_pages)
    except TimeoutError as exc:
        raise ValueError("could not read this URL (timeout)") from exc

    skipped: Counter[str] = Counter(discovery.skipped)
    semaphore = asyncio.Semaphore(max(1, concurrency))

    async def read(page: DiscoveredPage) -> PageExtraction:
        async with semaphore:
            html = (
                discovery.homepage_html
                if page.url == discovery.homepage
                else await reader.read(page.url)
            )
            return await asyncio.to_thread(extract_page, html, url=page.url)

    tasks = {page.url: asyncio.create_task(read(page)) for page in discovery.pages}
    remaining_s = max(0.1, timeout_s - (loop.time() - started))
    done, pending = await asyncio.wait(tasks.values(), timeout=remaining_s)
    timed_out = bool(pending)
    if pending:
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
        skipped["timeout"] += len(pending)

    extracted: dict[str, PageExtraction] = {}
    for page in discovery.pages:
        task = tasks[page.url]
        if task not in done:
            continue
        try:
            extracted[page.url] = task.result()
        except PageBlocked as exc:
            skipped["blocked"] += 1
            logger.info("crawl page blocked url=%s reason=%s", page.url, exc)
        except ValueError as exc:
            skipped["fetch_failed"] += 1
            logger.info("crawl page unreadable url=%s reason=%s", page.url, exc)
        except Exception:  # noqa: BLE001 - one bad page must not lose the site
            skipped["extract_failed"] += 1
            logger.exception("crawl page extraction failed url=%s", page.url)

    parts: list[str] = []
    used = 0
    pages: list[CrawledPage] = []
    seen_lines: set[str] = set()
    fingerprints: list[str] = []
    homepage_title = ""
    for page in discovery.pages:
        extraction = extracted.get(page.url)
        if extraction is None:
            continue
        if page.url == discovery.homepage:
            homepage_title = extraction.title
        opening = f"{extraction.title}\n{extraction.text[:600]}"
        if any(is_near_duplicate(opening, other) for other in fingerprints):
            skipped["duplicate_content"] += 1
            continue
        fingerprints.append(opening)
        body = dedupe_lines(extraction.text, seen_lines)
        if not body.strip():
            skipped["empty"] += 1
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
            skipped["budget"] += 1
            continue
        used += len(section) + (2 if parts else 0)
        parts.append(section)
        pages.append(CrawledPage(url=page.url, title=extraction.title, chars=len(body)))

    if not parts:
        raise ValueError("no extractable content at this URL")

    text = "\n\n".join(parts)
    # The budget is applied before the model calls; this assertion is the
    # invariant, not an estimate.
    if len(text) > max_chars:
        text = _truncate(text, max_chars)
    title = homepage_title or pages[0].title
    logger.debug("site crawl pages=%s", [page.url for page in pages])
    logger.info(
        "site crawl homepage=%s pages_discovered=%d pages_selected=%d pages_read=%d "
        "pages_skipped=%d blocked=%d robots_skipped=%d chars=%d timed_out=%s reasons=%s",
        discovery.homepage,
        discovery.considered,
        len(discovery.pages),
        len(pages),
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
        pages=pages,
        discovered=discovery.considered,
        selected=len(discovery.pages),
        skipped=dict(skipped),
        timed_out=timed_out,
    )
