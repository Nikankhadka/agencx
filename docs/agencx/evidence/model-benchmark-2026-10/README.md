# Model benchmark - October 2026

- Date: 2026-10-22
- Commit: `712033b` (the tree the benchmark ran at; the harness and this report
  were added after that measurement)
- Command: `python -m evals.model_benchmark --models all --suite all --out /evidence`
- Aggregation: `python -m evals.model_benchmark --report-only --out /evidence`
- Harness: `backend/evals/model_benchmark.py`, config `backend/evals/model_benchmark_config.json`
- Raw artifacts: `raw/*.json`; aggregate: `results.json`, `summary.md`; per-model logs: `logs/`
- Abandoned before the final run: `slow-variant-abandoned/` (partial qwen/gemma artifacts and why they were dropped)
- No key, and no full URL carrying a key, is written to any artifact or to this README.

## Question

Which model should serve the fallback leg of the chat provider chain? The primary
leg is Gemini 3.5 Flash-Lite on the Google AI Studio free tier, which is capped at
20 requests/day/model, so the fallback is the leg that actually answers on a
normal working day. The founder needs a candidate that survives that cap without
weakening injection resistance, refusal behaviour, or the no-invented-money rule.

## Candidates

| candidate | family | route | api model | measured |
|---|---|---|---|---|
| DeepSeek V4.1 Flash | deepseek | OpenRouter | `deepseek/deepseek-v4.1-flash` | yes |
| Mistral Small 3.2 24B | mistral | OpenRouter | `mistralai/mistral-small-3.2-24b-instruct` | yes |
| Qwen 3.8 27B | qwen | OpenRouter | `qwen/qwen3.8-27b` | yes |
| Gemma 4 26B A4B | gemma | OpenRouter | `google/gemma-4-26b-a4b-it` | yes |
| Gemini 3.5 Flash | gemini | Google native | `models/gemini-3.5-flash` | no - quota-blocked |
| Gemini 3.5 Flash-Lite | gemini | Google native | `models/gemini-3.5-flash-lite` | no - quota-blocked |

The two Gemini rows use the Google key (`LLM_API_KEY`), not the OpenRouter key.
Both failed the capability gate with `429 RESOURCE_EXHAUSTED`
(`GenerateRequestsPerDayPerProjectPerModel-FreeTier`, limit 20), so they have no
quality numbers in this window. They are listed because they are the primary,
not because they were scored.

## Criteria

- **Generation** (33 positive cases, 12 negative cases, 2 repeats each):
  faithfulness (gate 0.85), answer relevancy (0.85), citation faithfulness
  (0.85), fact coverage (0.80), strict refusal accuracy, semantic refusal.
- **Trajectory** (52 cases, 1 repeat): tool correctness (gate 0.90), step
  efficiency, persona quality.
- **Injection** (30 cases, 1 repeat): resistance to instruction-override and
  prompt-leak attempts inside tenant data (gate 0.80).
- **Money** (every drafted answer): monetary figures that reconcile to nothing
  the turn was allowed to see (gate 0 violations).
- **Operational**: latency p50/p95 per turn, calls per turn, error rate, judge
  errors, input/output tokens, cache share, cost in USD.

That is 127 distinct cases per candidate, 172 scored turns once generation's two
repeats are counted. Repeats are averaged into one observation per case before
any statistic, so `n` above is distinct cases, not call count.

## Judges

- Primary judge: **Claude Haiku 5.5** (`anthropic/claude-haiku-5.5`, fixed for
  every candidate, never itself a candidate).
- Agreement judge: **GPT-6 Luna** (`openai/gpt-6-luna`) on a 12-13 case sample
  per candidate. Agreement was 0.93-1.00 raw, Cohen's kappa 0.628-1.000.
- Judge calls are metered separately and excluded from every candidate's cost
  and latency. Judges run in `json_object` mode, validated client-side.

## Key results

Every OpenRouter candidate **FAILS** the gates.

| candidate | verdict | tool correctness (gate 0.90) | injection (gate 0.80) | semantic refusal | money violations | p95 turn | cost / 172 turns |
|---|---|---|---|---|---|---|---|
| DeepSeek V4.1 Flash | FAIL | 0.654 | 0.967 | 0.917 | 0 | 32.4 s | $0.650 |
| Gemma 4 26B A4B | FAIL | 0.577 | 0.933 | 0.917 | 0 | 127.0 s | $0.096 |
| Mistral Small 3.2 24B | FAIL | 0.500 | 0.567 | 0.500 | 0 | 17.3 s | $0.157 |
| Qwen 3.8 27B | FAIL | 0.635 | 0.967 | 0.958 | 0 | 82.6 s | $0.697 |

What decides it:

- **Nobody passes tool correctness.** The whole field lands in 0.500-0.654
  against a 0.90 gate, so this benchmark cannot justify *promoting* any of them.
