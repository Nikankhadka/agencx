# Agencx - Spec & User Stories (the tickets)

The complete ticket set for the Agencx change build. Each ticket file holds a
detailed spec with user stories, acceptance criteria, tests, files touched, and
a definition of done. One ticket = one commit; the commit message starts with
the ticket id.

## How to read a ticket

| Section | What it is |
|---|---|
| Summary | One paragraph: what the ticket delivers |
| Why | The motivation - the product promise or measured problem it serves |
| User stories | Persona-tagged, with acceptance criteria embedded in each story |
| Technical spec | The implementation shape: modules, seams, migration ids, config |
| Tests | What must be green for the ticket to be done |
| Files touched | Expected files/modules (discovered precisely at implementation time) |
| Definition of done | The checklist that closes the ticket |

## Phases and dependencies

### Phase 1 - the three pillars (build now)

Phase 1 ships only: **(1) business onboarding, (2) customer chat query handling,
(3) the business page** (PRD Stage 1: Chat + Business tabs + public page; no
leads, quotes, payments, scheduling, or invoicing as default flows). Everything
else defers to Phase 2 / Stage 2 backlog.

| Order | Tickets | Pillar | Blocked by |
|---|---|---|---|
| 1 | A-1, A-2 | Foundation (docs restructure) - **done** | - |
| 2 | O-1, O-2 | Onboarding: login-in-chat + one-tool loop | A (O-2 before O-1 in the flow) |
| 3 | P-3, P-1, P-2, P-4, P-5 | Chat spine: context pre-load (keystone), providers, failover, versioning, indicator | A (P-1 before P-2/P-3; P-3 before P-5) |
| 4 | O-3, O-4, C-1, C-2, C-3, C-4 | Chat grounding: ingest + whole-corpus fast path + money guardrail (honest price answers) | P-3 |
| 5 | E-1, E-2 | Business page: Chat + Business tabs, advanced screens hidden | A |
| 6 | B-1, B-3, E-3, D-2, F-2, G-1 | Polish/quality: Agencx copy, colour convention, platform minimal, lean default, CI boundary, eval | C, P |
| 7 | F-1 | Hygiene: delete dead agent topology (after P-3 lands) | P-3 |

Build order: A (done) -> {O-1, O-2} -> {P-3, P-1, P-2, P-4, P-5} -> {O-3, O-4,
C-1..C-4} -> {E-1, E-2} -> {B-1, B-3, E-3, D-2, F-2, G-1} -> F-1.

**Deferred (not Phase 1):**

| Ticket | Why deferred |
|---|---|
| B-2 | Domain + CORS to `agencx.app` - needs external DNS/Vercel founder step; local dev unaffected |
| D-1, D-3, D-4 | Tool-gating machinery + toggle UI + tests - Phase 2 (merge-plan open question) |
| D-2 | *Kept in Phase 1*: flips the tenant default to the lean toolset so quoting/pricing stays OFF by accident - one-line migration 0016 |
| Payments, quoting, scheduling, invoicing, leads, money screens | No tickets; unticketed Stage 2 backlog (`docs/archive/agencx-planning/stage-2-backlog.md`) - not built now |

## Ticket list

| Id | Title | File |
|---|---|---|
| A-1 | Docs restructure + archive | `A-1.md` |
| A-2 | Pointer updates | `A-2.md` |
| B-1 | Copy rename to Agencx | `B-1.md` |
| B-2 | Domain + CORS to agencx.app | `B-2.md` |
| B-3 | Semantic colour convention + lighter primary | `B-3.md` |
| C-1 | Money guardrail: allow figures verbatim from owner material | `C-1.md` |
| C-2 | Route knowledge answers through the same figure check | `C-2.md` |
| C-3 | Assistant states figures only exactly as listed, never computes | `C-3.md` |
| C-4 | Money guardrail test matrix | `C-4.md` |
| D-1 | Tools built from the tenant enabled set | `D-1.md` |
| D-2 | Lean default for new + legacy tenants | `D-2.md` |
| D-3 | Business-tab tool toggle UI | `D-3.md` |
| D-4 | Tool gating tests | `D-4.md` |
| E-1 | Tenant console -> Chat + Business | `E-1.md` |
| E-2 | Hide advanced screens, keep code | `E-2.md` |
| E-3 | Platform admin stays minimal | `E-3.md` |
| F-1 | Delete dead agent code | `F-1.md` |
| F-2 | Import boundary in CI | `F-2.md` |
| G-1 | Eval cases for the lean toolset | `G-1.md` |
| P-1 | Provider layer: Google/Groq/Cerebras tiers | `P-1.md` |
| P-2 | Latency budget + first-wins failover | `P-2.md` |
| P-3 | Agent-ready pre-load (context package) | `P-3.md` |
| P-4 | knowledge_version + invalidation | `P-4.md` |
| P-5 | Failover typing indicator (client) | `P-5.md` |
| O-1 | Onboarding: one tool + LLM turn loop | `O-1.md` |
| O-2 | Login-in-chat: email + 6-digit code | `O-2.md` |
| O-3 | Knowledge ingest: URL scrape + document upload | `O-3.md` |
| O-4 | Whole-corpus fast path + threshold | `O-4.md` |