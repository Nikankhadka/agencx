# Slice 6 report - paid-tier matrix

**Cost model.** `2004617`: `evals/latency_report.py` now prices cache reads when the
provider publishes `input_cache_read` - `(input - cached)*prompt +
cached*cache_read + output*completion`, with `cached` clamped to `input` per turn -
and keeps the old all-input-at-prompt formula when the price is absent (legacy
artifacts, cache-blind providers). Four tests pin legacy byte-identity, the reduced
figure, absent-price, and clamping; `make test-backend` is 1435 passed. Live prices
(prompt/completion/cache read per token): deepseek `0.0000000328/0.00000008/
0.0000000016`, ling `0.000000021/0.000000063/0.0000000042`.

**Ling trajectory.** Pinned single-leg `inclusionai/ling-3.0-flash`, fallback and
failover empty. Both attempts aborted before any aggregate row: attempt 1 at case
1/41 (`BadRequestError` 400 from Novita, "model features structured outputs not
support"; DeepInfra was 429), attempt 2 at case 8/41 (`UpstreamResponseError`, no
choices). No `eval_runs` row was written, so there was nothing to delete and the
slice-5 pairing (`302b9a94` repeat, `6219ba04` after) is untouched. No ling
tool-correctness number exists; deepseek's standing 41-case trajectory
(0.610 after, 0.634 repeat) is not re-run here.

**Matrix, x2 at `2004617`.** 13/15, 14/15, 12/15 and 14/15 turns were censored by
the 10 s budget. Completed - run 1: deepseek bytefix 1/5 (card), sababa2 1/5
(drafted, 4557 ms), sababa 0/5; ling sababa 1/5 (card), bytefix/sababa2 0/5. Run 2:
deepseek bytefix 3/5 (mixed), sababa/sababa2 0/5; ling sababa 1/5 (card),
bytefix/sababa2 0/5. `model_match` true and no failover on every artifact.
Cache-adjusted cost across three tenants: deepseek $0.003906 / $0.002753, ling
$0.001692 / $0.001563 (28-60% below cache-blind).

**Verdict.** No winner. This degraded window censors 12-14 of 15 turns per model per
run; completed moves are card turns or n=1-3, and ling's tool correctness cannot be
scored because the provider rejects structured outputs. Cost shows ling is cheaper
per token and per run - price, not quality. A paid-tier A/B needs an uncensored
window before it can rank latency or correctness.
