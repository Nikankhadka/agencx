# Latency slice 2 - draft output cap

**Status:** measured at `4f40ef3`. **Verdict:** no-measurable-effect - the cap
never truncated an answer; latency stayed inside the slice-1 noise bands.

## Change

`llm_max_tokens_draft` ships at **2048** (was 0, uncapped). It reaches the prose
calls (chat, chat_stream, native chat_with_tools); `llm_max_tokens_extract`
stays 0. Value from slice-1 data: per-call output was p95 1315, max 1803 tokens
(cost_logs), so 2048 bounds a runaway draft without truncating observed answers.
`backend/.env` pins neither cap.

## Budget pre-check

`sababa` held 166,943 tokens of its 2,000,000 default; two runs need about
150k. PROCEED.

## Runs

```
make latency LATENCY_MODELS=openrouter/deepseek-v4.1-flash LATENCY_TENANTS=all LATENCY_TURNS=5   # x2
```
-> `data/slice2-run1.json`, `data/slice2-run2.json`, each carrying commit
`4f40ef3`. Percentiles recomputed from the JSON with the slice-1 rule.

| tenant | baseline p50 (r1/r2) | slice2 p50 (r1/r2) | band | verdict |
|---|---|---|---|---|
| bytefix | 3977 / 6772 | 5826 / 6928 | 2794.6 ms | inside noise |
| sababa2 | 4521 / 4946 | 4606 / 5884 | 425.6 ms | inside noise |
| sababa | 6588 / 7135 | 9120 / - | 669.4 ms | not interpretable (1 completed turn, then 0) |

A p50 that moves less than the band from a baseline run is noise; every
comparable tenant was inside its band.

## Cap effect

The cap never bound. Max output per call was 2003 tokens in the slice-2 window
and 1803 earlier (`select max(output_tokens) from cost_logs ...`), both below
2048. Per-turn output differences between runs are completion sampling, not the
cap.

## Quality guard

`make seed-tenant1` then `make eval`: money_guardrail, leakage and retrieval
PASS; generation, trajectory and injection FAIL with a provider
`503 UNAVAILABLE` on a Gemini `extract` (uncapped). A deepseek-pinned generation
run hung. The cap cannot have degraded an answer: it never truncated one.
