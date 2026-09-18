# 19: Intent architecture and escalation-scoped contact capture

**Status:** Active - in progress on feat/intent-and-identity.
**Phase 1 area:** Grounded chat, money and escalation safety.

Numbering note: 17 is reserved for the M-7 storefront redesign, and 18 was the
refinement proposal absorbed into [12-refinement.md](12-refinement.md) on
2026-09-18, so 19 is the next free ticket.

## Summary

Formalize what a customer turn is trying to accomplish and record it, without
adding a classifier call or a graph node:

- Three broad intent families: **information**, **offer**, **support**.
- Four actions: **respond**, **offer_followup**, **escalate**, **handoff**.
- **Escalation is an action, not an intent**: a customer escalates on any
  family, and intent never triggers escalation.
- Capture contact **at the point of escalation**, never at conversation start,
  so the business can follow up without opening-phase friction.

Design principle: intent describes what the customer is trying to accomplish;
escalation describes what Agencx needs to do about it.

## Why

The mechanics this records already shipped - the inspection extract call, the
escalation row, the handoff message - but the vocabulary was implicit. Making
the families and actions explicit gives the assistant, the owner surfaces, and
future evaluation one shared, code-pinned language. The contact decision
supersedes the earlier name-only stance: the opening phase still collects no
phone or email, but a deliberate, escalation-scoped ask captures identity
exactly where the business needs it, and it never blocks the handoff.

## Locked decisions

1. **Three intent families only.** `information` (a fact, policy, hours, or
   order status), `offer` (buying, pricing, a quote, or a recommendation), and
   `support` (a problem, complaint, or request for a person). Vocabulary lives
   in `backend/app/agents/intent.py` (`Intent`).
2. **Four actions only.** `respond`, `offer_followup`, `escalate`, `handoff`
   (`Action` in the same module).
3. **Escalation is an action, not an intent.** `_ROUTE_INTENT` deliberately has
   no `escalation` entry; an escalated turn's intent comes from the
   `create_escalation` tool argument or `intent_for_tools`, and always carries
   `action="escalate"`.
4. **Classification rides the existing inspection extract call.** No new LLM
   call and no new graph node: `InspectionVerdicts` gained `intent`/`action`
   alongside the four check verdicts. Intent coerces through `as_intent()` and
   falls back to `intent_for_route(route)`; the classifier's action is accepted
   only when it is `respond` or `offer_followup`, anything else coerces to
   `respond`, because the graph outcome is authoritative. No new SSE event type
   was added.
5. **Intent never gates escalation.** Every writer coerces through
   `as_intent()`, unknown values become null, and a missing or unknown family
   never blocks a row or a handoff.
6. **Persistence.** `escalations.intent` (migration `0032`,
   `backend/migrations/0032_escalation_intent.sql`) is nullable and carries a
   check for the three families only; the escalation node records the coerced
   state intent, the tool path records `_create_escalation_impl`'s coerced
   argument, and limit stops stay null because no classifier ran.
   `messages.metadata.intent` and `messages.metadata.action` are written by
   `persist_assistant_turn` from the last inspection event, only when not None -
   an absent key, never a null one.
7. **Limit stops are terminal handoffs.** `record_limit_escalation` tags its
   message `{"limit_escalation": reason, "action": "handoff"}`, omits intent,
   and appends no contact ask, because the composer locks on a limit stop. It
   is the only writer of `conversations.status = 'escalated'`; every other
   escalation is non-terminal and leaves the conversation open (C-5/D20).

Intent source per path (the `route` key is internal drafting/routing, unchanged):

| Path | Intent source | Action |
|---|---|---|
| info / offer answered as LLM prose | inspection classifier | inspection classifier |
| missing knowledge (deterministic refusal) | `intent_for_route(route)` | `offer_followup` |
| structured card (catalog / price summary) | `intent_for_route("structured")` = offer | `respond` |
| order status template | `intent_for_route("order_status")` | `respond` |
| explicit human request / tool escalation | `create_escalation.intent` (fallback `intent_for_tools`) | `escalate` |
| price_gate second violation | `intent_for_route(route)` | `escalate` |
| inspection second failure | last classifier verdict | `escalate` |
| limit stop (budget / step / turn / provider) | null | `handoff` |

