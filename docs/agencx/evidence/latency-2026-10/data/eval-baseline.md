# Pre-slice-3 scored baseline

**Recorded:** 2026-10-16. **Rows written at (`git rev-parse HEAD`, host):**
`d152572a9ab7383d98dfd1c1635186ba06a79213` - the malformed-JSON resample + the
injection-gate lookup fix. An earlier header named
`07c3eca89bf7f3bc8831fc13f7e93a24fb5dc58d`, which is only the commit that
prepared this procedure; the first attempt under it aborted at generation case
31/45 before any row was written, so no baseline belongs to that sha.
In-container `git_sha` is empty (only `./backend` is mounted, so there is no
`.git`), which is why the sha is recorded here rather than read from the
`eval_runs` row. The raw rows are committed beside this file:
`data/eval-baseline-runs.psql.txt`.

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
  (`seed_injection_probe.SLUG`, `injection_eval.py:277`). **Fixed in `d152572`:**
  `run_gate` used to resolve `bytefix` for every run type, so it never found
  injection's row; it now resolves the tenant per run type via
  `slug_for_run_type()` (injection -> the probe slug).

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

**Trap, bytefix side:** `bytefix` must NOT be reseeded again before the
after-slice-3 run, or the gate silently passes as "no baseline". `bytefix` is
`e9139d84-0e9f-4282-9af6-e0dc9bf4b56e` and every later run must find it.

**Trap, injection side (the mirror image):** the probe tenant is
`464b8823-e113-4a0b-adef-db70db79d44d` and `injection_eval --reseed` recreates it
under a NEW id, which cascade-deletes the injection baseline row. The
after-slice-3 run must therefore NOT pass `--reseed`, or injection's gate
silently passes as "no baseline" for exactly the same reason. `--reseed` is a
baseline-creating step, never a pre-measurement clean-up.

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

## Prior attempt (aborted)

The first attempt aborted at generation case 31/45 on the pre-existing
`TypeError: JsonInvalid: 'error' required in context` (`openai_base.py:586`,
fixed in `d152572`), so no row was written. That log is preserved as
`data/eval-baseline-generation-aborted.log`.

## Result (rerun at `d152572a9ab7383d98dfd1c1635186ba06a79213`)

All three runs completed, no abort.

| run | cases | key metric | other metrics | wall |
|---|---|---|---|---|
| generation | 45 | faithfulness **0.7475** | answer_relevancy 0.7356, citation_faithfulness 0.3207, negative_cases 12, refusal_accuracy 0.000 | 24m18s |
| trajectory | 41 | tool_correctness **0.6341** | persona_quality 1.000, step_efficiency 0.9715 | 7m40s |
| injection | 30 | pass_rate **0.9667** (29/30) | pass_rate_direct 0.9565, pass_rate_indirect_chunk 1.000, pass_rate_indirect_tool 1.000 | 7m11s |

Wall times are log birth -> mtime (`data/eval-baseline-<type>.log`).

`eval_runs` rows:

| slug | run_type | metrics | created_at (UTC) |
|---|---|---|---|
| bytefix | generation | `{"cases":45.0,"faithfulness":0.7474…,"answer_relevancy":0.7356…,"citation_faithfulness":0.3207…,"negative_cases":12.0,"refusal_accuracy":0.0}` | 2026-10-16 13:05:56 |
| bytefix | trajectory | `{"cases":41.0,"persona_quality":1.0,"step_efficiency":0.9715…,"tool_correctness":0.6341…,"avg_cost_usd":0.0,"total_cost_usd":0.0}` | 2026-10-16 13:19:44 |
| injection-probe | injection | `{"cases":30,"passed":29,"pass_rate":0.9666…,"pass_rate_direct":0.9565…,"pass_rate_indirect_tool":1.0,"pass_rate_indirect_chunk":1.0}` | 2026-10-16 13:32:12 |

`git_sha` in every row is empty (no `.git` in the container); the sha above is
the attribution. The same three rows as raw `psql` output (with tenant ids):
`data/eval-baseline-runs.psql.txt`.

## Comparability notes (baseline vs the after-slice-3 run)

- **Case counts are a guard, not a detail.** The baseline is 45 generation / 41
  trajectory / 30 injection cases and every number in `metrics` is a ratio over
  its own case count, so a shorter run cannot be compared against it: verify
  45 / 41 / 30 on the after-run before reading any delta. (The 6-case smoke that
  briefly sat in this table is the trap this guard exists for.)
- **The slice-3 verdict is read off the full metric row, `citation_faithfulness`
  first** - the citations behaviour is what slice 3 changes - then the rest of
  the row (`faithfulness`, `answer_relevancy`, `refusal_accuracy`,
  `negative_cases` for generation; `tool_correctness`, `persona_quality`,
  `step_efficiency` for trajectory; `pass_rate` plus the `pass_rate_*`
  sub-metrics for injection). It is NOT read off `run_gate`'s PASS/FAIL: that
  compares only the gated key per run type (generation `faithfulness`,
  trajectory `tool_correctness`, injection `pass_rate`) at a -0.03 tolerance and
  prints "no baseline" when it cannot find a row - so a missing row and a clean
  run look alike until the rows are read directly.
- One paid leg pinned for all three (`deepseek/deepseek-v4.1-flash`; fallback and
  failover empty) - the after-run must use the same pins, so every answer is one
  model rather than a mix.
- Same harness semantics: per-case progress and the unwrapped eval provider,
  unchanged.
- **No reseed between now and the after-run.** `bytefix` is `e9139d84-…` and must
  stay; a reseed would cascade-delete these rows and the after-run would pass as
  "no baseline". Injection's probe tenant is `464b8823-…` (reseeded here); the
  gate resolves it correctly now that `run_gate` maps `injection` to the probe
  slug.
- Residual-abort caveat: the eval-layer retry helpers catch only
  `RateLimitError`/`ValidationError`, so a last-leg 5xx or a repeated canary echo
  can still abort trajectory/injection. None happened this run.
- **Slice 5's injection number:** the fresh measured `pass_rate` is **0.9667**
  (29/30), close to the founder's stated 0.967; use this as the re-measured
  value.

## Anomalies

- The generation run exercised the new malformed-JSON resample once
  (`malformed structured output; resampling`) and continued - the fix working.
- `refusal_accuracy` is 0.000 on generation's 12 negative cases (every refusal
  case scored a non-refusal). It is not a `run_gate` key (`faithfulness` is), but
  it is a quality finding worth flagging.
- `generation_eval --gate`'s absolute thresholds (faithfulness/relevancy >= 0.85)
  are above this baseline (0.748/0.736), so `--gate` fails while `run_gate`
  (regression mode) records it as "no baseline". Judge the two separately.


