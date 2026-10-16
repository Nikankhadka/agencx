# Latency evidence - October 2026

Evidence for the latency plan (`docs/agencx/spec/active/13-latency.md`).

| File | What it holds |
|---|---|
| [report.md](report.md) | Slice 1 report: instrument, noise floor, matrix, A/B verdict |
| [report-slice-2.md](report-slice-2.md) | Slice 2: the draft output cap, measured no-measurable-effect |
| [design-slice-3.md](design-slice-3.md) | Slice 3 design (not implemented): the discarded agent call, its gate, the retry options |
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
| `data/opencode-*-__bytefix.json` | Zen probe skips: the exact catalogue and provider refusal |
| [data/tenant-limits.md](data/tenant-limits.md) | The demo tenants' daily limits and the northgate ABN/GST gap |
| `data/make-check.log` | The `make lint && make typecheck && make test` output |

Reproduce the smoke with `make latency` (one model, one tenant, one turn), the
campaign runs with `make latency LATENCY_MODELS=<label> LATENCY_TENANTS=all
LATENCY_TURNS=5`, and the tables with
`docker compose run --rm --no-deps -v <evidence>:/evidence backend python -m evals.latency_report --data /evidence/data`.
See the plan of record for the widening flags.
