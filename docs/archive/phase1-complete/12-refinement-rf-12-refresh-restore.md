# 12 (RF-12): Same-tab refresh restoration of content, cards, and state

**Status:** Done - merged in `87375d564ef48d0ffa561f6f844f17a490f0ac2d` on 2026-10-03.
**Phase 1 area:** Refinement.

Delivered: after a same-tab refresh the customer surface restores the
conversation transcript with each turn's quote, catalog, or price-summary
card, plus the unsent composer draft and the handoff or escalated banner
state. Cards restore from the customer-safe `response` payload in
`messages.metadata`; the raw owner-only metadata blob never reaches the
surface. A formal quote turn now captures its live `quote` event into
`metadata.response`, so its QuoteCard restores too. A refresh with no
conversation renders the opening state, and a restored handoff keeps the
human-reply poll running. No schema change.

## Agreed behavior

- **RF-12** - Conversation content, structured cards, and relevant state
  (conversation id, composer draft, handoff or escalated banner) restore after
  same-tab refresh; card payloads restore from the customer-safe `response`
  payload in `messages.metadata`.

## Ticket detail

- **Visible outcome:** After a same-tab refresh the conversation content,
  structured cards, and relevant state restore: the conversation id, composer
  draft, and handoff or escalated banner.
- **Current vs proposed:** Current: `conversationId` lived in memory
  (`CustomerChat.tsx`) with nothing persisting it, and the history endpoint
  `GET /api/chat/{conversation_id}/messages` returned only `id`, `role`,
  `content`, and `created_at` (filtered to `customer`, `assistant`, and
  `human_agent` in `backend/app/features/chat/api.py` and `service.py`), so
  cards and stamps could not restore. Shipped: `PublicMessage` and
  `list_messages` also return the customer-safe `response` card payload read
  from `messages.metadata`, and the customer surface persists the conversation
  id, unsent composer draft, and handoff/escalated banner flags in
  `sessionStorage`, restoring the transcript - with each turn's quote, catalog,
  or price-summary card - through that same endpoint. A formal quote turn now
  captures its live `quote` event into `metadata.response`, so its QuoteCard
  restores too.
- **Design reference:** Shipped `frontend/src/app/[slug]/CustomerChat.tsx` and
  `frontend/src/lib/chat-restore.ts`; `backend/app/features/chat/api.py` /
  `service.py` / `controller.py`; card payloads in `messages.metadata`
  (`backend/migrations/0012_messages_metadata.sql`); `design/frontend.md` S1
  `Drop-off / return` state.
- **Dependencies:** RF-11 for the handoff and escalated banner states. Queue
  filtering and split-pane work do not block this.
- **API/DB changes:** Shipped: `PublicMessage` gains
  `response: dict[str, Any] | None`, and `list_messages` selects `metadata` and
  extracts only `metadata["response"]` per row - never the raw metadata blob,
  which holds owner-only inspection verdicts, intent, action, and timing (D41).
  `stream_chat_response` now also captures the live `quote` event into
  `response_payload` beside the existing `price_summary`/`catalog` capture, so
  a formal quote persists a restorable card. No schema change
  (`messages.metadata` exists).
- **Acceptance scenarios:** Send a few turns, refresh, and see the transcript,
  any quote/catalog/price-summary card, the unsent draft, and the handoff or
  escalated banner restored; a refresh with no conversation renders the opening
  state; a human reply still polls in after restore.
- **Regression checks:** The customer transcript poll, ticket 19's leak-free
  transcript, and the existing chat-stream tests stay green.
- **OPEN:** Resolved. No open product questions remained; the payload boundary,
  single-slot card capture, and storage choices were ruled (see Decisions
  below).

## Decisions

- **Decision (2026-10-03):** The customer-safe card payload is exposed as a new
  optional `PublicMessage.response` field, populated by `list_messages` from
  `metadata["response"]` only; the raw metadata blob (inspection verdicts,
  intent, action, timing, limit_escalation) never reaches the customer surface
  (D41). One `_response_from_metadata` helper extracts it for both
  `recent_messages` and `list_messages`, and a non-dict or absent value yields
  no response rather than a 500 at the response model.
- **Decision (2026-10-03):** `response` stays a single `{"type": ...}` event
  dict, not a dict keyed by card type. A formal quote turn emits its `quote`
  event from `draft_node`, so `stream_chat_response` captures the live `quote`
  event into `response_payload` alongside the existing `price_summary` and
  `catalog` capture; the last card event wins if a turn ever emits more than
  one, and readers that key on `response["type"]` (the agent's follow-up
  context) keep working.
- **Decision (2026-10-03):** Same-tab state persists in `sessionStorage` under
  the RF-10 conversation/name keys plus separate draft, handoff, and escalated
  keys. Only customer-owned values are stored - never email or any owner-only
  data. Restore goes through a module-level `hydrateFromSession` helper to
  satisfy `react-hooks/set-state-in-effect`. Restoring `handoffSeen` and
  `escalated` is what resumes the human-reply poll and restores the
  banner/composer lock after refresh.
- **Decision (2026-10-03):** `cardFromResponse` validates the minimal iterable
  each card renders (`line_items` for quote and price summary, `offerings` for
  the catalog) and rejects arrays, so a malformed or corrupt persisted payload
  degrades to a plain transcript instead of crashing the chat.

## Verification

- `make migrate` - no pending migrations; no schema change (the ticket adds no
  migration).
- `cd frontend && npm run gen:types -- --check` - `api-types.ts is up to date`
  (regenerated from the new backend model, not hand-edited).
- `make lint` - passed (`check:tokens: OK`, `Contracts: 3 kept, 0 broken`).
- `make typecheck` - passed (frontend `tsc`, backend mypy 225 files).
- `make format-check` - passed.
- `make test-backend` - passed: 1265 tests.
- `make test-frontend` - passed: 355 tests.
- `make seed-tenant1` + `make eval-skip-llm` - GATE PASSED.
- Targeted E2E `rf-12-refresh-restore` with `rf-10-preferred-name` and
  `rf-11-ask-for-a-person` - passed: 11.
- Full `make test-e2e` - passed: 208, zero flaky.
- CI run 37104551281 on `52ca109` - all green (backend, frontend, api-types,
  infra, security, e2e, eval-gate, Vercel). PR #73.
- Independent reviewer pass: NO-SHIP initially; findings fixed - hardened
  `cardFromResponse` against malformed nested payloads, made the handoff-poll
  E2E non-vacuous (the human reply now arrives only on a post-restore poll
  tick), dict-guarded the metadata extraction, reworded the card-capture and
  draft-clearing comments, removed the dead `ChatCardResponse` export, and
  deduplicated the metadata extraction into one helper.
