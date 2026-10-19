# Slice 5 - prompt-cache evidence (stable prefix)

**Change:** slice 5 replaces the per-request spotlight nonce with a stable fixed token so the prompt prefix is byte-identical across calls and the provider can serve it from its prompt cache. Commits `7613091` (the change) and `d99ca54` (review fixes, the measured tip). **Both runs below are at `d99ca54`.**

**Command (both runs):**

```
make latency LATENCY_MODELS=openrouter/deepseek-v4.1-flash LATENCY_TENANTS=all LATENCY_TURNS=5
```

**Bundles:** `data/slice5-run1.json`, `data/slice5-run2.json` (each `{run, command, artifacts}` - the three per-(model,tenant) artifacts). Raw `make latency` stdout: `data/slice5-run{1,2}.log`.

**Generated at (UTC):** run1 12:55:05 - 12:56:34; run2 12:58:34 - 13:00:08 (2026-10-19). Model `deepseek/deepseek-v4.1-flash`, present in the live catalogue (469 models); OpenRouter live pricing prompt `0.0000000376`, completion `0.00000008`, `input_cache_read` `0.0000000016` per token (re-read at run time, hence not the slice-4 values).

`cached_input_tokens` is the turn's total provider prompt-cache reads, a **subset** of `input_tokens` (slice 5 adds it to the record; it is observability, not an extra input count). A turn with no prose (`first_prose_ms` null) is a budget/escalation turn; only completed turns feed the p50s.

## slice5-run1

| tenant | turn | cached_in | input | calls | total_ms | route | path | completed |
|---|---|---|---|---|---|---|---|---|
| bytefix | 1 | 0 | 5810 | 1 | 10007.5 | knowledge | fast | no (budget) |
| bytefix | 2 | 0 | 5811 | 1 | 10004.9 | knowledge | fast | no (budget) |
| bytefix | 3 | 0 | 5813 | 1 | 10006.6 | knowledge | fast | no (budget) |
| bytefix | 4 | 0 | 8991 | 2 | 3167.6 | knowledge | fast | yes |
| bytefix | 5 | 5376 | 5811 | 1 | 10005.6 | knowledge | fast | no (budget) |
| sababa2 | 1 | 0 | 12124 | 1 | 10005.7 | knowledge | fast | no (budget) |
| sababa2 | 2 | 0 | 12103 | 1 | 10008.0 | knowledge | fast | no (budget) |
| sababa2 | 3 | 256 | 20764 | 2 | 3173.4 | knowledge | fast | yes |
| sababa2 | 4 | 0 | 12123 | 1 | 10016.8 | knowledge | fast | no (budget) |
| sababa2 | 5 | 12032 | 12122 | 1 | 10007.8 | knowledge | fast | no (budget) |
| sababa | 1 | 0 | 3469 | 1 | 10008.8 | None | hybrid | no (budget) |
| sababa | 2 | 3456 | 11144 | 2 | 10007.3 | knowledge | hybrid | no (budget) |
| sababa | 3 | 4480 | 5337 | 3 | 10006.7 | conversation | hybrid | no (budget) |
| sababa | 4 | 0 | 11664 | 2 | 10004.9 | recommendation | hybrid | no (budget) |
| sababa | 5 | 3456 | 7798 | 2 | 10009.6 | recommendation | hybrid | no (budget) |

## slice5-run2

