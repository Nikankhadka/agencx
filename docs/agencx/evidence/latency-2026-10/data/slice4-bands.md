# Slice 4 retrieval-timing bands

**The rule** (the campaign's, from `noise-floor.md`): a band is the max over
comparable run pairings of `max(|delta p50|, |delta p95|)` for one metric, on the
turns that carry it. Slice 4 moved `service.retrieve` only, so the metric is the
per-turn record's `embed_ms` / `search_ms` / `rerank_ms` on hybrid turns
(`sababa` - the only corpus tenant that runs retrieval at all; the fast tenants
record `null` for all three).

**The samples.** `noise-run1/2` + `slice2-run1/2` + `slice3-run1/2` are all
samples of the SAME mechanism: slices 2 (draft token cap) and 3 (grounded agent
prose) never touch `app/retrieval/`, and the per-turn records confirm it - the
three timings are non-null on exactly the same kind of turns across all six runs.

## Result A - the documented rule (completed hybrid turns): NO BAND

Completed hybrid turns **that ran `retrieve()`: 1/0/0/0/0/0** across
`noise-run1/2` + `slice2-run1/2` + `slice3-run1/2` - a single turn (`noise-run1`
turn 4, `embed_ms` 43.6 / `search_ms` 1.0 / `rerank_ms` 162.0). Every one of the
15 pre-slice pairings therefore lacks a sample on one side, and the rule returns
nothing.

Note the sibling, so the counts are not misread as the raw completion numbers:
`sababa` completed TWO hybrid turns in `noise-run1` (`noise-floor.md` records
2/5), but only one of them ran `retrieve()`. The other completed through the
tool's fast branch with all three retrieval timings null, so it is not a sample
for any retrieval band. Completed turns that ran the pipeline are
**1/0/0/0/0/0**; the hybrid path is the one that blows the 10s turn budget.

## Result B - fallback: every hybrid turn that ran `retrieve()`

A `retrieve` that returned always recorded its timings (`record_retrieval` is the
last thing it does), and retrieval finishes long before any budget kill, so these
timings are NOT censored the way `llm_call_count` is on a budget-blown turn. That
gives 3-4 turns per pre-slice run, and these bands:

| metric | band | from |
|---|---|---|
| `embed_ms` | 68.38 | slice2-run1 vs slice3-run2 |
| `search_ms` | 2.52 | slice2-run2 vs slice3-run1 |
| `rerank_ms` | 246.97 | slice2-run1 vs slice3-run1 |

Slice-4 runs against them (`n` = hybrid turns that ran retrieve):

| run | `embed_ms` p50/p95 | `search_ms` p50/p95 | `rerank_ms` p50/p95 |
|---|---|---|---|
| slice4-run1 | 24.5 / 35.4 (n=2) | **1.25 / 1.29** | 207.2 / 228.7 |
| slice4-run2 | 15.4 / 17.5 (n=2) | **1.15 / 1.46** | 163.4 / 207.8 |
| six pre-slice runs | 14.6-32.2 p50 | **1.9-2.7 p50**, max 5.2 | 223.3-345.3 p50 |

Readings:

- `search_ms` drops in **both** runs (p50 1.9-2.7 -> 1.15-1.25; deltas -0.6 to
  -1.55), the direction the mechanism predicts, and every p50 delta is inside the
  2.52 band. **Four** p95 deltas exceed it - -3.52 and -3.43 (slice4-run1), -3.35
  and -3.26 (slice4-run2), all four against `slice2-run1/2` - and all four are
  driven by those two runs' p95 outliers (4.72 / 4.81, from `search_ms` values of
  5.1 and 5.2 where every other run sits at 0.8-3.5). Same reading either way: a
  drop beyond an outlier-driven band is not a certified drop.
- `rerank_ms` - which slice 4 cannot touch - also "exceeds" its band (band 247;
  slice4-run2's p95 delta vs slice2-run1 is -285.5). A band that an
  untouched metric steps over cannot certify a causal claim in either direction,
  so the fallback bands are corroboration at best.
- The ceiling is physical: the overlap can only remove the **sparse** query's own
  duration from `search_ms`. The split probe (`data/slice4-retrieval-split.log`,
  script beside it) times the stages separately: sparse median **0.38 ms** / max
  **0.88 ms**, dense 0.55-1.75 ms, embed 9.5-14.8 ms warm. Its `retrieve=` totals
  (506-1098 ms warm, plus a cold row at 8.3 s) come from that separate process
  with a different candidate pool and are NOT the per-turn record sums (133-604
  ms, median 254, over the 26 retrieve-bearing hybrid turns) - the probe exists to
  bound the ceiling, nothing else. The saving is sub-millisecond by construction.

**Verdict for the slice-4 timing: no-measurable-effect.** The direction is
consistent and the mechanism is proven structurally; the magnitude is below what
this instrument can resolve at 3-4 hybrid turns per run. The load-bearing
evidence is the structural test, not the clock.
