# Latency slice 1 - instrument and campaign

**Status:** slice 1 done (instrument, noise floor, model matrix).
**Branch:** `latency/slice-1-instrument`.

## Instrument

`make latency` drives a fixed message set through the real chat surface with one
model pinned, writing the 14-key per-turn record; `backend/evals/latency_run.py`
runs it and `backend/evals/latency_report.py` tabulates it. Costs price by the
configured id.

## Noise floor

Two back-to-back runs, `deepseek/deepseek-v4.1-flash`, three tenants, five fixed
messages each. Data `data/noise-run1.json`, `data/noise-run2.json`; table
`data/noise-floor.md`.

- total_ms p50, run 1 to run 2: bytefix 3977 to 6772, sababa 6588 to 7135,
  sababa2 4521 to 4946.
- Cross-run delta (larger of p50 and p95): bytefix
  2794.6 ms, sababa 669.4 ms, sababa2 425.6 ms.
- **Tolerance rule:** a later change counts as real only when it exceeds these
  per-tenant bands; anything inside is noise, and single-run before/after
  claims are untrustworthy.
- Budget/escalation turns, flagged not averaged: 5 of 15 (run 1), 9 of 15 (run
  2).

## Matrix

Two candidates are runnable and both Zen probes are blocked
(`data/opencode-*-__bytefix.json`). Full table: `data/matrix.md`.

- deepseek: 4 of 5 completed on bytefix (p50 3977 ms) and sababa2 (4521 ms), 2
  of 5 on sababa (hybrid, 6588 ms).
- inclusionai/ling-3.0-flash: 0 of 5 on both fast tenants (every turn hit the
  10s budget); its 3 sababa completions are all catalog-card turns (route
  `structured`, buffer_hold_ms about 1 ms), so that p50 is not comparable to
  deepseek's drafted-answer turns, and its 2 sababa budget turns were
  conversation and recommendation routes.
- `model_match` true and `failover_engaged` false on every row; cost
  $0.0007 to $0.006 per five turns.

## Headline A/B (deepseek, same 96-item menu)

sababa2 (fast) p50 4521 ms, 4 of 5 completed; sababa (hybrid) p50 6588 ms, 2 of
5. The fast path is faster and far more reliable, but neither meets the 4s
first-token promise.
