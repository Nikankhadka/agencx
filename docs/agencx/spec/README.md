# Agencx - Spec and User Stories (the tickets)

The complete ticket set for the Agencx change build, organized by build phase.
Each ticket is a section inside its phase file with a detailed spec: user
stories, acceptance criteria, tests, files touched, and a definition of done.
One ticket = one commit; the commit message starts with the ticket id.

## How to read a ticket

| Section | What it is |
|---|---|
| Summary | One paragraph: what the ticket delivers |
| Why | The motivation - the product promise or measured problem it serves |
| User stories | Persona-tagged, with acceptance criteria embedded in each story |
| Design reference | UI tickets only: the prototype screen the ticket is built from |
| Technical spec | The implementation shape: modules, seams, migration ids, config |
| Tests | What must be green for the ticket to be done |
| Files touched | Expected files/modules (discovered precisely at implementation time) |
| Definition of done | The checklist that closes the ticket |

### Two shapes: ticket and amendment

Files in `spec/` hold two genres, and they are read differently.

- **Ticket** - a forward spec, written before the work. It carries all seven
  sections above, and its acceptance criteria are unchecked until the work
  lands. This is the default shape and what a new piece of work gets.
- **Amendment** - a record written after the work shipped, when a founder
  walkthrough turns up a fix inside a phase that had already closed. It carries
  Summary, Why, and User stories with acceptance already checked, plus what was
  deliberately not done and how the result was verified. It omits Technical
  spec, Tests, Files touched, and Definition of done, because those describe a
  plan and there was none - the code is the plan, and `git show` is the record.

An amendment declares itself in a line directly under its heading, naming where
it came from. The amendments in this set are **O-6, O-7, O-8, O-9, and E-6**.
Do not backfill the missing sections into them; a retrospective "Technical
spec" is invented, not recorded.

## Building UI: the prototype is the source, not a mood board

Every screen in this build already exists as a prototype in
`docs/agencx/design/prototypes/`. **A UI ticket is implemented by reading its
prototype screen and porting it, never by designing from the ticket text.** The
ticket says what the screen must do; the prototype says what it looks like and
how it behaves.

- `agencx-prototype-v6.html` - **current.** Tenant app: the home thread and its
  morning brief, onboarding thread, Chats (list + thread), Business hub,
  Booking page, Settings, plus the Stage 2 screens (Schedule, Money, Plan) that
  Phase 1 hides. Its tab bar carries two tabs; D21 makes it three - take the
  geometry and states from it, not the tab count. Trusted for screen
  inventory, states, interaction vocabulary, mobile chrome (D18), and the
  shipped crimson identity (D17).
- `agencx-storefront-customer-v3.html` - **superseded.** Customer storefront;
  trusted for storefront interaction vocabulary only, never for nav (pre-D18).

Two standing rules: copy in both files is demo copy for the Sababa reference
tenant (take structure and behaviour, never strings), and every visual value
still lands as a `theme.css` token - porting a prototype never means porting its
hex codes (CI enforces this via `check:tokens`).

Each UI ticket carries a **Design reference** section naming its exact screen or
render function. A ticket with no prototype screen says so explicitly - that is
a deliberate "do not invent one", not an omission.

## Phase files

Each file holds one build phase and its tickets (each ticket keeps its id as a
`## <ID>: <Title>` section).

| Phase file | Tickets |
|---|---|
| `01-foundation.md` | A-1, A-2 |
| `02-onboarding.md` | O-1, O-2, O-5, O-6, O-7, O-8, O-9 |
| `03-chat-spine.md` | P-3, P-1, P-2, P-4, P-5 |
| `04-chat-grounding.md` | O-3, O-4, C-1, C-2, C-3, C-4, C-5, C-6 |
| `05-business-page.md` | E-1, E-4, E-5, E-2, E-6 |
| `06-polish.md` | B-1, B-3, E-3, D-2, F-2, G-1 |
| `07-hygiene.md` | F-1 |
| `08-deferred.md` | B-2, D-1, D-3, D-4 |
| `09-devex.md` | K-1 |
| `10-deploy.md` | B-4 |

Tickets added during the build keep the numbering of the phase they belong to
rather than starting a new file: O-6 to O-9 and E-6 all came out of founder
walkthroughs after their phase had closed, and K-1 is developer experience
rather than product, so it sits outside the pillar order below. B-4 is the
deploy - it follows the three pillars rather than sitting inside one, so it gets
its own phase file even though its id belongs to the B block.

## Phases and dependencies

### Phase 1 - the three pillars (build now)

Phase 1 ships only: **(1) business onboarding, (2) customer chat query handling,
(3) the business page** (PRD Stage 1: Chat + Business tabs + public page; no
leads, quotes, payments, scheduling, or invoicing as default flows). Everything
else defers to Phase 2 / Stage 2 backlog.

The **platform console (`/admin`) is not a pillar** and is not part of Phase 1.
It is built and works locally, but its hosted login is broken on an
asymmetric-signing Supabase project - see Known gaps in
[progress.md](../progress.md). Treat it as out of scope when judging whether
Phase 1 is done.

