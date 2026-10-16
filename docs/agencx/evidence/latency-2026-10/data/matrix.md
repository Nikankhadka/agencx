# Model matrix (one row per model x tenant)

Generated: 2026-10-16T05:24:57Z. Percentiles are over completed turns only; `budget` turns are the turn-budget (or pre-draft escalation) count, and the calls column is the set over all turns.

| model | tenant | path (obs) | exp path | turns | budget | p50 total_ms | p95 total_ms | p50 first_tok | p50 buffer | calls (all turns) | exp calls | in/out tok | cost usd | model_match | failover |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| openrouter/deepseek-v4.1-flash | bytefix | fast | fast | 5 | 1 | 3977.3 | 9194.8 | 1862.0 | 2553.1 | [1, 2] | 2 | 37262/3974 | 0.004142 | True | False |
| openrouter/deepseek-v4.1-flash | sababa | hybrid | hybrid | 5 | 3 | 6587.5 | 7804.0 | 3152.8 | 3430.3 | [3, 4] | 4 | 51430/3348 | 0.004211 | True | False |
| openrouter/deepseek-v4.1-flash | sababa2 | fast | fast | 5 | 1 | 4520.6 | 5579.7 | 2047.9 | 2577.9 | [1, 2] | 2 | 95583/3355 | 0.005805 | True | False |
| openrouter/inclusionai-ling-3.0-flash | bytefix | fast | fast | 5 | 5 | - | - | - | - | [1] | 2 | 30455/753 | 0.000687 | True | False |
| openrouter/inclusionai-ling-3.0-flash | sababa | hybrid | hybrid | 5 | 2 | 2431.3 | 3191.9 | 2425.6 | 1.1 | [1, 2, 3, 4] | 4 | 39902/851 | 0.000892 | True | False |
| openrouter/inclusionai-ling-3.0-flash | sababa2 | fast | fast | 5 | 5 | - | - | - | - | [1] | 2 | 66339/968 | 0.001454 | True | False |

## Comparability note

A completed turn's route varies, and a catalog-card turn (`route: structured`) answers from the inline catalog with no draft call - its `total_ms` and `buffer_hold_ms` are not comparable to a drafted-answer turn. A row's p50/p95 mixes whatever routes completed, so read the routes before comparing two models.

- openrouter/inclusionai-ling-3.0-flash x bytefix: no completed turns; p50/p95 are unavailable (every turn hit the turn budget).
- openrouter/inclusionai-ling-3.0-flash x sababa: all 3 completed turns are card turns (route `structured`) - not comparable to a drafted-answer row.
- openrouter/inclusionai-ling-3.0-flash x sababa2: no completed turns; p50/p95 are unavailable (every turn hit the turn budget).

## Provenance

- openrouter/deepseek-v4.1-flash x bytefix: `make latency LATENCY_MODELS=openrouter/deepseek-v4.1-flash LATENCY_TENANTS=all LATENCY_TURNS=5` at 2026-10-16T05:24:57Z
- openrouter/deepseek-v4.1-flash x sababa: `make latency LATENCY_MODELS=openrouter/deepseek-v4.1-flash LATENCY_TENANTS=all LATENCY_TURNS=5` at 2026-10-16T05:25:57Z
- openrouter/deepseek-v4.1-flash x sababa2: `make latency LATENCY_MODELS=openrouter/deepseek-v4.1-flash LATENCY_TENANTS=all LATENCY_TURNS=5` at 2026-10-16T05:25:29Z
- openrouter/inclusionai-ling-3.0-flash x bytefix: `make latency LATENCY_MODELS=openrouter/inclusionai-ling-3.0-flash LATENCY_TENANTS=all LATENCY_TURNS=5` at 2026-10-16T05:29:55Z
- openrouter/inclusionai-ling-3.0-flash x sababa: `make latency LATENCY_MODELS=openrouter/inclusionai-ling-3.0-flash LATENCY_TENANTS=all LATENCY_TURNS=5` at 2026-10-16T05:31:37Z
- openrouter/inclusionai-ling-3.0-flash x sababa2: `make latency LATENCY_MODELS=openrouter/inclusionai-ling-3.0-flash LATENCY_TENANTS=all LATENCY_TURNS=5` at 2026-10-16T05:30:46Z
