# Latency slice 2 - draft output cap

**Status:** measured at `4f40ef3`. **Verdict:** mechanism inert - the cap never
bound, so no latency effect is attributable; the guard stays for runaway
protection.

## Change

`llm_max_tokens_draft` ships at **4096** (was 0, uncapped), on the prose calls
(chat, chat_stream, native chat_with_tools); `extract` stays 0. From
`data/cost-log-output-tokens.md`: per-call output p95 1315, max 2003, so 4096
leaves about 2x headroom. The first value, 2048, sat about 2% above the 2003
sample and was raised here.

## Runs

```
make latency LATENCY_MODELS=openrouter/deepseek-v4.1-flash LATENCY_TENANTS=all LATENCY_TURNS=5   # x2
```
-> `data/slice2-run{1,2}.json` (commit `4f40ef3`). Each cell is a slice-2 p50
against a baseline p50 (noise-run1/run2), versus the slice-1 band.

| tenant | band | inside | exceeds |
|---|---|---|---|
| bytefix | 2794.6 | 3 of 4 | run2 vs baseline1: +2950.8 |
| sababa2 | 425.6 | 2 of 4 | run2 vs both: +1363.4, +937.8 |
| sababa | 669.4 | 0 of 2 | run1 vs both: +2532.7, +1985.6 (n=1) |

So "every comparable tenant was inside its band" was false. The movement
happened while the cap never bound (max per-call 2003 < 4096), so it is
sampling noise: **the slice-1 bands, from two runs, understate cross-run
variance.** Revised bands from all four unchanged-mechanism runs (slice 2
counts as unchanged - the cap never engaged): bytefix 2950.8 ms, sababa2
2031.3 ms, sababa 2532.7 ms (n 2/1/1/0). These are the going-forward gate.

## Tool-call truncation

A length-truncated tool call raises failover-class `UpstreamResponseError`
(never a raw parse error, never a half-built call); with a second leg the model
is re-asked there. Two tests pin it.

## Eval

`make eval` after `make seed-tenant1`: money/leakage/retrieval PASS; generation,
trajectory and injection FAIL on a Gemini `503` and a Groq `400` -
`data/eval-slice2.log`. Not a cap regression.
