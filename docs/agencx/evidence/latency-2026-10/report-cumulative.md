# Cumulative comparison - slices 1-6 on `latency/stack`

Six unpushed slices: 1 instrument (`44f739b`), 2 draft cap, inert (`4f40ef3`),
3 grounded prose, one call saved (`2ac8247`), 4 retrieval overlap (`040a473`),
5 cacheable prefix, cache proven (`d99ca54`), 6 cache-adjusted cost (`2004617`)
plus matrix and Google primary (`5a4578a`). Tables: `data/cumulative.md`.

**Calls win.** Hybrid sababa p50 4.0 -> 3.0 on completed turns (grounded tool
turn, 8 firings); sababa2 2.0 -> 2.0 (0.00 band held); bytefix 2.0 -> 2.0 (band
1.90). Completion stays inside each tenant's own spread; no `total_ms` claim
(drift exceeds bands).

**Cache proof.** `cached_input_tokens` non-zero in both runs: run 1 (cold) 20.6%
of input tokens, run 2 (warm) 64.5%, turn 1 cold per tenant. Per tenant 5,376 ->
27,904; 12,288 -> 60,672; 11,392 -> 20,608. No clock claim: 10/15 turns per run
hit the 10 s budget.

**Cost model.** `2004617` charges `(input - cached) * prompt + cached *
input_cache_read + output * completion`, clamped, legacy formula when a price is
absent. Deepseek $0.003906/$0.002753; ling $0.001692/$0.001563; Google n/a (no
published price).

**Model A/B: no winner.** Twelve to fourteen of fifteen OpenRouter turns per
model per run were censored; Google completed 10/15 then 2/15 under 429s; ling
has no tool-correctness row (structured outputs rejected). No ranking is
supportable.

**Eval trio.** Generation 0.7628 passes (upward window shift, not attributed;
earlier FAIL closed by ruling). Trajectory 0.6098, repeat 0.6341: the -0.0244 IS
the same-code spread (one flaky case). Injection 0.967, same single leak.
The last-two-row gate pairings all pass (derived, not re-executed).

**Merge readiness.** Backend gates green at `5a4578a` (lint, typecheck, format,
1435 tests), only pre-existing tree dirt, no reseeds, unpushed. Blockers: slice
7 (deferred, founder scope) and the merge go.
