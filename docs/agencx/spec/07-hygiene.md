# Phase 1 - Hygiene (F)

**R-1 scope note:** The recommendation, quote, and order handlers mentioned in
this historical cleanup spec are dormant Phase 2 foundations. Phase 1 exposes
only grounded knowledge answering/search and human escalation.

Dead-code cleanup after the supervisor-with-tools topology (P-3) lands. The
one topology survives; superseded fixed-specialist routing is deleted.

Tickets in this file:

- F-1: Delete dead agent code
- F-3: Trim dead schema, dedupe seeds, enforce owner/staff roles

---

## F-1: Delete dead agent code

### Summary

Delete the agent code left over from the Wren topology that the Agencx
re-cut renders dead: the fixed five-specialist routing branches that the
supervisor-with-tools shape replaces, orphaned node modules, and unused
prompt/state scaffolding. Deletion over addition; every deleted symbol's
callers must be accounted for.

### Why

Dead code is the cheapest code to maintain - if it does not exist. The
multi-specialist topology (route -> specialist -> price_gate -> inspection
as fixed nodes) is superseded by supervisor-with-tools (D-13); keeping both
paths means every guardrail and inspection change is made twice, and the
second path is unexercised, which is worse than absent.

### User stories

#### US-1 One topology survives

**As** the maintainer,
**I want** exactly one customer-chat topology in the repo,
**so that** there is one path to reason about and test.

- [ ] The supervisor-with-tools flow (P-3) is the only graph shape after
  this ticket; fixed-specialist routing code is gone
- [ ] Specialist logic that becomes tool implementations is MOVED into tool
  handlers (not deleted wholesale - the knowledge/recommend/quote/order
  logic stays, in its new home); only the topology glue dies

#### US-2 No orphaned modules or tests

**As** the maintainer,
**I want** every deleted symbol's imports and tests cleaned in the same
commit,
**so that** nothing imports a deleted module.

- [ ] Import graph clean: no imports of deleted modules
- [ ] Tests that pinned the old topology are updated to the new shape or
  deleted when the shape they pin no longer exists

#### US-3 The safety net stays whole

**As** the platform owner,
**I want** the guardrail, inspection, and escalation behavior identical
after the cleanup,
**so that** deleting code never deletes safety.

- [ ] Money guardrail, inspection, leakage, and escalation suites green
  against the surviving topology (the suites assert behavior, not topology -
  where they asserted topology, they are re-pointed)

### Technical spec

- Order of work: land P-3 (supervisor-with-tools) first; F-1 then removes
  the superseded graph modules and the fixed routing
- `git grep` each deleted symbol before deletion; no orphan imports

### Tests

- Full `make check` + `make eval` green
- Import-linter green

### Files touched

- `backend/app/agents/**` (deletions + moves into tools)

### Definition of done

- [ ] One topology remains
- [ ] Import graph clean
- [ ] Safety suites green

---

## F-3: Trim dead schema, dedupe seeds, enforce owner/staff roles

### Summary

A schema audit found the database carrying columns, a table, and role
semantics nothing exercises. This ticket deletes the dead weight (migration
0025), makes the one column the app reads but never writes real
(`messages.agent_node`), enforces the `users.role` owner/staff split that
existed only on paper (G3.1), and dedupes the seed scripts behind one shared
helper module.

### Why

Every dead column is a promise the schema makes and the app does not keep:
`tenant_config.escalation_threshold` had its only reader deleted with the
old supervisor topology, `offerings.attributes` has zero references
anywhere, and `eval_cases` was write-only bookkeeping whose real source of
truth is the JSONL datasets. The trace viewer rendered an author chip that
was always empty because the app never populated `agent_node`. And staff
takeover (C-6) ships, but `users.role` was never enforced - any member was
any member.

### User stories

#### US-1 The schema says what the app does

**As** the maintainer,
**I want** every table and column backed by a live code path,
**so that** the schema is a map of the system, not a museum of past plans.

- [x] 0025 drops `tenant_config.escalation_threshold`, `offerings.attributes`,
  and the `eval_cases` table (and the eval runners' sync path dies with it)
- [x] `messages.agent_node` is populated by the graph (agent/draft/
  price_gate/inspection/escalation claim authorship) and the demo seed speaks
  the real node vocabulary
- [ ] Deliberate forward-looking columns stay: `enabled_tools` (D-1),
  `payment_processing_mode` (ADR decision 8), quotes immutability

#### US-2 Staff are staff, owners are owners

**As** a business with more than one person working the console,
**I want** staff to reach exactly the conversation work surface and nothing
else,
**so that** a wrong tap cannot change pricing, knowledge, or settings.

- [x] RLS branches on the context role (0025): staff reads the conversation
  tables, flips status human<->open, inserts human_agent/system messages,
  claims/resolves escalations - nothing else, no deletes anywhere
- [x] `require_owner` guards the settings/knowledge/offerings/pricing/
  onboarding routers; conversations/escalations/dashboards thread the role
  into their `tenant_context`
- [ ] Staff provisioning is still future work (no create-staff API) - the
  enforcement is proven with directly-inserted rows

#### US-3 Seeds tell their story, not their plumbing

**As** the maintainer,
**I want** each seed file to carry only its data and its narrative,
**so that** a new seed is a data file plus three helper calls.

- [x] `seeds/_helpers.py` owns pool/wipe/tenant-core/commerce/knowledge
  plumbing; behavior is byte-identical (seed tests pin the counts)

### Tests

- `make check`, `make test-backend`, `make seed` x2 (idempotency),
  `make eval-skip-llm` (the eval gate - eval_cases sync removed)
- test_rls.py proves the staff boundary at the SQL level; test_auth_api.py
  at the API level (staff 200s on conversations, 403s on owner surfaces)

### Files touched

- `backend/migrations/0025_schema_cleanup.sql` (drops, `app_role()`, role-
  branched policies; carries the M-2 media schema in the same file)
- `backend/app/agents/**` (author_node claims + inspection event),
  `backend/app/features/chat/**`, `backend/app/shared/auth.py` + `db.py`,
  `backend/app/features/{knowledge,business,pricing,tenants,onboarding}/
  api.py` (require_owner), `backend/app/features/{conversations,escalations,
  dashboards}/**` (role threading)
- `backend/evals/*` (eval_cases sync removed), `backend/seeds/*` (helpers +
  dedup), `backend/tests/*`, `docs/agencx/design/database.md`,
  `docs/agencx/industry-standard-gap.md` (G3.1 resolved), `progress.md`

### Definition of done

- [x] 0025 applied and audited (test_migrations, test_schema_audit green)
- [x] Staff boundary proven at SQL and API level
- [x] Seed suites green and idempotent
- [x] Gap doc G3.1 marked resolved
