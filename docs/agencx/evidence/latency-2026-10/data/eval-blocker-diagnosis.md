# Eval-blocker diagnosis (distilled)

Distilled from the debugger's gitignored report
`backend/var/eval-debug/REPORT.md` (branch `latency/stack` @ `5d3c5cf`). The
scratch dir is not committed; this doc is the record.

## Verdict

Neither failure was a slice-3/4/5/7 regression. Both are **error-classification
gaps on the provider seam**, and the "deepseek hang" was a **crawl misread as a
hang** because `generation_eval` prints nothing per case.

## Root cause 1 - a fast 5xx (and the server-side malformed-output 400) is not failover-class

- `app/llm/failover.py:59-64` `_FAILOVER_ERRORS = (RateLimitError,
  APIConnectionError, UpstreamResponseError, ValidationError)`.
  `openai.InternalServerError` (503) and `openai.BadRequestError`
  (`json_validate_failed`) are neither. The `if done:` branch
  (`failover.py:192-205` pre-fix) caught only `_FAILOVER_ERRORS`, so a **fast** 503
  propagated and killed the gate with a fallback configured but never tried. The
  **slow** path (`_first_win`, `failover.py:236` pre-fix) catches bare `Exception`, so
  the same 503 after 4s would have failed over - the asymmetry was the bug.
- `app/llm/openai_base.py:155-201` `_with_retry` (pre-fix) catches only
  `UpstreamResponseError | RateLimitError | ValidationError`, so a 503 was not
  retried either. Evidence: `data/eval-slice2.log:118` (generation) and `:216`
  (trajectory) crash on a 503; `:361` crashes on Groq
  `400 ... code: 'json_validate_failed', failed_generation:
  'INJECTION-CANARY-ALPHA'` - the fallback model echoed the injection canary
  instead of JSON, the server-side twin of the client-side `ValidationError` the
  code already resamples.

### Fixes landed (this order, commit `262d21d`)

- `failover.py`: `_is_failover_error()` (`failover.py:67`) = in
  `_FAILOVER_ERRORS` **or** an `APIStatusError` with `status_code >= 500`. The
  fast-path `if done:` branch (`failover.py:210-212`) now catches broadly and
  re-raises unless the predicate agrees. Narrow by design - a generic 4xx still
  propagates. The slow path (`_first_win`, `failover.py:244`) is unchanged.
- `openai_base.py`: `_is_json_validate_failed()` (`openai_base.py:155`) (exactly
  `body.error.code == "json_validate_failed"`) is resampled in `_with_retry`
  (`openai_base.py:172-234`) like the client-side `ValidationError`; a generic
  400 still surfaces.

**Residual (recorded, not fixed on purpose).** The eval-layer retry helpers -
`trajectory_eval.py:444-474` (`_with_rate_limit_retry`) and
`injection_eval.py:169-186` (`_with_retry`) - catch only `RateLimitError` and
`ValidationError`. A 5xx from the LAST leg (there is no further leg to fail
over to) or a repeated canary echo can still abort trajectory/injection. Left
as-is so the baseline and the after-slice-3 run share identical behavior.

### Deterministic repro, before and after

```
docker compose run --rm --no-deps -e PYTHONPATH=/app backend \
  python var/eval-debug/repro_failover_gap.py
```

Before (pre-fix):

```
[gap] primary 503 InternalServerError (Gemini 'high demand'): PROPAGATED InternalServerError   (NO failover)
[gap] primary 400 BadRequestError json_validate_failed (Groq canary echo): PROPAGATED BadRequestError   (NO failover)
[gap] primary 429 RateLimitError (control): FAILOVER OK -> 'FALLBACK-ANSWER'
```

After (fixed):

```
[gap] primary 503 InternalServerError (Gemini 'high demand'): FAILOVER OK -> 'FALLBACK-ANSWER'
[gap] primary 400 BadRequestError json_validate_failed (Groq canary echo): PROPAGATED BadRequestError   (NO failover)
[gap] primary 429 RateLimitError (control): FAILOVER OK -> 'FALLBACK-ANSWER'
```

The 400 still propagates **at the failover seam by design**: it is resampled on
the same leg inside `_with_retry` before the failover layer sees it, so the seam
repro is expected to show no failover for it.

## Root cause 2 - the "deepseek hang" is a crawl

Reproduced the as-run config (deepseek primary via OpenRouter + Groq fallback)
over the full 45-case loop, over ~15 min it reached **case 30/45**, continuously
active:

- failover engagements ("exceeded the 4.0s first-token budget"): **97**
- internal rate-limit retries ("rate-limited; retrying in 20s"): **41**
- hard-429 leg skips: **0**
- largest silent inter-log gap: **26 s**
- rate: **~45 s/case**

