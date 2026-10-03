# Phase 1 refinement (R + RF)

**Status:** Active - todo (R-3, R-4 remainder, R-5 remainder, RF-7 through
RF-17); RF-1, RF-2, RF-3, RF-4, RF-5, RF-6, and RF-18 are delivered and
archived, and U-1 through U-4 and the onboarding-normalization slice were
delivered and walked on the preview on 2026-10-01. Production hardening T-022 to
T-026 and T-028 to T-033 are built; T-027 (enforce the CSP) waits on a
real-deploy walkthrough.
**Phase 1 area:** Refinement.

This is the single refinement file. It merges the R hardening remainder
below and the RF product-refinement proposal (formerly
`spec/active/18-refinement-proposal.md`, removed 2026-09-18), the UI
companion (formerly `design/frontend-refinement.md`, removed 2026-09-18 -
the v7 prototype it specified was never built; shipped refinement was
implemented against v6 plus `design/frontend.md`). Completed R-1 and
R-2 records are preserved in
`docs/archive/phase1-complete/12-refinement-r1-r2.md`. Shipped UX consistency
(U-1 through U-4) is archived in
`docs/archive/phase1-complete/12-refinement-u1-u4.md`. Production hardening
(T-022 through T-033) is archived in
`docs/archive/phase1-complete/22-production-hardening.md`. This file is
distinct from the completed M-7 storefront redesign
(`docs/archive/phase1-complete/17-storefront-redesign.md`).

Canonical vocabulary, binding in UI copy and code identifiers:
**Business page, offering, preferred name, conversation, conversation
reference, issue, handoff, takeover, handback, resolution, price summary,
and request**. A request awaits business acceptance - it is not a confirmed
order or booking, and must never render as one, in any state, on either
surface.

## Part 1 - Hardening remainder (R)

### R-3: Schema and type safety

**Status:** Active - todo.
**Phase 1 area:** Refinement.

Pydantic models across the API layer are not uniformly configured with an
explicit unknown-field policy. The generated-types path currently covers error
responses, but success responses consumed by the frontend have not yet been
audited end to end.

#### Acceptance signal

- [ ] Every request and response model has an explicit, deliberate
  unknown-field policy.
- [ ] Generated TypeScript types are the only declared shapes for success
  responses consumed by the frontend.
- [ ] No hand-duplicated interface remains beside a generated type.

### R-4: Reliability and provider

The Google provider's multi-tool history fix is complete. Provider-owned
assistant metadata is preserved and replayed verbatim, including
`thought_signature` values required by Google.

#### Remaining work

- [ ] Judge calibration is completed using founder hand-labeling rather than
  agent-generated labels.
- [ ] Production-smoke evidence beyond the B-4 deployment smoke test is
  collected and recorded.

### R-5: Operations and security

The URL-ingest SSRF hardening is complete. HTTP(S)-only validation, public DNS
resolution, peer verification, redirect-hop validation, media-type checks, and
body-size limits are covered by backend tests.

#### Remaining work

- [ ] Backups, RPO/RTO, and a restore drill have a documented status and proof
  command. Built (T-033): `deploy.md` Step 9 records what is verified and what
  is not, `make db-dump` is the proof command, and a restore drill was run
  locally on 2026-09-26 (row counts equal, quote-delete revoke intact, storefront
  and a chat turn served from the restored copy). Open: the production project is
  on the Free plan and its Backups page has not been read, and the drill has not
  been run against production, so no real RTO exists. Owner is the founder;
  validate with `make db-dump` on the production URL and the Step 9 procedure.
- [ ] Error tracking has a documented status and operational verification.
  Built (T-024 backend, T-025 frontend, ADR D33), off until `SENTRY_DSN` is set;
  the in-memory event tests pass on both surfaces. Open: set `SENTRY_DSN` in the
  Vercel environment for both services, then raise a deliberate error on each and
  confirm the event arrives with no request body or query string. Owner is the
  founder.
