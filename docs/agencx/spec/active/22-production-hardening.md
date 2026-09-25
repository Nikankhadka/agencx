# 22: Production hardening - abuse control, data lifecycle, deploy safety net

**Status:** Active - in progress. T-022 to T-026 are built; the rest are
queued in the build order below.
**Phase 1 area:** Operations and security (closes the four open boxes in
[R-5](12-refinement.md)).

Numbering note: 21 is category management, so 22 is the next free ticket and
D32 is the next free ADR. Ticket ids T-022 to T-033 are local to this file and
do not collide with the original T-series, which is archived.

## Summary

The product works and is deployed, but it was built to prove itself, not to
hold paying tenants' customer data. An audit found three gaps that block
onboarding real clients:

1. **No abuse control.** `POST /api/chat` and the transcript poll are
   unauthenticated by design, had no rate limit, and `ChatRequest.message` had
   no maximum. The Vercel project has no firewall config, and `/docs` plus
   `/openapi.json` published the whole API surface in production.
2. **No privacy or data-lifecycle surface.** No privacy policy or terms, no
   retention policy, no way for an owner to delete a customer conversation, no
   way to export or offboard a tenant. Customer chat text accumulated verbatim
   and forever in `messages.content`.
3. **No safety net under the deploy.** No error tracking on either surface, no
   dependency or secret scanning, no `permissions:` block in CI, and no written
   backup, RPO, RTO or restore drill.

**Out of scope, by the founder's instruction:** billing, and escalation
notifications (email, SMS, webhook). Nothing here touches either.

## Confirmed decisions

- **Error tracking:** Sentry on both surfaces, off by default when `SENTRY_DSN`
  is unset (the Langfuse no-op pattern).
- **Deletion:** the owner deletes one customer conversation self-serve. Whole
  tenant deletion is an operator-run script plus a documented request process
  and SLA, not a button.
- **Quoted conversations are protected:** the owner delete answers 409 when the
  conversation has quotes, keeping the tamper-proof-quote invariant from
  migration `0006`. Those go through the operator path. No migration needed.
- **Retention:** a `python -m` module, dry run by default, a `make` target and a
  written policy. No scheduler, no authed purge endpoint, no new production
  secret.
- **Legal text:** full drafted prose with entity name, ABN and jurisdiction as
  marked placeholders. Not legal advice; a lawyer reviews before real clients
  sign up.

## Build order and status

One ticket is one commit on its own `<type>/<slug>` branch off `development`.

| Order | Ticket | Scope | ADR | Status |
|---|---|---|---|---|
| 1 | T-022 | Per-IP rate limit, 2000-char chat cap, docs off in production | D32 | Built |
| 2 | T-023 | CI `permissions`, Dependabot, dependency review, secret scanning note | - | Built |
| 3 | T-024 | Backend Sentry | D33 | Built |
| 4 | T-025 | Frontend Sentry | D33 | Built |
| 5 | T-026 | Security headers and report-only CSP | D34 | Built |
| 6 | T-028 | Conversation delete, backend | D35 | Queued |
| 7 | T-029 | Conversation delete, console UI | D35 | Queued |
| 8 | T-030 | Retention module and policy | D36 | Queued |
| 9 | T-031 | Operator export and offboard scripts | D35 | Queued |
| 10 | T-032 | Privacy policy and terms pages | - | Queued |
| 11 | T-027 | Enforce the CSP (after T-026 is on a real deploy) | D34 | Queued |
| 12 | T-033 | Backups: facts, proof command, restore drill | - | Queued |

## T-022: Per-IP abuse control on the public routes

Built. The decision, its numbers, both fail-open rules and the list of what it
does not stop are in [D32](../../design/decisions.md).

- `backend/app/shared/ratelimit.py`: one `BaseHTTPMiddleware`, wired innermost
  in `backend/app/main.py`. Buckets `chat` 12, `poll` 120, `public_read` 120,
  `default` 600 per 60s, `/health` exempt, `0` = unlimited, six `RATE_LIMIT_*`
  settings, all in `.env.example`.
- The address is the first entry of `x-vercel-forwarded-for`; absent header
  means not limited, with a one-shot production warning.
- `ChatRequest.message` capped at 2000 characters (existing 422 above it).
- `/docs`, `/redoc`, `/openapi.json` off when `ENVIRONMENT=production`, via the
  pure helper `docs_enabled`. `app.openapi()` is untouched, so `gen:types`
  still runs.

