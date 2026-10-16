# Slice 4 report - overlapping the retrieval steps

**Change.** `app/retrieval/service.py`: sparse starts first, the embedding runs
beside it, and dense is awaited once the embedding is in hand AND sparse has
landed - one connection runs one operation at a time (a second in-flight query
raises `InterfaceError`). Fused inputs stay `[dense, sparse]`, filters and fuse
untouched, single-failure semantics unchanged. Code `040a473`.

**Commands.** `make latency LATENCY_MODELS=openrouter/deepseek-v4.1-flash
LATENCY_TENANTS=all LATENCY_TURNS=5` x2 -> `data/slice4-run{1,2}.json`; gate ->
`slice4-eval-skip-llm.log`; split -> `slice4-retrieval-split.log`.

**Bands** (`data/slice4-bands.md`). The documented rule has no usable sample:
completed hybrid turns that ran `retrieve()` are 1/0/0/0/0/0 across six runs.
Fallback gives `search_ms` a 2.52 ms band.

**Timing, corroboration only.** Hybrid `search_ms` p50 fell in both runs (1.9-2.7
-> **1.25 / 1.15**), every p50 delta inside 2.52; four p95 deltas exceed it, all
against slice2-run1/2's outliers, and `rerank_ms` - untouched by this slice - also
steps over its band once, so the bands certify nothing. The ceiling is physical:
only the sparse query can move (median **0.38 ms**), and probe `retrieve=` totals
(506-1098 ms, one cold row) are a separate process, not the per-turn sums
(133-604 ms).

**Runs.** Completions unchanged (3/5 & 2/5, 4/5 & 3/5, 1/5 & 2/5 for
bytefix/sababa2/sababa); one leg, `deepseek/deepseek-v4.1-flash`.

**No scored eval, and why.** Output-preserving by construction (same filters and
SQL, same `[dense, sparse]` order, same fusion, same rerank), pinned by an
equivalence test against a spelled-out sequential reference. Both eval tenants are
fast-path, and the fast path never calls `retrieve`
(`services/retrieval.py:138-149`) - confirmed across 80 fast-path turns (8 runs x
2 fast tenants x 5 turns, all null) and slice 3's replay (0 of 116 cases used a
retrieval tool). The deterministic gate that does call `retrieve` passes: recall@5
1.000, MRR 0.911, nDCG@5 0.934 - identical to the pre-change logs.

**Verdict: pass structurally, no-measurable-effect on latency.**