- [x] The Playwright suite runs in CI, not only locally. Built: the `e2e` job
  in `.github/workflows/ci.yml`; validate with `make test-e2e`.
- [x] Dependency scanning has a documented status and scan report. Built (T-023):
  `.github/dependabot.yml`, the PR-only `security` job in `ci.yml`, and Dependabot
  alerts, secret scanning and push protection, recorded in `deploy.md` Step 7;
  owner is the founder, validate with the `gh api` readback there.

#### Acceptance signal

Each item above is marked built, planned, or deliberately deferred, with an
owner, urgency trigger, and validation command where applicable.

## Part 2 - Product refinement (RF-1 through RF-17)

**Status:** Active - todo. Design intent; production changes follow as
small, connected tickets. RF-1 precedes visual ports. RF-7 follows the
business-maintenance tickets; RF-8 and RF-9 follow it. RF-11 follows name
capture, and continuity covers those resulting states. Queue filtering
precedes split-pane work, which precedes integrated issue resolution. The
Part 2 design task is complete: the documentation and the prototype authority
agree, every workflow below has an implementation ticket, and each ticket is
implementable without deciding product behavior (the `OPEN:` lines record the
product questions that still need a founder ruling). The delivered tickets are
RF-1 (shared row grammar), RF-2 (business-detail editing), RF-3 (offering
search), RF-4 (pricing wording), RF-5 (cover and offering-image workflows),
RF-6 (document-review workspace clarification), and RF-18 (owner read state);
the remaining product-refinement tickets are **RF-7 through RF-17**, plus the
RF-14 tab-badge follow-up.

### Archive process for delivered RF tickets

Effective now: when an RF ticket merges, its full ticket record moves out of
this file into its own file in `docs/archive/phase1-complete/`, named
`12-refinement-rf-<n>-<slug>.md`. That archive file carries the ticket id and
title, a `Done - merged` status with the merge commit hash and date, the
agreed-behavior text, the ticket detail block, and a short "Verification"
section listing the commands run and their results. The block is removed from
this file, which then lists only undelivered tickets plus a one-line pointer
to the archived ones. `docs/archive/phase1-complete/README.md` gains an index
row per archived ticket, and `docs/agencx/progress.md` and
`docs/agencx/spec/README.md` are updated in the same closeout commit.

Refine the existing application using selected reference workflows and the
shipped Agencx visual language (Airbnb colour discipline, Plus Jakarta
Sans - `design/frontend.md`). Preserve working behavior, especially
onboarding and document review. Preserve Home, Chats, and Business
navigation, the onboarding sequence and completion flow, and document-review
drafts, source evidence, explicit price decisions, replacement, retry, and
independent publication. Allow go-live without uploaded documents or
confirmed offerings, with clear next steps (20 narrowed this: a stated
services overview is now required, though it is still not a priced catalog). Exclude old payment,
scheduling, and Copilot screens from the Phase 1 experience. Each ticket
specifies its visible outcome, current-versus-proposed behavior, design
reference, dependencies, API/DB changes, acceptance scenarios, and regression
checks;
backend and frontend work for one usable outcome belong together. The UI
standard of `design/conventions.md` section 6 applies unchanged: UI is
ported from the prototype, never designed from ticket text; every visual
value lands in `theme.css` as a token, never a hex in a component.

**Design authority (D37).** The console screens are ported from
`docs/agencx/design/prototypes/agencx-prototype-v6.html` plus
`docs/agencx/design/frontend.md` section 4, which wins where the two disagree
on spacing, type, radii, or elevation. The storefront authority is the shipped
implementation under `frontend/src/app/[slug]/`; the archived v5 storefront is
the accepted structure and interaction record, and the shipped code is what
the refinement tickets read. No v7 prototype exists and none is required - the
refinement was specified against a v7 that was never built and shipped against
v6 plus `frontend.md` (see `spec/README.md` and D37). The convention at
`design/conventions.md` section 6 is unchanged: UI is ported, never designed
from ticket text, and each ticket below names its exact screen, render
function, or shipped code path.