**Verification:** 31 tests in `backend/tests/test_ratelimit.py` (classifier,
counter, bound and sweep, `0` limit, middleware over a stub app with the real
`RequestContextMiddleware` outside it, kill switch, `/health`, docs helper,
message cap); `make lint-backend`, `make typecheck-backend`, `make format-check`
and `make test-backend` green. Live against the dev backend with the trusted
header set: 12 responses then a 429 `application/problem+json` with
`retry-after: 60`, an `x-request-id` and `code: rate_limited`; without the
header 14 of 14 pass; a 2001-character message is a 422 `string_too_long`.
`make test-e2e` is the guard for the one behavioural risk, a second
`BaseHTTPMiddleware` layer wrapping the SSE chat stream; its e2e run sends no
trusted header, so it proves pass-through streaming, not rejection.

**Founder action after deploy:** add a Vercel WAF rate-limit rule on
`POST /api/chat` as the real spend control (see D32). Confirm the production
log shows no "rate limiting is inactive" warning, which would mean the trusted
header is not arriving.

## T-023: CI hygiene

Built.

- `ci.yml` gains a top-level `permissions: contents: read`. It was the only one
  of the four workflows without one; `deploy.yml`, `keep-warm.yml` and
  `registry-cleanup.yml` already declared it and need nothing more (the last
  authenticates with `VERCEL_TOKEN`, not the workflow token).
- New PR-only `security` job in `ci.yml`: `actions/dependency-review-action@v5.0.0`,
  `fail-on-severity: high`, `comment-summary-in-pr: on-failure`, with its own
  `contents: read` + `pull-requests: write` (the reason it is a separate job).
  Pinned to the full tag because the action publishes no floating `v5`. Not
  `continue-on-error`: it fires only on what a PR newly introduces.
- New `.github/dependabot.yml`: `uv` (`/backend`), `npm` (`/frontend`),
  `github-actions` (`/`), `docker` (`/backend`, `/frontend`); weekly Monday,
  `deps` commit prefix, one grouped minor-and-patch PR per ecosystem, majors
  ungrouped, open-PR limits 3 / 3 / 2 / 1 / 1. The Node-in-two-files and
  pgvector-not-scanned gaps are written into the file as comments.
- No CI secret scanner: secret scanning and push protection were already on, and
  Dependabot alerts were switched on (they were off). All three are recorded in
  `deploy.md` Step 7 with the readback commands.

**Verified on PR #47:** the `security` job ran green and read the workflow
change (`actions/dependency-review-action@5.0.0`). GitHub's dependency graph
(`gh api repos/Nikankhadka/agencx/dependency-graph/sbom`) lists 104 PyPI, 522
npm and 6 GitHub Actions packages, so `backend/uv.lock` is parsed and no
backend-only `osv-scanner` step is needed. That PR changed no dependencies, so a
red run on a vulnerable Python bump has not been seen yet.

## T-024 and T-025: Error tracking (D33)

**T-024 (backend) is built.** `sentry-sdk==2.70.0`,
`backend/app/observability/sentry.py`, one `capture_exception()` line in
`RequestContextMiddleware`, `sentry_dsn` in `config.py` and `.env.example`.
Beyond the plan, `include_local_variables=False` is set: the SDK default
attaches stack-frame locals, which would have carried the chat handler's
`message` past the request-body setting. **Verified** by
`backend/tests/test_sentry.py` (9 tests): unset DSN creates no client, the
production warning fires once, the init kwargs are exactly the PII-safe set,
and a real event captured in memory from a stub app using the real middleware
contains no customer text, no `Authorization` header value, no cookie, no frame
locals and no request body, while an error-level log line creates no event.

**T-025 (frontend) is built.** `@sentry/nextjs@11.0.0`, `src/instrumentation.ts`
(`register()` and `onRequestError`), `src/instrumentation-client.ts`,
`src/lib/sentry-options.ts`, `sentryDsn` on `PublicConfig`, and
`Sentry.captureException` in the three error boundaries. Beyond the plan:
v11 has no `sendDefaultPii`, so privacy is an explicit restrictive
`dataCollection` plus `includeLocalVariables: false`; and Next's
`request.path` carries the query string, which Sentry copies into the event
past `urlQueryParams: false`, so `onRequestError` strips it. **Verified** by
`src/instrumentation.test.ts` (init contract, off without a DSN, no replay) and
`src/instrumentation-events.test.ts` (a real captured server error carries no
cookie, bearer token or query string; the strip test fails when the strip is
removed). `make lint-frontend`, `typecheck-frontend`, `test-frontend` and
`build` pass. **Not yet verified live:** an event arriving at a real Sentry
project, which needs `SENTRY_DSN` set in the Vercel environment.

Backend `sentry-sdk`, frontend `@sentry/nextjs`, both inert without a DSN.
No traces (Langfuse owns tracing), no Session Replay (the customer surface
would record a person typing their name and phone number into the chat), no
default PII, and no request bodies. The backend needs one explicit
`sentry_sdk.capture_exception()` inside `RequestContextMiddleware`'s
`except Exception:` block, because that middleware swallows the exception and
the ASGI integration would otherwise see only a 500 response. Frontend source
maps stay off, deliberately; the upgrade path is a `sentry-cli sourcemaps
upload` CI step. Read `frontend/node_modules/next/dist/docs/` for the
`instrumentation.ts` and `onRequestError` contract before writing any of it.

