# Latency slice 1 - instrument and campaign

**Status:** slice 1 done to its DoD (instrument, noise floor, model matrix).
**Branch:** `latency/slice-1-instrument`.

## Instrument

`make latency` drives a fixed message set through the real chat surface with one
model pinned and writes the 14-key per-turn record
(`backend/app/observability/turn_record.py`); `backend/evals/latency_run.py`
runs it and `backend/evals/latency_report.py` tabulates it. Costs price by the
configured id (`backend/app/observability/cost.py`).

## Noise floor

Two back-to-back runs, `deepseek/deepseek-v4.1-flash`, three tenants, five fixed
messages each. Data `data/noise-run1.json`, `data/noise-run2.json`; table
`data/noise-floor.md`.

- total_ms p50, run 1 to run 2: bytefix 3977 to 6772, sababa 6588 to 7135,
  sababa2 4521 to 4946.
- Cross-run absolute delta (larger of the p50 and p95 deltas): bytefix
  2794.6 ms, sababa 669.4 ms, sababa2 425.6 ms.
- **Tolerance rule:** a later change counts as real only when it exceeds these
  per-tenant bands; anything inside is noise. The bands are wide, so a
  single-run before/after claim is untrustworthy on this stack.
- Budget/escalation turns, flagged not averaged: 6 of 15 (run 1), 9 of 15 (run
  2).

## Matrix

Two candidates are runnable and both Zen probes are blocked
(`data/opencode-*-__bytefix.json`). Full table: `data/matrix.md`.

- deepseek: completed 4 of 5 (bytefix, p50 3977 ms), 4 of 5 (sababa2, 4521 ms),
  2 of 5 (sababa, hybrid, 6588 ms).
- inclusionai/ling-3.0-flash: 0 of 5 on both fast tenants (every turn hit the
  10s turn budget), 3 of 5 on sababa.
- `model_match` true and `failover_engaged` false on every row; cost
  $0.0007 to $0.006 per five turns.

## Headline A/B (deepseek, same 96-item menu)

sababa2 (fast) p50 4521 ms, 4 of 5 completed; sababa (hybrid) p50 6588 ms, 2 of
5. The fast path is both faster and far more reliable, but neither path meets
the 4s first-token promise on this stack.
