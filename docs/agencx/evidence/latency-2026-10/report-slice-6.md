# Slice 6 report - paid-tier matrix

**Cost model.** `2004617`: `evals/latency_report.py` prices cache reads when
`input_cache_read` is published - `(input - cached)*prompt + cached*cache_read +
output*completion`, `cached` clamped to `input` per turn - and keeps the old
all-input-at-prompt formula when absent. Four tests pin legacy identity, the reduced
figure, absent-price and clamping; 1435 backend tests pass. Live
prompt/completion/cache-read per token: deepseek `0.0000000328/0.00000008/
0.0000000016`, ling `0.000000021/0.000000063/0.0000000042`.

**Ling trajectory.** Pinned single-leg `inclusionai/ling-3.0-flash`, fallback and
failover empty. Both attempts aborted before any aggregate row: case 1/41
(`BadRequestError` 400, Novita, structured outputs unsupported; DeepInfra 429),
retry case 8/41 (`UpstreamResponseError`, no choices). No row was written, so the
slice-5 pairing (`302b9a94` repeat, `6219ba04` after) is untouched; no ling
tool-correctness number exists.

**OpenRouter matrix (x2 at `2004617`).** 13/15, 14/15, 12/15 and 14/15 turns were
censored by the 10 s budget. Completed - run 1: deepseek bytefix 1/5 (card), sababa2
1/5 (drafted, 4557 ms); ling sababa 1/5 (card). Run 2: deepseek bytefix 3/5 (mixed);
ling sababa 1/5 (card). `model_match` true, no failover. Cache-adjusted cost:
deepseek $0.003906/$0.002753, ling $0.001692/$0.001563 (28-60% below cache-blind).

**Production primary (Google gemini-3.5-flash-lite).** Added as a row
(`models/gemini-3.5-flash-lite`; no published price, cost n/a). It completed 10/15
turns in run 1 - including drafted `sababa` knowledge/conversation turns, 4/5 - but
only 2/15 in run 2, where Google 429s censored `sababa` entirely. The window is
unstable; still no winner.

**Verdict.** No winner. Twelve to fourteen of fifteen OpenRouter turns are censored
per model per run; Google swings 10 to 2 and has no cost. Completed moves are card
turns or n<=4, and ling's tool correctness cannot be scored (provider rejects
structured outputs). A paid-tier A/B needs an uncensored window.