The four switchable businesses - cafe, retail/repair, dental clinic, and
general clinic - prove the domain-agnostic invariant visually: identical
screens and workflow code, with content, offerings, categories, and
knowledge driven by config only.

### Resumable owner input and offering normalization

Delivered: implemented on `feat/onboarding-normalization` from the
founder-approved change brief, and walked on the preview on 2026-10-01. The
one defect the walk found (a price-list-only knowledge record could not be
saved, so its offerings never went live) was fixed in `7d8425b` and re-walked
(`docs/agencx/evidence/walkthrough-2026-10/README.md`, items 25-29). The
implementation supersedes the earlier preserve-onboarding-
flow restriction for this slice while keeping the existing server checkpoint,
knowledge review, and go-live boundaries.

- Required onboarding fields are business name, business type, hours, contact
  and, since 20, services. Optional beats resolve by default or, for the
  owner's name alone, to `skipped` on the two-ask cap - 20 retired the "Skip
  for now" chip from every beat, leaving only the knowledge ask with one.
- Name proposals are explicitly confirmed. A rejected proposal is edited
  locally, and a submitted replacement is checked without model rewriting.
- Services are broad normalized capabilities. Offerings are concrete reviewable
  candidates with source wording, category proposals, provenance, and explicit
  review status.
- Pending offering candidates are private. Go live ignores unreviewed
  candidates; Home and What you offer are the only later review entry points.
- Category records are tenant-scoped, normalized, RLS protected, and linked by
  nullable stable IDs while the legacy category label remains on the wire.

### Agreed behavior

**Business maintenance:**

- **RF-3** - Searchable, category-grouped offerings; equal prices never merge
  distinct offerings.
- **RF-4** - Fixed price (numeric, calculable) versus pricing wording
  (owner-confirmed display text such as "from $12 a head"); wording is
  display-only and never treated as a calculable amount on either surface.
- **RF-5** - One cover/offering-image workflow (upload, preview, replacement,
  removal) with the same states (empty, uploading, preview, done, remove);
  removal is explicit.
- **RF-6** - Document review is clarified only; publication semantics
  unchanged.

**Business page and customer presentation:**

- **RF-7** - Browse-first Business page (cover, identity, category-grouped
  offerings, price summaries, links) with clearly labeled chat access, plus
  contextual owner edit shortcuts that open the same editors as the Business
  hub - one editor per field kind, two entry points, explicit Save and Cancel.
  Offering card (image, name, category, price or wording, one line); price
  summary shows deterministic figures only, formatted from cents by
  `src/lib/money.ts`.
- **RF-8** - Customer chat is a desktop side panel (`lg+`) and a full-height
  mobile sheet; the Business page stays reachable while chat is open.
- **RF-9** - Offering and price-summary cards align on one width and chrome.

**Customer identity and continuity:**

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
- **RF-11** - Visible **Ask for a person** action; the handoff always happens,
  and when contact is incomplete the handoff reply asks once - the ask never
  gates or blocks the escalation. Refused or unanswered handoffs stay in the
  owner's All view; operational alerts may still use the conversation
  reference.
- **RF-12** - Conversation content, structured cards, and relevant state
  (conversation id, composer draft, handoff or escalated banner) restore after
  same-tab refresh; card payloads restore from the customer-safe `response`
  payload in `messages.metadata`.
- **RF-13** - Failed sends recover in place with the exact failed payload and
  the draft preserved - explicit retry in the failed-bubble idiom, no unsafe
  automatic replay.

**Owner work queue:**

- **RF-14** - Chats opens on **Needs you**, defined as an open escalation
  (`escalations.status <> 'resolved'`) or `conversations.status = 'human'`;
  All and Human handled are retained. One row per conversation (identity or
  conversation reference, attention reason, handler, waiting time) with
  attention counts beside the tabs; filtering, searching, and pagination apply
  to the complete dataset (verified past 200 conversations), and paging is
  "Load more" backed by a server total. Unanswered questions without a handoff
  stay in All unless an operational failure requires attention.
