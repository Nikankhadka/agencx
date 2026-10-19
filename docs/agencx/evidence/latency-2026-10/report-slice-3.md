# Slice 3 report

**Change.** `search_knowledge`'s result carries the chunks, so a grounded tool turn's prose
is the draft (agent -> price_gate -> inspection, no draft node). Code `cbad1b0`,
measured at `2ac8247`.

**Commands.** `make latency` (deepseek, all tenants, 5 turns) x2; three pinned evals, no
`--reseed`.

**Structural gate.** sababa2 `[2,2,2]`/`[2,2,2,2]`, bytefix `[2]`/`[1,2,2]`: p50 delta 0,
sababa2's 0.00 band held. Sababa's one completed turn (3 calls) sits 0.50 from baseline
p50 3.5 (the band); the mechanism proves it - `agent grounded tool answer` fired 8 times,
only on sababa's tool turns, only in the new branch.

**Retry edge.** 7 of 8 reached the gates; run 1's `b3de4472` was rejected and redrafted
by the draft node (`agent draft`, `cited: 0`); run 2: none.

**Citations.** No grounded turn emitted a citations event (`cited: 0`; run 1's lone event
was that redraft). It narrows internally only: markers are stripped from every approved
token run before flush and persistence (`controller.py:71-102`, `shared/text.py:42`), so
neither path renders a chip (`CustomerChat.tsx:117-124`). Ratified cited-only, no
fallback.

**Completion, timing, tokens.** Completions unchanged (1/5 & 3/5, 3/5 & 4/5, 0/5 & 1/5);
p50s above the bands; the grounded turn took 15,333 input tokens vs 5.7-11.9k pre-slice
(re-send cost). One leg.

**After-eval** (counts 45/41/30). Trajectory and injection identical. Generation:
faithfulness 0.7475 -> **0.7163**, answer_relevancy 0.7356 -> 0.8025, citation_faithfulness
0.3207 -> 0.3692 (refusal 0.000, negative 12). `run_gate` fails generation by 0.001.

**-0.0311 is not noise.** Repeat - after (identical code) = +0.0019, ~17x the within-window
spread: likely provider drift, unproven on one baseline. Accepted as a provider level shift
by founder ruling 2026-10-19; tolerance unchanged at 0.03, not noise.

**Blindness:** `_tools_for` never offers the retrieval tools on the fast path
(`agent_node.py:604-605`); the eval cannot reach the branch (0/116).

**Verdict: pass on the mechanism**; n=1, both rulings (accepted FAIL; citations
cited-only, internal only).
