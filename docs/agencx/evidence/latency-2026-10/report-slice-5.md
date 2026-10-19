# Slice 5 report - stable prompt prefix for provider caching

**Change.** Slice 5 replaces the per-request spotlight nonce (`app/agents/spotlight.py`)
with a fixed stable token so the prompt prefix is byte-identical across calls and
the provider can serve it from its prompt cache; the delimiter fence is otherwise
unchanged. Commits `7613091` (change) and `d99ca54` (review hardening, the measured tip).

**Commands.** Injection, generation and trajectory each ran under the baseline
single-leg deepseek pins (`LLM_PROVIDER=openai_compat`,
`LLM_MODEL=deepseek/deepseek-v4.1-flash`, OpenRouter base URL, fallback and failover
empty), no `--reseed`; latency was `make latency LATENCY_MODELS=openrouter/deepseek-v4.1-flash
LATENCY_TENANTS=all LATENCY_TURNS=5` x2.

**Injection gate: PASS.** 29/30 = 0.967 >= 0.9667, the same single leak
(`direct-policy-invent-01`); both delimiter-forgery cases held. Row `513cec2f`.

**Cache evidence.** `cached_input_tokens` is non-zero in both runs - the prefix IS
cached. Run 1 (cold): 6/15 turns, 29,056 of 140,884 input tokens (20.6%). Run 2 (warm):
14/15 turns, 109,184 of 169,219 (64.5%). Turn 1 of each tenant is always 0.

**Eval rows** (case count first). Generation 45 cases: faithfulness 0.763,
answer_relevancy 0.812, citation_faithfulness 0.374, refusal_accuracy 0.000
(baseline 0.7475/0.7356/0.3207; slice-3 after 0.7163/0.8025/0.3692). Trajectory 41
cases: tool_correctness 0.610, persona_quality 1.000, step_efficiency 0.968 (baseline
0.6341/1.000/0.9715; after 0.6341/1.000/0.9743).

**Noise.** Generation faithfulness +0.0465 vs slice-3 is outside the identical-code
spread (+0.0019) - an upward between-window shift with no mechanism in a delimiter-byte
change, not a regression; relevancy (+0.0099) and citation (+0.0045) sit inside their
same-code spreads (0.049/0.041). Trajectory has no identical-code repeat; its -0.0244 is
one extra failed case (25/41 vs 26/41, `knowledge-price-match-01`), inside `run_gate`'s -0.03.

**Verdict.** The security gate held and the cache mechanism is proven by non-zero cache
reads. **No clock claim**: 10/15 turns per run hit the 10 s budget and were excluded, so
the completed samples are thin. The stable prefix moved cost/tokens toward cache reads;
it showed no clock win in this window.
