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

Completed hybrid turns - narration reaching the customer - are **one turn in six
runs** (`noise-run1` turn 4, `embed_ms` 43.6 / `search_ms` 1.0 / `rerank_ms`
162.0). Every one of the 15 pre-slice pairings therefore lacks a sample on one
side, and the rule returns nothing. `sababa` completed 0, 1, 1, 0, 0, 1 turns in
the six runs; the hybrid path is the one that blows the 10s turn budget.

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
  2.52 band. One p95 delta (-3.52, vs slice2-run2) exceeds it, but that pairing is
  itself outlier-driven (slice2-run2's max was 5.2).
- `rerank_ms` - which slice 4 cannot touch - also "exceeds" its band in one
  pairing (-285.5, slice4-run2 vs slice2-run1, band 247). A band that an
  untouched metric steps over cannot certify a causal claim in either direction,
  so the fallback bands are corroboration at best.
- The ceiling is physical: the overlap can only remove the **sparse** query's own
  duration from `search_ms`, measured separately (`slice4-retrieval-split.log`)
  at median **0.38 ms**, max **0.88 ms** per query, against a warm `retrieve`
  total of 506-1098 ms and `embed_ms` of 9.5-14.8 ms. The saving is
  sub-millisecond by construction.

**Verdict for the slice-4 timing: no-measurable-effect.** The direction is
consistent and the mechanism is proven structurally; the magnitude is below what
this instrument can resolve at 3-4 hybrid turns per run. The load-bearing
evidence is the structural test, not the clock.
