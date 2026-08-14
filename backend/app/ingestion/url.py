"""T-056: fetch a URL and extract its main text for ingestion.

Pure fetch + extract - no database access here, so the fetch/extract pieces are
unit-testable without Postgres. The HTTP fetch is deliberately minimal:

- only ``http://``/``https://`` schemes are fetched (anything else raises
  ``ValueError`` before any network I/O);
- a 10s timeout;
- a 2MB body cap (rejecting, not truncating, oversized pages);
- redirects followed, bounded by httpx's own redirect limit.

HTML extraction removes boilerplate chrome (script/style/nav/header/footer/form)
and returns the collapsed plain text of what remains, plus the page title.
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

import httpx
from selectolax.parser import HTMLParser

_TIMEOUT = httpx.Timeout(10.0)
_MAX_BODY_BYTES = 2 * 1024 * 1024

# Tag names dropped before text extraction: page chrome, never the content an
# admin wants their agent to answer from.
_REMOVED_TAGS = "script, style, noscript, nav, header, footer, form"


async def fetch_page(url: str, *, client: httpx.AsyncClient | None = None) -> bytes:
    """Fetch ``url`` and return the raw response body.

    Raises ``ValueError`` for a non-http(s) scheme or a body over 2MB. A
    caller-supplied ``client`` (e.g. a MockTransport-backed test client) is used
    as-is; otherwise a fresh client with a 10s timeout is created.
    """
    scheme = urlparse(url).scheme.lower()
    if scheme not in ("http", "https"):
        raise ValueError(f"unsupported URL scheme {scheme!r}; only http and https are allowed")
    # ponytail: the SSRF guard is the scheme allowlist only. Blocking
    # private-IP / loopback / cloud-metadata hostnames is the upgrade path if
    # this ever faces untrusted input.
    if client is None:
        async with httpx.AsyncClient(follow_redirects=True, timeout=_TIMEOUT) as owned:
            return await _get_bounded(owned, url)
    return await _get_bounded(client, url)


async def _get_bounded(client: httpx.AsyncClient, url: str) -> bytes:
    # follow_redirects and timeout are passed per-request so they hold even when
    # a caller supplies its own client.
    response = await client.get(url, follow_redirects=True, timeout=_TIMEOUT)
    body = response.content
    if len(body) > _MAX_BODY_BYTES:
        raise ValueError(f"page body exceeds the {_MAX_BODY_BYTES // (1024 * 1024)}MB fetch limit")
    return body


def extract_main_text(html: bytes) -> str:
    """Plain text of the page with script/style/nav/header/footer/form removed.

    Returns "" when nothing meaningful remains.
    """
    tree = HTMLParser(html)
    for node in tree.css(_REMOVED_TAGS):
        node.decompose()
    return re.sub(r"\s+", " ", tree.text(separator=" ", strip=True)).strip()


def extract_title(html: bytes) -> str:
    """The page's ``<title>`` text, stripped, or "" when absent."""
    node = HTMLParser(html).css_first("title")
    return node.text(strip=True) if node is not None else ""
