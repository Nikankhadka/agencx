# 13 - Latency instrument

**Status:** In progress - slice 1 landed (instrument, noise floor, model
matrix). Slice 2 (draft output cap, 4096) measured: mechanism inert - the cap
never bound, so no latency effect is attributable. Slice 3 (drop the discarded
agent call) is recon'd (`docs/agencx/evidence/latency-2026-10/design-slice-3.md`)
and its **eval gate is now unblocked**: the provider-seam gaps that killed
generation/trajectory/injection are fixed (a fast 5xx now fails over; a
server-side `json_validate_failed` 400 resamples) - see
`docs/agencx/evidence/latency-2026-10/data/eval-blocker-diagnosis.md`. A scored
baseline run is the next order; the slice-3 implementation is untouched.
**Phase 1 area:** Performance (post-launch).
**Branch:** `latency/stack` (all slices stack here; one merge to
`development` at the end, on the founder's go).

## Objective

Measure a real customer turn's latency with one command, on the app's own
telemetry, so a later change is judged against a measured noise floor rather
than a guess. The work changes no prompt, route, or budget and leaves the
platform `DEFAULT_*` limits untouched; the only settings it moves are the demo
tenants' own daily limits, raised so a matrix day does not hit them (see
`docs/agencx/evidence/latency-2026-10/data/tenant-limits.md`).

## Protocol

All slices stack on one branch, `latency/stack`. Each slice carries its own
commits, its own test, and one measurement run at that slice's commit against
the frozen slice-1 baseline (`data/noise-run1.json`, `data/noise-run2.json`)
and its tolerance bands (`data/noise-floor.md`). A slice whose metric does not
exceed the bands is written up as no-measurable-effect - findings are recorded
pass or fail either way, never dropped. Nothing is pushed. One merge to
`development`, then `staging`, happens only when the cumulative result is
validated and the founder says go.

## Slice backlog

1. The instrument: per-turn record, percentile math, runner, `make latency`;
   DoD includes the noise floor and the model matrix - landed (instrument,
   noise floor, matrix; see
   `docs/agencx/evidence/latency-2026-10/report.md`).
2. Cap output tokens: `LLM_MAX_TOKENS_DRAFT` is 0 (uncapped); cap the draft
   prose first, and cap extract only after the schemas shrink - a reasoning
   model spends its cap on hidden thinking and dies with
   `LengthFinishReasonError`. Done: `llm_max_tokens_draft` ships at 4096
   (raised from a first 2048 that sat near the observed max); measured
   mechanism-inert - per-call output stayed under the cap, so it never
   truncated - see
   `docs/agencx/evidence/latency-2026-10/report-slice-2.md`.
3. Kill the discarded agent call (`backend/app/agents/agent_node.py:1167`):
   the hybrid path makes a call whose result is thrown away, so
   `llm_call_count` 4 to 3; the grounding/money reason the call exists for must
   be preserved. Recon (see
   `docs/agencx/evidence/latency-2026-10/design-slice-3.md`) found the loop runs
   until a round returns no tool calls - that terminal round IS the completion
   signal - and multi-round tool use is the norm on the hybrid path (4 of 5
   turns, 1 to 3 rounds; record `data/slice2-rounds.md`). Breaking after the
   first tool round would change most hybrid turns, so it is ruled out; the
   only call-saving design that preserves multi-round makes the
   `search_knowledge` tool result carry the chunks (grounding-seam change) and
   needs a scored eval.
   **Gate:** slice 3 is judged on `llm_call_count` on completed turns per
   tenant, with a band by the same documented rule over the four existing runs:
   bytefix 1.90, sababa2 0.00, sababa 0.50 - so a one-call saving is
   detectable. Timing is corroboration only (a one-call saving sits inside the
   2031-2950 ms bands), and a rise in completed turns is a second signal.
   Timeouts truncate recorded call counts (max observed 4), so the structural
   claim rests on completed turns. The measurement must also report
   `input_tokens` (a chunk-carrying tool result is re-sent each later round).
   The eval gate that blocked slice 3 is now unblocked - the provider-seam gaps
   are fixed (`data/eval-blocker-diagnosis.md`); a scored pre-slice-3 baseline
   is the next order, before the implementation.