- **RF-15** - Desktop (`lg+`) split pane (list left, thread right, no
  navigation); mobile keeps list-then-thread with the bar preserved, and
  `/chats/[id]` survives as a deep link inside the split pane.
- **RF-16** - Takeover, reply, issue resolution, and handback stay distinct;
  replying or handing back never silently resolves - resolution is explicit
  with its own confirmation and writes an owner-only `thr-pill` system stamp,
  with an optional customer-facing message, shown in the shipped `thr-pill`
  stamp idiom.

**Cross-cutting:** composer text is never sent automatically; contextual
questions arrive editable. This applies to every ticket below.

**Home:** unchanged in behavior (greeting plus the brief); refinement
restyles through shared tokens only (RF-1). Brief cards include the queue
attention count when Needs you is non-empty (RF-14).

### Tickets

Every ticket below keeps `Status: Active - todo`; the delivered tickets are
archived. "Current" restates the read-only audit of 2026-10-02 and "Proposed"
is the agreed behavior above. The hard rules in `design/conventions.md`
sections 8 and 9 bind every ticket.

**Delivered and archived:** RF-1, RF-2, RF-3, RF-4, RF-5, RF-6, and RF-18. Their
full records, including verification, live in
[12-refinement-rf-1-shared-ui.md](../../../archive/phase1-complete/12-refinement-rf-1-shared-ui.md),
[12-refinement-rf-2-business-detail-editing.md](../../../archive/phase1-complete/12-refinement-rf-2-business-detail-editing.md),
[12-refinement-rf-3-offering-search.md](../../../archive/phase1-complete/12-refinement-rf-3-offering-search.md),
[12-refinement-rf-4-pricing-wording.md](../../../archive/phase1-complete/12-refinement-rf-4-pricing-wording.md),
[12-refinement-rf-5-media-workflows.md](../../../archive/phase1-complete/12-refinement-rf-5-media-workflows.md),
[12-refinement-rf-6-document-review-clarity.md](../../../archive/phase1-complete/12-refinement-rf-6-document-review-clarity.md),
and
[12-refinement-rf-18-owner-read-state.md](../../../archive/phase1-complete/12-refinement-rf-18-owner-read-state.md).

#### RF-7: Business page composition and contextual owner editing

- **Status:** Active - in progress on `feat/rf-7-business-page-shortcuts`.
- **Visible outcome:** The public business page is browse-first (cover,
  identity, category-grouped offerings, price summaries, links) with clearly
  labeled chat access, and the owner reaches the same field editors from
  contextual shortcuts on that page.
- **Current vs proposed:** Current: the browse-first business page and
  storefront ship (M-4, M-7); no contextual owner edit shortcuts exist. The
  storefront price label already routes through `src/lib/money.ts` -
  `frontend/src/app/[slug]/Offerings.tsx:62-64` delegates to `formatCents` -
  so the earlier `priceLabel` arithmetic claim is satisfied and the remaining
  work is the owner-gated shortcuts. Proposed: add contextual shortcuts that
  open the RF-2 editors, keep one editor per field kind and two entry points,
  and gate the owner markup server-side so customers and anonymous visitors
  never receive it.
- **Design reference:** `agencx-prototype-v6.html` `.edit-btn` (the circular
  pencil idiom) and the `.set-field-row` / `.set-edit` settings-row idiom;
  the archived v5 storefront is the accepted structure record. Shipped public
  route: `frontend/src/app/[slug]/Storefront.tsx`, `StorefrontHero.tsx`,
  `Offerings.tsx`. The shortcuts reuse the RF-2 editors, imported from the
  console owner screen at
  `frontend/src/app/(tenant-admin)/(console)/business/details/components/`
  (`ProfileFieldSheet.tsx`, `ContactSheet.tsx`); that is the reused-editor
  path, not `business/page/components/`.
- **Dependencies:** RF-1 and RF-2.
- **API/DB changes:** None. The existing authenticated
  `PATCH /api/business/profile` (RF-2) is the save path, and the price item is
  already satisfied.
