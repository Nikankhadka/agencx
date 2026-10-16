# Latency slice 1 - the instrument

**Status:** landed. **Branch:** `latency/slice-1-instrument`.

## What landed

- `make latency` drives one real turn through `POST /api/chat` with one model
  pinned per run, and writes one JSON record per turn.
- The record (`backend/app/observability/turn_record.py`) carries the 14
  required keys. It is emitted as one structured line on the `app.latency`
  logger; the runner taps it in-process, so a turn cannot be misattributed.
- The percentile rule (linear interpolation between the two closest ranks) is
  in `backend/app/observability/percentile.py`, unit-tested in
  `backend/tests/test_percentile.py`.
- Per-tenant daily limits are raised to 50,000,000 tokens and $50 for bytefix,
  sababa2 and northgate, written by their seeds (`config.limits`). sababa is
  unchanged, by design.

## Smoke

Command: `make latency`. Model `deepseek/deepseek-v4.1-flash` on OpenRouter,
tenant bytefix.

| measure | value |
|---|---|
| total_ms | 9761.8 |
| first_model_token_ms | 4941.6 |
| first_prose_ms | 9760.9 |
| buffer_hold_ms | 4819.3 |
| llm_call_count / path / route | 2 / fast / knowledge |
| input_tokens / output_tokens | 8487 / 2119 |
| leg / failover_engaged | null / false |

Artifact: `data/openrouter-deepseek-v4-1-flash__bytefix.json` (prices fetched
live at 04:17:04Z).

Three identical runs totalled 6.1s, 10.0s and 9.8s - the spread slice 2 must
quantify before any before/after claim.

## Findings

- Pass: `make latency`, lint, typecheck and the full suite (1373 backend tests)
  are green.
- The two Zen probes cannot be exercised: the free tier rejects any non-OpenCode
  client (`FreeTierError`), and `ling-3.1-flash-free` is absent from the live
  catalogue. Recorded, not substituted.
- `leg` is null because each run pins a single leg (no failover provider is
  built); `usage_models` proves the pinned model answered.
- Pre-existing: `make seed-tenant2` (northgate) fails confirm with
  `incomplete - missing: ABN; GST registration`; northgate got its limits by an
  idempotent update instead.
