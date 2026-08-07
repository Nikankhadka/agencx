# Backend Restructure (scoped): api/ -> features/, core/ -> shared/

Restructure only two packages of `backend/app/`: type-based `api/` -> feature-based `features/` (3-file split per feature) and `core/` -> `shared/`. Everything else (`agents/`, `llm/`, `retrieval/`, `pricing/`, `ingestion/`, `onboarding/`, `observability/`) **stays exactly where it is** - it will follow the same idea later. Pure relocation: zero behavior change, no repository layer, no logic rewrite. Package root stays `backend/app/` (imports stay `from app...`). Idiomatic Python filenames. tests/seeds/evals stay top-level, imports updated only where they point at `app.core` / `app.api`.

## Target layout (only what changes)

```
backend/app/
├── main.py                          (stays; router imports rewritten)
├── shared/                         (from core/  <- observability, agents STAY)
│   ├── config.py  db.py  auth.py  limits.py  migrate.py  startup.py
├── features/
│   ├── tenants/      api.py, public_api.py, controller.py, service.py   [from api/tenants.py + api/public.py]
│   ├── platform/     api.py, controller.py, service.py                  [from api/platform.py]
│   ├── onboarding/   api.py, controller.py, service.py                  [from api/onboarding.py]
│   ├── knowledge/    api.py, controller.py, service.py                  [from api/knowledge.py]
│   ├── chat/         api.py, controller.py, service.py                  [from api/chat.py]
│   ├── conversations/ api.py, controller.py, service.py                 [from api/conversations.py]
│   ├── escalations/  api.py, controller.py, service.py                  [from api/escalations.py]
│   ├── pricing/      api.py, controller.py, service.py                  [from api/pricing.py]
│   └── dashboards/   api.py, controller.py, service.py                  [from api/dashboards.py]
└── (unchanged: agents/, llm/, retrieval/, pricing/, ingestion/, onboarding/, observability/)
```

