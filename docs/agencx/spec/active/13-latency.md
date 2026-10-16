# 13 - Latency instrument

**Status:** In progress - slice 1 of 7.
**Phase 1 area:** Performance (post-launch).
**Branch:** `latency/slice-1-instrument` off `development`.

## Objective

Measure a real customer turn's latency with one command, on the app's own
telemetry, so a later change is judged against a measured noise floor rather
than a guess. This slice builds the instrument and changes no prompt, route, or
budget.

## Protocol

Each slice gets its own branch off `development`. A slice is validated when its
own test passes and its target metric beats the measured noise floor. A
validated slice merges to `development`, then `staging`. Every slice is written
up, pass or fail, in the evidence folder.

## Slice backlog

1. The instrument: per-turn record, percentile math, runner, `make latency` - landed.
2. Noise floor: two runs of unchanged code, per-metric variance - next.
3. Four-model matrix: one comparison table - next.
4. Faster route and retrieval steps - later.
5. Prompt-cache tradeoff - needs the founder's ruling first.
6. Evidence: JSON plus markdown under `docs/agencx/evidence/latency-2026-10/` - structure landed.
7. Lint, typecheck, and tests green - landed.

## Corpus

| Tenant | Vertical | Path (expected) | LLM calls (expected) |
|---|---|---|---|
| bytefix | phone repair | fast | 2 |
| sababa2 | restaurant | fast | 2 |
| sababa | restaurant | hybrid | 4 |
| northgate | dental | fast | 2 |

`sababa` versus `sababa2` is a controlled A/B on the same 96-item menu.

## Model matrix

| Route | Base URL | Model id | Key env var | Tier |
|---|---|---|---|---|
| OpenRouter | `https://openrouter.ai/api/v1` | `deepseek/deepseek-v4.1-flash` | `OPENROUTER_API_KEY` | candidate |
| OpenRouter | `https://openrouter.ai/api/v1` | `inclusionai/ling-3.0-flash` | `OPENROUTER_API_KEY` | candidate |
| Zen | `https://opencode.ai/inference/openai/v1` | `opencode/ling-3.1-flash-free` | `OPENCODE_ZEN_API_KEY` | probe |
| Zen | `https://opencode.ai/inference/openai/v1` | `opencode/space-bunny-free` | `OPENCODE_ZEN_API_KEY` | probe, never a candidate |

The committed config is `backend/evals/latency_config.json`.

## Open decisions

- The noise tolerance is set from slice 2's measured floor.
- The prompt-cache tradeoff needs the founder's ruling before slice 5.

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
