# Final evaluation - PRT691, 2026-10-08

Evidence for slide 10 and the appendix test plan. Target tenant: `sababa2` (fast path, 96 items), local demo stack. Start with `report.md`.

| Path | What it is |
|---|---|
| `report.md` | The single combined report: rounds 1 to 3, money checks, latency, failures quoted in full, open items |
| `deck-content.md` | Slide 10 text and the appendix test plan, ready to paste |
| `plan/stories.md` | Pre-registered success stories (written before any live run) |
| `plan/tester-kit.md` | Brief for QA teammates and the business manager |
| `plan/human-findings.csv` | Shared log for human testers (empty until sessions run) |
| `data/round1-sababa2-first-pass.jsonl` | Round 1 raw per-turn data, first pass (11 turns blocked by the provider quota) |
| `data/round1-sababa2-rerun.jsonl` | Round 1, the 11 blocked turns re-run on a second key |
| `data/round2-sababa2.jsonl` | Round 2 raw data, 44 turns (includes `price_summary` payloads) |
| `data/round3-sababa2-partial.jsonl` | Round 3 raw data: 27 valid turns, 7 blocked by the tenant token cap |
| `data/tenant-routes.json` | Which tenants take the fast path and which take hybrid retrieval |
| `data/layer-a-checks/` | Logs of `make check`, the deterministic eval gate and the tenant 1 seed |
| `data/layer-b-probes/` | Early live probes (S1 story, one cross-tenant probe) |

Datasets live with the code in `backend/evals/datasets/`: `sababa2_demo.jsonl` (round 1), `sababa2_round2.jsonl` (round 2), `sababa_extended_r3.jsonl` (round 3).

The pre-fix baseline this evidence is compared against is `../sababa-chat-eval-interim.md`.

No API keys appear in any file here. Rotate the Gemini key before the demo.