Per-feature file roles:
- `api.py` - FastAPI router + request/response pydantic schemas + Depends wiring
- `controller.py` - handler logic (what today sits in the api/*.py handler bodies)
- `service.py` - the logic handlers call: DB access (SQL via `db.tenant_context`), orchestration of existing packages (`app.agents`, `app.ingestion`, `app.onboarding`, `app.llm`, `app.retrieval`) - imports of those stay unchanged

Feature-specific notes:
- **tenants**: `api/tenants.py` + `api/public.py` both land here (one tenant domain, two routers). Slug resolution (`_resolve_active_tenant` logic via `resolve_tenant_slug` db fn) + `invalidate_slug_cache` live in `tenants/service.py` - reused by chat, conversations, and platform via the two sanctioned cross-feature edges below. `public_api.py` holds the unauthenticated slug router.
- **chat**: `api/chat.py` splits at the existing seams: `ChatRequest`/`PublicMessage`/router -> `api.py`; the SSE streaming generators (`_stream_chat_response`, `_stream_budget_escalation`, `_stream_escalated_response`, `_record_limit_escalation`) -> `controller.py`; graph invocation, initial-state build, and DB persistence helpers -> `service.py`. Graph still imported from `app.agents.*` (unchanged).
- **dashboard**: `GATE_THRESHOLDS` -> `dashboards/service.py`.
- **all others**: router file -> 3 files; SQL currently inline in handlers moves into `service.py`, handler bodies into `controller.py`.
- **migrate.py** lands at `app/shared/migrate.py`: depth invariant `parents[2] == backend` still holds (`app/core` and `app/shared` are both 2 levels deep). Do not move deeper. Test `test_migrations.py` pins it.

Only two sanctioned cross-feature edges (both unidirectional, both to tenants, pricing-style leaves otherwise):
1. `chat.features.service` + `platform` -> `tenants.service` (slug resolve / invalidate cache)
2. No other feature imports another feature.

## Execution order (one commit per milestone, `git mv` for every move)

Gate every milestone: `cd backend && uv run ruff check . && uv run mypy && uv run pytest -q`.

**M0 baseline** - clean `git status`; record `make check` green.

**M1 core -> shared** - `git mv` all of `core/*` -> `app/shared/`; global rewrite `app.core` -> `app.shared` (backend/app, backend/tests, backend/seeds, backend/evals); update `Makefile:52`, `ci.yml:150`, `scripts/demo.sh:134`, `AGENTS.md:36` (`app.core.migrate` -> `app.shared.migrate`); delete emptied `core/`. Gate + grep-zero `app\.core`.

**M2 tenants** - `api/tenants.py` + `api/public.py` -> `features/tenants/{api,public_api,controller,service}.py`; slug logic + cache -> `service.py`. Rewrite `app.api.tenants` -> `app.features.tenants.api` and `app.api.public` -> `app.features.tenants.public_api` (only importer: main.py). Gate.

**M3 platform** - `api/platform.py` -> `features/platform/`; hand-fix the internal edge `from app.api.public import invalidate_slug_cache` -> `from app.features.tenants.service import invalidate_slug_cache`. Gate.

**M4 thin features** - escalations, conversations, dashboards -> `features/<f>/{api,controller,service}.py` (`GATE_THRESHOLDS` -> `dashboards/service.py`; fix `tests/test_dashboards_api.py`). Gate.

**M5 pricing** - `api/pricing.py` -> `features/pricing/`. Gate.

**M6 knowledge** - `api/knowledge.py` -> `features/knowledge/` (imports `app.ingestion`, `app.llm` unchanged). Gate.

**M7 onboarding** - `api/onboarding.py` -> `features/onboarding/` (imports `app.onboarding`, `app.ingestion`, `app.llm` unchanged). Gate.

**M8 chat (largest)** - `api/chat.py` -> `features/chat/{api,controller,service}.py`; fix the 2 test symbol imports (below). Gate.

**M9 finish** - rewrite `main.py` import block; delete emptied `api/`; grep-proof; full verification; doc/tooling sweep (below).

## main.py new import block

```python
from app.features.tenants.api import router as tenants_router
from app.features.tenants.public_api import router as public_router
from app.features.platform.api import router as platform_router
from app.features.onboarding.api import router as onboarding_router
from app.features.knowledge.api import router as knowledge_router
from app.features.chat.api import router as chat_router
from app.features.conversations.api import router as conversations_router
from app.features.escalations.api import router as escalations_router
from app.features.pricing.api import router as pricing_router
from app.features.dashboards.api import router as dashboards_router
# app.core.* -> app.shared.* (db, config, startup, logging from shared)
# llm/retrieval/observability imports unchanged
```

## Import rewrite rules (global over backend/app + tests + seeds + evals, in order)

- `app.core` -> `app.shared` (R1, at M1)
- `app.api.tenants` -> `app.features.tenants.api` (M2)
- `app.api.public` -> `app.features.tenants.public_api` (M2)
- per-feature: `app.api.<f>` -> `app.features.<f>.api` (M3-M8)

Manual (symbol moves, not path moves):
- `tests/test_limits_api.py`: `app.api.chat._stream_budget_escalation, _stream_chat_response` -> `app.features.chat.controller`
- `tests/test_validation_gate.py`: `app.api.chat.ChatRequest` -> `app.features.chat.api`
- `tests/test_dashboards_api.py`: `app.api.dashboards.GATE_THRESHOLDS` -> `app.features.dashboards.service`
- `app/api/platform.py`: `invalidate_slug_cache` comes from `app.features.tenants.service`
- `frontend/scripts/gen-api-types.mjs`: imports `app.main` - unchanged
- Confirmed clean: `from app.main import app` (13 tests) untouched; no other `app.api` importers exist anywhere (verified by grep)

## Refactor approach & tooling / doc updates

Update the plan's tooling section: `Makefile`/`ci.yml`/`demo.sh` only change once (the migrate path, M1). `AGENTS.md` command-table line update.
`backend/README.md`: replace package list (features/ + shared/ + unchanged rest). `docs/phases/phase-1-foundations.md`: update the layout contract + path pins. `.agents/map.md`: hand-refresh tree (no regen tool - header note "hand-refreshed after backend restructure"). `.agents/memory.md`: stale path pins. `docs/PROGRESS.md`: restructure row. `Dockerfile`, `pyproject.toml`, `frontend/`: no change (uvicorn app.main:app; pytest pythonpath; tokens).

## Verification

1. Per-milestone gate: `make lint-backend` && `make typecheck-backend` && `make test-backend` (db tests need `make db` once).
2. `make format-check` + `make check`.
3. DB pipeline: `make db` -> `make migrate` (proves `app.shared.migrate` + depth invariant) -> `make seed-tenant1` + `make seed-tenant2` (proves seeds -> app.shared.db still resolve).
4. Eval gate: `make eval-skip-llm` (evals import `app.agents`, `app.llm`, `app.shared` - unaffected graph build).
5. Boot: `uv run uvicorn app.main:app --port 8100` -> curl `/health` 200; `python -c 'import app.main'`.
6. grep-proof: `grep -rnE 'from app\.(api|core)' backend --include='*.py'` -> zero.
7. `git log --follow backend/app/features/tenants/api.py` shows the original api/tenants.py lineage.
8. Smoke a chat turn via `scripts/demo.sh` (or curl the SSE endpoint) to prove the chat feature wiring end-to-end.