# Phase 9 - Developer experience (K)

**Status: complete.**

Infrastructure tickets that make the repo easier to run and reason about.
Nothing here touches product behavior.

Tickets in this file:

- K-1: Everything runs in containers

---

## K-1: Everything runs in containers

### Summary

Every `make` target routes through docker compose. `make dev` brings up the
full stack as containers (frontend, backend, db, GoTrue, auth-proxy), `make
stop` brings it down, install/migrate/seed/lint/typecheck/test/eval/e2e all
run inside containers. The host needs only Docker; Node, uv, Postgres and the
dev servers no longer exist natively. Live reload is preserved via bind
mounts.

### Why

One environment everywhere: onboarding is `brew install docker && make demo`,
CI parity stops being aspirational, and "works on my machine" loses its main
ingredient. The native path also drifted (host Node/uv versions, leftover dev
servers holding ports) - containers make the drift impossible.

### User stories

#### US-1 One command up, one command down

**As** a developer or the founder,
**I want** `make demo` / `make dev` to bring the entire stack up as containers,
**so that** running the product locally is one step with no local toolchain.

- [x] Frontend (:3000) and backend (:8000) are compose services with hot
  reload off bind mounts (WATCHPACK_POLLING / WATCHFILES_FORCE_POLLING)
- [x] `make stop` downs everything and keeps volumes (db data survives);
  `make clean` removes volumes and dev images too

#### US-2 All quality gates containerized

**As** the maintainer,
**I want** lint/typecheck/test/eval/e2e green through the same containers,
**so that** local gates and CI exercise identical toolchains.

- [x] Gates run via `docker compose run`; backend deps live in the
  `wren-backend-venv` volume (uv sync), frontend in `wren-node-modules`
- [x] E2E runs in a Playwright container whose loopback mirrors the stack's
  published ports, so specs need no URL rewriting

#### US-3 URLs unchanged

**As** anyone using the running stack,
**I want** every URL and port exactly as before,
**so that** docs, CORS lists and muscle memory keep working.

- [x] Host ports stay 3000/8000/5432/54321/8025/8081; browser-facing URLs stay
  `localhost`; server-side fetches inside containers use internal DNS instead
  (`API_INTERNAL_URL` for the RSC tenant lookup)

### Technical spec

- Dev images are toolchain-only (`backend/Dockerfile.dev`,
  `frontend/Dockerfile.dev`, `docker/Dockerfile.e2e`); dependencies install
  into named volumes so lockfile changes never rebuild an image
- Compose `environment:` overrides win over `.env` files for network
  addresses (pydantic-settings precedence); env_file entries are optional so
  a fresh checkout can still start infra alone
- `SUPABASE_JWT_SECRET` is persisted to the compose project env (`.env`) by
  `scripts/dev.sh`, so any entry point interpolates the same secret -
  otherwise compose recreates auth with an empty one and GoTrue refuses boot
- torch resolves from the CPU wheel index (`[tool.uv.sources]`, declared as a
  direct dep of `local-ml`): PyPI linux wheels drag ~5GB of CUDA packages;
  the CPU index ships the same runtime without them (mac was already CPU-only)
- The e2e runner forwards its own 3000/8000/54321 to the compose services
  because Chromium pins `*.localhost` to 127.0.0.1 regardless of /etc/hosts

### Tests

- `make check` green in containers (lint + typecheck + 704 backend tests +
  vitest suite)
- `make eval-skip-llm` GATE PASSED against seeded db
- Full e2e suite in the Playwright container: 67 passed, remainder pre-existing
  order-dependent flakes reproduced identically with a native runner
- `make stop && make dev`: data survives; bytefix tenant id unchanged

### Files touched

- `docker-compose.yml` (backend/frontend/e2e services + volumes),
  `backend/Dockerfile.dev`, `backend/docker-entrypoint.sh`,
  `frontend/Dockerfile.dev`, `frontend/.dockerignore`,
  `docker/Dockerfile.e2e`
- `scripts/dev.sh` (replaces demo.sh), `scripts/up-infra.sh` (comment refs)
- `Makefile` retargeted; `frontend/src/lib/tenant.ts` internal-URL fallback;
  `frontend/playwright.config.ts` env-overridable base URL;
  `frontend/e2e/business-hub.spec.ts` jsQR decode (BarcodeDetector is absent
  from Playwright Chromium builds); SITE_URL overrides in two paste-a-link specs
- `backend/pyproject.toml` + `uv.lock` (CPU torch index)

### Definition of done

- [x] Host prerequisite list is just Docker
- [x] Every gate green from containers
- [x] Prod image (`backend/Dockerfile`) and deploy workflow untouched
