# Cumulative comparison - slices 1-6 (`latency/stack`)

Every number below comes from the committed run artifacts; nothing was re-run for
this file. The command differs by slice (table below): slices 1-5 used the one
model, slice 6's matrix used `LATENCY_MODELS=all` and its Google row used the
production-primary selector.

## Runs and provenance

| run | artifact | `commit` stamp | committed in | command | slice |
|---|---|---|---|---|---|
| noise-run1 | `data/noise-run1.json` | (none) | `44f739b` | `make latency LATENCY_MODELS=openrouter/deepseek-v4.1-flash LATENCY_TENANTS=all LATENCY_TURNS=5` | 1 - instrument |
| noise-run2 | `data/noise-run2.json` | (none) | `44f739b` | same | 1 - instrument |
| slice2-run1 | `data/slice2-run1.json` | `4f40ef3` | `1f19c37` | same | 2 - draft cap |
| slice2-run2 | `data/slice2-run2.json` | `4f40ef3` | `1f19c37` | same | 2 - draft cap |
| slice3-run1 | `data/slice3-run1.json` | `2ac8247` | `05195b2` | same | 3 - grounded prose |
| slice3-run2 | `data/slice3-run2.json` | `2ac8247` | `05195b2` | same | 3 - grounded prose |
| slice4-run1 | `data/slice4-run1.json` | `040a473` | `7b7f7a4` | same | 4 - retrieval overlap |
| slice4-run2 | `data/slice4-run2.json` | `040a473` | `7b7f7a4` | same | 4 - retrieval overlap |
| slice5-run1 | `data/slice5-run1.json` | `d99ca54` | `add13f6` | `make latency LATENCY_MODELS=openrouter/deepseek-v4.1-flash LATENCY_TENANTS=all LATENCY_TURNS=5` | 5 - prompt cache |
| slice5-run2 | `data/slice5-run2.json` | `d99ca54` | `add13f6` | same | 5 - prompt cache |
| slice6 matrix run1 | `data/matrix-slice6-run1-*.json` | `2004617` | `520f476` | `make latency LATENCY_MODELS=all LATENCY_TENANTS=all LATENCY_TURNS=5` | 6 - paid-tier matrix |
| slice6 matrix run2 | `data/matrix-slice6-run2-*.json` | `2004617` | `520f476` | same | 6 - paid-tier matrix |
| slice6 Google run1 | `data/matrix-slice6-google-run1-*.json` | `8ebf463` | `5a4578a` | `make latency LATENCY_MODELS=google/gemini-3.5-flash-lite LATENCY_TENANTS=all LATENCY_TURNS=5` | 6 - production primary |
| slice6 Google run2 | `data/matrix-slice6-google-run2-*.json` | `8ebf463` | `5a4578a` | same | 6 - production primary |

The slice-1 artifacts carry no `commit` stamp (the runner's `LATENCY_COMMIT`
wiring came later); their provenance is the commit that added them. The slice-6
Google artifacts are stamped `8ebf463` (the commit the runner recorded; the
config row itself landed next in `5a4578a`).

**Bands** (rules in `data/noise-floor.md` and `report-slice-2.md`, derived from
the four unchanged-mechanism runs: noise-run1/2 + slice2-run1/2 - slices 2-4 are
unchanged-mechanism for retrieval and the fast tenants):

| metric | bytefix | sababa2 | sababa |
|---|---|---|---|
| `llm_call_count` | 1.90 | 0.00 | 0.50 |
| `total_ms` | 2950.8 ms | 2031.3 ms | 2532.7 ms |

Baseline = the slice-1 runs (`noise-run1/2`); tip for the same-model runtime
tables = the slice-4 runs (`slice4-run1/2`, stamped `040a473`). **Slice 4 is the
last same-model runtime tip for calls, tokens, completion and `total_ms`.** Slice
5 changed the record and token reporting (it adds `cached_input_tokens` as a
subset of `input_tokens`; the input definition itself is unchanged) and slice 6
changed only the report cost code and the model config, so neither supplies a
new same-model runtime row for these tables. `5617eb6` and later are docs-only.

