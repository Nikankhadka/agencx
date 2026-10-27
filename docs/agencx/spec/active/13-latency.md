# 13 - Latency instrument

**Status:** Merged 2026-10-23 - slices 1-6 and the burst-coalescing follow-on at
`d544ce5` (evidence tip `fcc7efa`); slice 7 deferred, waiting on a founder scope
decision.
**Phase 1 area:** Performance (post-launch).

## Objective

Measure a real customer turn from the app's own telemetry with one command
(`make latency`), so a later change is judged against a measured noise floor
instead of a guess. No prompt, route, or budget changed; the only settings moved
were the demo tenants' daily limits, raised so a matrix day would not hit them
([tenant-limits.md](../../evidence/latency-2026-10/data/tenant-limits.md)).

## Outcome

| # | Change | Verdict |
|---|---|---|
| 1 | The instrument: per-turn record, percentile math, runner, `make latency`, noise floor, model matrix | landed |
| 2 | Draft output cap (`llm_max_tokens_draft` 4096) | inert - the cap never bound |
| 3 | Drop the discarded agent call; the `search_knowledge` tool result carries the chunks | pass on the mechanism |
| 4 | Overlap the retrieval steps | pass structurally, no clock effect |
| 5 | Prompt caching, replacing the per-request spotlight nonce | cache proven, injection gate 0.967 PASS, no clock claim |
| 6 | Paid-tier A/B across the matrix | closed with no winner - too censored to rank |
| 7 | Streaming with inspection off the critical path | deferred |

Each slice has one report and its raw data under
[evidence/latency-2026-10](../../evidence/latency-2026-10/report.md); the
cross-slice package is
[report-cumulative.md](../../evidence/latency-2026-10/report-cumulative.md).

**The founder's 10% bar** is met by the coalesced burst, not by a single turn. One
combined three-question turn takes 3.4-5.7 s against 10.8-21.6 s for three serial
turns (68-77% faster), 6/6 turns completed, every question answered
([report-coalesce.md](../../evidence/latency-2026-10/report-coalesce.md)). Hybrid
provider calls fell p50 4.0 -> 3.0. There is no single-turn clock claim:
`total_ms` is noise-dominated, with the same-command p50 spanning 3977-7466 ms
across eight runs.

**Burst coalescing** (follow-on, no backend change): the composer keeps accepting
messages while a reply is in flight and sends the burst as one turn. That is a
product behavior change - one reply covering the burst instead of three.

## Noise floor

A change counts only when it beats its band on completed turns:

| Tenant | Band (ms) | Driven by |
|---|---|---|
| bytefix | 2950.80 | p50 |
| sababa2 | 2031.33 | p95 |
| sababa | 2532.65 | p50 |

Band = max over comparable run pairings of `max(|delta p50|, |delta p95|)` on
`total_ms`, over completed turns. Mechanism plausibility comes first: a change
that cannot mechanically affect timing is inert, whatever the noise did.

## Corpus

| Tenant | Vertical | Path | LLM calls |
|---|---|---|---|
| sababa2 | restaurant | fast | 2 |
| sababa | restaurant | hybrid | 4 |
| bytefix | phone repair | control | 2 |

`sababa` versus `sababa2` is a controlled A/B on the same 96-item menu.
`northgate` is limits-only: its seed path is dead on the pre-existing ABN/GST
onboarding gap, so it cannot serve a turn yet.

## Model matrix

Config: `backend/evals/latency_config.json`. Two OpenRouter candidates are
runnable; both Zen probes are blocked with recorded artifacts.

| Route | Model id | Tier | State |
|---|---|---|---|
| OpenRouter | `deepseek/deepseek-v4.1-flash` | candidate | runnable |
| OpenRouter | `inclusionai/ling-3.0-flash` | candidate | runnable |
| Zen | `opencode/ling-3.1-flash-free` | probe | blocked: absent from the live catalogue |
| Zen | `opencode/space-bunny-free` | probe | blocked: the endpoint refuses non-OpenCode clients |

Zen expects the bare id (`space-bunny-free`), which the config carries in
`api_model`.

## Rulings and close-out

- Slice 3 narrows citations to the cited chunks, internal only: the controller
  strips markers on both paths, so no chip renders either way. No fallback to all
  retrieved chunks.
- `run_gate`'s generation FAIL (-0.0311 against a 0.03 tolerance) is accepted as a
  provider level shift and closed. It is not reclassified as noise and the
  tolerance is unchanged.
- The spotlight nonce is retired for one fixed 16-hex delimiter so the prompt
  prefix is cacheable. Enforcement is `escape_delimiters` plus the standing
  instruction plus Inspection; none of the three may be weakened without
  re-running the injection gate.
- Merged with `make ci` exit 0: pytest 1514, vitest 373, ruff, the import
  contracts, `tsc`, mypy, `format-check` and the frontend build all clean. No
  migration.

## Slice 7 (deferred)

Streaming with inspection off the critical path. It needs a chunked-validation
design, a security ruling, and eval rework; it changes when a customer sees model
prose and the US-060 inspection buffer is ratified, so only a founder scope
decision reopens it.

## Evidence standard

Every number traces to the command that produced it; provider prices are read live
at run time, never copied from a config comment. One report per slice or work
item, under 300 words, beside its data.

## Instrument

Runner `backend/evals/latency_run.py`; record sink
`backend/app/observability/turn_record.py`; percentile math
`backend/app/observability/percentile.py`. Protocol follows
[Agent Conventions](../../design/conventions.md).
