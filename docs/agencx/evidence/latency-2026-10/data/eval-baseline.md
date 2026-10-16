# Pre-slice-3 scored baseline

**Recorded:** 2026-10-16. **Sha (`git rev-parse HEAD`, host):**
`07c3eca89bf7f3bc8831fc13f7e93a24fb5dc58d`. In-container `git_sha` is empty
(only `./backend` is mounted, so there is no `.git`), which is why the sha is
recorded here rather than read from the `eval_runs` row.

## Pinned configuration (one paid leg)

Applied to all three runs via `docker compose run -e ...`:

| var | value |
|---|---|
| `LLM_PROVIDER` | `openai_compat` |
| `LLM_MODEL` | `deepseek/deepseek-v4.1-flash` |
| `LLM_BASE_URL` | `https://openrouter.ai/api/v1` |
| `LLM_API_KEY` | set (from `backend/.env`'s `OPENROUTER_API_KEY`; its value is never recorded here or in any log) |
| `LLM_FALLBACK_MODEL` | empty (leg disabled) |
| `LLM_FALLBACK_API_KEY` | empty |
| `LLM_FAILOVER_MODEL` | empty |
| `LLM_FAILOVER_API_KEY` | empty |
| `LLM_TTFT_BUDGET_S` | unset -> default `4.0` (`app/shared/config.py:82`) |

`backend/.env`'s own baseline, superseded by the pins above: `LLM_PROVIDER=openai_compat`,
`LLM_MODEL=gemini-3.5-flash-lite` (Google AI Studio), `LLM_FALLBACK_MODEL=openai/gpt-oss-120b`
(Groq).

**Empty disables a leg:** `app/llm/dependency.py:140-141` - `_leg_provider`
returns `None` when a non-primary leg's model is empty. With both fallback and
failover empty, `get_llm_provider` (`dependency.py:152-181`) builds only the
primary and returns it bare, with no `FailoverProvider`, so there is no race and
model identity is deterministic.

**Rationale:** in the raced config the eval answers were a MIX of deepseek and
Groq - deepseek exceeds the 4s first-token budget on most calls, so the Groq
fallback often won - which is not comparable across runs.

## How the evals pick their provider and judge

- All three call `get_llm_provider()`: `generation_eval.py:502`,
  `trajectory_eval.py:612`, `injection_eval.py:285`.
- The same provider is both the answering model and the judge: generation passes
  it into `score_case(..., provider=provider)`, so the judge is the pinned
  deepseek too.
- Embedder/reranker from `get_embedder(settings)` / `get_reranker(settings)`
  (`EMBEDDER=local`, `RERANKER=local`); the eval calls the provider bare, with no
  `TimeLimitedProvider` wrap.
- Tenants: generation and trajectory run against `bytefix`
  (`seed_tenant1_phoneshop.SLUG`); injection against `injection-probe`
  (`seed_injection_probe.SLUG`, `injection_eval.py:277`). **Mismatch recorded:**
  `run_gate._seeded_tenant_id()` (`run_gate.py:144-149`) reads `bytefix` for all
  three run types, so it will not find injection's row (written under
  `injection-probe`) - the injection regression gate is mis-wired; pre-existing,
  not fixed here.

## Procedure

1. `make seed-tenant1` - recreates `bytefix` with a new id. `eval_runs.tenant_id`
   is `on delete cascade` (`migrations/0008_eval_cost.sql:21`), so the two stale
   6-case generation rows are **deleted**, not just hidden: the table holds 0
   rows for generation/trajectory/injection, and the first full run records "no
   baseline - recorded". That single row is what the after-slice-3 run compares
   against (`current` = after-run, `baseline` = this row).
2. generation, then trajectory, then injection, each run individually so a late
   abort does not lose earlier rows; no `--skip-llm`.
3. `injection_eval --reseed` for a clean probe tenant (it held 90 stale
   conversations).

**Trap:** `bytefix` must NOT be reseeded again before the after-slice-3 run, or
the gate silently passes as "no baseline".

## Commands

```
docker compose run --rm -T -e LLM_PROVIDER=openai_compat \
  -e LLM_MODEL=deepseek/deepseek-v4.1-flash \
  -e LLM_BASE_URL=https://openrouter.ai/api/v1 \
  -e LLM_FALLBACK_MODEL= -e LLM_FALLBACK_API_KEY= \
  -e LLM_FAILOVER_MODEL= -e LLM_FAILOVER_API_KEY= \
  backend sh -c 'LLM_API_KEY="$OPENROUTER_API_KEY" python -m evals.generation_eval'
```

The same shape for `evals.trajectory_eval` and `evals.injection_eval --reseed`.

## Results

**Blocked - the generation run aborted at case 31/45, so no baseline was
recorded.** Per the order, the run was stopped, not re-run, and no code was
changed.

Case 1-30 completed (answer + judge); the run writes its `eval_runs` row only
after all 45 cases, so nothing was banked. Wall: ~25 min to 31/45 (~45-50 s per
case, 0 rate-limit retries this run).

The abort:

```
File "/app/evals/generation_eval.py", line 370, in score_case
    relevancy = await answer_relevancy(case.question, answer, provider=provider, embedder=embedder)
File "/app/evals/generation_eval.py", line 225, in answer_relevancy
    generated = await provider.extract(
File "/app/app/llm/openai_base.py", line 598, in extract
    return await _with_retry(_call)
File "/app/app/llm/openai_base.py", line 180, in _with_retry
    return await factory()
File "/app/app/llm/openai_base.py", line 586, in _call
    raise ValidationError.from_exception_data(
TypeError: JsonInvalid: 'error' required in context
```

Root cause: `openai_base.py:586-592` hand-builds a pydantic `ValidationError`
for an unparseable structured output using `type: "json_invalid"` without the
`ctx: {"error": ...}` that type requires, so pydantic raises `TypeError` instead
of the `ValidationError` `_with_retry` catches. The intended resample never runs
and the eval aborts. Pre-existing (the same class as the malformed-output
handling the earlier eval-blocker order touched), not from this branch.

Recommended fix (not applied): give the `line_errors` entry a
`"ctx": {"error": str(error)}`, or raise via
`schema.model_validate(json.loads(content))`, so the resample path fires.

**Not recorded for trajectory or injection** - both judge through the same
`extract`, so either would abort the same way. No `eval_runs` row was written
for any run type. Log: `data/eval-baseline-generation.log`.

