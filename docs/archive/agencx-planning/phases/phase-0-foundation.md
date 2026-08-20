# Phase 0: Foundation

**Calendar slot:** Week 0 (days 1-2)

## Goal

A working monorepo with Postgres+pgvector running locally via Supabase CLI, a Makefile that builds, and CI enforcing the import boundary and token guard from the first commit. At the end, `make dev` starts Postgres and the backend, `make check` runs lint+typecheck, and CI is green.

## Tickets

| Ticket | Name | What it delivers | Files/modules | Depends on |
|---|---|---|---|---|
| T-001 | Monorepo scaffold | `backend/` (Python/FastAPI/uv), `frontend/` (Next.js+TS+Tailwind), shared config, `.env.example` | `backend/pyproject.toml`, `frontend/package.json`, `Makefile`, `.env.example` | - |
| T-002 | Supabase + pgvector + /health | Supabase CLI local dev with Postgres + pgvector, a `/health` endpoint in FastAPI, frontend dev server | `supabase/config.toml`, `backend/app/main.py`, `backend/app/routes/health.py` | T-001 |
| T-003 | Makefile + .env.example | `make dev`, `make check`, `make test`, `make migrate`, `make seed`; env template | `Makefile`, `.env.example`, `backend/app/core/config.py` | T-001 |
| T-004 | CI + import-boundary + token guard | GitHub Actions workflow; import-linter rule forbidding `llm/provider.py` imports outside `agents/` and `llm/`; ESLint `no-restricted-imports` on frontend; `check-tokens.mjs` wired as `npm run check:tokens` | `.github/workflows/ci.yml`, `backend/.importlinter`, `frontend/scripts/check-tokens.mjs`, `frontend/eslint.config.mjs` | T-001 |

## Gate

- [ ] `make dev` starts Postgres (via Supabase CLI), backend, and frontend
- [ ] `make check` passes (lint + typecheck + import-boundary)
- [ ] CI is green on every branch (lint, typecheck, import-boundary, token guard)
- [ ] Import-linter forbidding `llm/provider.py` outside `agents/` and `llm/` is wired and enforced
- [ ] `check-tokens.mjs` fails the build if a color literal appears in `src/` outside `theme.css`
- [ ] Supabase local setup includes pgvector extension

## Done when

- [ ] Four tickets complete (one commit each)
- [ ] `make dev` works from a clean clone
- [ ] CI green
- [ ] Fits or observed slip
