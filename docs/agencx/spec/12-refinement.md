# Phase 1 refinement (R)

With the three pillars closed (onboarding, chat, business page) and B-4
deployed, this phase is hardening rather than new product surface. It sits
between Phase 1's close and any Phase 2 ticketing - no Phase 2 feature work
happens as a side effect of it.

Tickets in this file:

- R-2: Standard API contract

---

## R-2: Standard API contract

### Summary

Every JSON error response, across every route, is now RFC 9457 Problem
Details (`application/problem+json`): a stable `code`, a safe `detail` that
never leaks internals, a `request_id` that matches the `X-Request-ID` echoed
on the response, and a `pointer`-addressed `errors` list for validation
failures. SSE streams (`/api/chat`, `/api/onboarding/message/stream`) can't
return a Problem Details response once they've started, so a failure
mid-stream becomes a typed `error` event carrying the same `code`/`detail`/
`request_id` instead of hanging the client or dropping silently. The OpenAPI
schema documents every 4xx/5xx with the `ProblemDetails` shape, and the
generated frontend types (`api-types.ts`) plus `ApiError` carry the same
fields, so a caller no longer guesses at `detail`'s shape.

### Why

Before this, error bodies were ad hoc per route (`{"detail": "..."}`,
sometimes a validation-error list, sometimes nothing but a status code), the
500 handler's body and the health check's body used two different shapes,
and nothing validated an inbound `X-Request-ID` header before trusting it
into logs and responses. A support conversation ("it broke") had no stable
code to search logs by, and a customer whose chat stream failed mid-turn saw
the assistant bubble hang in "streaming" forever with no signal at all.

### User stories

#### US-1 Every JSON error looks the same

**As** a frontend developer or API consumer,
**I want** one error shape everywhere, machine-readable and human-safe,
**so that** I can branch on `code`, show `detail` verbatim, and hand a
support conversation `request_id` without inventing a parser per route.

- [x] `app/shared/errors.py::problem_response` is the single JSON-error
  constructor; `ProblemDetails`/`ProblemError` are the only shapes returned
- [x] FastAPI's `RequestValidationError` and `StarletteHTTPException`
  handlers (`app/main.py`) route every raised error through it, including
  404s, auth failures, and framework-level 4xxs no route explicitly raises
- [x] 401 carries `WWW-Authenticate: Bearer`; 429 carries `Retry-After`; a
  5xx's `detail` is always the safe generic string, never the exception's own
  message
