"""Hybrid extraction for one discovered page.

Trafilatura is the primary reader: it produces readable markdown and keeps
headings and lists. It is not enough on its own. A product grid can have its
prices stripped as boilerplate, a contact page can lose the phone number in a
sidebar, and a small business often publishes its real opening hours only in
JSON-LD. So extraction has three layers:

1. trafilatura, standard mode first and recall mode only when the standard pass
   is short or missing contact/hours;
2. inclusive selectolax text on pricing/menu pages when it retains more money
   figures than trafilatura;
3. structured facts from JSON-LD and targeted contact/hours/address blocks,
   appended under one heading.

A 200 status is not permission to ingest. CAPTCHA and bot-challenge pages are
rejected by phrase, and anything under the minimum content threshold is
rejected as too thin to teach an assistant anything.

Every function here is synchronous. Callers run them with
``asyncio.to_thread`` so trafilatura's parsing never blocks the event loop.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from urllib.parse import urlsplit

import trafilatura
from selectolax.parser import HTMLParser

from app.ingestion.url import extract_title

MIN_CONTENT_CHARS = 200
_RECALL_SHORT_STANDARD = 800
_MAX_FACT_CHARS = 1_500

_BLOCKED_PHRASES = (
    "just a moment",
    "robot challenge",
    "attention required",
    "checking your browser",
    "verify you are human",
    "verify you are a human",
    "are you a robot",
    "complete the security check",
    "enable javascript and cookies to continue",
    "needs to review the security of your connection",
    "access denied",
    "request blocked",
    "ddos protection by",
    "cf-challenge",
    "captcha",
)

_CONTACT_HOURS = re.compile(
    r"\b(?:phone|telephone|tel|call|email|e-mail|address|opening hours|hours|"
    r"monday|tuesday|wednesday|thursday|friday|saturday|sunday|mon|tue|wed|thu|fri|sat|sun)\b",
    re.IGNORECASE,
)
_CONTACT_HOURS_KEYS = (
    "contact",
    "hours",
    "opening",
    "location",
    "address",
    "find-us",
    "findus",
    "visit",
)
_PRICING_TOKENS = {
    "pricing",
    "prices",
    "price",
    "rates",
    "rate",
    "menu",
    "cost",
    "costs",
    "quote",
}
_MONEY = re.compile(
    r"(?:[$£€]\s?\d[\d,]*(?:\.\d{2})?"
    r"|\b\d[\d,]*(?:\.\d{2})?\s?(?:aud|usd|eur|gbp|dollars?)\b)",
    re.IGNORECASE,
)
_CSS_LIKE = re.compile(r"(?:^|\s)[.#]?[a-z][\w-]*\s*\{[^}]*\}", re.IGNORECASE)


class PageBlocked(ValueError):
    """A page that must never become tenant knowledge."""


@dataclass(frozen=True)
class PageExtraction:
    url: str
    title: str
    text: str
    facts: list[str]
    used_recall: bool
    used_inclusive: bool

    @property
    def chars(self) -> int:
        return len(self.text)


def _collapse(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _visible_text(html: bytes) -> str:
    tree = HTMLParser(html)
    for node in tree.css("script, style, noscript, template"):
        node.decompose()
    root = tree.body or tree.root
    return _collapse(root.text(separator=" ", strip=True)) if root is not None else ""


def detect_blocked(html: bytes) -> str | None:
    """The block reason for a CAPTCHA/bot-challenge page, or None.

    A challenge page is frequently a 200 with a title and almost no content.
    Returning a reason keeps the log diagnosable instead of collapsing every
    unreadable page into "too short".
    """
    tree = HTMLParser(html)
    title_node = tree.css_first("title")
    title = _collapse(title_node.text(strip=True)) if title_node is not None else ""
    visible = f"{title} {_visible_text(html)}".casefold()
    for phrase in _BLOCKED_PHRASES:
        if phrase in visible:
            return f"page is a bot challenge ({phrase})"
    return None


def is_pricing_page(url: str) -> bool:
    tokens = {token for token in re.split(r"[/_.-]+", urlsplit(url).path.casefold()) if token}
    return bool(tokens & _PRICING_TOKENS)


def _money_count(text: str) -> int:
    return len(_MONEY.findall(text))


def _needs_recall(text: str) -> bool:
    return len(text) < _RECALL_SHORT_STANDARD or not _CONTACT_HOURS.search(text)


def _trafilatura(html: bytes, url: str, *, recall: bool) -> str:
    try:
        return (
            trafilatura.extract(
                html,
                url=url,
                output_format="markdown",
                include_formatting=True,
                include_tables=True,
                include_links=False,
                include_comments=False,
                deduplicate=False,
                favor_recall=recall,
            )
            or ""
        ).strip()
    except Exception:  # noqa: BLE001 - extraction degrades to the inclusive pass
        return ""


def _choose_text(standard: str, recall: str) -> tuple[str, bool]:
    """Standard text unless recall genuinely recovers a thin or contactless page."""
    if not standard:
        return recall, bool(recall)
    if len(standard) < _RECALL_SHORT_STANDARD and len(recall) >= len(standard) * 1.2:
        return recall, True
    if not _CONTACT_HOURS.search(standard) and _CONTACT_HOURS.search(recall):
        if len(recall) <= max(len(standard) * 2, 2_000):
            return recall, True
    return standard, False


def inclusive_text(html: bytes) -> str:
    """Readable body text that keeps prices trafilatura may discard.

    This is deliberately a whole-body read rather than a selected-block walk:
    a product card often puts its price in a link or a span that no semantic
    selector would choose, and dropping it is exactly the failure this pass
    exists to cover. Chrome is removed first, and blank-line structure is
    preserved so the model still reads separate items as separate things.
    """
    tree = HTMLParser(html)
    for node in tree.css("script, style, noscript, template, svg, nav, header, footer, form"):
        node.decompose()
    root = tree.body or tree.root
    if root is None:
        return ""
    text = root.text(separator="\n", strip=True)
    lines = [_collapse(line) for line in text.splitlines()]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(line for line in lines if line)).strip()


def _json_objects(html: bytes) -> Iterator[dict[str, object]]:
    tree = HTMLParser(html)
    for node in tree.css('script[type="application/ld+json"]'):
        raw = node.text() or ""
        if not raw.strip():
            continue
        try:
            data: object = json.loads(raw)
        except (TypeError, ValueError):
            continue
        yield from _walk_json(data)


def _walk_json(value: object) -> Iterator[dict[str, object]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            if isinstance(child, (dict, list)):
                yield from _walk_json(child)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_json(item)


def _address_text(value: object) -> str:
    if isinstance(value, str):
        return _collapse(value)
    if not isinstance(value, dict):
        return ""
    country = value.get("addressCountry")
    if isinstance(country, dict):
        country = country.get("name") or country.get("code")
    parts = [
        value.get("streetAddress"),
        value.get("addressLocality"),
        value.get("addressRegion"),
        value.get("postalCode"),
        country,
    ]
    return _collapse(", ".join(str(part) for part in parts if part))


def _days(value: object) -> str:
    if isinstance(value, list):
        return ", ".join(str(item) for item in value)
    return str(value)


def _opening_spec(value: object) -> list[str]:
    if not isinstance(value, list):
        value = [value]
    lines: list[str] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        days = _days(item.get("dayOfWeek", "")).replace("https://schema.org/", "")
        opens = str(item.get("opens") or "").strip()
        closes = str(item.get("closes") or "").strip()
        window = f"{opens}-{closes}".strip("-")
        if days and window:
            lines.append(f"{days}: {window}")
        elif days:
            lines.append(days)
        elif window:
            lines.append(window)
    return lines


def _json_ld_facts(html: bytes) -> list[str]:
    facts: list[str] = []
    for item in _json_objects(html):
        telephone = item.get("telephone")
        if telephone:
            facts.append(f"Phone: {_collapse(str(telephone))}")
        email = item.get("email")
        if email:
            facts.append(f"Email: {_collapse(str(email).removeprefix('mailto:'))}")
        address = _address_text(item.get("address"))
        if address:
            facts.append(f"Address: {address}")
        hours = item.get("openingHours")
        if isinstance(hours, str):
            facts.append(f"Hours: {_collapse(hours)}")
        elif isinstance(hours, list):
            for value in hours:
                facts.append(f"Hours: {_collapse(str(value))}")
        for line in _opening_spec(item.get("openingHoursSpecification")):
            facts.append(f"Hours: {line}")
        price_range = item.get("priceRange")
        if price_range:
            facts.append(f"Price range: {_collapse(str(price_range))}")
        menu = item.get("menu")
        if isinstance(menu, str) and menu:
            facts.append(f"Menu: {menu}")
        elif isinstance(menu, dict):
            name = menu.get("name")
            url = menu.get("url")
            if name or url:
                facts.append(f"Menu: {_collapse(str(name or url))}")
    return facts


def _looks_like_css(text: str) -> bool:
    return bool(_CSS_LIKE.search(text)) or ("{" in text and "}" in text and ";" in text)


def _targeted_blocks(html: bytes) -> list[str]:
    """Visible contact/hours/address blocks, including a bare ``<address>``."""
    tree = HTMLParser(html)
    for node in tree.css("script, style, noscript, template, svg"):
        node.decompose()
    blocks: list[str] = []
    seen: set[str] = set()
    for node in tree.css("[id], [class], address"):
        marker = f"{node.attributes.get('id', '')} {node.attributes.get('class', '')}".casefold()
        if node.tag != "address" and not any(key in marker for key in _CONTACT_HOURS_KEYS):
            continue
        text = _collapse(node.text(separator="\n", strip=True))
        if not text or len(text) < 10 or len(text) > 600 or _looks_like_css(text):
            continue
        key = text.casefold()
        if key in seen:
            continue
        seen.add(key)
        blocks.append(text)
    total = 0
    kept: list[str] = []
    for block in blocks:
        if total + len(block) > _MAX_FACT_CHARS:
            break
        kept.append(block)
        total += len(block)
    return kept


def _dedupe_facts(facts: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    kept: list[str] = []
    for fact in facts:
        key = _collapse(fact).casefold()
        if not key or key in seen:
            continue
        seen.add(key)
        kept.append(_collapse(fact))
    return kept


def dedupe_lines(text: str, seen: set[str] | None = None) -> str:
    """Drop lines already emitted on a previous page.

    ``seen`` is threaded through the crawl so a footer repeated on every page
    costs one line, not ten. Short lines are kept: "Battery $80" is content,
    even though it is short enough to collide by accident.
    """
    seen = set() if seen is None else seen
    kept: list[str] = []
    for line in text.splitlines():
        key = _collapse(line).casefold()
        if len(key) >= 16:
            if key in seen:
                continue
            seen.add(key)
        kept.append(line)
    return "\n".join(kept).strip()


def is_near_duplicate(text: str, other: str, *, threshold: float = 0.7) -> bool:
    """Shingle/Jaccard check for two pages that say the same thing.

    Used on each page's title plus opening text, so a city landing page that
    is the same copy with the place name swapped is dropped before it spends
    budget. The sets are small (one page opening), so this is cheap.
    """

    def shingles(value: str) -> set[tuple[str, ...]]:
        words = re.findall(r"[a-z0-9$%.]+", value.casefold())
        if not words:
            return set()
        if len(words) < 3:
            return {tuple(words)}
        return {tuple(words[index : index + 3]) for index in range(len(words) - 2)}

    left, right = shingles(text), shingles(other)
    if not left or not right:
        return False
    return len(left & right) / len(left | right) >= threshold


def _compose(body: str, facts: list[str]) -> str:
    body = body.strip()
    if not facts:
        return body
    body_key = body.casefold()
    useful = [fact for fact in facts if _collapse(fact).casefold() not in body_key]
    if not useful:
        return body
    details = "\n".join(f"- {fact}" for fact in useful)
    return f"{body}\n\n## Business details\n{details}".strip()


def extract_page(html: bytes, *, url: str) -> PageExtraction:
    """Read one page into the text and facts that will be sent to the model.

    Raises PageBlocked for a challenge page or a page below the minimum content
    threshold. Synchronous on purpose; call it from a worker thread.
    """
    blocked = detect_blocked(html)
    if blocked:
        raise PageBlocked(blocked)

    heading = HTMLParser(html).css_first("h1")
    title = _collapse(extract_title(html)) or _collapse(
        heading.text(strip=True) if heading is not None else ""
    )
    standard = _trafilatura(html, url, recall=False)
    recall = _trafilatura(html, url, recall=True) if _needs_recall(standard) else ""
    body, used_recall = _choose_text(standard, recall)

    used_inclusive = False
    if is_pricing_page(url):
        inclusive = inclusive_text(html)
        if _money_count(inclusive) > _money_count(body):
            body = inclusive
            used_inclusive = True

    if not body.strip():
        body = inclusive_text(html)

    facts = _dedupe_facts([*_json_ld_facts(html), *_targeted_blocks(html)])
    text = _compose(body, facts)
    if len(_collapse(text)) < MIN_CONTENT_CHARS:
        raise PageBlocked("page had too little readable content")

    return PageExtraction(
        url=url,
        title=title or url,
        text=text,
        facts=facts,
        used_recall=used_recall,
        used_inclusive=used_inclusive,
    )
