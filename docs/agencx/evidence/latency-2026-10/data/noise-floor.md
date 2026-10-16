# Noise floor (two runs of unchanged code)

Run 1: `make latency LATENCY_MODELS=openrouter/deepseek-v4.1-flash LATENCY_TENANTS=all LATENCY_TURNS=5`

Run 2: `make latency LATENCY_MODELS=openrouter/deepseek-v4.1-flash LATENCY_TENANTS=all LATENCY_TURNS=5`

Generated: 2026-10-16T05:24:57Z

## bytefix

| metric | run1 p50 | run1 p95 | run2 p50 | run2 p95 | abs delta p50 | abs delta p95 |
|---|---|---|---|---|---|---|
| total_ms | 3977.35 | 9194.81 | 6771.95 | 8595.66 | 2794.60 | 599.15 |
| first_model_token_ms | 1861.95 | 3048.03 | 1823.20 | 2795.92 | 38.75 | 252.11 |
| buffer_hold_ms | 2553.05 | 7588.82 | 4944.45 | 5795.09 | 2391.40 | 1793.73 |
| llm_call_count | 2.00 | 2.00 | 3.00 | 3.90 | 1.00 | 1.90 |
| tokens | 9431.00 | 10167.45 | 13276.50 | 16206.45 | 3845.50 | 6039.00 |

Completed 4/5 (run 1), 2/5 (run 2); budget/escalation turns 1 and 3. Paths ['fast'].

## sababa

| metric | run1 p50 | run1 p95 | run2 p50 | run2 p95 | abs delta p50 | abs delta p95 |
|---|---|---|---|---|---|---|
| total_ms | 6587.55 | 7804.03 | 7134.60 | 7134.60 | 547.05 | 669.43 |
| first_model_token_ms | 3152.85 | 5021.29 | 907.70 | 907.70 | 2245.15 | 4113.59 |
| buffer_hold_ms | 3430.25 | 6516.22 | 6219.30 | 6219.30 | 2789.05 | 296.91 |
| llm_call_count | 3.50 | 3.95 | 4.00 | 4.00 | 0.50 | 0.05 |
| tokens | 9855.50 | 12073.55 | 7691.00 | 7691.00 | 2164.50 | 4382.55 |

Completed 2/5 (run 1), 1/5 (run 2); budget/escalation turns 3 and 4. Paths ['hybrid'].

## sababa2

| metric | run1 p50 | run1 p95 | run2 p50 | run2 p95 | abs delta p50 | abs delta p95 |
|---|---|---|---|---|---|---|
| total_ms | 4520.55 | 5579.67 | 4946.10 | 5737.20 | 425.55 | 157.53 |
| first_model_token_ms | 2047.90 | 2669.77 | 1867.00 | 2157.25 | 180.90 | 512.52 |
| buffer_hold_ms | 2577.90 | 3089.53 | 3075.80 | 3575.21 | 497.90 | 485.68 |
| llm_call_count | 2.00 | 2.00 | 2.00 | 2.00 | 0.00 | 0.00 |
| tokens | 21714.00 | 22131.20 | 21640.00 | 21688.60 | 74.00 | 442.60 |

Completed 4/5 (run 1), 3/5 (run 2); budget/escalation turns 1 and 2. Paths ['fast'].

## Tolerance rule

Movement counts as real only when it exceeds the measured run-to-run spread. Concretely, for a metric and tenant below, the threshold is the larger of the two runs' p50 and p95 absolute deltas (the max column):

| metric | bytefix | sababa | sababa2 |
|---|---|---|---|
| total_ms | 2794.60 | 669.43 | 425.55 |
| first_model_token_ms | 252.11 | 4113.59 | 512.52 |
| buffer_hold_ms | 2391.40 | 2789.05 | 497.90 |
| llm_call_count | 1.90 | 0.50 | 0.00 |
| tokens | 6039.00 | 4382.55 | 442.60 |

A later slice's metric change on a tenant+config counts as a real improvement only when it exceeds that metric's threshold above; anything inside the band is noise and must not be claimed.
