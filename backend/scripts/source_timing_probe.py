"""Time both halves of the onboarding source turn, old shape and new.

Ticket 29 changed what a pasted URL costs in two places: the crawl (offerings
pages first, body links before the sitemap, six concurrent reads under a 10s
deadline) and the processing that follows it (the readable-sections pass, the
offering-extraction pass and the profile read now run together instead of one
after another). ``scripts/crawl_probe.py`` measures the crawl half; this probe
measures the whole turn so the two halves can be read side by side.

Two shapes of the same source turn are measured, interleaved per run:

- ``legacy``: the pre-ticket crawl (``legacy_discovery=True``, 3 concurrent
  reads, 30s deadline) then ``structure_document``, ``extract_offerings`` and
  ``prepare_source_profile`` one after another.
- ``new``: the shipped crawl, then the shipped concurrent draft
  (``_draft_sections_and_extraction`` runs structure, offerings and the profile
  read together).

The legacy shape is a serial composition of the SAME shipped functions - it is
not an old checkout. That is the only honest way to compare them in one tree,
and it isolates exactly the composition the ticket changed.

``--provider stub`` replaces the model with a fixed sleep per call type, so the
serial sum against the longest path is provable with no model noise.
``--provider real`` uses the configured provider chain; a failed call is
recorded as ``429``, ``timeout`` or ``error:<type>`` and never lands as a fast
run.

    python -m scripts.source_timing_probe --url <url> --label <name> --runs 3 \
        --provider stub --json <path>
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import time
from collections import defaultdict
from collections.abc import AsyncIterator, Callable
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.features.knowledge.offering_extraction import ExtractedOfferings, extract_offerings
from app.features.knowledge.service import _draft_sections_and_extraction, _StageFailure
from app.features.knowledge.structuring import StructuredKnowledge, structure_document
from app.llm.dependency import get_llm_provider
from app.llm.provider import ChatMessage, LLMProvider, SchemaT, ToolSpec, ToolTurn
from app.onboarding.agent import OnboardingRecord, prepare_source_profile
from app.onboarding.flow import DraftUpdate, ProfileDraft
from app.shared.limits import DEFAULT_LLM_TIMEOUT_S, TimeLimitedProvider
from app.shared.startup import ConfigError
from scripts import crawl_probe

SHAPES = ("legacy", "new")

# The stub's fixed per-call sleeps. Structure is deliberately the slowest pass:
# the new shape's draft is then bound by it, and the serial sum is the visible
# contrast rather than two numbers that happen to be close.
STUB_STRUCTURE_MS = 1200
STUB_OFFERINGS_MS = 900
STUB_PROFILE_MS = 700

# The shipped turn's source-processing cap (controller._SOURCE_TURN_TIMEOUT_S).
# Used here only so a hung provider cannot hang the probe.
PROCESSING_TIMEOUT_S = 90.0

_CALL_KINDS: dict[type[Any], str] = {
    StructuredKnowledge: "structure",
    ExtractedOfferings: "offerings",
    DraftUpdate: "profile",
}


class StubProvider(LLMProvider):
    """Deterministic model: sleep a fixed time per call type, return valid output.

    The point is the composition, not the content. Each return value is shaped
    so the real caller accepts it: readable sections that pass the money guard,
    an empty offering list (a valid "nothing found"), and a profile with a
    single blank-filling field.
    """

    def __init__(
        self,
        *,
        structure_ms: int = STUB_STRUCTURE_MS,
        offerings_ms: int = STUB_OFFERINGS_MS,
        profile_ms: int = STUB_PROFILE_MS,
    ) -> None:
        self._delays = {
            "structure": structure_ms,
            "offerings": offerings_ms,
            "profile": profile_ms,
        }

    async def extract(
        self, *, system_prompt: str, user_input: str, schema: type[SchemaT]
    ) -> SchemaT:
        kind = _CALL_KINDS.get(schema)
        if kind is None:
            raise TypeError(f"stub provider has no output for {schema.__name__}")
        await asyncio.sleep(self._delays[kind] / 1000)
        if schema is StructuredKnowledge:
            return schema(  # type: ignore[return-value]
                business_overview=["Stub Business is a local business."],
                hours=["9am to 5pm"],
                contact=["hello@example.com"],
            )
        if schema is ExtractedOfferings:
            return schema(offerings=[])  # type: ignore[return-value]
        return schema(  # type: ignore[return-value]
            profile=ProfileDraft(
                business_name="Stub Business",
                business_type="test business",
                hours="9am to 5pm",
            )
        )

    async def chat(self, messages: list[ChatMessage]) -> str:
        raise NotImplementedError("the timing probe never chats")

    async def chat_stream(self, messages: list[ChatMessage]) -> AsyncIterator[str]:
        raise NotImplementedError("the timing probe never chats")

    async def chat_with_tools(
        self, *, messages: list[ChatMessage], tools: list[ToolSpec], tool_choice: str = "auto"
    ) -> ToolTurn:
        raise NotImplementedError("the timing probe never chats")


class TimedProvider(LLMProvider):
    """Records one duration per ``extract`` call, even when the call raises.

    The shipped draft records ``offerings_ms`` only after the structure pass is
    awaited, so under concurrency its number can absorb structure's wait. The
    probe times each call itself, which is what the composition claim needs.
    """

    def __init__(
        self,
        inner: LLMProvider,
        calls: dict[str, list[float]],
        failures: list[BaseException],
    ) -> None:
        self._inner = inner
        self._calls = calls
        self._failures = failures

    @property
    def supports_tools(self) -> bool:
        return self._inner.supports_tools

    async def extract(
        self, *, system_prompt: str, user_input: str, schema: type[SchemaT]
    ) -> SchemaT:
        kind = _CALL_KINDS.get(schema, "other")
        started = time.perf_counter()
        try:
            return await self._inner.extract(
                system_prompt=system_prompt, user_input=user_input, schema=schema
            )
        except BaseException as exc:
            self._failures.append(exc)
            raise
        finally:
            self._calls[kind].append((time.perf_counter() - started) * 1000)

    async def chat(self, messages: list[ChatMessage]) -> str:
        return await self._inner.chat(messages)

    def chat_stream(self, messages: list[ChatMessage]) -> AsyncIterator[str]:
        return self._inner.chat_stream(messages)

    async def chat_with_tools(
        self, *, messages: list[ChatMessage], tools: list[ToolSpec], tool_choice: str = "auto"
    ) -> ToolTurn:
        return await self._inner.chat_with_tools(
            messages=messages, tools=tools, tool_choice=tool_choice
        )


def _marker(exc: BaseException) -> str:
    """One failure label: 429, timeout, or the exception type."""
    text = f"{type(exc).__name__}: {exc}".casefold()
    if isinstance(exc, TimeoutError) or "timeout" in text or "timed out" in text:
        return "timeout"
    if "429" in text or "rate limit" in text or "quota" in text:
        return "429"
    return f"error:{type(exc).__name__}"


def _crawl_marker(message: str) -> str:
    """``crawl_site`` wraps every fetch failure in ValueError; keep the reason."""
    text = message.casefold()
    if "timeout" in text or "timed out" in text:
        return "timeout"
    if "429" in text or "rate limit" in text or "quota" in text:
        return "429"
    return "error:ValueError"


def _provider_factory(kind: str) -> Callable[[], LLMProvider]:
    if kind == "stub":

        def _stub() -> LLMProvider:
            return TimeLimitedProvider(StubProvider(), DEFAULT_LLM_TIMEOUT_S)

        return _stub

    def _real() -> LLMProvider:
        # A fresh chain per shape, exactly as the app builds one per turn: a
        # provider that skipped a leg on a hard 429 must not poison the next
        # shape's run.
        return TimeLimitedProvider(get_llm_provider(), DEFAULT_LLM_TIMEOUT_S)

    return _real


def _call_ms(calls: dict[str, list[float]], kind: str) -> float | None:
    values = calls.get(kind)
    return round(sum(values), 1) if values else None


def _ms(started: float) -> float:
    return round((time.perf_counter() - started) * 1000, 1)


async def _measure_legacy(text: str, timed: TimedProvider) -> tuple[dict[str, float], str | None]:
    """Pre-ticket processing: structure, then offerings, then the profile read."""
    document_started = time.perf_counter()
    await structure_document(text, provider=timed)
    await extract_offerings(text, provider=timed, document_id=uuid4())
    draft_ms = round((time.perf_counter() - document_started) * 1000, 1)
    await prepare_source_profile(record=OnboardingRecord(), text=text, provider=timed)
    return {"draft_ms": draft_ms}, None


async def _measure_new(text: str, timed: TimedProvider) -> tuple[dict[str, float], str | None]:
    """Shipped processing: the draft and the profile read run together.

    This is the controller's own composition: the document draft (which runs
    structure and offerings concurrently inside) gathered with the profile
    read, exceptions kept per branch.
    """
    record = OnboardingRecord()
    draft_wall: dict[str, float] = {}

    async def _draft() -> Any:
        started = time.perf_counter()
        try:
            return await _draft_sections_and_extraction(
                text.encode("utf-8"),
                ".txt",
                provider=timed,
                document_id=uuid4(),
            )
        finally:
            draft_wall["ms"] = round((time.perf_counter() - started) * 1000, 1)

    document, profile = await asyncio.gather(
        _draft(),
        prepare_source_profile(record=record, text=text, provider=timed),
        return_exceptions=True,
    )
    marker: str | None = None
    if isinstance(document, _StageFailure):
        marker = _marker(document.error)
    elif isinstance(document, BaseException):
        marker = _marker(document)
    elif isinstance(profile, BaseException):
        # prepare_source_profile swallows provider failures, so this is the
        # caller-side guard the controller also keeps.
        marker = _marker(profile)
    return {"draft_ms": draft_wall.get("ms", 0.0)}, marker


_MEASURE = {"legacy": _measure_legacy, "new": _measure_new}


async def _measure_shape(url: str, shape: str, provider_kind: str, run: int) -> dict[str, Any]:
    calls: dict[str, list[float]] = defaultdict(list)
    failures: list[BaseException] = []
    timed = TimedProvider(_provider_factory(provider_kind)(), calls, failures)

    shape_started = time.perf_counter()
    legacy = shape == "legacy"
    crawl, crawl_ms, crawl_error = await crawl_probe._run(url, legacy=legacy)

    row: dict[str, Any] = {
        "shape": shape,
        "run": run,
        "crawl_ms": crawl_ms,
        "pages": len(crawl.pages) if crawl is not None else 0,
        "chars": len(crawl.text) if crawl is not None else 0,
        "crawl_status": _crawl_marker(crawl_error) if crawl_error else "ok",
        "structure_ms": None,
        "offerings_ms": None,
        "profile_ms": None,
        "draft_ms": None,
        "total_ms": None,
        "status": "ok",
    }
    if crawl is None:
        row["status"] = row["crawl_status"]
        row["total_ms"] = _ms(shape_started)
        return row

    processing: dict[str, float] = {}
    marker: str | None = None
    try:
        async with asyncio.timeout(PROCESSING_TIMEOUT_S):
            processing, marker = await _MEASURE[shape](crawl.text, timed)
    except TimeoutError:
        marker = "timeout"
    except Exception as exc:
        # A failure the shipped functions let through (a rejected input, say)
        # is still a failed shape, never a silent fast one.
        marker = _marker(exc)

    row["draft_ms"] = processing.get("draft_ms")
    row["structure_ms"] = _call_ms(calls, "structure")
    row["offerings_ms"] = _call_ms(calls, "offerings")
    row["profile_ms"] = _call_ms(calls, "profile")
    if marker is None and failures:
        marker = _marker(failures[0])
    row["status"] = marker or "ok"
    row["total_ms"] = _ms(shape_started)
    return row


def _stats(values: list[float]) -> dict[str, float] | None:
    if not values:
        return None
    return {
        "median": round(statistics.median(values), 1),
        "min": round(min(values), 1),
        "max": round(max(values), 1),
    }


def _summarise(rows: list[dict[str, Any]]) -> dict[str, Any]:
    ok = [row for row in rows if row["status"] == "ok"]
    crawled = [row for row in rows if row["crawl_status"] == "ok"]
    summary: dict[str, Any] = {
        "runs": len(rows),
        "ok_runs": len(ok),
        "crawl_ok_runs": len(crawled),
        "statuses": dict(sorted((status, _count(rows, status)) for status in _statuses(rows))),
    }
    for field in ("crawl_ms", "pages", "chars"):
        summary[field] = _stats([float(row[field]) for row in crawled])
    for field in ("structure_ms", "offerings_ms", "profile_ms", "draft_ms", "total_ms"):
        summary[field] = _stats([float(row[field]) for row in ok if row[field] is not None])
    return summary


def _statuses(rows: list[dict[str, Any]]) -> set[str]:
    return {str(row["status"]) for row in rows}


def _count(rows: list[dict[str, Any]], status: str) -> int:
    return sum(1 for row in rows if row["status"] == status)


def _fmt(value: float | int | None) -> str:
    if value is None:
        return "-"
    if isinstance(value, float):
        return f"{value:.0f}"
    return str(value)


def _fmt_stats(stats: dict[str, float] | None) -> str:
    if stats is None:
        return "-"
    return f"{stats['median']:.0f}/{stats['min']:.0f}/{stats['max']:.0f}"


def _print_rows(label: str, url: str, rows: list[dict[str, Any]]) -> None:
    print(f"# {label}: {url}")
    print(
        f"{'shape':<7} {'run':>3} {'crawl_ms':>9} {'pages':>5} {'chars':>6} "
        f"{'struct':>7} {'offer':>7} {'profile':>8} {'draft':>7} {'total':>7} status"
    )
    for row in rows:
        print(
            f"{row['shape']:<7} {row['run']:>3} {_fmt(row['crawl_ms']):>9} "
            f"{_fmt(row['pages']):>5} {_fmt(row['chars']):>6} "
            f"{_fmt(row['structure_ms']):>7} {_fmt(row['offerings_ms']):>7} "
            f"{_fmt(row['profile_ms']):>8} {_fmt(row['draft_ms']):>7} "
            f"{_fmt(row['total_ms']):>7} {row['status']}"
        )


def _print_summary(label: str, summary_by_shape: dict[str, dict[str, Any]]) -> None:
    print(f"# {label} summary (median/min/max over ok runs)")
    for shape in SHAPES:
        summary = summary_by_shape[shape]
        print(
            f"{shape:<7} ok={summary['ok_runs']}/{summary['runs']} "
            f"crawl={summary['crawl_ok_runs']}/{summary['runs']} "
            f"crawl_ms={_fmt_stats(summary['crawl_ms'])} "
            f"chars={_fmt_stats(summary['chars'])} "
            f"struct={_fmt_stats(summary['structure_ms'])} "
            f"offer={_fmt_stats(summary['offerings_ms'])} "
            f"profile={_fmt_stats(summary['profile_ms'])} "
            f"draft={_fmt_stats(summary['draft_ms'])} "
            f"total={_fmt_stats(summary['total_ms'])} "
            f"status={summary['statuses']}"
        )


async def _warm(url: str) -> None:
    """Read the site once outside the measurement.

    The compose fixture is served by ``next dev``, which compiles each route on
    its first request; charging that one-off cost to whichever shape ran first
    would make the comparison meaningless. A full crawl warms every page the
    shipped selection picks, and a second attempt covers a cold compile that
    outran the shipped 10s deadline. A real site is unaffected beyond one extra
    read, which also settles DNS and TLS.
    """
    for _ in range(2):
        result, _wall_ms, _error = await crawl_probe._run(url, legacy=False)
        if result is not None:
            return


async def _measure(url: str, label: str, runs: int, provider_kind: str) -> dict[str, Any]:
    await _warm(url)
    rows: list[dict[str, Any]] = []
    for run in range(1, runs + 1):
        # Legacy first, then new, inside every run so provider drift hits both.
        for shape in SHAPES:
            rows.append(await _measure_shape(url, shape, provider_kind, run))

    summary_by_shape = {
        shape: _summarise([row for row in rows if row["shape"] == shape]) for shape in SHAPES
    }
    return {
        "label": label,
        "url": url,
        "provider": provider_kind,
        "rows": rows,
        "summary": summary_by_shape,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Time the legacy and new shapes of one onboarding source turn."
    )
    parser.add_argument("--url", required=True, help="the business URL to read")
    parser.add_argument("--label", required=True, help="a short name for the evidence row")
    parser.add_argument("--runs", type=int, default=1, help="runs per shape (interleaved)")
    parser.add_argument(
        "--provider",
        choices=("real", "stub"),
        default="real",
        help="real uses the configured chain; stub sleeps a fixed time per call type",
    )
    parser.add_argument("--json", type=Path, default=None, help="also write the payload as JSON")
    args = parser.parse_args()
    if args.runs < 1:
        parser.error("--runs must be at least 1")

    try:
        payload = asyncio.run(_measure(args.url, args.label, args.runs, args.provider))
    except ConfigError as exc:
        print(f"probe could not run: {exc}")
        return 1
    _print_rows(args.label, args.url, payload["rows"])
    _print_summary(args.label, payload["summary"])

    if args.json is not None:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    failed = any(row["status"] != "ok" for row in payload["rows"])
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
