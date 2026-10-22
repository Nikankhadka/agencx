# Abandoned slow variants (2026-10-22)

The first `--suite all` attempts for the qwen and gemma families were stopped after
about 11 minutes and replaced by faster same-family variants. Nothing here counts
toward the benchmark: `raw/` no longer holds these labels, so `--report-only` and
`--resume` ignore them.

Moved here (partial raw artifacts, generation suite in progress):

- `openrouter-qwen3-8-flash.json` - `qwen/qwen3.8-flash`, 15 of 45 generation cases
  logged in repeat 1 of 2, file wrote at 04:53Z before the suite finished.
- `openrouter-gemma-4-31b-it.json` - `google/gemma-4-31b-it`, 13 of 45 generation
  cases logged in repeat 1 of 1, file wrote at 04:56Z before the suite finished.

`logs/` holds copies of the container logs at the moment of the stop (the live
`logs/qwen.log` and `logs/gemma.log` now belong to the replacement runs).

## Why they were abandoned

Gate (capability check) wall times, from the two artifacts above:

| Check | qwen3.8-flash | gemma-4-31b-it |
|---|---|---|
| inspection_extract_1 | 18,243 ms | 252,161 ms |
| inspection_extract_2 | 24,892 ms | 2,031 ms |
| inspection_extract_3 | 64,213 ms | 13,607 ms |
| tool_call | 2,408 ms | 565 ms |
| long_context_chat | 5,693 ms | 2,758 ms |
| gate total | 115,449 ms | 271,122 ms |

Generation throughput measured from the log copy over the first 11 minutes:

- qwen3.8-flash: 15 case starts in about 660 s, about 44 s per case, 0 timeout retries.
- gemma-4-31b-it: 13 case starts in about 660 s, about 51 s per case, 4 extract calls
  hit the 120 s per-call bound and were retried.

The multi-minute figures that triggered this switch matched the gate's worst extract
(64 s for qwen, 252 s for gemma), not a steady per-case rate. The steady rate was
already the reason to look for a smaller variant: both replacement rows cut the
gate dramatically and the qwen replacement has run the generation suite with no
timeouts.

Cancellation note: `docker stop` sends SIGTERM, so the containers exited 137 and the
partial artifacts were never finalized by the runner.
