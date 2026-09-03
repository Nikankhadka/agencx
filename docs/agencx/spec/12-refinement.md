# Phase 1 refinement (R)

With the three pillars closed (onboarding, chat, business page) and B-4
deployed, this phase is hardening rather than new product surface. It sits
between Phase 1's close and any Phase 2 ticketing - no Phase 2 feature work
happens as a side effect of it.

Tickets in this file:

- R-2: Standard API contract
- R-4: Reliability and provider (partial - see US-2)
- R-5: Operations and security (partial - see US-2)

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

## R-4: Reliability and provider

### Summary

`ChatMessage`/`ToolTurn` now carry the provider's own assistant message
(`extra_content`/`history_message`) and send it back verbatim on the next
turn, instead of the app reconstructing a stripped-down `{role, content,
tool_calls}` message from scratch. That reconstruction was silently dropping
Google's `thought_signature` metadata, which Gemini requires echoed back on
any function-call part of a multi-tool turn.

### Why

Found by G-1's live run (2026-08-22):
`openai.BadRequestError: 400 - Function call is missing a thought_signature
in functionCall parts ... function call
default_api:lookup_order_or_ticket, position 2`. It fired on any turn with
more than one tool call, so `generation_eval`, `trajectory_eval`, and
`injection_eval` all errored out against the primary tier - the deterministic
gates were unaffected, but the tier that most customers actually run against
could not complete a multi-tool turn at all. Failover correctly did not
absorb it (`_FAILOVER_ERRORS` covers rate limits, connection faults, upstream
errors and validation errors, not a provider-specific `BadRequestError`,
which is the right default in general), so this needed a real fix rather than
a retry.

### User stories

#### US-1 A multi-tool turn survives Google's primary tier

**As** a customer whose question needs more than one tool call in a turn,
**I want** the turn to complete instead of erroring out on the provider's own
metadata requirement,
**so that** the primary (free) tier is actually usable for the turns that
need it most.

- [x] `ToolTurn.history_message` / `ChatMessage.extra_content` carry the
  provider's complete assistant message; `agent_node.py` appends
  `turn.history_message` verbatim rather than rebuilding one
- [x] Native, emulated, and no-tool-call paths in `openai_base.py` all
  populate `history_message`, so every provider shape (including ones that
  never carry a `thought_signature`) has one
- [x] A `history_message is None` guard degrades to a safe refusal instead
  of appending `None` into the conversation, if a provider path is ever added
  that forgets to set it

#### US-2 Production-smoke and judge-calibration evidence status

**As** the maintainer,
**I want** an honest, current statement of what evidence exists,
**so that** "done" doesn't imply more verification happened than actually
did.

- [ ] Judge calibration is still blocked on founder hand-labeling
  (circular if agent-generated) - unchanged, not addressed by this ticket
- [ ] Production-smoke evidence beyond the B-4 deploy's own smoke test has
  not been re-run since - unchanged, not addressed by this ticket

### Tests

- `backend/tests/test_llm_tool_calling.py`, `test_llm_failover.py`,
  `test_llm_provider_retry.py`, `test_knowledge_agent.py`,
  `backend/tests/fakes.py` (test double gained `history_message` support)
- `make test-backend` green

### Files touched

- `backend/app/llm/provider.py`, `backend/app/llm/openai_base.py`,
  `backend/app/agents/agent_node.py`

### Definition of done

- [x] A multi-tool turn against Google's primary tier no longer 400s on a
  missing `thought_signature`
- [ ] US-2 (judge calibration, production-smoke evidence) stays open -
  this ticket is partial

---

## R-5: Operations and security (partial - see US-2)

#### US-1 The URL-ingest path can't be turned into an SSRF probe [done]

**As** the platform operator,
**I want** O-3's server-side URL fetch (an owner pastes a link, the backend
scrapes it) to be unable to reach internal/private network addresses,
**so that** an onboarding conversation can't be used to probe the deploy's
own internal network.

- [x] Only absolute `http`/`https` URLs are accepted; scheme and host are
  validated before any network I/O
- [x] DNS resolution is validated - every resolved address must be globally
  routable, non-multicast; a literal IP in the URL is validated the same way
  (`_public_addresses`)
- [x] The connected peer is verified against the validated address after
  connect (`_verify_peer`), closing the DNS-rebinding gap between resolution
  and connection
- [x] Redirects are followed manually, one hop at a time, each hop
  re-validated the same way, bounded at `_MAX_REDIRECTS`
- [x] Only HTML media types are accepted; a 2MB body cap rejects (not
  truncates) oversized pages; every failure surfaces as a safe `ValueError`
  and is logged

**Why**: O-3 scrapes an owner-supplied URL server-side during onboarding.
Before this, redirects were followed only bounded by httpx's own limit, with
no validation that the resolved address - or any address a redirect hop
resolved to - was actually a public, internet-routable host. An onboarding
conversation is unauthenticated-adjacent (the owner is mid-signup) and
world-reachable, so an unvalidated server-side fetch is a classic SSRF
vector into the deploy's own internal network (cloud metadata endpoints,
internal services on the Vercel/Supabase network).

#### US-2 The rest of operations and security [not started]

**Why**: backups/restore, error tracking (a Sentry-class tool), running the
Playwright suite in CI rather than only locally, and dependency scanning are
all named in the `.lavish` closeout draft this backlog is sourced from, and
none currently has a status, owner, or validation command recorded anywhere
canonical.

- [ ] Backups/restore - no status recorded
- [ ] Error tracking - no status recorded
- [ ] E2E in CI (currently local-only, `make test-e2e`) - no status recorded
- [ ] Dependency scanning - no status recorded

**Acceptance signal**: each item above has a status (built / planned /
deliberately deferred), a trigger for when it becomes urgent, and - once
built - a command that proves it (a migration-restore drill, a CI job, a scan
report).

### Tests (US-1)

- `backend/tests/test_url_ingestion.py` - resolution, peer verification,
  redirect-hop validation, media-type and size limits, safe failure logging
- `make test-backend` green

### Files touched (US-1)

- `backend/app/ingestion/url.py`, `backend/app/features/onboarding/controller.py`

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

