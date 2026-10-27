"""Compare the pre-29 crawl with the source-first crawl on one URL.

Ticket 29 changed what a pasted URL costs: offerings pages rank first, body
links are considered before the sitemap, the sitemap is only fetched when
nothing in the menu sells, and six page reads run at once under a 10s deadline.
This probe runs the same URL through both selections so the evidence table in
``docs/agencx/evidence/onboarding-source-2026-10/`` compares like with like.

    python -m scripts.crawl_probe --url <url> --label <name> [--json <path>]

The legacy run is the pre-ticket shape - eager sitemap, sitemap before body,
path-only priorities, 3 concurrent reads, 30s deadline. The new run uses the
shipped defaults. "Overlap" is how much of the legacy crawl's priced material
the new crawl still carries: the offering name before the price on each
price-bearing line of the legacy text, counted when that name survives in the
new text. It is a coverage proxy, not a model judgement - the model-backed
coverage check lives in the eval gate.

Run it from the backend container:

    docker compose run --rm backend python -m scripts.crawl_probe \
        --url http://frontend:3000/fixtures/example-business.html --label fixture
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import time
from pathlib import Path
from typing import Any

from app.features.knowledge.service import _url_fetch_allowlist
from app.ingestion.site import CrawlResult, HttpReader, crawl_site

# The pre-29 budget, pinned here rather than in the crawl module so the shipped
# defaults stay the shipped defaults.
LEGACY_CONCURRENCY = 3
LEGACY_TIMEOUT_S = 30.0

_PRICE = re.compile(r"[$£€]\s?\d")


def _unwrap(raw: str) -> str:
    return " ".join(raw.split())


def _offering_names(text: str) -> list[str]:
    """Offering names as written before a price, in document order.

    A price-bearing line is the only place a static crawl knows an offering was
    named: ``Battery replacement $49`` reads as the offering, the price, and
    nothing else. Long prose lines and the crawl's own headings are ignored.
    """
    names: list[str] = []
    for line in text.splitlines():
        collapsed = _unwrap(line)
        if not _PRICE.search(collapsed) or len(collapsed) > 120:
            continue
        name = _unwrap(_PRICE.split(collapsed)[0]).strip(" -:.,|")
        if len(name) < 3 or not any(char.isalpha() for char in name):
            continue
        if name not in names:
            names.append(name)
    return names


def _overlap(legacy_text: str, new_text: str) -> tuple[int, int]:
    """(names the new crawl kept, names the legacy crawl named)."""
    names = _offering_names(legacy_text)
    haystack = _unwrap(new_text).casefold()
    found = sum(1 for name in names if _unwrap(name).casefold() in haystack)
    return found, len(names)


async def _run(url: str, *, legacy: bool) -> tuple[CrawlResult | None, int, str | None]:
    reader = HttpReader(allowed_targets=_url_fetch_allowlist())
    budget: dict[str, Any] = (
        {"concurrency": LEGACY_CONCURRENCY, "timeout_s": LEGACY_TIMEOUT_S} if legacy else {}
    )
    started = time.perf_counter()
    try:
        result = await crawl_site(url, reader=reader, legacy_discovery=legacy, **budget)
    except ValueError as exc:
        return None, _elapsed_ms(started), str(exc)
    return result, _elapsed_ms(started), None


def _elapsed_ms(started: float) -> int:
    return int(round((time.perf_counter() - started) * 1000))


def _summary(result: CrawlResult | None, wall_ms: int, error: str | None) -> dict[str, Any]:
    if result is None:
        return {
            "pages": 0,
            "chars": 0,
            "wall_ms": wall_ms,
            "timed_out": False,
            "skipped": {},
            "error": error,
        }
    return {
        "pages": len(result.pages),
        "chars": len(result.text),
        "wall_ms": wall_ms,
        "timed_out": result.timed_out,
        "skipped": dict(sorted(result.skipped.items())),
        "error": error,
    }


def _skipped_text(skipped: dict[str, int]) -> str:
    return ",".join(f"{reason}={count}" for reason, count in skipped.items()) or "-"


def _print_rows(label: str, url: str, legacy: dict[str, Any], new: dict[str, Any]) -> None:
    overlap = f"{new['overlap_found']}/{new['overlap_total']}"
    rows = [
        (label, "legacy", legacy, "-"),
        (label, "new", new, overlap),
    ]
    print(f"# {url}")
    print(
        f"{'label':<16} {'mode':<7} {'pages':>5} {'chars':>6} {'ms':>6} {'timeout':>7} "
        f"{'skipped':<28} overlap"
    )
    for row_label, mode, row, overlap_text in rows:
        print(
            f"{row_label:<16} {mode:<7} {row['pages']:>5} {row['chars']:>6} "
            f"{row['wall_ms']:>6} {str(row['timed_out']):<7} "
            f"{_skipped_text(row['skipped']):<28} {overlap_text}"
        )
        if row.get("error"):
            print(f"{'':<16} {mode:<7} error: {row['error']}")


async def _warm(url: str) -> None:
    """Read the URL once outside the measurement.

    The compose fixture is served by ``next dev``, which compiles a route on its
    first request; charging that one-off cost to whichever mode runs first would
    make the comparison meaningless. A real site is unaffected.
    """
    reader = HttpReader(allowed_targets=_url_fetch_allowlist())
    try:
        await reader.read(url)
    except ValueError:
        return


async def _measure(url: str, label: str) -> dict[str, Any]:
    await _warm(url)
    legacy_result, legacy_ms, legacy_error = await _run(url, legacy=True)
    new_result, new_ms, new_error = await _run(url, legacy=False)

    legacy_text = legacy_result.text if legacy_result is not None else ""
    new_text = new_result.text if new_result is not None else ""
    found, total = _overlap(legacy_text, new_text)

    legacy = _summary(legacy_result, legacy_ms, legacy_error)
    new = _summary(new_result, new_ms, new_error)
    new["overlap_found"] = found
    new["overlap_total"] = total
    return {"label": label, "url": url, "legacy": legacy, "new": new}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compare the pre-29 crawl with the source-first crawl on one URL."
    )
    parser.add_argument("--url", required=True, help="the business URL to read")
    parser.add_argument("--label", required=True, help="a short name for the evidence row")
    parser.add_argument("--json", type=Path, default=None, help="also write the row as JSON")
    args = parser.parse_args()

    payload = asyncio.run(_measure(args.url, args.label))
    _print_rows(args.label, args.url, payload["legacy"], payload["new"])

    if args.json is not None:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    failed = payload["legacy"].get("error") or payload["new"].get("error")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
