# 12 (RF-11): Visible human-help action and requested handoff

**Status:** Done - merged in `5e2dc3b9740f2230b6f75f4bacf9e767708115ab` on 2026-10-03.
**Phase 1 area:** Refinement.

Delivered: a visible **Ask for a person** control on the customer chat.
Tapping it always creates an escalation and the handoff reply; when
contact is incomplete the reply asks once, and the ask never gates or
blocks the escalation. The control is hidden once a handoff is open, so
an already-open escalation does not hand off twice. No schema change.

## Agreed behavior

- **RF-11** - Visible **Ask for a person** action; the handoff always
  happens, and when contact is incomplete the handoff reply asks once -
  the ask never gates or blocks the escalation. Refused or unanswered
  handoffs stay in the owner's All view; operational alerts may still
  use the conversation reference.

## Ticket detail

- **Visible outcome:** A visible **Ask for a person** control lets the
  customer request a human; the handoff always happens, and when contact
  is incomplete the handoff reply asks once. The ask never gates or
  blocks the escalation.
- **Current vs proposed:** Current: handoff row-first, one contact ask,
  and never-gating ship (ticket 19); the visible **Ask for a person**
  control is absent. Proposed: add the control, wire it to the existing
  escalation/handoff path, and keep the handoff unconditional.
- **Design reference:** `agencx-prototype-v6.html` thread handoff
  behavior and `renderThreadScreen`; `design/frontend.md` S1
  `Handed off (C-5)` state. Shipped: the composer `Chip` idiom in
  `frontend/src/app/[slug]/CustomerChat.tsx`,
  `backend/app/agents/agent_node.py` escalation tool, and ticket 19
  behavior in `backend/app/agents/escalation.py`.
- **Dependencies:** RF-10. Continuity (RF-12) covers the resulting
  states.
- **API/DB changes:** A new unauthenticated `POST /api/chat/handoff` on
  the customer surface, body `{slug, conversation_id?}`. It records the
  same escalation row the assistant's `create_escalation` tool records,
  through one shared writer (`record_escalation` in
  `backend/app/agents/escalation.py`), and streams the deterministic
  handoff reply from `handoff_message`. `conversation_id` is optional so
  a customer can ask for a person before typing. No schema change.
- **Acceptance scenarios:** Tapping **Ask for a person** creates an
  escalation and the handoff reply; an incomplete contact asks once and
  never blocks; the escalation appears in the owner's Needs you queue;
  the public transcript leaks no contact detail; an already-open
  escalation does not hand off twice.
- **Regression checks:** Ticket 19's tests and the escalation-scoped
  contact capture stay green.
- **OPEN:** Resolved. No open product questions remained; the
  deterministic-endpoint choice and the summary decision were ruled (see
  Decisions below).

## Decisions

- **Decision (2026-10-03):** A dedicated deterministic endpoint
  (`POST /api/chat/handoff`) over a synthetic model message, because a
  visible control must not depend on the model choosing the
  `create_escalation` tool. It reuses one shared row writer so the
  assistant path and the control cannot drift.
- **Decision (2026-10-03):** The endpoint schedules no LLM escalation
  summary, so a fresh handoff's owner-queue preview falls back to the
  existing empty state; RF-14's one-row-per-conversation queue absorbs
  it. Keeping the handoff deterministic was preferred over threading a
  provider through the endpoint.
- **Decision (2026-10-03):** The recorded reason is `human_requested`;
  the conversation stays non-terminal (C-5). `human` (staff takeover)
  does not create a new handoff; `escalated` (a limit stop) is not
  reopened.

## Verification

- `make lint` - passed (`check:tokens: OK`,
  `Contracts: 3 kept, 0 broken`).
- `make typecheck` - passed (frontend tsc, backend mypy 225 files).
- `make format-check` - passed.
- `make test-backend` - passed: 1262 tests.
- `make test-frontend` - passed: 344 tests.
- `make migrate` - no pending migrations (no schema change).
- `npm run gen:types -- --check` - up to date.
- Targeted E2E `rf-11-ask-for-a-person` - passed: 3.
- Regression subset `rf-10-preferred-name`, `rf-8-desktop-chat-panel`,
  `chats-takeover` - passed: 14.
- Full `make test-e2e` - passed: 204, zero flaky.
- CI run 37100919989 (attempt 2) on `b5223d6` - all green (backend,
  frontend, api-types, infra, security, e2e, eval-gate, Vercel). PR #72.
  The first attempt's `frontend` Build failed on the documented
  `next/font/google` build-time flake (unrelated to the diff, no
  font/layout files touched); the identical commit rebuilt green on
  re-run.
- Independent reviewer pass: SHIP; findings fixed - regenerated
  `frontend/src/lib/api-types.ts` (the CI `api-types` job's blocker),
  documented the no-summary decision in `stream_handoff_response`, and
  typed the shared writer's connection seam.