| Order | Phase file | Pillar | Blocked by |
|---|---|---|---|
| 1 | `01-foundation.md` | Foundation (docs restructure) - **done** | - |
| 2 | `02-onboarding.md` | Onboarding: login-in-chat + one-tool loop | A (O-2 before O-1 in the flow) |
| 3 | `03-chat-spine.md` | Chat spine: context pre-load (keystone), providers, failover, versioning, indicator | A (P-1 before P-2/P-3; P-3 before P-5) |
| 4 | `04-chat-grounding.md` | Chat grounding: ingest + whole-corpus fast path + money guardrail (honest price answers) | P-3 |
| 5 | `05-business-page.md` | Business page: Chat + Business tabs, advanced screens hidden | A |
| 6 | `06-polish.md` | Polish/quality: Agencx copy, colour convention, platform minimal, lean default, CI boundary, eval | C, P |
| 7 | `07-hygiene.md` | Hygiene: delete dead agent topology (after P-3 lands) | P-3 |
| 8 | `10-deploy.md` | Deployment: two containers behind one Vercel origin | the three pillars |

Build order: A (done) -> {O-1, O-2} -> {P-3, P-1, P-2, P-4, P-5} -> {O-3, O-4,
C-1, C-2, C-3, C-5, C-6, C-4} -> {E-1, E-2} -> {B-1, B-3, E-3, D-2, F-2, G-1}
-> F-1 -> B-4. C-5 and C-6 precede C-4 so the money matrix is written once,
against the final escalation/takeover behaviour rather than the terminal one.

**Deferred (not Phase 1)** - see `08-deferred.md`:

| Ticket | Why deferred |
|---|---|
| B-2 | Point `agencx.app` at the deployed stack - founder buys the domain; one DNS record since D22; local dev unaffected. Depends on B-4 |
| D-1, D-3, D-4 | Tool-gating machinery + toggle UI + tests - Phase 2 (merge-plan open question) |
| D-2 | *Kept in Phase 1*: flips the tenant default to the lean toolset so quoting/pricing stays OFF by accident - one-line migration 0016 |
| Payments, quoting, scheduling, invoicing, leads, money screens | No tickets; unticketed Stage 2 backlog (`docs/archive/agencx-planning/stage-2-backlog.md`) - not built now |

## Ticket list (by phase)

### Foundation (`01-foundation.md`)

| Id | Title |
|---|---|
| A-1 | Docs restructure + archive |
| A-2 | Pointer updates |

### Onboarding (`02-onboarding.md`)

| Id | Title |
|---|---|
| O-1 | Onboarding: one tool + LLM turn loop |
| O-2 | Login-in-chat: email + 6-digit code |
| O-5 | Onboarding UI: port the prototype thread |
| O-6 | Chips, the contact widget, and the ABN beat |
| O-7 | A link that cannot be read says so, and says why |
| O-8 | Go-live lands on Home without a blank screen |
| O-9 | An ABN the owner can read, and correct |

### Chat spine (`03-chat-spine.md`)

| Id | Title |
|---|---|
| P-3 | Agent-ready pre-load (context package) |
| P-1 | Provider layer: Google/Groq/Cerebras tiers |
| P-2 | Latency budget + first-wins failover |
| P-4 | knowledge_version + invalidation |
| P-5 | Failover typing indicator (client) |

### Chat grounding (`04-chat-grounding.md`)

| Id | Title |
|---|---|
| O-3 | Knowledge ingest: URL scrape + document upload |
| O-4 | Whole-corpus fast path + threshold |
| C-1 | Money guardrail: allow figures verbatim from owner material |
| C-2 | Route knowledge answers through the same figure check |
| C-3 | Assistant states figures only exactly as listed, never computes |
| C-4 | Money guardrail test matrix |
| C-5 | Non-blocking escalation - chat continues after handoff |
| C-6 | Human takeover - staff step in, and hand back |

### Business page (`05-business-page.md`)

| Id | Title |
|---|---|
| E-1 | Tenant console -> Home + Chats + Business |
| E-4 | Home: the greeting and the brief |
| E-5 | Business hub + Booking page |
| E-6 | The Booking page as the customer's view |
| E-2 | Hide advanced screens, keep code |

### Polish (`06-polish.md`)

| Id | Title |
|---|---|
| B-1 | Copy rename to Agencx |
| B-3 | Semantic colour convention + lighter primary |
| E-3 | Platform admin stays minimal |
| D-2 | Lean default for new + legacy tenants |
| F-2 | Import boundary in CI |
| G-1 | Eval cases for the lean toolset |

### Hygiene (`07-hygiene.md`)

| Id | Title |
|---|---|
| F-1 | Delete dead agent code |

### Developer experience (`09-devex.md`)

| Id | Title |
|---|---|
| K-1 | Everything runs in containers |

### Deployment (`10-deploy.md`)

| Id | Title |
|---|---|
| B-4 | Deploy as two containers behind one Vercel origin |

### Deferred (`08-deferred.md`)

| Id | Title |
|---|---|
| B-2 | Point agencx.app at the deployed stack |
| D-1 | Tools built from the tenant enabled set |
| D-3 | Business-tab tool toggle UI |
| D-4 | Tool gating tests |
