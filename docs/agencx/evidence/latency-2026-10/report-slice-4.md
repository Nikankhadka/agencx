# Slice 4 report - overlapping the retrieval steps

**Change.** `app/retrieval/service.py`: sparse starts first and the embedding
runs beside it; dense is awaited once the embedding is in hand AND sparse has
landed - one asyncpg connection runs one operation at a time (a second in-flight
query raises `InterfaceError`) and the RLS context lives on the caller's
connection. Fused inputs stay `[dense, sparse]`, filters and fuse untouched,
failure semantics sequential. Code `040a473`, measured there.

**Commands.** `make latency LATENCY_MODELS=openrouter/deepseek-v4.1-flash
LATENCY_TENANTS=all LATENCY_TURNS=5` x2 -> `data/slice4-run{1,2}.json`; gate ->
`slice4-eval-skip-llm.log`; split -> `slice4-retrieval-split.log`.

**Bands** (`data/slice4-bands.md`). The documented rule - completed hybrid turns
- yields **none**: sababa completed one turn in six runs. Fallback (every hybrid
turn that ran `retrieve`) gives `search_ms` a 2.52 ms band.

**Timing, corroboration only.** Hybrid `search_ms` p50 fell in both runs (1.9-2.7
-> **1.25 / 1.15**), every p50 delta inside 2.52; `embed_ms` unchanged as
designed. But `rerank_ms`, which this slice cannot touch, also steps over its own
band once - so the bands certify nothing either way, and the ceiling is physical:
only the sparse query can move, measured at median **0.38 ms** against a 506-1098
ms warm `retrieve`.

**Runs.** Completions unchanged (bytefix 3/5 & 2/5, sababa2 4/5 & 3/5, sababa 1/5
& 2/5); one leg, model verified (`deepseek/deepseek-v4.1-flash`).

**No scored eval, and why.** Output-preserving by construction (same filters and
SQL, same `[dense, sparse]` order, same fusion, same rerank), pinned by an
equivalence test against a spelled-out sequential reference. Both eval tenants are
fast-path, and the fast path never calls `retrieve`
(`services/retrieval.py:138-149`) - confirmed across 70 fast-path turns (null
retrieval timings) and slice 3's replay (0 of 116 cases used a retrieval tool).
The deterministic gate that does call `retrieve` passes: recall@5 1.000, MRR
0.911, nDCG@5 0.934 - identical to the pre-change logs.

**Verdict: pass structurally, no-measurable-effect on latency.**