4. Parallelize retrieval (`backend/app/retrieval/service.py:43-60`): sparse
   search needs no embedding, so embed and search can run together; a
   `search_ms` drop; watch transaction and connection semantics.
5. Prompt caching, replacing the per-request spotlight nonce - needs the
   founder's ruling; gate at no regression against injection's 0.967 (the
   founder's stated baseline - re-measure it before slice 5 gates on it).
6. Paid-tier A/B across the matrix: latency, cost, and tool-call correctness
   per model.
7. Streaming with inspection off the critical path - deferred; needs a
   chunked-validation design, a security ruling, and eval rework, and may be
   unnecessary if 2 through 6 land.

## Corpus

| Tenant | Vertical | Path (expected) | LLM calls (expected) |
|---|---|---|---|
| sababa2 | restaurant | fast | 2 |
| sababa | restaurant | hybrid | 4 |
| bytefix | phone repair | control | 2 |

`sababa` versus `sababa2` is a controlled A/B on the same 96-item menu.
`northgate` is limits-only, not a corpus tenant: its seed path is dead on the
pre-existing ABN/GST onboarding-confirm gap, so it cannot serve a real turn yet
(see `docs/agencx/evidence/latency-2026-10/data/tenant-limits.md`).

## Model matrix

The committed config is `backend/evals/latency_config.json`. At the time of
writing, two OpenRouter candidates are runnable, and both Zen probes are
blocked with recorded reasons and artifacts:

| Route | Model id | Tier | State |
|---|---|---|---|
| OpenRouter | `deepseek/deepseek-v4.1-flash` | candidate | runnable |
| OpenRouter | `inclusionai/ling-3.0-flash` | candidate | runnable |
| Zen | `opencode/ling-3.1-flash-free` | probe | blocked: absent from the live catalogue |
| Zen | `opencode/space-bunny-free` | probe | blocked: the endpoint refuses non-OpenCode clients |

The Zen rows show OpenCode's provider-namespaced id for readability; the Zen
endpoint expects the **bare** id (`space-bunny-free`), which is what the
config's `api_model` carries. See the `data/opencode-*-__bytefix.json` skip
artifacts for the exact catalogue and error.

## Open decisions

- Noise tolerance, revised and derived from four runs. The rule, verbatim:

  > band = max over the comparable run pairings (slice2-run{1,2} vs
  > noise-run{1,2}) of max(|delta p50|, |delta p95|) on `total_ms`, over
  > completed turns.

  The four runs are the two slice-1 baselines (noise-run1/2) plus slice2-run1/2;
  slice 2 counts as an unchanged-mechanism run because its output cap never
  bound. The going-forward bands, with the pairing that drives each:

  | tenant | band (ms) | driven by | completed turns (noise1/noise2/slice2run1/slice2run2) |
  |---|---|---|---|
  | bytefix | 2950.80 | p50 (3977.35 vs 6928.15) | 4/2/3/4 |
  | sababa2 | 2031.33 | p95 (5579.67 vs 7611.00) | 4/3/3/4 |
  | sababa | 2532.65 | p50 (6587.55 vs 9120.20) | 2/1/1/0 |

  A change counts as real only when it exceeds its band.
- Mechanism plausibility comes first: a slice that cannot mechanically affect a
  timing metric - for example an output cap that never binds - is judged inert
  regardless of whether the noise happened to move inside or outside the band.
- The prompt-cache tradeoff (slice 5) needs the founder's ruling first.

## Evidence standard

Every number is traceable to the command that produced it. Provider prices are
read live from the provider's models endpoint at run time and stored with the
fetch timestamp, never taken from a config comment.

## Report format

One report per slice or work item, under 300 words, beside its data.

## Instrument

The runner is `backend/evals/latency_run.py`; the record sink is
`backend/app/observability/turn_record.py`; the percentile math is
`backend/app/observability/percentile.py`. The protocol follows
[Agent Conventions](../../design/conventions.md).
