# Coalesced burst: one turn vs three

**Measured:** `b857399`, production primary `google/gemini-3.5-flash-lite` with the configured
Groq fallback, one turn per tenant, the first three corpus questions joined by blank lines, run
twice. Raw tables in `data/coalesce.md`.

| Tenant | 3 serial turns (r1 / r2) | 1 coalesced turn (r1 / r2) |
|---|---|---|
| bytefix | 10.8 / 10.8 s | 3.4 / 3.4 s |
| sababa2 | 14.9 / 21.6 s | 3.5 / 5.7 s |
| sababa | 18.9 / 14.7 s | 4.8 / 4.5 s |

**Inside the budget?** Yes, all six turns completed with prose delivered: 3.4-5.7 s against the
10 s cap, a margin of 4.3-6.6 s. No budget handoff, no provider handoff, failover never engaged,
`model_match` true on every turn. The margin is larger than the measured run-to-run noise floor
(p50 moved 2.8 s), so the result is not a lucky window.

**Coverage:** the persisted reply in every conversation answers all three questions in order,
including numbers from the corpus (for example bytefix's `$35` water-damage assessment). No turn
answered only part of the burst.

**Verdict:** coalescing clears the budget. Three serial turns pay three route/retrieve/draft/
inspect chains (11-19 s cumulative); one coalesced turn pays one (3.4-5.7 s). This is a product
change, not a latency optimization of the same workload: the customer gets one reply covering a
burst instead of three replies. That interaction is the remaining unknown, not the clock. The
composer now queues a message submitted mid-reply and sends the burst as one combined turn, so the
measured interaction is the shipped one; it does not need a smaller judge or a longer budget.
