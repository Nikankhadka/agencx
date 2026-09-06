"""T-056: fetch a URL and extract its main text for ingestion.

Pure fetch + extract - no database access here, so the fetch/extract pieces are
unit-testable without Postgres. The HTTP fetch is deliberately minimal:

- only ``http://``/``https://`` schemes are fetched (anything else raises
  ``ValueError`` before any network I/O);
- a 10s timeout;
- a 2MB body cap (rejecting, not truncating, oversized pages);
- redirects followed manually, with every hop validated and bounded;
- non-2xx responses rejected, so an error page is never ingested as content;
- DNS answers and connected peers must be globally routable and match; only
  HTML media types are accepted.

Every failure surfaces as ``ValueError`` - see ``_get_bounded``. O-7: the
message names *why*, including the HTTP status, because the one caller that
swallows it (the onboarding turn) now logs the reason instead of collapsing a
403, an empty page and a dead host into the same silence.

O-7 also sends browser-like request headers. httpx defaults to a
``python-httpx/x.y`` user agent, which a good share of real business sites -
anything behind a CDN's bot protection - answers with a 403. A small business
pasting the link to its own shop page is not a bot, and the fetch should not
look like one. This does not defeat protection that fingerprints beyond
headers; those pages still fail, and now they fail legibly.

HTML extraction removes boilerplate chrome (script/style/nav/header/footer/form)
and returns the collapsed plain text of what remains, plus the page title.
"""

from __future__ import annotations

import asyncio
import ipaddress
import re
import socket
from collections.abc import Callable, Collection, Sequence
from urllib.parse import urljoin, urlparse

import httpx
from selectolax.parser import HTMLParser

_TIMEOUT = httpx.Timeout(10.0)
_OPERATION_TIMEOUT_S = 10.0
_MAX_BODY_BYTES = 2 * 1024 * 1024
_MAX_REDIRECTS = 3

AllowedTarget = tuple[str, int]

# A current desktop Chrome string. Sent verbatim rather than built from a
# version constant: it is one literal that either matches a real browser or
# does not, and an assembled one drifts into looking synthetic.
_HEADERS = {
    "user-agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
    ),
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "accept-language": "en-AU,en;q=0.9",
}

# Tag names dropped before text extraction: page chrome, never the content an
# admin wants their agent to answer from.
_REMOVED_TAGS = "script, style, noscript, nav, header, footer, form"


def _resolve(host: str, port: int) -> list[str]:
    try:
        return list(
            {str(item[4][0]) for item in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)}
        )
    except OSError as exc:
        raise ValueError("could not read this URL (resolution failed)") from exc


