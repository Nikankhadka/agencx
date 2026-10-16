# Latency evidence - October 2026

Evidence for the latency plan (`docs/agencx/spec/active/13-latency.md`).

| File | What it holds |
|---|---|
| [report.md](report.md) | Slice 1 report: the instrument, the smoke record, and findings |
| `data/openrouter-deepseek-v4-1-flash__bytefix.json` | One turn on bytefix with `deepseek/deepseek-v4.1-flash` pinned, plus the provider prices fetched live at run time |

Reproduce the smoke the artifact came from with `make latency` (one model, one
tenant, one turn). See the plan of record for the widening flags.
