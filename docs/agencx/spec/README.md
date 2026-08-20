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

| Phase | Tickets | What it does | Blocked by |
|---|---|---|---|
| **A - Docs** | A-1, A-2 | The restructure itself; canonical set + pointers | - |
| **B - Rebrand** | B-1, B-2 | Agencx name on every surface; domain + CORS | A |
| **C - Money guardrail** | C-1, C-2, C-3, C-4 | Allow figures verbatim from owner material; engine output becomes one allowed source | A |
| **D - Tool gating** | D-1, D-2, D-3, D-4 | Tools built from the tenant enabled set; lean default | A |
| **E - Screens** | E-1, E-2, E-3 | Chat + Business tabs; advanced screens hidden; platform minimal | A |
| **F - Hygiene** | F-1, F-2 | Delete dead agent code; import boundary in CI | A |
| **G - Eval** | G-1 | Re-cut eval cases for the lean toolset | C, D |
| **P - Performance & providers** | P-1, P-2, P-3, P-4, P-5 | Provider tiers, failover budget, pre-load, versioning, indicator | A (P-1 before P-2/P-3; P-3 before P-5) |
| **O - Flow & onboarding** | O-1, O-2, O-3, O-4 | Onboarding tool loop, login-in-chat, ingest paths, fast path | A (O-2 before O-1 in the flow) |

Suggested build order: A -> {B, C, D, E, F} in parallel -> {G, P, O}. P and O
are independent; G-1 lands after C/D change the toolset.

## Ticket list

| Id | Title | File |
|---|---|---|
| A-1 | Docs restructure + archive | `A-1.md` |
| A-2 | Pointer updates | `A-2.md` |
| B-1 | Copy rename to Agencx | `B-1.md` |
| B-2 | Domain + CORS to agencx.app | `B-2.md` |
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