- **Decisions (founder-ruled 2026-10-03):**
  - Shortcut fields are **name, hours, description, contact**. There is no
    separate public-address shortcut; the address lives inside the free-text
    `business_contact` value.
  - Owner detection is **server-side**: `resolveViewerSlug` in
    `frontend/src/lib/tenant.ts` reads the Supabase session cookie (pinned
    cookie name `sb-<host>-auth-token`, `SUPABASE_INTERNAL_URL || supabaseUrl`)
    and calls `GET /api/tenants/me`; `frontend/src/app/[slug]/page.tsx:82`
    compares its slug to the page slug with `isStorefrontOwner` and passes
    `canEdit` down to `Storefront`.
  - `description` and `contact` are not published by the storefront
    (`lib/tenant.ts`; `read_public_storefront` at
    `backend/app/features/business/service.py` returns neither), so their
    shortcuts are **owner-only**.
- **Acceptance scenarios:** A contextual shortcut opens the field's editor with
  the current value, Save updates the page and customer answers, and Cancel
  changes nothing; the storefront renders the same price as the owner editor;
  the owner markup appears only for the matching signed-in tenant owner.
- **Regression checks:** The storefront tests, the `money.ts` contract tests,
  and the deterministic-pricing tests stay green. Anonymous and customer HTML
  (any viewer other than the matching owner) contains no owner controls and no
  contact value.
- **OPEN:** None.

#### RF-8: Desktop customer chat panels and mobile sheets

- **Status:** Active - todo.
- **Visible outcome:** On `lg+` the customer chat is a side panel that leaves
  the business page reachable; below `lg` it is a full-height sheet.
- **Current vs proposed:** Current: chat renders as a mobile `Sheet` only; no
  `lg+` desktop side panel exists. Proposed: add the `lg+` side panel while
  keeping the mobile sheet, with the business page visible beside it.
- **Design reference:** Shipped `frontend/src/app/[slug]/CustomerChat.tsx`,
  `Storefront.tsx` (sheet host), and `components/ui/Sheet.tsx`;
  `design/frontend.md` S3. v6 is mobile-only.
- **Dependencies:** RF-7.
- **API/DB changes:** None.
- **Acceptance scenarios:** At 1024px the chat opens beside the page and the
  page stays scrollable and interactive; at 360px the sheet is full height with
  the composer reachable; closing the panel restores the page state.
- **Regression checks:** The storefront E2E at both widths; focus trap and
  `aria-modal` behavior for the sheet.
- **OPEN:** none.

#### RF-9: Offering and price-summary card alignment

- **Status:** Active - todo.
- **Visible outcome:** The offering card and the price-summary card share one
  width and chrome so they read as one family.
- **Current vs proposed:** Current: grouping logic is already correct in
  `CatalogCard.tsx`; the only mismatch is width and chrome -
  `PriceSummaryCard.tsx` and `QuoteCard.tsx` use `max-w-[420px]`, while
  `CatalogCard.tsx` uses `max-w-[520px]`. Proposed: pick one width and one
  chrome and apply it to all three cards.
- **Design reference:** Shipped `frontend/src/components/ui/CatalogCard.tsx`,
  `PriceSummaryCard.tsx`, and `QuoteCard.tsx`; `design/frontend.md` section 6
  `QuoteCard`.
- **Dependencies:** RF-1, RF-4, and RF-7.
- **API/DB changes:** None.
- **Acceptance scenarios:** The offering, price-summary, and quote cards
  left-align in one column at the same width and share padding, radius, and
  header treatment.
- **Regression checks:** `CatalogCard.test.tsx` and `PriceSummaryCard.test.tsx`
  stay green; a visual check at 360px and 1024px.
- **OPEN:** whether 420px or 520px becomes the canonical chat-card width.

#### RF-10: Preferred-name capture, correction, and persisted prompt limits

- **Status:** Active - todo.
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
- **API/DB changes:** Add `conversations.opening_name_asks integer not null
  default 0` (migration with the implementation ticket); expose `customer_ref`
  on the customer chat read so the chip can render; the counter increments on
  each opening-phase name prompt and caps at two.