## Escalation-scoped contact capture

- The agent reads `customer_ref`/`customer_email` from the conversation at turn
  start and sets `customer_name_known`/`customer_email_known` in state.
- Every escalation message builder appends a contact ask when either flag is
  false (`contact_ask` / `handoff_message` in
  `backend/app/agents/escalation.py`, wrapped by
  `gate_escalation_message`/`escalation_message`). One ask covers both name and
  email: "Can I get your name and email so the business can follow up?"
- A name-only answer is always accepted and never blocks. For an order, quote,
  or booking handoff, the prompt and the customer contract direct one more ask
  for the email; that follow-up is guidance to the model, not a gate.
- Never a phone number: both the contract and `set_customer_contact`'s
  description forbid it, and the tool schema has only `name` and `email`.
- `set_customer_contact` is an always-on bookkeeping tool registered in
  `_tools_for` independent of the tenant-gated set: it stores the preferred
  first name (capped at 80) and a leniently validated email (one `@`, no
  whitespace, <= 254 chars) in `conversations.customer_ref`/`customer_email`
  with `coalesce`, so one call sets either or both and a correction overwrites.
  An unusable email raises a tool error the model can re-ask about; a
  name-only call is always valid.
- **The escalation row is written first, always.** `_create_escalation_impl`
  inserts the row and only then does the flow produce the reply text, so the
  contact ask can never gate or delay the escalation itself.

## Owner surface

- `customer_email` is added to the owner `ConversationDetail` response
  (`backend/app/features/conversations/api.py`) and passed through the
  controller/service from the conversation row. `ConversationSummary` is
  unchanged: the queue still labels by name.
- The Chats thread shows it as a small meta line below the thread status
  (`data-testid="thread-email"`) only when present.
- The public customer surface never sees it: the transcript poll still selects
  only `id, role, content, created_at`, and a test pins that the seeded email
  never appears in the public transcript response.

## Acceptance criteria

- [x] Intent and action vocabulary is code-pinned, with unknown values coercing
  to null/`respond` rather than raising.
- [x] The inspection extract call classifies intent and action; no new LLM call
  or graph node exists.
- [x] `escalations.intent` is nullable with a three-family check; unknown intent
  still writes the row (null).
- [x] `messages.metadata.intent`/`action` are written only when classified;
  limit stops are tagged `action="handoff"` with no intent and no contact ask.
- [x] Escalation contact capture is one ask, name-only accepted, email chased
  once for order/quote/booking, no phone, and never blocks the row.
- [x] `customer_email` appears on the owner detail response and the Chats
  thread, and never on the public surface.
- [x] Deterministic refusals that already offer forwarding are `offer_followup`;
  order-status and prose routes stay `respond`.

## Verification run on this branch

Run from the repo root on `feat/intent-and-identity`, 2026-09-18:

- Targeted backend suites (the plan's list):
  `docker compose run --rm backend pytest tests/test_intent.py
  tests/test_agent_identity.py tests/test_escalation_agent.py
  tests/test_inspection.py tests/test_validation_gate.py
  tests/test_agent_graph.py tests/test_chat_api.py tests/test_limits_api.py
  tests/test_conversations_api.py tests/test_migrations.py -q`
  -> **205 passed**.
- Full backend suite: `docker compose run --rm backend pytest -q`
  -> **1117 passed**. The session drops and recreates `wren_test` and applies
  every migration fresh, so `0032`/`0033` parse and apply.
- Frontend unit suite: `docker compose run --rm --no-deps frontend npm run test`
  -> **229 passed** (20 files).

Not yet run on this branch: `make ci` (includes the api-types drift check),
`make eval`, and `make test-e2e`. No CI or E2E result is claimed here.

## Definition of done

- [ ] Local E2E run once the full stack is available: `make dev && make seed &&
  make test-e2e`.
- [ ] Founder preview walkthrough: a seeded chat that trips a pricing question
  (offer), a bad order (support), and an explicit person request (escalation
  row, name+email ask); reply with both and confirm the Chats thread shows the
  email while the customer transcript does not; keep chatting to confirm the
  handoff is non-terminal.
- [ ] Merge to `development` and record the commit.
