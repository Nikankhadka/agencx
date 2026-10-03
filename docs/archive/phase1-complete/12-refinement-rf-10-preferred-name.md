# 12 (RF-10): Preferred-name capture, correction, and persisted prompt limits

**Status:** Done - merged in `edab038154eea623c9c47089ddb7a28d80cd890e` on 2026-10-03.
**Phase 1 area:** Refinement.

Delivered: during the opening phase - the window before the first escalation or
handoff - the assistant asks for a preferred name at most twice, backed by a
deterministic counter persisted on `conversations` (migration `0037`); the
stored name reaches the customer surface as a name-only `contact` SSE event
(never the owner-only email) and shows in a display-only chip that is
correctable in natural language through `set_customer_contact` and survives
same-tab refresh; after the two-ask cap the prompt stops silently. Ticket 19's
handoff contact capture is unchanged.

## Agreed behavior

- **RF-10** - Answer while asking for a preferred name. The opening phase is
  the window before the first escalation or handoff; during it the assistant
  asks for a preferred name at most twice. First name or nickname is accepted
  without verification, and no phone number, email, or other contact detail is
  collected. The preferred name shows on the customer surface in a small chip
  and is correctable in natural language, which routes to
  `set_customer_contact`; it persists across refresh, and after the two-ask cap
  the prompt stops silently. Contact is captured deliberately at handoff
  instead, scoped to the escalation (ticket `19`): one ask covers name and
  email, a name-only answer is accepted, and the email is chased once more only
  for an order, quote, or booking.

## Ticket detail

- **Visible outcome:** During the opening phase the assistant asks for a
  preferred name at most twice; the name is shown on the customer surface in a
  small chip, correctable by natural language, persists across refresh, and the
  prompt stops silently after the cap.
- **Current vs proposed:** Current: no opening-phase name ask or counter exists;
  the customer surface shows no name; `customer_ref` storage and owner display
  ship. Proposed: define the opening phase, persist the ask counter in a new
  `conversations` column, and add the customer-facing name chip and correction
  path through `set_customer_contact`.
- **Design reference:** `agencx-prototype-v6.html` `initName()` name pill in the
  onboarding thread (`#ni`); the opened account shows the customer reference.
  Shipped: `backend/app/agents/agent_node.py` `set_customer_contact`
  (`_set_customer_contact_impl`) and
  `frontend/src/app/[slug]/CustomerChat.tsx` header.
- **Dependencies:** RF-1. RF-11 follows name capture.
- **API/DB changes:** Shipped migration `0037` adds
  `conversations.opening_name_asks integer not null default 0`; the agent node
  increments it atomically once per opening-phase ask and caps at two. The
  stored `customer_ref` reaches the customer surface as a name-only `contact`
  SSE event (never the owner-only email). Same-tab refresh persists the
  conversation id and displayed name in `sessionStorage` and restores the text
  transcript through the existing `GET /api/chat/{id}/messages`; no new endpoint
  was added.
- **Acceptance scenarios:** The first two opening-phase name prompts show; a
  third non-answer stops the prompt silently; a first name or nickname is
  accepted without verification; the chip shows the stored name; a
  natural-language correction ("call me Sam") updates `customer_ref` and the
  chip; a refresh keeps the chip; no phone, email, or other contact detail is
  collected.
- **Regression checks:** Ticket 19's handoff contact capture and its
  never-blocking behavior stay green; name refusal, correction, and duplicate
  names; the public transcript stays leak-free.
- **OPEN:** Resolved. No open product questions remained; the ask cap and the
  name-only `contact` passthrough were ruled (see Decisions below).

## Decisions

- **Decision (2026-10-03):** The opening phase is the window before the first
  `escalations` row for the conversation. The chat API already short-circuits
  `human`/`escalated` statuses before the graph runs, so the escalation-existence
  check is the complete boundary.
- **Decision (2026-10-03):** The ask counter is deterministic and persisted, not
  model-counted. The agent node runs exactly once per turn (retries re-enter the
  draft node), so at turn start, when the name is unknown, no escalation row
  exists, and `opening_name_asks < 2`, it appends the opening ask instruction and
  increments the column by exactly one in the same turn. At the cap it appends a
  one-line suppression; when the name is known or a handoff exists it appends
  nothing (the known-name path keeps the existing "never ask again" line).
- **Decision (2026-10-03):** `customer_ref` reaches the customer surface as a new
  SSE `contact` event carrying the name only, never email (email is owner-only,
  ticket 19). It is emitted at turn start when a name is stored and again
  whenever `set_customer_contact` stores or changes one; the controller passes it
  through live next to `citations`/`quote` because a redraft cannot invalidate it.
- **Decision (2026-10-03):** Same-tab refresh persists the conversation id and
  the displayed name in `sessionStorage` and restores the text transcript through
  the existing `GET /api/chat/{id}/messages`. Cards, composer draft, and banner
  state stay RF-12. A name chip over an empty thread would be a visibly broken
  state.
- **Decision (2026-10-03):** The name chip is display-only (a `<span>`, not a
  Button/Chip) rendered above the message list in `CustomerChat`, with
  `data-testid="customer-name-chip"`. It uses the prototype `.svc-lbl` recipe
  through existing theme tokens, so `check:tokens` passes with no hex.

## Verification

- `make migrate` - passed; `0037` applied, dev DB ledger 37/37,
  `conversations.opening_name_asks integer not null default 0`.
- `make lint` - passed (`check:tokens: OK`, `Contracts: 3 kept, 0 broken`).
- `make typecheck` - passed (frontend `tsc`, backend mypy 224 files).
- `make test-backend` - passed: 1253 tests.
- `make test-frontend` - passed: 338 tests.
- `make eval-skip-llm` - GATE PASSED.
- Targeted E2E `rf-10-preferred-name` - passed: 4.
- Full `make test-e2e` on the merge SHA - passed: 201, zero flaky.
- CI run 37098239707 on `0149711` - all green (backend, frontend, api-types,
  infra, security, e2e, eval-gate, Vercel). PR #71.
- Independent reviewer pass: SHIP; the ask-cap decision was made atomic after
  review; guidance test and the API/DB ticket bullet tightened; accepted
  follow-ups noted (E2E mocks the `contact` event so model-driven correction is
  covered by backend tests; RF-12 owns cards/draft/banner restore).
