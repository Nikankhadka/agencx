# Slice 3 report

**Change.** `search_knowledge`'s result now carries the chunks, so a grounded tool turn's
prose is the draft; the draft node is skipped (agent -> price_gate -> inspection). Code
`cbad1b0`, measured at `2ac8247`.

**Commands.** `make latency LATENCY_MODELS=openrouter/deepseek-v4.1-flash
LATENCY_TENANTS=all LATENCY_TURNS=5` x2; three pinned evals, no `--reseed`.

**Structural gate.** sababa2 `[2,2,2]`/`[2,2,2,2]`, bytefix `[2]`/`[1,2,2]`: p50 delta 0,
sababa2's 0.00 band held. Sababa's ONE completed turn (3 calls) is 0.50 from baseline p50
3.5 (the band), 1.0 from 4.0; the proof is the mechanism - `agent grounded
tool answer` fired 8 times, only on sababa's tool turns, and only the new branch logs it.

**Retry edge.** 7 of the 8 ran to the gates; run 1's knowledge turn `b3de4472` was rejected
and redrafted by the draft node (`agent draft`, `cited: 0`); run 2: none.

**Citations narrowing.** No grounded turn emitted a citations event (`cited: 0`): no source
chips where the old path emitted one per chunk (run 1's lone event was that redraft).
Founder review.

**Completion, timing, tokens.** Completions unchanged (1/5 & 3/5, 3/5 & 4/5, 0/5 & 1/5);
p50s above the bands; the grounded turn took 15,333 input tokens vs 5.7-11.9k pre-slice
(the re-send cost). One leg,
`usage_models == ["deepseek/deepseek-v4.1-flash"]`.

**After-eval** (counts 45/41/30). Trajectory and injection identical. Generation:
faithfulness 0.7475 -> **0.7163**, answer_relevancy 0.7356 -> 0.8025, citation_faithfulness
0.3207 -> 0.3692 (refusal_accuracy 0.000, negative_cases 12). `run_gate` fails generation
by 0.001.

**-0.0311 is not noise.** Repeat - after (identical code) = +0.0019, ~17x the within-window
spread: a between-window shift, likely provider drift (2 resamples vs 1), unproven (one
baseline sample). -0.03 cannot resolve it; FAIL open.

**Blindness is structural:** `_tools_for` returns the fast-path list before the retrieval
tools are appended (`agent_node.py:604-605`), so fast-path tenants cannot reach it (0/116
replayed).

**Verdict: pass on the mechanism**; the n=1 sample, chip change and open FAIL.