| tenant | turn | cached_in | input | calls | total_ms | route | path | completed |
|---|---|---|---|---|---|---|---|---|
| bytefix | 1 | 5760 | 5810 | 1 | 10025.3 | knowledge | fast | no (budget) |
| bytefix | 2 | 5760 | 8985 | 2 | 9945.0 | knowledge | fast | yes |
| bytefix | 3 | 5376 | 5813 | 1 | 10006.4 | knowledge | fast | no (budget) |
| bytefix | 4 | 5632 | 8590 | 2 | 8993.4 | knowledge | fast | yes |
| bytefix | 5 | 5376 | 5811 | 1 | 10006.8 | knowledge | fast | no (budget) |
| sababa2 | 1 | 12032 | 12124 | 1 | 10005.3 | knowledge | fast | no (budget) |
| sababa2 | 2 | 12288 | 30858 | 3 | 10008.5 | knowledge | fast | no (budget) |
| sababa2 | 3 | 12288 | 20775 | 2 | 4729.0 | knowledge | fast | yes |
| sababa2 | 4 | 12032 | 12123 | 1 | 10008.0 | knowledge | fast | no (budget) |
| sababa2 | 5 | 12032 | 20784 | 2 | 7146.1 | knowledge | fast | yes |
| sababa | 1 | 0 | 3469 | 1 | 10006.8 | None | hybrid | no (budget) |
| sababa | 2 | 6912 | 11138 | 2 | 10006.3 | knowledge | hybrid | no (budget) |
| sababa | 3 | 3456 | 3467 | 1 | 10005.7 | conversation | hybrid | no (budget) |
| sababa | 4 | 3328 | 11673 | 2 | 10007.7 | recommendation | hybrid | no (budget) |
| sababa | 5 | 6912 | 7799 | 2 | 10008.0 | recommendation | hybrid | no (budget) |

## p50 per tenant vs the slice-4 bands

Bands (slice-4, `data/cumulative.md`): `total_ms` binary/tri 2950.8 (bytefix), 2031.3 (sababa2), 2532.65 (sababa); `llm_call_count` 1.90 / 0.00 / 0.50. p50 over **completed** turns only.

| tenant | completed r1 / r2 | p50 total_ms r1 | p50 total_ms r2 | band (ms) | delta r1 | delta r2 | p50 calls r1 | p50 calls r2 | call band |
|---|---|---|---|---|---|---|---|---|---|
| bytefix | 1 / 2 | 3167.6 | 9469.2 | 2950.8 | +216.8 | +6518.4 | 2.00 | 2.00 | 1.90 |
| sababa2 | 1 / 2 | 3173.4 | 5937.6 | 2031.3 | +1142.1 | +3906.2 | 2.00 | 2.00 | 0.00 |
| sababa | 0 / 0 | - | - | 2532.65 | - | - | - | - | 0.50 |

## Cache reads - plainly

**Cache reads are non-zero in both runs** - the provider did serve part of the prefix from its prompt cache once `7613091`'s stable token was in place. Warm-up differs by run: in **run 1** only some turns hit (turn 1 of every tenant is 0 - the prefix is cold on the first request), while in **run 2** the prefix is already warm and nearly every turn hits, hard.

| tenant | run | turns with cache > 0 | per-turn cached_in | total cached_in |
|---|---|---|---|---|
| bytefix | 1 | 1/5 | t5=5376 | 5376 |
| bytefix | 2 | 5/5 | t1=5760, t2=5760, t3=5376, t4=5632, t5=5376 | 27904 |
| sababa2 | 1 | 2/5 | t3=256, t5=12032 | 12288 |
| sababa2 | 2 | 5/5 | t1=12032, t2=12288, t3=12288, t4=12032, t5=12032 | 60672 |
| sababa | 1 | 3/5 | t2=3456, t3=4480, t5=3456 | 11392 |
| sababa | 2 | 4/5 | t2=6912, t3=3456, t4=3328, t5=6912 | 20608 |

## Clock

No clock claim is made. Ten of fifteen turns per run hit the 10 s turn budget and are excluded from the p50s, so the completed sample is thin (bytefix 1/5 and 2/5; sababa2 1/5 and 2/5; **sababa 0/5 in both runs** - the hybrid path never completes, as in every prior slice). The bytefix and sababa2 run-2 p50s step over their bands, but the completed turns there are the slow near-budget ones and the live provider drifts more than the band (slice-1 `bytefix` p50 alone spans 3977-7466 ms across eight runs). Cache reads do not show up as a clock win in this window.