- **Cost ordering is clear and does not track quality.** Gemma is cheapest at
  $0.096 per 172 cases, then Mistral $0.157, DeepSeek $0.650, Qwen $0.697. Those
  are cache-adjusted where the provider publishes a cache-read price.
- **Injection separates the field.** DeepSeek 0.967 and Qwen 0.967 versus
  Mistral 0.567. A fallback that can be talked out of its delimiters is worse
  than a slow one.
- **Strict refusal is 0.000 for every candidate** - they refuse in their own
  words rather than the exact `REFUSAL_MESSAGE` constant. That is why semantic
  refusal exists as a second, judge-assessed column; it is narrative evidence
  and changes no verdict.
- Every candidate also misses answer relevancy (0.803-0.841 against 0.85).
  Gemma additionally fails fact coverage, DeepSeek and Qwen fail it on the
  interval, and DeepSeek/Qwen have citation intervals reaching below 0.85.

## Scorer corrections made during this run

The first pass under-scored correct answers. Three fixes were applied and the
artifacts re-scored (`backend/evals/rescore_citations.py`,
`backend/evals/rescore_money_and_refusals.py`), so these numbers are the
corrected ones:

1. **Citation faithfulness no longer truncates the cited chunk at 400 chars.**
   The judge saw a prefix, and the sentence supporting a citation often starts
   later in the chunk, so accurate citations were graded unsupported. Chunks go
   to the judge whole.
2. **Money scoring allows the tenant catalog's own prices.** The trajectory
   scorer could not reconstruct the catalog rows the turn actually saw, so a
   draft quoting a real catalog price looked invented. `check_unsourced_figures`
   now takes `extra_allowed_cents` for exactly that. The runtime `price_gate` is a
   separate seam and does not call this scorer.
3. **Semantic refusal was added.** Strict exact-match refusal scored 0.000 for
   every candidate, which said nothing about whether they withheld the requested
   information. The judge-assessed column does, and is reported beside the
   strict metric rather than replacing it.

## Limitations

- **One window.** A single 2026-10-22 run, no repeat of the whole benchmark. The
  rankings are directional, not stable-to-the-decimal.
- **Judge-assessed.** Faithfulness, relevancy, citations, persona, semantic
  refusal and the injection verdicts are model judgements. The second judge
  agrees with the first on 0.93-1.00 of sampled cases, which bounds but does not
  remove judge error.
- **The primary could not be measured.** Gemini's free-tier daily cap blocked
  both Gemini rows, so there is no same-window primary baseline. The fallback
  decision is therefore relative to the other candidates, not to the primary.
- **Variant substitution for speed.** The Qwen and Gemma rows are the variants
  that responded in this window, not necessarily the newest or fastest in their
  family; live catalog availability changes daily. A different variant could move
  both latency and cost.
- **Tool correctness may be partly a harness fit.** These models are not
  tool-calling specialists, and the supervisor shape (one call per turn with
  tools) is demanding. The gate is the gate, but a low score here is not proof
  the model is unsafe - it is proof it cannot take this slot without losing tool
  fidelity.
- **Cost is per the pinned prices** captured from the OpenRouter catalogue on
  2026-10-22, used only when the live fetch failed. Google publishes no price on
  its native OpenAI-compatible catalogue, so a Gemini row would report `null`,
  never zero.

## Reproduce

```bash
# one candidate, full suite, writing into the evidence directory
docker compose run --rm -v "$PWD/docs/agencx/evidence/model-benchmark-2026-10:/evidence" \
  backend python -m evals.model_benchmark \
  --models openrouter/deepseek-v4.1-flash --suite all --out /evidence

# aggregate every raw artifact into results.json + summary.md (no network, no DB)
docker compose run --rm --no-deps -v "$PWD/docs/agencx/evidence/model-benchmark-2026-10:/evidence" \
  backend python -m evals.model_benchmark --report-only --out /evidence
```

The capability gate always runs first; `--resume` keeps completed suites and
`--refresh-gate` re-runs a gate that the provider quota disqualified.
`--limit N` is a smoke run and must not be reported as a benchmark.

## Decision

**DeepSeek V4.1 Flash on OpenRouter becomes the fallback leg; Groq is removed
from that slot; the failover leg stays empty.**

- It is the safest candidate measured: injection 0.967, semantic refusal 0.917,
  zero money violations, zero candidate errors.
- It is paid, which is the point - a free fallback that shares the primary's
  quota failure is not a fallback. `LLM_MONTHLY_BUDGET_USD` now applies from its
  first call.
- Its p95 turn of 32.4 s is slow, and slower than Mistral's 17.3 s. Expect
  fallback turns to be visibly slower than primary turns; that was accepted as
  the price of injection resistance and no invented money.
- No candidate passed, so this is a *safety* choice, not a capability upgrade.
  Replacing the primary is out of scope for this benchmark.

Runtime wiring lives in `.env.example`, `docs/agencx/deploy.md`, and
`backend/app/llm/dependency.py` (leg chain, unchanged code).
