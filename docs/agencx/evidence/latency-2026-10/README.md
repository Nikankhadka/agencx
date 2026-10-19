# Latency evidence - October 2026

Evidence for the latency plan (`docs/agencx/spec/active/13-latency.md`).

| File | What it holds |
|---|---|
| [report.md](report.md) | Slice 1 report: instrument, noise floor, matrix, A/B verdict |
| [report-slice-2.md](report-slice-2.md) | Slice 2: the draft output cap, measured no-measurable-effect |
| [design-slice-3.md](design-slice-3.md) | Slice 3 design and post-implementation notes: the discarded agent call, its gate, the retry options; implemented in `cbad1b0`, citations ratified cited-only and internal only (founder ruling 2026-10-19) |
| [report-slice-3.md](report-slice-3.md) | Slice 3: the skipped draft call, a PASS on the mechanism; both founder rulings recorded (cited-only citations; generation FAIL accepted as provider drift) |
| [report-slice-4.md](report-slice-4.md) | Slice 4: retrieval overlap, a PASS structurally with no-measurable-effect on the clock |
| [report-slice-5.md](report-slice-5.md) | Slice 5: stable prompt prefix - injection gate PASS (29/30 = 0.967), cache reads proven, no clock claim |
| [report-slice-6.md](report-slice-6.md) | Slice 6: cache-adjusted cost, the censored paid-tier matrix, ling's structured-output rejection, the Google primary, no winner |
| [report-cumulative.md](report-cumulative.md) | Slices 1-6, baseline vs tip: calls, completion, tokens, the cache proof, the cost model, the model A/B, the eval trio, merge readiness |
| [data/slice2-rounds.md](data/slice2-rounds.md) | Per-turn agent rounds / tool rounds from the slice-2 logs, with the extraction recipe |
| `data/slice2-run{1,2}-lines.jsonl` | The filtered log lines behind `slice2-rounds.md` (source logs were `/tmp`) |
| `data/slice2-run1.json`, `data/slice2-run2.json` | The two slice-2 measurement runs (commit `4f40ef3`) |
| `data/openrouter-deepseek-v4-1-flash__bytefix.json` | The default smoke: one bytefix turn, prices fetched live |
| [data/noise-run1.json](data/noise-run1.json), [data/noise-run2.json](data/noise-run2.json) | Two back-to-back runs of unchanged code, three tenants x five fixed turns |
| [data/noise-floor.md](data/noise-floor.md) | p50/p95 per run and the cross-run tolerance rule |
| `data/matrix-*.json` | One artifact per model x tenant (both candidates x three tenants) |
| [data/matrix.md](data/matrix.md) | The comparison table and its provenance |
| [data/sababa-budget-check.md](data/sababa-budget-check.md) | The pre-matrix daily-budget check for the unraised tenant (slice-1 and slice-2) |
| [data/cost-log-output-tokens.md](data/cost-log-output-tokens.md) | Per-call output-token SQL behind the draft-cap value |
| `data/eval-slice2.log` | The slice-2 `make eval` output (free chain, provider-blocked) |
| `data/eval-slice3-deepseek.log` | The slice-3 `make eval` pinned to deepseek (stalls in generation_eval) |
| [data/eval-blocker-diagnosis.md](data/eval-blocker-diagnosis.md) | Eval-blocker root causes, the failover repro, the crawl numbers, and the baseline mechanism |
| [data/eval-baseline.md](data/eval-baseline.md) | The pre-slice-3 scored baseline: procedure, pinned config, results, and `eval_runs` rows |
| `data/eval-baseline-{generation,trajectory,injection}.log` | The three completed baseline runs |
| `data/eval-baseline-generation-aborted.log` | The first attempt, which aborted on the pre-existing pydantic TypeError |
| `data/eval-scored-smoke-after-fixes.log` | The 6-case scored smoke re-run after the two provider-seam fixes |
| `data/slice5-run{1,2}.json` | The two slice-5 measurement runs (measured at `d99ca54`), with `cached_input_tokens` in the per-turn record |
| `data/slice5-run{1,2}.log` | The runner logs behind those two runs |
| [data/slice5-cache.md](data/slice5-cache.md) | The cache evidence: per-run and per-tenant `cached_input_tokens`, turn 1 always cold, and the sample counts behind the no-clock-claim |
| `data/eval-after-slice5-{generation,injection,trajectory}.log` | The slice-5 after-evals in order of the gate, under the baseline single-leg deepseek pins |
| `data/eval-after-slice5-trajectory-repeat.log` | The identical-code trajectory repeat that bounds the -0.0244 as the harness's own same-code spread |
| `data/eval-after-slice5-generation-aborted.log` | The aborted first generation attempt: a degraded OpenRouter window stalled one case for ~10+ min, killed by the 15-min no-progress watchdog |
| `data/opencode-*-__bytefix.json` | Zen probe skips: the exact catalogue and provider refusal |
| [data/slice6-matrix.md](data/slice6-matrix.md) | Slice 6 paid-tier matrix: both OpenRouter candidates x three tenants, two runs at `2004617`, cache-adjusted cost and the censoring |
| [data/slice6-google.md](data/slice6-google.md) | Slice 6 addendum: the Google gemini-3.5-flash-lite primary, no published price, 10/15 then 2/15 under 429s |
| `data/matrix-slice6-run{1,2}-*.json`, `data/matrix-slice6-google-run{1,2}-*.json` | The per-(model,tenant) matrix artifacts behind the two slice-6 tables, including the Zen skip artifacts |
| `data/slice6-run{1,2}.log`, `data/slice6-matrix-run{1,2}.log`, `data/slice6-google-run{1,2}.log` | The raw runner and report stdout behind the slice-6 tables |
| `data/eval-slice6-ling-trajectory.log`, `data/eval-slice6-ling-trajectory-retry.log`, `data/eval-slice6-ling-runs.psql.txt` | Ling's two aborted trajectory attempts (structured outputs rejected; no `eval_runs` row) and the row-count check that the slice-5 pairing stayed intact |
| [data/gates-slice6.log](data/gates-slice6.log) | The four gate tails at `5a4578a`, the tenant ids (no reseeds) and the newest three `eval_runs` rows per type |
| [data/multiturn.md](data/multiturn.md) | Multi-turn measurement at `3fb604a`: 30 reused-conversation turns, per-turn numbers, cumulative wall time and cache share |
| [report-multiturn.md](report-multiturn.md) | The multi-turn report: serialized UI, no queue, 4/30 completed and 26 budget handoffs, and why no lever has a measured winner |
| `data/multiturn-run{1,2}-openrouter-deepseek-v4-1-flash__*.json` | The six per-(run,tenant) reused-conversation artifacts, plus `data/multiturn-run{1,2}.log` |
| [data/tenant-limits.md](data/tenant-limits.md) | The demo tenants' daily limits and the northgate ABN/GST gap |
| `data/make-check.log` | The `make lint && make typecheck && make test` output |

Reproduce the smoke with `make latency` (one model, one tenant, one turn), the
campaign runs with `make latency LATENCY_MODELS=<label> LATENCY_TENANTS=all
LATENCY_TURNS=5`, and the tables with
`docker compose run --rm --no-deps -v <evidence>:/evidence backend python -m evals.latency_report --data /evidence/data`.
See the plan of record for the widening flags.