- **Acceptance scenarios:** The first two opening-phase name prompts show; a
  third non-answer stops the prompt silently; a first name or nickname is
  accepted without verification; the chip shows the stored name; a
  natural-language correction ("call me Sam") updates `customer_ref` and the
  chip; a refresh keeps the chip; no phone, email, or other contact detail is
  collected.
- **Regression checks:** Ticket 19's handoff contact capture and its
  never-blocking behavior stay green; name refusal, correction, and duplicate
  names; the public transcript stays leak-free.
- **OPEN:** none.

#### RF-11: Visible human-help action and requested handoff

- **Status:** Active - todo.
- **Visible outcome:** A visible **Ask for a person** control lets the customer
  request a human; the handoff always happens, and when contact is incomplete
  the handoff reply asks once. The ask never gates or blocks the escalation.
- **Current vs proposed:** Current: handoff row-first, one contact ask, and
  never-gating ship (ticket 19); the visible **Ask for a person** control is
  absent, so a customer cannot request a human explicitly. Proposed: add the
  control, wire it to the existing escalation/handoff path, and keep the
  handoff unconditional. The ticket title no longer implies the handoff is
  gated on a name.
- **Design reference:** `agencx-prototype-v6.html` thread handoff behavior and
  `renderThreadScreen`; `design/frontend.md` S1 `Handed off (C-5)` state.
  Shipped: `components/ui/EscalationBanner.tsx`,
  `backend/app/agents/agent_node.py` escalation tool, and ticket 19 behavior in
  `backend/app/agents/escalation.py`.
- **Dependencies:** RF-10. Continuity (RF-12) covers the resulting states.
- **API/DB changes:** Reuse the existing escalation and handoff endpoints; the
  control posts the same request the assistant's escalation tool records; no
  schema change.
- **Acceptance scenarios:** Tapping **Ask for a person** creates an escalation
  and the handoff reply; an incomplete contact asks once and never blocks; the
  escalation appears in the owner's Needs you queue; the public transcript
  leaks no contact detail; an already-open escalation does not hand off twice.
- **Regression checks:** Ticket 19's tests and the escalation-scoped contact
  capture stay green.
- **OPEN:** none.

#### RF-12: Same-tab refresh restoration of content, cards, and state

- **Status:** Active - todo.
- **Visible outcome:** After a same-tab refresh the conversation content,
  structured cards, and relevant state restore: the conversation id, composer
  draft, and handoff or escalated banner.
- **Current vs proposed:** Current: `conversationId` lives in memory
  (`CustomerChat.tsx`); nothing persists it; the history endpoint
  `GET /api/chat/{conversation_id}/messages` returns only `id`, `role`,
  `content`, and `created_at` and filters to `customer`, `assistant`, and
  `human_agent` (`backend/app/features/chat/api.py` and `service.py`), so cards
  and stamps cannot restore. Proposed: persist the conversation id, draft, and
  banner state in the browser for the same tab, widen the history query to
  return the customer-safe `response` card payload read from
  `messages.metadata`, and restore quote, catalog, and price-summary cards from
  that payload.
- **Design reference:** Shipped `frontend/src/app/[slug]/CustomerChat.tsx` and
  `backend/app/features/chat/api.py` / `service.py`; card payloads in
  `messages.metadata` (`backend/migrations/0012_messages_metadata.sql`);
  `design/frontend.md` S1 `Drop-off / return` state.
- **Dependencies:** RF-11 for the handoff and escalated banner states. Queue
  filtering and split-pane work do not block this.
- **API/DB changes:** Widen `PublicMessage` and `list_messages` to return the
  customer-safe `response` card payload only, read from `messages.metadata`;
  never the raw metadata blob, which holds owner-only inspection verdicts,
  intent, action, and timing (D41). No schema change (`messages.metadata`
  exists).