def _normalize_ip(value: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address:
    address = ipaddress.ip_address(value)
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped:
        return address.ipv4_mapped
    return address


def _verify_peer(response: httpx.Response, selected: str) -> None:
    stream = response.extensions.get("network_stream")
    if stream is None:
        raise ValueError("network peer could not be verified")
    peer = stream.get_extra_info("server_addr") or stream.get_extra_info("peername")
    peer_host = peer[0] if isinstance(peer, tuple) else None
    if peer_host is None or str(_normalize_ip(peer_host)) != selected:
        raise ValueError("network peer did not match the validated address")


async def _public_addresses(
    host: str,
    port: int,
    resolver: Callable[[str, int], Sequence[str]],
    *,
    allow_private: bool = False,
) -> list[str]:
    try:
        addresses = [str(_normalize_ip(host))]
    except ValueError:
        addresses = list(await asyncio.to_thread(resolver, host, port))
    if not addresses:
        raise ValueError("URL has no usable network address")
    normalized: list[str] = []
    for value in addresses:
        try:
            address = _normalize_ip(value)
        except ValueError as exc:
            raise ValueError("URL resolved to an invalid network address") from exc
        if (not allow_private and not address.is_global) or address.is_multicast:
            raise ValueError("URL resolves to a blocked network address")
        normalized.append(str(address))
    return normalized


async def _target(
    url: str,
    resolver: Callable[[str, int], Sequence[str]],
    allowed_targets: Collection[AllowedTarget] = (),
) -> tuple[str, str, int, list[str]]:
    try:
        parsed = urlparse(url)
    except ValueError as exc:
        raise ValueError("unsupported URL; only absolute http and https URLs are allowed") from exc
    if parsed.scheme.lower() not in ("http", "https") or not parsed.hostname:
        raise ValueError("unsupported URL scheme; only absolute http and https URLs are allowed")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("URL credentials are not allowed")
    try:
        port = parsed.port or (443 if parsed.scheme.lower() == "https" else 80)
    except ValueError as exc:
        raise ValueError("URL has an invalid port") from exc
    allow_private = (parsed.hostname.casefold(), port) in allowed_targets
    if port not in (80, 443) and not allow_private:
        raise ValueError("URL port must be 80 or 443")
    addresses = await _public_addresses(
        parsed.hostname, port, resolver, allow_private=allow_private
    )
    return parsed.scheme.lower(), parsed.hostname, port, addresses


async def fetch_page(
    url: str,
    *,
    client: httpx.AsyncClient | None = None,
    resolver: Callable[[str, int], Sequence[str]] | None = None,
    allowed_targets: Collection[AllowedTarget] = (),
) -> bytes:
    """Fetch ``url`` and return the raw response body.

    Raises ``ValueError`` for a non-http(s) scheme or a body over 2MB. A
    caller-supplied ``client`` (e.g. a MockTransport-backed test client) is used
    as-is; otherwise a fresh client with a 10s timeout is created.
    """
    resolver = resolver or _resolve
    try:
        if client is None:
            async with httpx.AsyncClient(
                follow_redirects=False, timeout=_TIMEOUT, headers=_HEADERS, trust_env=False
            ) as owned:
                async with asyncio.timeout(_OPERATION_TIMEOUT_S):
                    return await _get_bounded(owned, url, resolver, allowed_targets)
        async with asyncio.timeout(_OPERATION_TIMEOUT_S):
            return await _get_bounded(client, url, resolver, allowed_targets)
    except TimeoutError as exc:
        raise ValueError("could not read this URL (timeout)") from exc


async def _get_bounded(
    client: httpx.AsyncClient,
    url: str,
    resolver: Callable[[str, int], Sequence[str]],
    allowed_targets: Collection[AllowedTarget] = (),
) -> bytes:
    current = url
    for redirect in range(_MAX_REDIRECTS + 1):
        scheme, host, port, addresses = await _target(current, resolver, allowed_targets)
        selected = addresses[0]
        parsed = urlparse(current)
        bound_netloc = f"[{selected}]:{port}" if ":" in selected else f"{selected}:{port}"
        request_url = parsed._replace(netloc=bound_netloc).geturl()
        headers = {**_HEADERS, "host": parsed.netloc, "connection": "close"}
        extensions = {"sni_hostname": host} if scheme == "https" else {}
        try:
            request = client.build_request(
                "GET",
                request_url,
                timeout=_TIMEOUT,
                headers=headers,
                extensions=extensions,
            )
            response = await client.send(request, follow_redirects=False, stream=True)
            try:
                _verify_peer(response, selected)
            except ValueError:
                await response.aclose()
                raise
            if response.status_code in {301, 302, 303, 307, 308}:
                try:
                    location = response.headers.get("location")
                    if not location:
                        raise ValueError("redirect response has no location")
                    if redirect == _MAX_REDIRECTS:
                        raise ValueError("too many redirects")
                    current = urljoin(current, location)
                finally:
                    await response.aclose()
                continue
            try:
                response.raise_for_status()
                content_type = (
                    response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
                )
                if content_type not in {"text/html", "application/xhtml+xml"}:
                    raise ValueError("URL did not return HTML")
                length = response.headers.get("content-length")
                if length is not None and (not length.isdigit() or int(length) > _MAX_BODY_BYTES):
                    raise ValueError("page body exceeds the 2MB fetch limit")
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > _MAX_BODY_BYTES:
                        raise ValueError("page body exceeds the 2MB fetch limit")
                return bytes(body)
            finally:
                await response.aclose()
        except ValueError:
            raise
        except httpx.HTTPStatusError as exc:
            raise ValueError(f"could not read this URL (HTTP {exc.response.status_code})") from exc
        except httpx.HTTPError as exc:
            raise ValueError(f"could not read this URL ({exc.__class__.__name__})") from exc
    raise ValueError("too many redirects")


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
