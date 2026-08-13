# Phase 5: Evaluation, Generalization, Deploy

**Calendar slot:** Spill-over best-effort on top of a green month. Minimum deliverable: `make eval` reporting real numbers.

## Goal

The eval harness is wired: generation eval, trajectory eval, injection and leakage evals run in CI and report real numbers. The generalization proof is demonstrable: a cleaner and a dental clinic onboard via the public path alone with zero code change. The backend is deployed to AWS ECS. Frontend host decision is made and executed. Artifacts (eval report, security write-up, LEARNINGS) are produced.

## Tickets

| Ticket | Name | What it delivers | Files/modules | Depends on |
|---|---|---|---|---|
| T-032 | Generation eval | Runs the real assistant graph over held-out `eval_cases` (case_type `generation`), judged by a judge model via `LLMProvider.extract()`. Metrics: faithfulness, answer relevancy, citation-faithfulness. Regression-gated (±3-point budget). Refusal cases score 0.0 on positive cases. | `backend/evals/generation_eval.py` | T-029 |
| T-033 | Trajectory eval + cost | Runs real conversations through the graph (`stream_mode="updates"`) and checks: node path correctness, tool-call correctness, step efficiency, cost per conversation (from `cost_logs`). Regression-gated. | `backend/evals/trajectory_eval.py` | T-029 |
| T-034 | Injection + leakage evals | Direct/indirect-chunk/direct-tool injection families run through the real stack. Gate: pass rate >= 0.967 (Wren's 29/30 golden record). Leakage suite: 100/100 both directions with positive controls (absolute gate). | `backend/evals/injection_eval.py`, `backend/evals/leakage_eval.py` | T-032 |
| T-035 | run_gate + CI eval job + safety caps | `make eval` target runs all eval layers; absolute gate failures fail CI; regression beyond ±3 fails CI; cost logging wired for all eval runs; safety caps (token limits, per-conversation cost ceiling). Never-skipped rule enforced. | `Makefile` (eval target), `.github/workflows/eval.yml`, `backend/evals/run_gate.py` | T-033, T-034 |
| T-036 | Generalization proof | Seed a cleaning business tenant and a dental clinic tenant through the conversational onboarding flow + uploads (raw inputs, never direct table writes). Both reach go-live. Both can hold grounded conversations on their public pages. The `git diff` between them is empty - a code change required is a bug in I8. | `backend/seeds/seed_generalization.py` (inputs), generalization proof documented in artifact | T-031 |
| T-037 | Deploy (ECS, frontend host decision) | Backend deployed to AWS ECS via Wren's Terraform. Frontend host decision resolved (Cloudflare Pages via `next-on-pages`, or paid Vercel) and deployed. | `infra/*.tf`, frontend deployment config | T-035 |
| T-038 | Artifacts | Eval report (all numbers with git_sha, free-tier limitations, honest about live vs persisted observations), security write-up (RLS, import boundary, money guardrail, injection defense), LEARNINGS (what Wren got right, what changed, what the free tier held down). | `docs/artifacts/eval-report.md`, `docs/artifacts/security-write-up.md`, `docs/artifacts/LEARNINGS.md` | T-036, T-037 |

## Gate

- [ ] `make eval` runs all eval layers and reports real numbers
- [ ] Leakage: 100/100 both directions (absolute)
- [ ] Money air-gap: 100/100 (zero model-authored figures; absolute)
- [ ] Injection: pass rate >= 0.967 (golden record)
- [ ] Generation and trajectory metrics within ±3-point regression budget of baseline
- [ ] Absolute gates never skipped in CI
- [ ] Generalization proof: cleaning tenant and dental clinic tenant onboard via public path alone, zero code change
- [ ] Backend deployed; frontend host decided and deployed
- [ ] Three artifacts produced

## Done when

- [ ] Seven tickets complete
- [ ] `make eval` green in CI: all absolute gates pass, all regression metrics within budget
- [ ] Two generalization tenants onboard via public path without code change
- [ ] Backend live on ECS; frontend live on chosen host
- [ ] Eval report, security write-up, and LEARNINGS written
- [ ] Fits or observed slip
