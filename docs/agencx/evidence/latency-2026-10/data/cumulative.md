# Cumulative comparison - slices 1-4 (`latency/stack`)

Every number below comes from the committed run artifacts; nothing was re-run for
this file. All eight latency runs used the same command:

```
make latency LATENCY_MODELS=openrouter/deepseek-v4.1-flash LATENCY_TENANTS=all LATENCY_TURNS=5
```

## Runs and provenance

| run | artifact | `commit` stamp | committed in | slice |
|---|---|---|---|---|
| noise-run1 | `data/noise-run1.json` | (none) | `44f739b` | 1 - instrument |
| noise-run2 | `data/noise-run2.json` | (none) | `44f739b` | 1 - instrument |
| slice2-run1 | `data/slice2-run1.json` | `4f40ef3` | `1f19c37` | 2 - draft cap |
| slice2-run2 | `data/slice2-run2.json` | `4f40ef3` | `1f19c37` | 2 - draft cap |
| slice3-run1 | `data/slice3-run1.json` | `2ac8247` | `05195b2` | 3 - grounded prose |
| slice3-run2 | `data/slice3-run2.json` | `2ac8247` | `05195b2` | 3 - grounded prose |
| slice4-run1 | `data/slice4-run1.json` | `040a473` | `7b7f7a4` | 4 - retrieval overlap |
| slice4-run2 | `data/slice4-run2.json` | `040a473` | `7b7f7a4` | 4 - retrieval overlap |

The slice-1 artifacts carry no `commit` stamp (the runner's `LATENCY_COMMIT`
wiring came later); their provenance is the commit that added them.

**Bands** (rules in `data/noise-floor.md` and `report-slice-2.md`, derived from
the four unchanged-mechanism runs: noise-run1/2 + slice2-run1/2 - slices 2-4 are
unchanged-mechanism for retrieval and the fast tenants):

| metric | bytefix | sababa2 | sababa |
|---|---|---|---|
| `llm_call_count` | 1.90 | 0.00 | 0.50 |
| `total_ms` | 2950.8 ms | 2031.3 ms | 2532.7 ms |

Baseline = the slice-1 runs (`noise-run1/2`); tip = the slice-4 runs
(`slice4-run1/2`, stamped `040a473`, the runtime tip - `5617eb6` and later are
docs-only).

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

## Eval trio (`data/eval-baseline.md`, `data/eval-noise-repeat.md`)

| run type | baseline (`d152572`) | after slice 3 (`2ac8247`) | repeat (`05195b2`) | verdict |
|---|---|---|---|---|
| generation | 0.7475 | 0.7163 | 0.7182 | FAIL by 0.001 (drop 0.0311 > 0.03) - OPEN, provider level shift |
| trajectory | 0.6341 | 0.6341 | - | identical, same 15 failing case names |
| injection | 0.9667 | 0.9667 | - | identical, same single leak |

Slice 5's future injection gate uses the **re-measured 0.9667** (29/30), not the
founder's stated 0.967. The eval exercises neither slice 3 nor slice 4: 0 of 116
replayed cases reach either changed path (`data/branch-exercise-probe.py`).