- **Acceptance scenarios:** Send a few turns, refresh, and see the transcript,
  any quote/catalog/price-summary card, the unsent draft, and the handoff or
  escalated banner restored; a refresh with no conversation renders the opening
  state; a human reply still polls in after restore.
- **Regression checks:** The customer transcript poll, ticket 19's leak-free
  transcript, and the existing chat-stream tests stay green.
- **OPEN:** none.

#### RF-13: Failed-send recovery and draft preservation

- **Status:** Active - todo.
- **Visible outcome:** A failed send recovers in place: the failed bubble offers
  an explicit retry that replays the exact failed payload, and the draft
  survives the failure. Nothing replays automatically.
- **Current vs proposed:** Current: an error state and Retry exist in-session,
  but Retry replays the previous bubble rather than the failed payload
  (`CustomerChat.tsx` reads `messages[index - 1]?.text`), and the draft is
  cleared before send and not restored. Proposed: keep the draft in a slot
  cleared only on success, and retry the stored failed payload.
- **Design reference:** Shipped `frontend/src/app/[slug]/CustomerChat.tsx` send,
  error, and retry paths; `design/frontend.md` S1 and S3 `Error / disconnect`
  states (inline retry in the failed bubble).
- **Dependencies:** RF-12 (draft persistence).
- **API/DB changes:** None.
- **Acceptance scenarios:** Force a network failure, confirm the draft stays in
  the composer and the failed bubble carries Retry; Retry sends the exact
  original text once; a success clears the draft; no automatic replay occurs.
- **Regression checks:** The `redraft` price-gate path and the existing
  error-state tests stay green.
- **OPEN:** none.

#### RF-14: Complete-dataset queue filtering, searching, pagination, and attention counts

- **Status:** Active - todo.
- **Visible outcome:** Chats opens on **Needs you** (an open escalation or
  `conversations.status = 'human'`); All and Human handled are retained. Rows
  carry identity or reference, attention reason, handler, and waiting time;
  attention counts sit beside the tabs; filter, search, and paging apply to the
  complete dataset with a server total behind "Load more".
- **Current vs proposed:** Current: tabs are All/Action needed/Unread with no
  Needs you or Human handled; there is no handler field; the client filters the
  first 50 rows only (`chats/page.tsx`); there is no pagination; attention
  counts appear only on the nav tab. Proposed: server-side filter, search, and
  paging with a total; a derived `handler` field; counts beside the tabs.
- **Design reference:** `agencx-prototype-v6.html` `renderScreen('chats')`
  `.chat-row` and filter row, `openChatsSearch()` / `filterChats()`;
  `design/frontend.md` S1 owner-surface paragraph. Shipped:
  `frontend/src/app/(tenant-admin)/(console)/chats/page.tsx`,
  `home/lib/brief.ts`, and `components/ui/TabBar.tsx`.
- **Dependencies:** RF-1. Queue filtering precedes split-pane work (RF-15).
- **API/DB changes:** Extend `GET /api/conversations` with `q` (search), a
  `needs_you` / `human` filter, and a server total (response envelope or
  `X-Total-Count`); add a derived `handler` field to `ConversationSummary` from
  `conversations.status = 'human'`; no new column required. Pagination keeps
  `limit`/`offset` and returns the total for "Load more".
- **Acceptance scenarios:** Seed 200 or more conversations including older
  unresolved issues beyond the first page; Needs you returns open escalations
  and human-handled threads; All returns everything; Human handled returns only
  `status = 'human'`; search matches a name or reference across the whole
  dataset, not the first page; "Load more" appends and stops at the total; the
  tab counts match the dataset.
- **Regression checks:** Tenant isolation on the conversations read; the
  existing Chats list and Home brief tests stay green.
- **OPEN:** whether the legacy **Unread** tab survives alongside Needs you, All,
  and Human handled, or is dropped.
- **Follow-up (from RF-18):** the console Chats tab badge is still driven by
  `needs_attention` rather than unread; reconcile it here, since switching it in
  RF-18 broke `home-brief.spec.ts`. See
  [12-refinement-rf-18-owner-read-state.md](../../../archive/phase1-complete/12-refinement-rf-18-owner-read-state.md).

