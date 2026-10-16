# Latency evidence - October 2026

Evidence for the latency plan (`docs/agencx/spec/active/13-latency.md`).

| File | What it holds |
|---|---|
| [report.md](report.md) | Slice 1 report: instrument, noise floor, matrix, A/B verdict |
| [report-slice-2.md](report-slice-2.md) | Slice 2: the draft output cap, measured no-measurable-effect |
| `data/slice2-run1.json`, `data/slice2-run2.json` | The two slice-2 measurement runs (commit `4f40ef3`) |
| `data/openrouter-deepseek-v4-1-flash__bytefix.json` | The default smoke: one bytefix turn, prices fetched live |
| [data/noise-run1.json](data/noise-run1.json), [data/noise-run2.json](data/noise-run2.json) | Two back-to-back runs of unchanged code, three tenants x five fixed turns |
| [data/noise-floor.md](data/noise-floor.md) | p50/p95 per run and the cross-run tolerance rule |
| `data/matrix-*.json` | One artifact per model x tenant (both candidates x three tenants) |
| [data/matrix.md](data/matrix.md) | The comparison table and its provenance |
| [data/sababa-budget-check.md](data/sababa-budget-check.md) | The pre-matrix daily-budget check for the unraised tenant (slice-1 and slice-2) |
| [data/cost-log-output-tokens.md](data/cost-log-output-tokens.md) | Per-call output-token SQL behind the draft-cap value |
| `data/eval-slice2.log` | The slice-2 `make eval` output (provider-blocked) |
| `data/opencode-*-__bytefix.json` | Zen probe skips: the exact catalogue and provider refusal |
| [data/tenant-limits.md](data/tenant-limits.md) | The demo tenants' daily limits and the northgate ABN/GST gap |
| `data/make-check.log` | The `make lint && make typecheck && make test` output |

Reproduce the smoke with `make latency` (one model, one tenant, one turn), the
campaign runs with `make latency LATENCY_MODELS=<label> LATENCY_TENANTS=all
LATENCY_TURNS=5`, and the tables with
`docker compose run --rm --no-deps -v <evidence>:/evidence backend python -m evals.latency_report --data /evidence/data`.
See the plan of record for the widening flags.
