# Latency evidence - October 2026

Evidence for the latency plan (`docs/agencx/spec/active/13-latency.md`).

| File | What it holds |
|---|---|
| [report.md](report.md) | Slice 1 report: the instrument, the smoke record, and findings |
| `data/openrouter-deepseek-v4-1-flash__bytefix.json` | One bytefix turn with `deepseek/deepseek-v4.1-flash` pinned, plus the provider prices fetched live at run time |
| `data/opencode-ling-3-1-flash-free__bytefix.json` | Zen probe skip: the model is absent from the live catalogue (ids in the file) |
| `data/opencode-space-bunny-free__bytefix.json` | Zen probe skip: the model is listed but the endpoint refuses non-OpenCode clients |
| [data/tenant-limits.md](data/tenant-limits.md) | The demo tenants' daily limits, the commands that applied them, and the northgate ABN/GST gap |
| `data/make-check.log` | The `make lint && make typecheck && make test` output behind the green claim |

Reproduce the smoke with `make latency` (one model, one tenant, one turn), and
the probes with `make latency LATENCY_MODELS=opencode/ling-3.1-flash-free,opencode/space-bunny-free`.
See the plan of record for the widening flags.
