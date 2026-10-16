# Cumulative comparison - slices 1-4 on `latency/stack`

**Stack.** Slices 1-4, each verified against its own gate, nothing merged or
pushed: 1 instrument + noise floor (`44f739b`), 2 draft cap, inert (`4f40ef3`),
3 grounded prose, one call saved (`cbad1b0`/`2ac8247`), 4 retrieval overlap
(`040a473`). Slices 5-7 await rulings. Tables: `data/cumulative.md`.

**Baseline (slice-1 `noise-run1/2`) vs tip (`slice4-run1/2`, `040a473`).**

- **Calls per completed turn.** Hybrid `sababa` p50 **4.0 -> 3.0** (grounded tool
  turn; -1.0 vs a 0.50 band); sababa2 **2.0 -> 2.0** (0.00 band held; 2 calls on
  all 28 completed turns); bytefix **2.0 -> 2.0** (band 1.90).
- **Completion.** Inside every tenant's own historical spread (bytefix 1-4,
  sababa2 3-4, sababa 0-2 of 5).
- **`total_ms`.** No claim: one of four bytefix pairings exceeds its band
  (+3488.8 vs 2950.8), and the bytefix p50 spans 3977-7466 over eight identical
  runs.
- **Tokens.** Fast tenants flat (sababa2 input 20.5-21.1k); the hybrid tip reaches
  16.2k against 11.9k, as slice 3's tool result re-sends the chunks.

**Mechanism gains the clock cannot see:** one saved provider call per grounded
tool turn (8 log firings), and the retrieval overlap (at most the sparse query's
0.38 ms).

**Eval trio.** Trajectory and injection are case-identical to the baseline
(0.6341; 0.9667 - the re-measured number for slice 5's future gate, not 0.967).
Generation 0.7475 -> 0.7163 -> 0.7182: an open FAIL by 0.001, a provider level
shift, **not** absorbed as noise - the 0.03 tolerance cannot resolve it. The eval
reaches neither changed path (0 of 116 cases).

**Not claimed:** no clock gain inside any band; slices 2 and 4 are structural only;
slice 3's own timing is corroboration (n=1).

**Merge readiness** (checklist in `13-latency.md`): gates green, tree clean,
unpushed. Blockers: the citation-chip ruling, the 5-7 decisions (5 needs the
security ruling), the open `run_gate` FAIL, the merge request.