- [x] `/health`'s DB-down path returns the same shape (`503
  service_unavailable`) instead of its own ad hoc body

#### US-2 A request can be traced end to end

**As** whoever is debugging a failure,
**I want** the `request_id` in an error body to be the same id in the logs
and in the `X-Request-ID` response header, and never attacker-controlled,
**so that** correlation is trustworthy.

- [x] An inbound `X-Request-ID` is only trusted if it matches a bounded
  `[A-Za-z0-9._:-]{1,96}` pattern (`observability/logging.py`); otherwise a
  fresh id is generated - unvalidated input never reaches logs or the
  `instance`/`request_id` fields verbatim
- [x] The unhandled-exception fallback in `RequestContextMiddleware` returns
  `problem_response(request, 500)`, not a hand-rolled body

#### US-3 A broken stream doesn't hang the client

**As** a customer or the onboarding owner mid-conversation,
**I want** a mid-stream failure to end the turn with a visible message and a
retry path, not an infinite spinner,
**so that** a backend error never looks like the app froze.

- [x] `/api/chat`'s stream wraps the event generator in a try/except that
  yields a typed `{"type": "error", "code", "detail", "request_id"}` event on
  any exception, and logs it (`chat/api.py` had no logger before this ticket
  - unhandled mid-stream failures were invisible in the logs as well as to
  the customer)
  - **Verify**: `case "error"` exists in `CustomerChat.tsx`'s SSE switch. It
    is easy to add the event on the backend and still leave the frontend
    silently dropping it, since TypeScript's discriminated union isn't
    exhaustively checked against a switch with no `default` - this ticket's
    own first pass did exactly that.
- [x] `/api/onboarding/message/stream` gives its three failure branches
  (`HTTPException`, `LimitTimeout`, bare `Exception`) the same shape; the
  bare-`Exception` branch already logged before this ticket, the other two
  gained `request_id`
- [x] Both SSE sites read the request id through `errors.py`'s
  `request_id(request)` helper (safe fallback to `"unknown"`), not
  `request.state.request_id` directly

#### US-4 The contract is documented and machine-checked

**As** a frontend developer,
**I want** the OpenAPI schema and the generated TypeScript types to describe
the real error shape, and a way to catch drift before it ships,
**so that** `ApiError`'s fields aren't a guess.

- [x] `app.openapi()` is overridden (`main.py::_openapi`) to inject the
  `ProblemDetails` schema into every documented 4xx/5xx response plus a
  `default` fallback, for every route
- [x] `docs/agencx/api-contract.md` documents the shape once, in prose
- [x] `frontend/scripts/gen-api-types.mjs --check` regenerates the schema
  in-memory and diffs it against the committed `api-types.ts` without
  writing, failing the run on drift
  - **Verify**: this needs both a Python/uv toolchain (to import
    `app.main.app` and dump its OpenAPI schema) and a Node toolchain (to run
    `openapi-typescript`) in the same job. Neither the frontend nor the
    backend dev container has both - `--check` cannot live in
    `make lint-frontend` or `make lint-backend`. It runs as its own CI job
    (`.github/workflows/ci.yml`'s `api-types` job)
- [x] `frontend/src/lib/api.ts`'s `throwApiError` parses the Problem Details
  body (`type`/`detail`/`code`/`request_id`/`errors`) using the generated
  `components["schemas"]["ProblemDetails"]` type rather than a hand-written
  shape

### Technical spec

- `backend/app/shared/errors.py` (new) - `ProblemDetails`/`ProblemError`
  pydantic models, `problem_response()`, `validation_problem()`,
  `request_id()`. `validation_problem` indexes a validation error's `loc`
  defensively (`tuple(loc)[:1] == ("body",)`) rather than `loc[0]`, since an
  empty `loc` would otherwise raise inside the error handler itself and turn
  a 400 into a 500.
- `backend/app/main.py` - `RequestValidationError`/`StarletteHTTPException`
  exception handlers; `app.openapi` override injecting `ProblemDetails` into
  the schema (`_error_description` uses `.get(status_code, "Error")`, not
  `[status_code]`, so an undocumented status code can't crash
  `/openapi.json`); `/health` returns `HealthResponse` or, on DB failure,
  `problem_response(request, 503)` (a `Response` subclass bypasses FastAPI's
  `response_model` validation, so mixing the two return types is safe).
- `backend/app/observability/logging.py` - bounded regex validation of an
  inbound `X-Request-ID`; the 500 fallback uses `problem_response`.
- `backend/app/features/chat/api.py` / `onboarding/api.py` - SSE-safe error
  wrapping, both now logging every failure and reading the request id
  through the shared helper.
- `frontend/src/lib/api.ts`, `chat-events.ts`, `onboarding.ts` - `ApiError`
  gained `code`/`requestId`/`errors`; both `ChatStreamEvent` and
  `OnboardingStreamEvent`'s `error` variant require `code`/`detail`/
  `request_id`; `CustomerChat.tsx`'s SSE switch handles it the same way the
  onboarding thread already did.
- `frontend/scripts/gen-api-types.mjs` - `--check` mode.
- `.github/workflows/ci.yml` - new `api-types` job (setup-node + setup-uv,
  `uv sync --frozen --no-group local-ml`, `npm ci`, `gen:types -- --check`).

### Tests

- `backend/tests/test_health.py::test_json_errors_use_problem_details` -
  malformed body, unauthenticated, and unknown-route all return the Problem
  Details shape with the right status/code/headers.
- `backend/tests/test_request_context.py` - the unhandled-500 body matches
  `problem_response`'s shape, not a hand-rolled one.
- `make lint`, `make typecheck`, `make test` (backend + frontend) green.
- CI's new `api-types` job green (proves the committed `api-types.ts`
  matches the schema this ticket's backend changes produce).

### Files touched

- `backend/app/shared/errors.py` (new), `backend/app/main.py`,
  `backend/app/observability/logging.py`,
  `backend/app/features/chat/api.py`,
  `backend/app/features/onboarding/api.py`, `backend/tests/test_health.py`,
  `backend/tests/test_request_context.py`
- `frontend/src/lib/api.ts`, `frontend/src/lib/api-types.ts` (generated),
  `frontend/src/lib/chat-events.ts`, `frontend/src/lib/onboarding.ts`,
  `frontend/src/app/[slug]/CustomerChat.tsx`,
  `frontend/scripts/gen-api-types.mjs`
- `.github/workflows/ci.yml`, `docs/agencx/api-contract.md` (new),
  `docs/agencx/progress.md`, `README.md`

### Definition of done

- [x] Every JSON error response is Problem Details, no route bypasses it
- [x] SSE failures on both streaming routes yield a typed, logged error event
- [x] `X-Request-ID` is validated inbound and correlates body/header/logs
- [x] OpenAPI documents the error shape; generated types match; a CI job
  catches drift
- [x] `make ci` green

---

## Backlog (not yet scoped)

### R-1: Documentation truth

**Why**: `docs/agencx/progress.md` and `spec/` have drifted from the code in
small, verifiable ways - `D-4` (tool-gating tests) is still listed as a live
deferred ticket in `spec/08-deferred.md`, `spec/README.md`, and `progress.md`
though the product decision that would have driven it (per-tenant tool
gating, D-1/D-3) has stayed deferred since it was written; some superseded
designs (the deleted `auth_codes` table, O-5's removed email-extraction
module, P-5's removed `turn_started` event) are recorded in the commit
history but not consistently flagged as historical everywhere they're
mentioned. A build doc that quietly disagrees with the code costs whoever
reads it next the time to discover which one is wrong.

**Acceptance signal**: every phase file and `progress.md` agree with the
current code and with each other - no ticket both "deferred" and absent from
its owning phase file, no design description of something the code has since
deleted without a note saying so, no broken internal links.

### R-3: Schema and type safety

**Why**: Pydantic models across the API layer aren't uniformly
`extra="forbid"`, so an unexpected field in a request body may be silently
dropped rather than rejected - a caller could believe a field was applied
when it wasn't. The generated-types path this ticket (R-2) built for errors
only covers error responses; whether every success response is equally
covered end to end (login, onboarding, ingest, storefront, staff, tenant
isolation) hasn't been audited.

**Acceptance signal**: every request/response model has an explicit,
deliberate unknown-field policy (not an accident of Pydantic's default), and
the generated TypeScript types are the only declared shape for every route's
success response the frontend consumes - no hand-duplicated interface next
to a generated one.

### R-4: Reliability and provider

**Why**: `progress.md`'s "Known gaps" already tracks two open items this
ticket would close or deliberately re-defer: Google's primary tier rejects
multi-tool turns with a missing `thought_signature` (not absorbed by
failover, since `BadRequestError` isn't in `_FAILOVER_ERRORS` - correctly, in
general, since most 400s mean the request is wrong, not the provider), and
judge calibration is blocked on founder hand-labeling. Production-smoke and
live-LLM-eval evidence also needs a current, explicit status rather than
being inferred from when B-4 last ran.

**Acceptance signal**: the `thought_signature` gap has a decision (echo it in
the provider shim, or classify provider-specific 400s as failover-eligible)
recorded even if not yet implemented; the "Known gaps" section states, for
each item, whether it's still true today or has been overtaken by later work.

### R-5: Operations and security

**Why**: backups/restore, error tracking (Langfoo/Sentry-class), running the
Playwright suite in CI rather than only locally, dependency scanning, and
SSRF hardening on the URL-ingest path (O-3 scrapes an owner-supplied URL
server-side) are all named in the `.lavish` closeout draft this phase file's
backlog is sourced from, and none currently has a status, owner, or
validation command recorded anywhere canonical.

**Acceptance signal**: each item above has a status (built / planned /
deliberately deferred), a trigger for when it becomes urgent, and - once
built - a command that proves it (a migration-restore drill, a CI job, a scan
report).
