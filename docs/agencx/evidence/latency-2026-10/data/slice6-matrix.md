# Slice 6 - paid-tier matrix (two runs, same code at `2004617`)

**Command (identical for both runs):**

```
make latency LATENCY_MODELS=all LATENCY_TENANTS=all LATENCY_TURNS=5
```

At `HEAD` `2004617` (the slice-6 cost commit). Each run wrote 12 files: the two OpenRouter candidates x three tenants (the rows below) and the two Zen probes x three tenants (canonical `opencode-*.json`, all six skipped - `ling-3.1-flash-free` and `space-bunny-free` are both absent from the live Zen catalogue, which carried 45 ids). The Zen artifacts are kept beside this file as `matrix-slice6-run{1,2}-opencode-*.json`; they are skip evidence, not matrix rows.

`all` selects all four config rows; only the two OpenRouter candidates are runnable, so only those produce turns. This is the same selector behaviour as slice 1.

**Artifact windows (UTC, from each artifact's `generated_at`):** run 1 15:30:20-15:33:04Z; run 2 15:34:06-15:38:07Z (2026-10-19). Provider prices were re-read live at run time.

`cost usd` is the cache-adjusted figure from `evals/latency_report.py`: `(input - cached) * prompt + cached * input_cache_read + output * completion`, with `cached` clamped to `input` per turn.

**Live prices per token:**

| model | prompt | completion | input_cache_read |
|---|---|---|---|
| openrouter/deepseek-v4.1-flash | 0.0000000328 | 0.00000008 | 0.0000000016 |
| openrouter/inclusionai-ling-3.0-flash | 0.000000021 | 0.000000063 | 0.0000000042 |

## Run 1

| model | tenant | path | route (completed) | turns (completed/total) | p50 total_ms | p95 total_ms | calls (all turns) | in/out tok | cache tok | cost usd (cache-adjusted) | model_match | failover |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| openrouter/deepseek-v4.1-flash | bytefix | fast | structured | 1/5 | 1999.0 | 1999.0 | [1] | 29058/581 | 22272 | 0.000305 | True | False |
| openrouter/deepseek-v4.1-flash | sababa | hybrid | - | 0/5 | - | - | [2, 3, 4] | 50959/3868 | 14336 | 0.001534 | True | False |
| openrouter/deepseek-v4.1-flash | sababa2 | fast | knowledge | 1/5 | 4557.3 | 4557.3 | [1, 2] | 69276/2130 | 12032 | 0.002067 | True | False |
| openrouter/inclusionai-ling-3.0-flash | bytefix | fast | - | 0/5 | - | - | [1] | 30512/768 | 24320 | 0.000281 | True | False |
| openrouter/inclusionai-ling-3.0-flash | sababa | hybrid | structured | 1/5 | 1113.9 | 1113.9 | [1, 2, 3] | 54836/1781 | 26112 | 0.000825 | True | False |
| openrouter/inclusionai-ling-3.0-flash | sababa2 | fast | - | 0/5 | - | - | [1] | 66549/1250 | 52992 | 0.000586 | True | False |

## Run 2

| model | tenant | path | route (completed) | turns (completed/total) | p50 total_ms | p95 total_ms | calls (all turns) | in/out tok | cache tok | cost usd (cache-adjusted) | model_match | failover |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| openrouter/deepseek-v4.1-flash | bytefix | fast | knowledge,structured | 3/5 | 7958.3 | 8406.1 | [1, 2] | 34599/2927 | 22272 | 0.000674 | True | False |
| openrouter/deepseek-v4.1-flash | sababa | hybrid | - | 0/5 | - | - | [2, 3] | 47783/2652 | 21632 | 0.001105 | True | False |
| openrouter/deepseek-v4.1-flash | sababa2 | fast | - | 0/5 | - | - | [1] | 60594/1411 | 36096 | 0.000974 | True | False |
| openrouter/inclusionai-ling-3.0-flash | bytefix | fast | - | 0/5 | - | - | [1] | 30512/901 | 30400 | 0.000187 | True | False |
| openrouter/inclusionai-ling-3.0-flash | sababa | hybrid | structured | 1/5 | 3983.5 | 3983.5 | [1, 2, 4] | 76342/1984 | 42048 | 0.001022 | True | False |
| openrouter/inclusionai-ling-3.0-flash | sababa2 | fast | - | 0/5 | - | - | [1] | 66549/1101 | 66240 | 0.000354 | True | False |

## Run 1 vs run 2

| model | tenant | completed r1 / r2 | p50 total_ms r1 / r2 | cost usd r1 / r2 | calls r1 / r2 | cache tok r1 / r2 |
|---|---|---|---|---|---|---|
| openrouter/deepseek-v4.1-flash | bytefix | 1/5 / 3/5 | 1999.0 / 7958.3 | 0.000305 / 0.000674 | [1] / [1, 2] | 22272 / 22272 |
| openrouter/deepseek-v4.1-flash | sababa | 0/5 / 0/5 | - / - | 0.001534 / 0.001105 | [2, 3, 4] / [2, 3] | 14336 / 21632 |
| openrouter/deepseek-v4.1-flash | sababa2 | 1/5 / 0/5 | 4557.3 / - | 0.002067 / 0.000974 | [1, 2] / [1] | 12032 / 36096 |
| openrouter/inclusionai-ling-3.0-flash | bytefix | 0/5 / 0/5 | - / - | 0.000281 / 0.000187 | [1] / [1] | 24320 / 30400 |
| openrouter/inclusionai-ling-3.0-flash | sababa | 1/5 / 1/5 | 1113.9 / 3983.5 | 0.000825 / 0.001022 | [1, 2, 3] / [1, 2, 4] | 26112 / 42048 |
| openrouter/inclusionai-ling-3.0-flash | sababa2 | 0/5 / 0/5 | - / - | 0.000586 / 0.000354 | [1] / [1] | 52992 / 66240 |

## Comparability notes

### Run 1

A completed turn's route varies, and a catalog-card turn (`route: structured`) answers from the inline catalog with no draft call - its `total_ms` and `buffer_hold_ms` are not comparable to a drafted-answer turn. A row's p50/p95 mixes whatever routes completed, so read the routes before comparing two models.

- openrouter/deepseek-v4.1-flash x bytefix: all 1 completed turns are card turns (route `structured`) - not comparable to a drafted-answer row.
- openrouter/deepseek-v4.1-flash x sababa: no completed turns; p50/p95 are unavailable (every turn hit the turn budget).
- openrouter/inclusionai-ling-3.0-flash x bytefix: no completed turns; p50/p95 are unavailable (every turn hit the turn budget).
- openrouter/inclusionai-ling-3.0-flash x sababa: all 1 completed turns are card turns (route `structured`) - not comparable to a drafted-answer row.
- openrouter/inclusionai-ling-3.0-flash x sababa2: no completed turns; p50/p95 are unavailable (every turn hit the turn budget).

### Run 2

A completed turn's route varies, and a catalog-card turn (`route: structured`) answers from the inline catalog with no draft call - its `total_ms` and `buffer_hold_ms` are not comparable to a drafted-answer turn. A row's p50/p95 mixes whatever routes completed, so read the routes before comparing two models.

- openrouter/deepseek-v4.1-flash x sababa: no completed turns; p50/p95 are unavailable (every turn hit the turn budget).
- openrouter/deepseek-v4.1-flash x sababa2: no completed turns; p50/p95 are unavailable (every turn hit the turn budget).
- openrouter/inclusionai-ling-3.0-flash x bytefix: no completed turns; p50/p95 are unavailable (every turn hit the turn budget).
- openrouter/inclusionai-ling-3.0-flash x sababa: all 1 completed turns are card turns (route `structured`) - not comparable to a drafted-answer row.
- openrouter/inclusionai-ling-3.0-flash x sababa2: no completed turns; p50/p95 are unavailable (every turn hit the turn budget).

## Provenance

- run 1 - openrouter/deepseek-v4.1-flash x bytefix: `make latency LATENCY_MODELS=all LATENCY_TENANTS=all LATENCY_TURNS=5` at 2026-10-19T15:30:20Z
- run 1 - openrouter/deepseek-v4.1-flash x sababa: `make latency LATENCY_MODELS=all LATENCY_TENANTS=all LATENCY_TURNS=5` at 2026-10-19T15:31:48Z
- run 1 - openrouter/deepseek-v4.1-flash x sababa2: `make latency LATENCY_MODELS=all LATENCY_TENANTS=all LATENCY_TURNS=5` at 2026-10-19T15:31:03Z
- run 1 - openrouter/inclusionai-ling-3.0-flash x bytefix: `make latency LATENCY_MODELS=all LATENCY_TENANTS=all LATENCY_TURNS=5` at 2026-10-19T15:32:39Z
- run 1 - openrouter/inclusionai-ling-3.0-flash x sababa: `make latency LATENCY_MODELS=all LATENCY_TENANTS=all LATENCY_TURNS=5` at 2026-10-19T15:33:04Z
- run 1 - openrouter/inclusionai-ling-3.0-flash x sababa2: `make latency LATENCY_MODELS=all LATENCY_TENANTS=all LATENCY_TURNS=5` at 2026-10-19T15:32:50Z
- run 2 - openrouter/deepseek-v4.1-flash x bytefix: `make latency LATENCY_MODELS=all LATENCY_TENANTS=all LATENCY_TURNS=5` at 2026-10-19T15:34:06Z
- run 2 - openrouter/deepseek-v4.1-flash x sababa: `make latency LATENCY_MODELS=all LATENCY_TENANTS=all LATENCY_TURNS=5` at 2026-10-19T15:35:35Z
- run 2 - openrouter/deepseek-v4.1-flash x sababa2: `make latency LATENCY_MODELS=all LATENCY_TENANTS=all LATENCY_TURNS=5` at 2026-10-19T15:34:44Z
- run 2 - openrouter/inclusionai-ling-3.0-flash x bytefix: `make latency LATENCY_MODELS=all LATENCY_TENANTS=all LATENCY_TURNS=5` at 2026-10-19T15:36:26Z
- run 2 - openrouter/inclusionai-ling-3.0-flash x sababa: `make latency LATENCY_MODELS=all LATENCY_TENANTS=all LATENCY_TURNS=5` at 2026-10-19T15:38:07Z
- run 2 - openrouter/inclusionai-ling-3.0-flash x sababa2: `make latency LATENCY_MODELS=all LATENCY_TENANTS=all LATENCY_TURNS=5` at 2026-10-19T15:37:16Z
Raw report stdout: `data/slice6-matrix-run1.log`, `data/slice6-matrix-run2.log`. Per-(model,tenant) artifacts: `data/matrix-slice6-run{1,2}-<slug>__<tenant>.json`.
