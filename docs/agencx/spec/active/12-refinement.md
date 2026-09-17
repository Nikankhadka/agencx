# Phase 1 refinement (R + RF + U)

**Status:** Active - todo (R-3, R-4 remainder, R-5 remainder, RF-1 through
RF-17); U-1 through U-4 shipped, founder walkthrough remains.
**Phase 1 area:** Refinement.

This is the single refinement file. It merges the R hardening remainder
below, the RF product-refinement proposal (formerly
`spec/active/18-refinement-proposal.md`, removed 2026-09-18), the UI
companion (formerly `design/frontend-refinement.md`, removed 2026-09-18 -
the v7 prototype it specified was never built; shipped refinement was
implemented against v6 plus `design/frontend.md`), and the shipped UX
consistency record (formerly `spec/active/15-ux-consistency.md`, removed
2026-09-18 - code in `development`, walkthrough pending). Completed R-1 and
R-2 records are preserved in
`docs/archive/phase1-complete/12-refinement-r1-r2.md`. This file is
distinct from the M-7 storefront redesign (`active/17-storefront-redesign.md`,
lands with `feat/m7-storefront-redesign`).

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
  command.
- [ ] Error tracking has a documented status and operational verification.
- [ ] The Playwright suite runs in CI, not only locally.
- [ ] Dependency scanning has a documented status and scan report.

#### Acceptance signal

Each item above is marked built, planned, or deliberately deferred, with an
owner, urgency trigger, and validation command where applicable.

## Part 2 - Product refinement (RF-1 through RF-17)

**Status:** Active - todo. Design intent; production changes follow as
small, connected tickets. RF-1 precedes visual ports. RF-7 follows the
business-maintenance tickets; RF-8 and RF-9 follow it. RF-11 follows name
capture, and continuity covers those resulting states. Queue filtering
precedes split-pane work, which precedes integrated issue resolution.

Refine the existing application using selected Hivee workflows and the
shipped Agencx visual language (Airbnb colour discipline, Plus Jakarta
Sans - `design/frontend.md`). Preserve working behavior, especially
onboarding and document review. Preserve Home, Chats, and Business
navigation, the onboarding sequence and completion flow, and document-review
drafts, source evidence, explicit price decisions, replacement, retry, and
independent publication. Allow go-live without uploaded documents or
confirmed offerings, with clear next steps. Exclude old payment,
scheduling, and Copilot screens from the Phase 1 experience. Each ticket
specifies its visible outcome, current/proposed behavior, prototype states,
dependencies, API changes, acceptance scenarios, and regression checks;
backend and frontend work for one usable outcome belong together. The UI
standard of `design/conventions.md` section 6 applies unchanged: UI is
ported from the prototype, never designed from ticket text; every visual
value lands in `theme.css` as a token, never a hex in a component.

The four switchable businesses - cafe, retail/repair, dental clinic, and
general clinic - prove the domain-agnostic invariant visually: identical
screens and workflow code, with content, offerings, categories, and
knowledge driven by config only.

### Resumable owner input and offering normalization

Implemented on `feat/onboarding-normalization` from the founder-approved
change brief. The implementation supersedes the earlier preserve-onboarding-
flow restriction for this slice while keeping the existing server checkpoint,
knowledge review, and go-live boundaries.

- Required onboarding fields remain business name, business type, hours, and
  contact. Optional beats can be skipped once and are persisted as skipped.
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

- Core business-detail editing after launch (name, hours, description,
  business contact), in the shipped ABN-editor sheet idiom; the public
  address is a separate field and stays stable when the name changes. Saved
  edits appear immediately on the Business page and in customer answers.
- Searchable, category-grouped offerings; equal prices never merge distinct
  offerings. Fixed price (numeric, calculable) versus pricing wording
  (owner-confirmed display text such as "from $12 a head") - wording is
  display-only and never treated as a calculable amount on either surface.
- One cover/offering-image workflow (upload, preview, replacement, removal)
  with the same states (empty, uploading, preview, done, remove); removal is
  explicit.
- Contextual owner edit shortcuts open the same editors as the Business hub -
  one editor per field kind, two entry points, explicit Save and Cancel.
- Document review is clarified only; publication semantics unchanged.

**Business page and customer presentation:**

- Browse-first Business page (cover, identity, category-grouped offerings,
  price summaries, links) with clearly labeled chat access. Offering card
  (image, name, category, price or wording, one line); price summary shows
  deterministic figures only, formatted from cents by `src/lib/money.ts`.
- Customer chat is a desktop side panel (`lg+`) and a full-height mobile
  sheet; the Business page stays reachable while chat is open.
- Composer text is never sent automatically; contextual questions arrive
  editable and composed text survives navigation and refresh.

**Customer identity and continuity:**

- Answer while asking for a preferred name, at most two opening-phase name
  requests; first name or nickname accepted without verification; no phone
  number or email collected. Name shown, correctable, persisted across
  refresh; after the limit the prompt stops silently.
- Visible **Ask for a person** action; customer-requested handoff requires
  the name, otherwise the action explains the one missing thing. Refused or
  unanswered handoffs stay in the owner's All view; operational alerts may
  still use the conversation reference.
- Conversation content, structured cards, and relevant state restore after
  same-tab refresh. Failed sends recover in place with the draft preserved -
  explicit retry in the failed-bubble idiom, no unsafe automatic replay.

**Owner work queue:**

- Chats opens on **Needs you** (unresolved issues + active human-handled);
  All and Human handled retained. One row per conversation (identity or
  conversation reference, attention reason, handler, waiting time) with
  attention counts beside the tabs; filtering, searching, and pagination
  apply to the complete dataset (verified past 200 conversations).
