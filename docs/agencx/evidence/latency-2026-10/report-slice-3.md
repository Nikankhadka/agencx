# Slice 3 report - the discarded agent call

**Change.** `search_knowledge`'s result now carries the chunks, so a tool turn's grounded
terminal prose becomes the draft and the draft node is skipped (agent -> price_gate ->
inspection); retries, money, refusals, cards unchanged. Code `cbad1b0`, measured at
`2ac8247`.

**Commands.** `make latency LATENCY_MODELS=openrouter/deepseek-v4.1-flash
LATENCY_TENANTS=all LATENCY_TURNS=5` x2 -> `data/slice3-run{1,2}.json`; three pinned evals,
no `--reseed` -> `data/eval-after-slice3-<type>.log`.

**Structural gate.** Completed-turn `llm_call_count`: sababa2 `[2,2,2]`/`[2,2,2,2]` (band
0.00 held), bytefix `[2]`/`[1,2,2]` (inside 1.90). Sababa: one completed turn at 3 (2 rounds
+ inspection, no draft) where that shape was 4, plus a `citations` event proving the branch
ran; `grounded=1, draft=0` on every tool turn.

**Completion, timing, tokens.** Completions did not rise (bytefix 1/5 & 3/5, sababa2 3/5 &
4/5, sababa 0/5 & 1/5). p50s exceed the revised bands, as pre-slice p50s in this window did -
corroboration only. The grounded hybrid turn carried 15,333 input tokens against 5.7-9.1k
pre-slice: the chunk-carrying result is re-sent, so the counter-effect is real. All turns:
one leg, `usage_models == ["deepseek/deepseek-v4.1-flash"]`.

**After-eval** (counts verified 45/41/30). Trajectory and injection are
case-for-case identical to the baseline: tool_correctness 0.634->0.634 (same 15 failures),
persona 1.000->1.000, step_efficiency 0.972->0.974, pass_rate 0.967->0.967 (same single
leak). Generation: faithfulness 0.747->0.716, answer_relevancy 0.736->0.802,
citation_faithfulness 0.321->0.369, refusal_accuracy 0.000->0.000, negative_cases 12->12.
`run_gate`: absolute gates pass; its rule fails generation by 0.001 (drop 0.031 > 0.03).

**Honesty check.** The eval never touches the change: replaying its 45 generation and 30
injection cases gave **0** new-branch hits (43 P-3 + 2 structured; 26 P-3 + 4 other). It
scores the unchanged path, so -0.031 is this harness's noise on faithfulness and the
tolerance sits at the noise floor.

**Verdict: pass.** Structural gate met, mechanism confirmed; the eval is a
no-collateral-regression check whose failing key is noise, not a regression - flagged for
the founder.