## T-026 and T-027: Security headers and CSP (D34)

**T-026 is built.** The header values live in
`frontend/src/lib/security-headers.ts` (unit-tested) and `frontend/next.config.ts`
applies them with `poweredByHeader: false`; `proxy.ts` is untouched.
`X-Content-Type-Options`, `Referrer-Policy`, `X-Frame-Options: SAMEORIGIN`,
`Permissions-Policy`, `Cross-Origin-Opener-Policy` and HSTS without `preload`.
The CSP ships report-only, with a `frame-src` for the YouTube-nocookie and Vimeo
storefront embeds that the first draft of the plan missed. Verified by building
the production image path and running `.next/standalone/server.js`: `curl -I`
on `/login` and a storefront route shows every header and no `X-Powered-By`.

**T-027 is queued.** It renames the header to the enforcing one, only after
T-026 is on a real deploy and a manual walkthrough (storefront, a full chat
turn, login, all three console tabs, onboarding, admin) shows zero violations,
because CSP failures are client side and return 200, so `keep-warm.yml` cannot
see them. `security-headers.test.ts` asserts the enforcing header is absent, so
that flip has to update the test on purpose. `script-src` keeps
`'unsafe-inline'` because `app/layout.tsx` injects a runtime-valued inline
public-config script; the upgrade path is moving it out of an inline script.
Unknowns to watch in the walkthrough are listed in D34: a custom Supabase auth
domain, and a tenant `brand.logo_url` from an arbitrary origin.

## T-028 and T-029: Conversation delete (D35)

A sixth route in `backend/app/features/conversations/api.py`, guarded by
`require_tenant_admin`, `204` on success, `404` for an unknown conversation,
`409` when the conversation has quotes. The delete statement excludes quoted
conversations, so it never cascades into `quotes`. `messages`, `tool_calls` and
`escalations` cascade; `cost_logs.conversation_id` is `on delete set null`, so
unit economics survive. `orders` are not conversation-linked. DB test with a
negative control proving `wren_app` still cannot `delete from quotes`.
`frontend/src/lib/api-types.ts` regenerated in the same commit. The console
action lives on the conversation drill-down, uses `useConfirm` and explains
the 409 in plain words.

## T-030: Retention (D36)

`python -m app.shared.retention`, dry run by default, `--apply` to delete.
Two rules: stale conversations (365 days, quoted conversations excluded) and
abandoned conversations (30 days, no assistant message and no escalation).
Never purged: `cost_logs`, the business's own content, `quotes`, `orders`, and
identity and brand tables. Policy in `docs/agencx/design/retention.md`;
`make retention` and `make retention-apply`.

## T-031: Operator export and offboard

`python -m app.shared.export --slug <slug>` (JSON to stdout, `make export`)
and `python -m app.shared.offboard --slug <slug> --confirm <slug> [--apply]`.
Both connect as the database owner with an explicit `where tenant_id = $1` on
every query. Offboard runs external systems first (Cloudinary, Storage, GoTrue)
and aborts before touching Postgres if any fail, so it stays re-runnable, then
prints a receipt that is the evidence for the deletion log. The request process
and SLA go in `deploy.md`.

## T-032: Privacy policy and terms

Static `frontend/src/app/privacy/page.tsx` and `terms/page.tsx`, with
`"privacy"` and `"terms"` added to `RESERVED_SLUGS` in the same commit (the
frontend reserved-slugs test fails otherwise). Linked from the storefront
footer and the login screen. Names every sub-processor and states that free
LLM tiers may train on inputs. Draft prose, placeholders for entity, ABN and
jurisdiction; needs a lawyer's review before real clients sign up.

## T-033: Backups

A section in `deploy.md`: managed backup cadence, no point-in-time recovery, so
RPO up to 24 hours and RTO manual, in hours; `keep-warm.yml` is load bearing for
database liveness on the free tier; Storage and Cloudinary objects are an
accepted gap; GoTrue users are covered only if the dump includes the `auth`
schema. `make db-dump` as the proof command, and a restore drill run once and
dated, whose wall-clock time is the RTO.

## Definition of done

Each ticket: `make check` green (`make ci` when the frontend build is touched),
its own tests, an end-to-end check against `make demo`,
its `progress.md` row updated, and one commit prefixed with its ticket id.
Anything failing that is unrelated is reported separately rather than folded
in. The R-5 boxes in [12-refinement.md](12-refinement.md) are ticked as their
tickets land.