#### RF-15: Desktop split-pane Chats, mobile navigation preserved

- **Status:** Active - todo.
- **Visible outcome:** At `lg+` Chats is a split pane (list left, thread right)
  with no navigation between them; mobile keeps list-then-thread with the
  bottom bar preserved. `/chats/[id]` remains a deep link that opens the thread
  in the split pane.
- **Current vs proposed:** Current: list and thread are separate routes reached
  by navigation; no split pane exists. Proposed: add the `lg+` split pane while
  keeping both routes; `/chats/[id]` selects the thread pane.
- **Design reference:** `agencx-prototype-v6.html` `renderScreen('chats')` plus
  `renderThreadScreen` (list-then-screen in v6; the split pane is the `lg+`
  composition of the same two); `design/frontend.md` section 7 tenant console
  shell. Shipped: `chats/page.tsx` and `chats/[id]/page.tsx`.
- **Dependencies:** RF-14 (queue filtering precedes split-pane work).
- **API/DB changes:** None.
- **Acceptance scenarios:** At 1024px, selecting a row loads the thread in the
  right pane and keeps the list; `/chats/[id]` deep-links to the same state; at
  360px the list navigates to the full thread with the bar visible; browser
  back returns to the list state.
- **Regression checks:** The existing Chats E2E, focus order, and the mobile bar
  behavior stay green.
- **OPEN:** none.

#### RF-16: Explicit issue resolution in the conversation workspace

- **Status:** Active - todo.
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
- **OPEN:** whether resolution is available from the "Handling" state or only
  after the owner takes over.

#### RF-17: Four-business walkthroughs with visual and behavioral evidence

- **Status:** Active - todo.
- **Visible outcome:** Four businesses (cafe, retail/repair, dental clinic, and
  general clinic) are walked on identical workflow code with
  configuration-driven content, with screenshots per state and E2E checks, plus
  a ledger of what was verified where.
- **Current vs proposed:** Current: four-business visual and behavioral
  walkthroughs and the evidence ledger are specified but not yet assembled for
  the refined experience. Proposed: run every ticket's existing checks within
  each ticket, then verify the assembled experience once across all four
  businesses. RF-17 verifies the assembled experience rather than postponing
  testing.
- **Design reference:** Existing walkthrough evidence under
  `docs/agencx/evidence/` and the four seeded businesses; no prototype change.
  Shipped: `frontend/e2e/`.
- **Dependencies:** RF-1 through RF-16.
- **API/DB changes:** None.
- **Acceptance scenarios:** Each business completes the refined owner queue,
  business page, storefront, and customer chat flows with config-only
  differences; every screenshot maps to a named E2E check; the ledger names the
  environment and date; a cross-tenant check proves isolation.
- **Regression checks:** `make test-e2e`, `make eval-skip-llm`, and the
  deterministic pricing and domain-agnostic invariant tests.
- **OPEN:** none.

### Verification and boundaries

Verify existing login, onboarding, document review, pricing safeguards, and
tenant isolation; all four businesses on identical workflow code with
configuration-driven content; name refusal, correction, and duplicate names;
escalation-scoped contact capture (one ask, name-only accepted) with the public
transcript staying leak-free; 200+ conversations
including older unresolved issues beyond the first page; owner/customer
transcript consistency across takeover, reply, resolution, handback, and
refresh; long offerings, missing images, unpriced items, pricing wording,
and partial processing failures; mobile and desktop layout, keyboard
access, focus restoration, and scroll preservation. Use a dedicated branch
per implementation ticket; keep contract changes backward compatible so
intermediate deployments stay usable.

Out of scope: owner Copilot, image understanding, galleries, independent
page-pause controls, scheduling, payments, invoices, billing, external
reviews, account-management additions, and request submission with business
acceptance (documented separately).

This design task is complete when the documentation and the prototype
agree, every included workflow has an implementation ticket, and each
ticket is implementable without deciding product behavior.