The committed-log picture (silence after the weights load, 0% CPU, no
`cost_logs`) is fully explained: `generation_eval` printed nothing per case; 0%
CPU is the 41 backoffs; and **`cost_logs` is empty in evals because no eval opens
a `collect_usage()` sink** (`app/observability/cost.py:105-119`; `grep
collect_usage backend/evals/` is empty), so it is a void signal, not evidence of
a hang. deepseek-v4.1-flash is a reasoning model on large prompts, so it exceeds
the 4s TTFT budget on ~80% of calls (97/120) and races the Groq leg every time,
doubling upstream load. There is no infinite hang: `_first_win` is bounded by
each leg's 60s read timeout and 3-attempt backoff.

### Fix landed (this order)

`generation_eval.py` now prints `[i/N] <question>` per case, mirroring
`injection_eval.py:209`. No scoring change.

## Scored path (proven, unmodified app code)

A 6-case scored generation smoke against deepseek + Groq wrote real metrics and
the `eval_runs` row the gate reads:

```
cases                   6.000
faithfulness            0.910   <- run_gate's generation metric key
answer_relevancy        0.812
citation_faithfulness   0.292
DB: generation | 2026-10-16 11:33:09 | {"cases":6.0,"faithfulness":0.9095,...}
```

`run_gate` sees `current=0.910, baseline=None` -> `regression_pass` returns "no
baseline - recorded" -> PASS. ~4.5 min for 6 cases, so the full 45-case eval is
~30-45 min. Caveat: `generation_eval --gate` uses absolute thresholds
`faithfulness>=0.85` and `answer_relevancy>=0.85` (`generation_eval.py:58-59`),
so the smoke's relevancy 0.812 would fail `--gate` even though `run_gate` passes;
judge the two separately.

**Re-run after this order's fixes:** the same 6-case smoke completed
(faithfulness 0.931, answer_relevancy 0.807, citation_faithfulness 0.542) and now
printed `[i/N]` per case - `data/eval-scored-smoke-after-fixes.log`. State after
it: two `generation` `eval_runs` rows for bytefix's current id, both 6-case; no
`trajectory` or `injection` rows. (Both were later cascade-deleted by the
baseline reseed - see `data/eval-baseline.md`.)

## Free-chain congestion (observed)

Gemini `gemini-3.5-flash-lite` was up but congested: 5-19 s/call, and in a
6-call burst one call received **0 bytes for 30 s**. The 503 is a recurring
capacity spike, not a hard failure (a single call at 10:53 UTC returned 200).
Both classification gaps above are fixed as of `262d21d`, so the free chain is
no longer fatal, but it is still congested - a scored run there would crawl
under the un-raced fallback, so the baseline pins one paid leg instead.

## Caveats

- Results are for the as-run config assumed to be **deepseek primary + Groq
  fallback**; a single-leg deepseek run would 429-crash rather than crawl.
- The Groq canary 400 is **stochastic** - not replayed; the mechanism is proven
  from the response body (`failed_generation == the canary`).
- Absolute wall time tracks **live OpenRouter 429 pressure**, not a fixed bound.

## Deferred (recorded, not fixed)

- **Evals resolve the provider unwrapped** - `get_llm_provider()` returns the
  bare chain; `TimeLimitedProvider` (`app/shared/limits.py:201`) is applied only
  by the app controllers. So an eval has no per-call bound beyond httpx's 60 s.
  Deliberately not changed: the scored baseline and the after-slice-3 run must
  share identical harness semantics, so wrapping the eval provider now would move
  the goalposts. Recorded as the change that would prevent a future misread.
- **Other evals still print nothing per case** (`trajectory_eval`,
  `injection_eval` already prints; `generation_eval` now does). Only
  `generation_eval` was changed, per the order.

## Baseline mechanism (for the next order)

- Storage: the `eval_runs` table (Postgres), columns `tenant_id`, `run_type`,
  `metrics` jsonb, `git_sha`, `created_at`. No env var and no file.
- Read: `run_gate.py::_last_two_metrics(tenant_id, run_type, metric_key)` takes
  the two most recent rows for `(tenant_id, run_type)` -> `(current, baseline)`.
- Decide: `regression_pass` (`run_gate.py`) - `current is None` -> FAIL; `baseline
  is None` -> PASS, "no baseline - recorded"; else FAIL only if
  `current - baseline < -0.03`.
- Keys: `_REGRESSION_GATES = (("generation_eval","faithfulness","generation"),
  ("trajectory_eval","tool_correctness","trajectory"),
  ("injection_eval","pass_rate","injection"))`; the tenant is
  `_seeded_tenant_id()` = **bytefix's current id**.
- Two traps for the next order: (1) the baseline must be a **full run** - the
  only `generation` row today is the 6-case smoke, so a full run would compare
  45 cases against 6 (mismatched); and (2) **do not reseed bytefix** between the
  baseline and the after run - a new tenant id makes the old rows invisible and
  the gate silently passes as "no baseline". No `trajectory` or `injection` rows
  exist yet.
