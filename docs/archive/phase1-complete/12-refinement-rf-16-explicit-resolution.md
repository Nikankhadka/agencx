# 12 (RF-16): Explicit issue resolution in the conversation workspace

**Status:** Done - merged in `c59d4d0e5862b33165bab1577b5581509db42062` on 2026-10-03.
**Branch:** `feat/rf-16-explicit-resolution`.
**Phase 1 area:** Refinement.

Delivered: resolution is an explicit third action in the Chats thread
(`/chats/[id]`); `ConversationDetail` gains a derived `pending_escalation_id`;
the thread shows an inline resolve shelf from the Handling state whether or not
the owner has taken over, with its own confirmation and an optional
customer-facing message; `POST /api/escalations/{id}/resolve` now always writes
the owner-only `system` stamp `RESOLUTION_STAMP = "You resolved this issue"`
before the optional `human_agent` message; replying and handing back never
resolve; no migration, no schema change, no new route.

## Agreed behavior

- **RF-16** - Takeover, reply, issue resolution, and handback stay distinct;
  replying or handing back never silently resolves - resolution is explicit
  with its own confirmation and writes an owner-only `thr-pill` system stamp,
  with an optional customer-facing message, shown in the shipped `thr-pill`
  stamp idiom.

## Ticket detail

- **Visible outcome:** From the conversation workspace the owner resolves an
  issue explicitly, with its own confirmation and an owner-only `thr-pill`
  system stamp; an optional customer-facing message may accompany the
  resolution. Replying or handing back never silently resolves. Takeover,
  reply, resolution, and handback stay distinct, and the owner and customer
  transcripts agree across all four and a refresh.
- **Current vs proposed:** Current: the resolve endpoint exists
  (`POST /api/escalations/{id}/resolve`) but its UI is the hidden Wren-era
  `/escalations` table; the thread has takeover, handback, reply, and delete
  only; resolve writes no stamp; handback already never silently resolves.
  Proposed: move resolution into the thread, write a `system` message stamp on
  resolve, allow an optional customer-facing message, and keep reply and
  handback from resolving anything. Customer-facing handoff copy matches the
  shipped bubble.
- **Design reference:** `agencx-prototype-v6.html` `renderThreadScreen`
  `.thr-pill` stamps and `alexTko` / `alexHbk`; `design/frontend.md` S1 `The
  owner's side of the same surface (C-6)`. Shipped: `chats/[id]/page.tsx`,
  `backend/app/features/escalations/api.py` (`ResolveRequest`), and `service.py`
  `resolve`.
- **Dependencies:** RF-14 and RF-15.
- **API/DB changes:** `resolve` writes an owner-only `system` message (the
  `thr-pill` stamp); the existing optional message becomes a `human_agent`
  message. No schema change (`messages.role` already allows `system`).
- **Acceptance scenarios:** Resolving from the thread asks for confirmation,
  writes a stamp, and optionally posts a customer-visible message; reply alone
  does not resolve; handback alone does not resolve; after resolving, the issue
  leaves Needs you and the stamp survives a refresh; the customer transcript
  shows the optional message and not the owner-only stamp.
- **Regression checks:** The escalations resolve tests, ticket 19's transcripts,
  and the never-silent-resolve behavior stay green.
- **OPEN:** Resolved. See Decisions.

## Decisions

- **Decision (2026-10-03):** **Resolution is available from the Handling state
  (an unresolved escalation), not gated on takeover.** The shipped `resolve`
  endpoint already accepts `open`/`claimed`; RF-14's Needs you is an unresolved
  escalation OR a human takeover; gating resolution on takeover would couple two
  actions the ticket requires to stay distinct. This resolves the ticket's OPEN
  item.
- **Decision (2026-10-03):** **The resolution stamp is a `system` message
  (`RESOLUTION_STAMP`), owner-only**, reusing the existing customer-transcript
  role filter rather than a new column; no migration.
- **Decision (2026-10-03):** **The stamp is written first and the optional
  message at `now() + interval '1 microsecond'`** so the order is deterministic
  (Postgres `now()` is transaction-stable, so same-transaction inserts would
  tie).
- **Decision (2026-10-03):** **The thread learns the escalation id from the
  derived `ConversationDetail.pending_escalation_id`** rather than a new
  conversations endpoint or a client-side escalations join.
- **Decision (2026-10-03):** **While taken over, resolving does not remove the
  row from Needs you (status is still human)**; the confirmation copy says so
  and handback is what clears it.

## Verification

- `make migrate` - no pending migrations (no new migration).
- `make lint` - passed (frontend eslint, `check:tokens: OK`; backend ruff,
  import contracts 3 kept, 0 broken).
- `make typecheck` - passed (frontend tsc clean; mypy 225 source files).
- `make test` - passed: backend 1280, frontend 365.
- `make build` - passed.
- `npm run gen:types -- --check` - `api-types.ts is up to date`.
- `make format-check` - passed (226 files already formatted).
- `make seed-tenant1 && make eval-skip-llm` - GATE PASSED (money guardrail,
  leakage, retrieval; generation, trajectory, and injection skipped with
  `--skip-llm`).
- `make seed` - demo world restored.
- `make test-e2e` - passed: 226, zero flaky.
- CI on PR [#77](https://github.com/Nikankhadka/agencx/pull/77) - all green:
  backend, frontend, api-types, infra, security, e2e, eval-gate, Vercel.
- Independent reviewer pass (SHIP-WITH-FIXES); findings fixed: per-conversation
  remount so drafts do not leak across threads, state-aware confirmation copy
  while taken over, seeded demo resolution stamp, S1 design-reference update,
  E2E cleanup, and a deterministic `pending_escalation_id` tiebreaker.
