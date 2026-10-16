# Latency slice 1 - the instrument

**Status:** landed. **Branch:** `latency/slice-1-instrument`.

## What landed

- `make latency` drives one real turn through `POST /api/chat` with one model
  pinned, and writes one JSON record per turn.
- The record (`backend/app/observability/turn_record.py`) carries the 14
  required keys, emitted once per graph turn in the handler's outermost
  `finally` so `total_ms` spans the same range on success and failure.
- `usage_models` carries the model the provider response names (the **served**
  model, `backend/app/llm/openai_base.py`), not the id that was requested, so
  `model_match` is a real identity check.
- The percentile rule (linear interpolation between the two closest ranks) is
  in `backend/app/observability/percentile.py`, unit-tested.
- Per-tenant daily limits raised to 50,000,000 tokens and $50 for bytefix,
  sababa2 and northgate; sababa stays at the defaults. See
  `data/tenant-limits.md`.

## Smoke

Command: `make latency`. Model `deepseek/deepseek-v4.1-flash` on OpenRouter,
tenant bytefix. Artifact:
`data/openrouter-deepseek-v4-1-flash__bytefix.json`.

| measure | value |
|---|---|
| total_ms | 7295.1 |
| first_model_token_ms | 3792.3 |
| first_prose_ms | 7257.1 |
| buffer_hold_ms | 3464.8 |
| llm_call_count / path / route | 2 / fast / knowledge |
| input_tokens / output_tokens | 8875 / 754 |
| leg / failover_engaged | null / false |
| model_match | true |

## Probe skips

Command: `make latency LATENCY_MODELS=opencode/ling-3.1-flash-free,opencode/space-bunny-free LATENCY_TENANTS=bytefix`.

- `ling-3.1-flash-free` is absent from the Zen catalogue (46 ids, in the
  artifact).
- `space-bunny-free` is listed, but the endpoint answers `HTTP 403
  FreeTierError` (non-OpenCode clients are refused).
Artifacts: `data/opencode-*-__bytefix.json`.

## Findings

- Pass: `make latency`, lint, typecheck and the suite are green
  (`data/make-check.log`).
- `leg` is null because a run pins one leg (no failover provider);
  `usage_models` proves which model answered.
- Pre-existing: `make seed-tenant2` (northgate) fails confirm on missing
  ABN/GST; see `data/tenant-limits.md`.
- Not started: the noise floor and the matrix (the next order).
