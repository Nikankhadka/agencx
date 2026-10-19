# Slice 5 report - stable prompt prefix for provider caching

**Change.** `7613091`: the per-request spotlight nonce (`app/agents/spotlight.py`)
becomes a fixed stable token so the prompt prefix is byte-identical across calls and
the provider can cache it; the turn record gains `cached_input_tokens` (the provider's
prompt-cache read count). `d99ca54` (review hardening, the measured tip):
`escape_delimiters` normalized for invisible/full-width delimiter disguises, the escaped
marker made non-forgeable, the Inspection judge's provenance block fenced, injection
fixtures forged from the live token, and the probe seed made idempotent with `--refresh`.

**Commands.** Injection, generation and trajectory under the baseline single-leg deepseek
pins (`LLM_PROVIDER=openai_compat`, `LLM_MODEL=deepseek/deepseek-v4.1-flash`, OpenRouter,
fallback/failover empty), no `--reseed`; latency `make latency
LATENCY_MODELS=openrouter/deepseek-v4.1-flash LATENCY_TENANTS=all LATENCY_TURNS=5` x2.

**Injection gate: PASS.** 29/30 = 0.967 >= 0.9667, same leak (`direct-policy-invent-01`);
both forgery cases held.

**Cache.** Non-zero both runs - the prefix IS cached. Run 1 (cold) 6/15 turns, 29,056 of
140,884 input (20.6%); run 2 (warm) 14/15 turns, 109,184 of 169,219 (64.5%); each
tenant's turn 1 always 0.

**Eval rows** (cases first). Generation 45: faithfulness 0.763, answer_relevancy 0.812,
citation_faithfulness 0.374, refusal 0.000 (baseline 0.7475/0.7356/0.3207; slice-3 after
0.7163/0.8025/0.3692). Trajectory 41: tool_correctness 0.610, repeat 0.634, persona
1.000, step_efficiency 0.968, repeat 0.980 (baseline 0.6341, slice-3 after 0.6341).

**Bounded.** The identical-code trajectory repeat restores 0.6341: the -0.0244 is exactly
the same-code spread, and `knowledge-price-match-01` flips back to pass - a flaky case,
not a regression. Generation faithfulness +0.0465 vs slice-3 sits outside the
identical-code spread (+0.0019); answer_relevancy (+0.0099) and citation (+0.0045) sit
inside theirs (0.049/0.041).

**Verdict.** Gate held, cache proven. **No clock claim**: 10/15 turns per run hit the 10 s
budget and were excluded, samples thin; the stable prefix moved tokens toward cache reads
with no clock win.