## Provider calls per completed turn

| tenant | baseline values (p50) | tip values (p50) | delta | band | history p50s (8 runs) |
|---|---|---|---|---|---|
| bytefix | 1,2,2,2,2,4 (**2.0**) | 2,2,2,2,2 (**2.0**) | 0.0 | 1.90 | 2.0, 3.0, 2.0, 2.0, 2, 2.0, 2.0, 2.0 |
| sababa2 | 2x7 (**2.0**) | 2x7 (**2.0**) | 0.0 | 0.00 | 2.0 in all eight |
| sababa | 4,3,4 (**4.0**) | 3,3,3 (**3.0**) | **-1.0** | 0.50 | 3.5, 4, 4, -, -, 3, 3, 3.0 |

The hybrid `-1.0` is the grounded tool turn: slice 3 makes the tool result carry
the chunks, so the agent's terminal prose is the draft and the draft node's call
disappears (design and caveats: `design-slice-3.md`, `report-slice-3.md`). The
mechanism is evidenced by the branch's own log line (`agent grounded tool
answer`, 8 firings, `data/slice3-run{1,2}-lines.jsonl`), not by the count alone.

## Completion rate (completed turns per 5)

| tenant | baseline | tip | full history (8 runs) |
|---|---|---|---|
| bytefix | 4/5, 2/5 | 3/5, 2/5 | 4, 2, 3, 4, 1, 3, 3, 2 (of 5) |
| sababa2 | 4/5, 3/5 | 4/5, 3/5 | 4, 3, 3, 4, 3, 4, 4, 3 |
| sababa | 2/5, 1/5 | 1/5, 2/5 | 2, 1, 1, 0, 0, 1, 1, 2 |

The tip sits inside each tenant's own historical spread; the hybrid path is the
one that blows the 10s turn budget, on every run of every slice.

## `total_ms` p50 / p95 (completed turns) vs band

| tenant | baseline p50 / p95 | tip p50 / p95 | band | p50 deltas, tip x baseline (4 cells) |
|---|---|---|---|---|
| bytefix | 3977.3 / 9194.8, 6771.9 / 8595.7 | 7466.1 / 8309.0, 5912.7 / 7655.7 | 2950.8 | +3488.8, +694.2, +1935.4, -859.2 |
| sababa2 | 4520.6 / 5579.7, 4946.1 / 5737.2 | 6438.6 / 7230.3, 4049.0 / 6197.3 | 2031.3 | +1918.0, +1492.5, -471.6, -897.1 |
| sababa | 6587.5 / 7804.0, 7134.6 / 7134.6 | 6818.4 / 6818.4, 7651.9 / 9160.8 | 2532.7 | +230.9, -316.2, +1064.4, +517.3 |

One cell exceeds its band: bytefix tip-run1 vs noise-run1, +3488.8 ms against
2950.8. Nothing in slices 1-4 adds seconds to a fast-path turn (slice 2's cap
never bound; slices 3-4 do not run there), and the bytefix p50 alone spans
3977-7466 across the eight runs of the same command - the live provider drifts
more than the band. No clock claim is made anywhere.

## Tokens (input per completed turn)

| tenant | baseline | tip | history |
|---|---|---|---|
| bytefix | 5,746-15,302 | 8,409-8,843 | 5,746-15,302 |
| sababa2 | 20,481-21,118 | 20,544-21,129 | 20,481-21,129 |
| sababa | 5,733-11,941 | 8,735-16,169 | 5,733-16,169 |

The hybrid tip carries more input than the slice-1 baseline because slice 3's
tool result re-sends the retrieved chunks on the terminal round (the counter-effect
reported in `report-slice-3.md`); the fast tenants, which carry the whole corpus
either way, are flat.

## Slice 5 - prompt cache

`cached_input_tokens` is a subset of `input_tokens` (a provider prompt-cache
read), not an extra input count. Both runs are at `d99ca54`; the fixed 16-hex
spotlight delimiter is in place, so the prefix is cacheable.

| tenant | run | turns with cache > 0 | per-turn cached_in | total cached_in |
|---|---|---|---|---|
| bytefix | 1 | 1/5 | t5=5376 | 5,376 |
| bytefix | 2 | 5/5 | t1=5760, t2=5760, t3=5376, t4=5632, t5=5376 | 27,904 |
| sababa2 | 1 | 2/5 | t3=256, t5=12032 | 12,288 |
| sababa2 | 2 | 5/5 | t1=12032, t2=12288, t3=12288, t4=12032, t5=12032 | 60,672 |
| sababa | 1 | 3/5 | t2=3456, t3=4480, t5=3456 | 11,392 |
| sababa | 2 | 4/5 | t2=6912, t3=3456, t4=3328, t5=6912 | 20,608 |

Run-level shares: run 1 (cold) 29,056 of 140,884 input tokens cached (20.6%);
run 2 (warm) 109,184 of 169,219 (64.5%). Turn 1 of every tenant is cold in both
runs; there is nothing to hit yet on the first request. **No clock claim**: 10
of 15 turns per run hit the 10 s budget and are censored, so the completed
samples are thin (bytefix 1/5 and 2/5, sababa2 1/5 and 2/5, sababa 0/5 both
runs). Cache reads do not show up as a clock win in this window.

## Slice 6 - paid-tier matrix

Cost is the cache-adjusted figure from `evals/latency_report.py` at `2004617`:
`(input - cached) * prompt + cached * input_cache_read + output * completion`,
with `cached` clamped to `input` per turn. Live prices were read at run time;
Google publishes no price, so its cost is `n/a` and none is invented. p50 is
over completed turns only, and a `structured` card turn is not comparable to a
drafted-answer turn (noted below).

| model | run | completed (bytefix / sababa2 / sababa) | p50 ms where they exist | cached tok | cost usd (cache-adjusted) | censored |
|---|---|---|---|---|---|---|
| openrouter/deepseek-v4.1-flash | 1 | 1/5 / 1/5 / 0/5 | 1999.0 / 4557.3 / - | 48,640 | 0.003906 | 13/15 |
| openrouter/deepseek-v4.1-flash | 2 | 3/5 / 0/5 / 0/5 | 7958.3 / - / - | 80,000 | 0.002753 | 12/15 |
| openrouter/inclusionai-ling-3.0-flash | 1 | 0/5 / 0/5 / 1/5 | - / - / 1113.9 | 103,424 | 0.001692 | 14/15 |
| openrouter/inclusionai-ling-3.0-flash | 2 | 0/5 / 0/5 / 1/5 | - / - / 3983.5 | 138,688 | 0.001563 | 14/15 |
| google/gemini-3.5-flash-lite | 1 | 3/5 / 3/5 / 4/5 | 8355.2 / 6248.8 / 5897.6 | 48,872 | n/a (no published price) | 5/15 |
| google/gemini-3.5-flash-lite | 2 | 1/5 / 1/5 / 0/5 | 8581.9 / 3625.8 / - | 68,627 | n/a (no published price) | 13/15 |

Censoring: 13/15, 14/15, 12/15 and 14/15 for the OpenRouter runs (run 1
deepseek, run 1 ling, run 2 deepseek, run 2 ling); Google completed 10/15 in a
good window then 2/15 under 429s. Every deepseek and ling completed turn that
produced a p50 was either a single card turn or n<=3, and only two
drafted-answer samples exist in the whole matrix; the Google run-1 sababa turns
are drafted (knowledge/conversation) but n=4 in one window. Ling has no
tool-correctness number at all: its providers reject structured outputs
(Novita 400, retried upstream with no choices), so the trajectory eval wrote no
row. **No winner**: no latency or correctness ranking is supportable from this
window, and the Google row has no cost.

## Eval trio (`data/eval-baseline.md`, `data/eval-noise-repeat.md`)

| run type | baseline (`d152572`, `24e961dc` / `f0573dba` / `2f739e87`) | after slice 3 (`2ac8247`, `9a4e3918` / `2e4371b8` / `db028f43`) | noise repeat (`f11f79f9`) | slice 5 after (`e8ab818f` / `6219ba04` / `513cec2f`) | slice 5 repeat (`302b9a94`) | verdict |
|---|---|---|---|---|---|---|
| generation | 0.7475 | 0.7163 | 0.7182 | 0.7628 | - | PASS - upward window shift, not attributed to the change; the earlier FAIL was closed by ruling |
| trajectory | 0.6341 | 0.6341 | - | 0.6098 | 0.6341 | PASS - the -0.0244 IS the same-code spread (one flaky case) |
| injection | 0.9667 | 0.9667 | - | 0.967 | - | PASS - identical apart from the same single leak |

The real last-two pairings at the tip, from the Phase 1 query (the rows are
committed in `data/gates-slice6.log`):

- generation: `e8ab818f-3947-4d9c-8d09-ef328ace3551` at 2026-10-19 14:43:00 UTC
  (0.7628) against `f11f79f9-af16-46e2-a33b-85431f8bfa73` at 2026-10-16
  20:14:17 UTC (0.7182): +0.0446, upward, outside the +0.0019 identical-code
  spread, with no mechanism in a delimiter-byte change. Not attributed to slice
  5; the earlier -0.0311 FAIL stays closed by the founder ruling.
- trajectory: `6219ba04-11e7-43d6-909e-bc466cf77409` at 2026-10-19 14:58:24 UTC
  (0.6098, 25/41) against its identical-code repeat
  `302b9a94-66f0-4066-aa72-8eadf163a1ed` at 2026-10-19 15:09:49 UTC (0.6341,
  26/41): -0.0244 is the same-code spread, the one flipped case being
  `knowledge-price-match-01` (flaky), inside `run_gate`'s -0.03.
- injection: `513cec2f-04b6-4426-8f0d-9835a90ad302` at 2026-10-19 12:54:12 UTC
  (29/30 = 0.967) against `db028f43-9f83-4ff9-a013-9c80d7e66e46` at 2026-10-16
  15:27:49 UTC (29/30 = 0.9667): identical apart from the same single leak
  (`direct-policy-invent-01`); both delimiter-forgery cases held.

**`run_gate` has no failing type at the tip.** The eval still exercises neither
slice 3 nor slice 4: 0 of 116 replayed cases reach either changed path
(`data/branch-exercise-probe.py`).

## Merge readiness

Checked at `5a4578a` (the tip):

- **Gates green:** `make lint-backend` (ruff + import contracts, 3 kept),
  `make typecheck-backend` (mypy, 246 files), `make format-check` (248 files),
  `make test-backend` (1435 passed). Tails in `data/gates-slice6.log`.
- **Tree state:** `git status --porcelain` shows only the pre-existing dirty
  entries (`.gitignore`'s stray line, the 26 RF-17 deletions plus its README,
  the interim sababa doc, untracked `.claude/`) and the files this package adds.
  Nothing else.
- **No reseeds:** bytefix is still `e9139d84-0e9f-4282-9af6-e0dc9bf4b56e` and
  the injection probe `464b8823-e113-4a0b-adef-db70db79d44d`; the eval rows
  above are intact.
- **Branch:** `latency/stack`, unpushed, no upstream configured.

**Blockers:** slice 7 (streaming with inspection off the critical path) stays
deferred pending a founder scope decision - it changes when a customer sees
model prose and needs a chunked-validation design, a security ruling and eval
rework - plus the merge go itself (one merge to `development`, then `staging`,
on the founder's word only).
