# 13 - Latency instrument

**Status:** In progress - slice 1 landed (instrument, noise floor, model
matrix). Slices 2 through 7 not started.
**Phase 1 area:** Performance (post-launch).
**Branch:** `latency/slice-1-instrument` off `development`.

## Objective

Measure a real customer turn's latency with one command, on the app's own
telemetry, so a later change is judged against a measured noise floor rather
than a guess. The work changes no prompt, route, or budget and leaves the
platform `DEFAULT_*` limits untouched; the only settings it moves are the demo
tenants' own daily limits, raised so a matrix day does not hit them (see
`docs/agencx/evidence/latency-2026-10/data/tenant-limits.md`).

## Protocol

Each slice gets its own branch off `development`. A slice is validated when its
own test passes and its target metric beats the measured noise floor. A
validated slice merges to `development`, then `staging`. Every slice is written
up, pass or fail, in the evidence folder.

## Slice backlog

1. The instrument: per-turn record, percentile math, runner, `make latency`;
   DoD includes the noise floor and the model matrix - landed (instrument,
   noise floor, matrix; see
   `docs/agencx/evidence/latency-2026-10/report.md`).
2. Cap output tokens: `LLM_MAX_TOKENS_DRAFT` is 0 (uncapped); cap the draft
   prose first, and cap extract only after the schemas shrink - a reasoning
   model spends its cap on hidden thinking and dies with
   `LengthFinishReasonError`.
3. Kill the discarded agent call (`backend/app/agents/agent_node.py:1167`):
   the hybrid path makes a call whose result is thrown away, so
   `llm_call_count` 4 to 3; the grounding/money reason the call exists for must
   be preserved.
4. Parallelize retrieval (`backend/app/retrieval/service.py:43-60`): sparse
   search needs no embedding, so embed and search can run together; a
   `search_ms` drop; watch transaction and connection semantics.
5. Prompt caching, replacing the per-request spotlight nonce - needs the
   founder's ruling; gate at no regression against injection's 0.967.
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

- The noise tolerance is set from the measured floor (`data/noise-floor.md`):
  a change counts as real only when it exceeds the per-tenant run-to-run band
  for that metric - for example 2.8s on bytefix `total_ms`. The bands are wide,
  so slices 2 through 6 need repeats, not single runs, to clear them.
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