- Takeover, reply, issue resolution, and handback stay distinct; replying or
  handing back never silently resolves - resolution is explicit with its own
  confirmation, shown in the shipped `thr-pill` stamp idiom. Unanswered
  questions without handoff stay in All unless an operational failure
  requires attention.
- Desktop (`lg+`) split pane (list left, thread right, no navigation);
  mobile keeps list-then-thread with the bar preserved.

**Home:** unchanged in behavior (greeting plus the brief); refinement
restyles through shared tokens only (RF-1). Brief cards include the queue
attention count when Needs you is non-empty.

### Tickets

- **RF-1**: Shared typography, surfaces, controls, responsive navigation,
  and focus behavior; preserves routes and flow order. Row grammar (icon or
  identity slot, primary line, meta line, trailing action) reused across
  list screens. `:focus-visible` ring on every interactive element, focus
  restoration after sheets close, scroll preserved on list return. U-1
  through U-4 below are landed pre-work for this ticket.
- **RF-2**: Business-detail editing and immediate consistency with customer
  answers.
- **RF-3**: Offering search and category grouping.
- **RF-4**: Explicit pricing wording across editing, publication, and
  customer display.
- **RF-5**: Cover and offering-image workflows.
- **RF-6**: Document-review workspace clarification, semantics unchanged.
- **RF-7**: Business page composition and contextual owner editing.
- **RF-8**: Desktop customer chat panels and mobile sheets.
- **RF-9**: Offering and price-summary card alignment.
- **RF-10**: Preferred-name capture, correction, and persisted prompt
  limits.
- **RF-11**: Visible human-help action and name-gated requested handoff.
- **RF-12**: Same-tab refresh restoration of content, cards, and state.
- **RF-13**: Failed-send recovery and draft preservation.
- **RF-14**: Complete-dataset queue filtering, searching, pagination, and
  attention counts.
- **RF-15**: Desktop split-pane Chats, mobile navigation preserved.
- **RF-16**: Explicit issue resolution in the conversation workspace;
  customer-facing handoff copy matches the shipped bubble; transcript
  consistency across takeover, reply, resolution, handback, and refresh.
- **RF-17**: Four-business walkthroughs with visual evidence (screenshots
  per state) and behavioral evidence (e2e checks), plus the ledger of what
  was verified where. Existing checks run within every ticket; RF-17
  verifies the assembled experience rather than postponing testing.

### Verification and boundaries

Verify existing login, onboarding, document review, pricing safeguards, and
tenant isolation; all four businesses on identical workflow code with
configuration-driven content; name refusal, correction, duplicate names,
and handoff without customer contact collection; 200+ conversations
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

## Part 3 - Shipped UX consistency record (U-1 through U-4)

Code in `development` (commit `ff90e4a`); founder mobile/desktop
walkthrough is the remaining step before this record closes. Landed
pre-work for RF-1: the mobile tab bar's accent active state and the
desktop sidebars' grey pill were visibly different products. All navs now
wear the mobile accent idiom, every button answers hover and press,
destructive actions ask through one in-app dialog, and mutations report
through toasts. Deltas recorded in `design/frontend.md` (nav idiom,
`ConfirmDialog`, `Toast` rows).

- **U-1: one nav idiom.** Shared `navTone()` helper in
  `components/ui/TabBar.tsx`; tenant sidebar, platform sidebar/drawer, and
  storefront category navs all use it. Active is accent text on a 9% accent
  wash with the filled glyph; inactive hover is the same wash. Inactive text
  is the only per-surface choice, and it is a contrast choice
  (`text-text-secondary` on the light sidebars, `text-ink-a40` on the mobile
  bar).
  - [ ] `tab-shell` computed-style test: active Home is
    `rgba(255, 56, 92, 0.09)` / `rgb(180, 0, 78)`; hovered Chats is
    `rgba(255, 56, 92, 0.07)`.
  - [ ] `tab-shell-mobile` computed-style test: active tab is the accent
    wash.
- **U-2: button feel.** One unlayered global rule in `globals.css` restores
  `cursor: pointer` on buttons (Tailwind v4 preflight leaves `default`);
  per-role hover/active idioms everywhere else, semantic tokens only.
  - [ ] `make lint` (includes `check:tokens`) and `make typecheck` pass.
  - [ ] Keyboard pass: visible focus ring on every button, pointer cursor
    everywhere enabled.
- **U-3: confirmations.** `components/ui/ConfirmDialog.tsx`
  (`ConfirmDialog` + `useConfirm`), built on `Modal` with a `layer` prop
  for confirms opened over a sheet. Destructive removes (offering, media,
  link, knowledge row, review source, non-draft discard), hand-back, and
  all three sign-outs ask through it. Take-over, draft discard, and copy
  link never ask. `window.confirm` is gone (`grep` is empty).
  - [ ] `business-hub` Escape test: cancel closes the confirm, no DELETE
    fires.
  - [ ] `auth-login` sign-out, `chats-takeover` hand-back,
    `settings-knowledge` remove all pass through `confirm-accept`.
- **U-4: toasts.** `react-hot-toast` (already mounted top-center) for every
  mutation: offering added/saved/removed, link saved/removed, cover
  updated, knowledge saved/draft-ready/replaced/removed/discarded, tenant
  suspended/reactivated. Inline errors remain only for initial loads; field
  validation stays inline.
  - [ ] `business-hub`, `settings-knowledge` assert toast text, not roles.
  - [ ] `copy-rules` passes on the new confirm and toast copy.
