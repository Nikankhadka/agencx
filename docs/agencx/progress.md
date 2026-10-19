# Agencx build dashboard

This page is the single authority for Phase 1 scope, what is done, and
what is next. Ticket detail lives in [the spec index](spec/README.md).
The Wren origin story lives in [history.md](history.md).

## Current status

Stage 1 is deployed and the production smoke test is green. Feature
delivery is complete; refinement and hardening remain open.

| Environment | Value |
|---|---|
| Production branch | `staging` |
| Live origin | `https://agencx-iota.vercel.app` |
| Preview branch | `development` |

Production database: hosted Supabase, migrated and seeded with `bytefix`.

## Phase 1 scope

Phase 1 is onboarding plus customer chat plus the business page plus
hardening: the owner self-onboards in a chat, lands in Home, Chats, and
Business, uploads knowledge, and an anonymous customer asks questions at
`/{slug}` grounded in that material, with escalation and handoff.

Out of Phase 1: lead records, quotes, payments, scheduling, invoicing,
custom domains, and the per-tenant tool registry plus toggle UI. Full
scope boundary is in [the PRD](prd.md).

## What is done

Full ticket records live in [the phase-1-complete
archive](../archive/phase1-complete/README.md); verification narratives
live in the ticket files, not here.

| Area | Tickets |
|---|---|
| Foundation and tenancy | A-1, A-2 |
| Onboarding, login, chat spine, grounding, money and escalation safety | O-1 through O-12, P-1 through P-5, C-1 through C-6 |
| Tenant console, storefront and media, product polish and hygiene | E-1 through E-6, M-1 through M-7, B-1, B-3, D-2, F-1 through F-3, G-1 |
| Developer experience, deployment, security and API reliability | K-1, B-4, R-1, R-2, R-4 US-1, R-5 US-1 |
| Walkthrough fixes, schema drop, document review, auth OTP | W-1 through W-13, migration `0029`, hosted-verified |
| Intent and identity, required services, category management | 19, 20, 21 |
| Storefront and console refinement batch | 23 through 28 |

## What is next

- [ ] Latency workstream (ticket [13-latency.md](spec/active/13-latency.md),
  post-launch): slices stack on `latency/stack` (not merged until the founder
  says go). Slice 1, the instrument - `make latency` drives real turns with one
  model pinned and writes the 15-key per-turn record (`cached_input_tokens` added
  by slice 5); the noise floor and model
  matrix are in
  [evidence/latency-2026-10](evidence/latency-2026-10/report.md). Slice 2, the
  draft output cap (`llm_max_tokens_draft` 4096) - measured mechanism-inert
  ([report-slice-2.md](evidence/latency-2026-10/report-slice-2.md)). Slice 3,
  the discarded agent call - **implemented, measured, through its after-eval:
  PASS on the mechanism**. The tool result now carries the chunks, so a grounded
  tool turn's prose is the draft and the draft node is skipped; measured at
  `2ac8247` the evidence is the mechanism - `agent grounded tool answer` fired 8
  times, only on the hybrid tenant's tool turns, and only the new branch logs it
  - plus the fast tenants' completed counts not moving (p50 delta 0, sababa2's
  0.00 band held). The hybrid tenant's single completed turn ran 3 model calls
  against 4 (n=1, 0.50 from one baseline p50 and 1.0 from the other). Run 1's
  grounded knowledge turn was rejected by inspection and redrafted through the
  draft node (the retry edge still works); seven of the eight grounded turns went
  straight through. The citations event narrows to the cited chunks, but the
  customer surface is unchanged: citation markers are stripped from every
  approved token run before the flush and persistence
  (`controller.py:71-102`), so no chip renders on either path. Cited-only is
  founder-ratified (2026-10-19, no fallback to all retrieved chunks).
  After-eval with the
  baseline pins: counts 45/41/30, trajectory and injection case-for-case
  identical to the baseline, generation faithfulness 0.7475 -> 0.7163,
  citation_faithfulness 0.3207 -> 0.3692, answer_relevancy 0.7356 -> 0.8025. The
  eval cannot reach the branch (`_tools_for` never offers the retrieval tools on
  the fast path, `agent_node.py:604-605`), and the -0.0311 faithfulness drift is
  NOT noise - the identical-code repeat spread is +0.0019 - so `run_gate` fails
  that key by 0.001; founder ruling 2026-10-19 accepted it as a provider level
  shift and closed it, with the 0.03 tolerance unchanged and no reclassification
  as noise
  ([report-slice-3.md](evidence/latency-2026-10/report-slice-3.md),
  [data/eval-noise-repeat.md](evidence/latency-2026-10/data/eval-noise-repeat.md),
  [design-slice-3.md](evidence/latency-2026-10/design-slice-3.md),
  [eval-after-slice3-env.txt](evidence/latency-2026-10/data/eval-after-slice3-env.txt)).
  Slice 4, parallelize the retrieval steps - **implemented, measured: PASS
  structurally, no-measurable-effect on the clock**. `sparse_search` now starts
  first and the embedding runs beside it, with dense awaited only once the
  embedding is in hand and sparse has landed (one connection, one operation at a
  time; the RLS context is on the caller's connection). Measured at `040a473`:
  the documented band rule has no sample (completed hybrid turns that ran
  `retrieve()`: 1/0/0/0/0/0 across six runs),
  the fallback band for `search_ms` is 2.52 ms, and both runs' hybrid `search_ms`
  p50 fell (1.9-2.7 -> 1.25 / 1.15) - but `rerank_ms`, untouched by this slice,
  also steps over its own band once, and the overlap can only ever save the
  sparse query's own duration (median 0.38 ms). No scored eval: the change is
  output-preserving and both eval tenants are fast-path, so `retrieve()` never
  runs there; the deterministic gate that does call it passes unchanged
  (recall@5 1.000, MRR 0.911, nDCG@5 0.934)
  ([report-slice-4.md](evidence/latency-2026-10/report-slice-4.md),
  [data/slice4-bands.md](evidence/latency-2026-10/data/slice4-bands.md)).
  **The cumulative comparison for slices 1-4 is built and merged-ready, pending
  the 5-7 decisions and the merge go**: baseline (slice-1 runs) vs stack tip per
  tenant - hybrid provider
  calls p50 4.0 -> 3.0, sababa2's 0.00 band held exactly, completion inside every
  tenant's own spread, no `total_ms` claim (provider drift exceeds the bands), the
  hybrid input up to 16.2k from slice 3's chunk re-send - plus the eval trio
  (trajectory and injection case-identical; generation FAIL by 0.001, accepted as
  a provider level shift by founder ruling 2026-10-19, tolerance unchanged)
  ([report-cumulative.md](evidence/latency-2026-10/report-cumulative.md),
  [data/cumulative.md](evidence/latency-2026-10/data/cumulative.md)).
  **Slice 5, prompt caching (a stable prompt prefix) - implemented, measured,
  gate PASS, the cache proven, and NO clock claim.** The per-request spotlight
  nonce is retired for ONE fixed 16-hex delimiter, so the prompt prefix is
  byte-identical across calls and the provider can cache it (ruling recorded
  2026-10-20 by the supervisor under the founder's delegation of 2026-10-19 - the
  fixed token is public by design, and the enforcement is `escape_delimiters`,
  now case/whitespace/invisible/full-width tolerant and emitting a non-forgeable
  `escaped` marker, plus the standing instruction plus Inspection, with the
  injection gate guarding the decision). Code landed `7613091`; review hardening
  and the measured tip `d99ca54`. Injection gate PASS: 29/30 = 0.967 >= 0.9667,
  the same single leak (`direct-policy-invent-01`), both delimiter-forgery cases
  held (row `513cec2f`). Cache reads proven by non-zero `cached_input_tokens` in
  both runs - run 1 (cold) 6/15 turns, 29,056 of 140,884 input tokens (20.6%);
  run 2 (warm) 14/15 turns, 109,184 of 169,219 (64.5%); turn 1 of every tenant is
  always cold; per-tenant cached totals 5,376 -> 27,904 (bytefix), 12,288 ->
  60,672 (sababa2), 11,392 -> 20,608 (sababa). No clock claim: 10/15 turns per
  run hit the 10 s turn budget and are censored out, so the completed samples are
  thin (bytefix 1/5 and 2/5, sababa2 1/5 and 2/5, sababa 0/5 both runs).
  Generation (45 cases, row `e8ab818f`) faithfulness 0.7628, answer_relevancy
  0.8124, citation_faithfulness 0.3737, refusal 0.000 - the faithfulness rise
  (+0.0465 against the slice-3 after row) is OUTSIDE the +0.0019 identical-code
  spread, an upward between-window shift with no mechanism in a delimiter-byte
  change, so it is not a regression and is not attributed to slice 5, while
  answer_relevancy (+0.0099) and citation (+0.0045) sit inside theirs.
  Trajectory (41 cases, row `6219ba04`) tool_correctness 0.6098 (25/41), persona
  1.000, step_efficiency 0.9677; the identical-code repeat (row `302b9a94`) gives
  0.6341 (26/41) / 1.000 / 0.9797, so the -0.0244 delta IS the same-code spread
  (the one flipped case is `knowledge-price-match-01`, flaky) and it sits inside
  `run_gate`'s -0.03
  ([report-slice-5.md](evidence/latency-2026-10/report-slice-5.md),
  [data/slice5-cache.md](evidence/latency-2026-10/data/slice5-cache.md)).
  **Slice 6 (paid-tier A/B across the matrix) is implemented, measured, and
  CLOSED WITH NO WINNER**: the cache-adjusted cost model shipped (`2004617`),
  the OpenRouter matrix ran twice at that commit and is heavily censored
  (13/15, 14/15, 12/15, 14/15 turns), ling's trajectory cannot run because its
  providers reject structured outputs (Novita 400, retry upstream with no
  choices) so no tool-correctness row exists, and the production primary Google
  gemini-3.5-flash-lite was added (`5a4578a`, no published price) with 10/15
  turns completed in a good window then 2/15 under 429s. No latency or
  correctness ranking is supportable. The cumulative package for slices 1-6 is
  [report-cumulative.md](evidence/latency-2026-10/report-cumulative.md) with raw
  tables in
  [data/cumulative.md](evidence/latency-2026-10/data/cumulative.md).
  **Slice 7 (streaming with inspection off the critical path) stays deferred and
  needs the founder to reopen scope.** The merge checklist and its two remaining
  blockers (slice 7 and the merge request) are in
  [13-latency.md](spec/active/13-latency.md#merge-readiness-slices-1-4).
- [ ] Production hardening (ticket 22, T-022 to T-033): per-IP rate limit and
  a 2000-character chat cap (T-022, built, ADR D32) and CI hygiene (T-023,
  built), Sentry on both surfaces (T-024 and T-025, built, ADR D33),
  security headers and a report-only CSP (T-026, built, ADR D34; enforcing it is
  T-027, after a real-deploy walkthrough), conversation delete backend
  (T-028, built, ADR D35) and its console action (T-029, built), retention
  (T-030, built, ADR D36), operator export and offboard (T-031, built),
  privacy and terms pages (T-032, built; placeholders in
  `frontend/src/lib/legal.ts` still to fill, lawyer review before real clients),
  and backups (T-033, built: `make db-dump` and a local restore drill in
  `deploy.md` Step 9; the production drill, the Supabase Backups page and the
  Free-versus-Pro decision are still open founder items). Billing and
   notifications are out of scope. Ticket file
   [12-refinement.md](spec/active/12-refinement.md) Part 4.
- [x] Storefront and console refinement batch 23-28: all six merged (23
  `b64736a`, 24 `c85e96f`, 25 `72f2944`, 26 `c14ff4f`, 27 `33a63b6`,
  28 `3823740`). Sparse-storefront invitation alignment, the desktop overlay
  standard, media replace hardening, Business page services edit plus
  candidate review, the Home link chip target, and the offerings-first review
  list. Archived ticket files are indexed in
  [the phase-1-complete archive](../archive/phase1-complete/README.md).
- [x] Required services, price-aware overview, knowledge Skip chip: `services`
  joins the required set and asks for a rough price with it, no beat renders
  "Skip for now" any more (`__skip__` and `SkipPayload` deleted), the
  knowledge ask keeps one always-visible Skip chip, and the storefront and its
  owner preview read the overview back when nothing is priced yet. Built on
  `feat/20-required-services` off M-7's base; archived ticket file
  [20-required-services.md](../archive/phase1-complete/20-required-services.md),
  ADR D30. Merged to `development` as PR #45. The 2026-10-01 walkthrough's
  one defect (the read-back printed the `services` list as a Python list) is
  fixed with tests.
- [x] Intent architecture and escalation-scoped contact capture: three intent
  families (information/offer/support) and four actions
  (respond/offer_followup/escalate/handoff) classified by the existing
  inspection call and persisted on the escalation row and message metadata;
  contact is captured at handoff (one name+email ask, never blocking). Code
  merged to `development` and `staging` as `5300586` (PR #43). The 2026-10-01
  walkthrough's defect (a name sent after the handoff re-sent the handoff) was
  fixed in `4cc2683`, and the preview re-walk passed, including a support turn
  and an owner-only email. Archived ticket file
  [19-intent-and-identity.md](../archive/phase1-complete/19-intent-and-identity.md);
  evidence in [the walkthrough ledger](evidence/walkthrough-2026-10/README.md).
- [x] Resumable owner input and offering normalization: optional beats can
  be skipped and stay skipped (ticket 20 retired the chip that did it), name
  proposals are confirmed rather than
  assumed, services are a normalized list, offering suggestions stay private
  until the owner reviews them, and categories are tenant-scoped rows
  (migration `0031`). Walked on the preview on 2026-10-01; the one defect it
  found (a price-list-only record could not be saved) was fixed in `7d8425b`
  and re-walked. Record in
  [12-refinement.md](spec/active/12-refinement.md), ADR D28.
- [x] U-1 through U-4 UX consistency: shared nav idiom, button feel,
  shared confirm dialog, toasts. Walked on the preview on 2026-10-01, and every
  Part 3 test box is backed by a named E2E check; record in
  [12-refinement.md](spec/active/12-refinement.md) Part 3.
- [ ] R-3 schema and type safety: `Active - todo`, not yet scoped. See
  [12-refinement.md](spec/active/12-refinement.md).
- [ ] R-4 remainder: founder judge calibration plus production-smoke
  evidence. See [12-refinement.md](spec/active/12-refinement.md).
- [ ] R-5 remainder: restore drill on production (the tooling and a local drill
  are built), error tracking live verification. See
  [12-refinement.md](spec/active/12-refinement.md).
- [x] RF-1 shared row grammar, focus visibility, and scroll restoration: merged
  in `ac11c6f`. One list-row grammar across the console lists, focus returns to
  the opener after a sheet closes, inner-container scroll is restored, the chat
  preview is a single truncated line, and the attention indicator is a compact
  amber exclamation badge. Record in the archived
  [12-refinement-rf-1-shared-ui.md](../archive/phase1-complete/12-refinement-rf-1-shared-ui.md).
- [x] RF-18 owner read state in the chat queue: merged in `e1d5144`.
  `conversations.owner_read_at` plus `POST /api/conversations/{id}/read`; the
  Unread filter reads the real field and an unread row bolds its title with a
  small accent dot. The Chats tab badge follow-up was resolved by RF-14, which
  moved it onto the server Needs you count. Record in the archived
  [12-refinement-rf-18-owner-read-state.md](../archive/phase1-complete/12-refinement-rf-18-owner-read-state.md),
  ADR D42.
- [x] RF-2 business-detail editing and immediate consistency: merged in
  `baa0ade`. Business name, hours, description and contact are editable in the
  Business details sheets, persisted to both profile jsonb copies, and reach
  the Business page and customer answers. Record in the archived
  [12-refinement-rf-2-business-detail-editing.md](../archive/phase1-complete/12-refinement-rf-2-business-detail-editing.md).
- [x] RF-3 offering search and category grouping: merged in `486156c`. The owner
  editor and the storefront filter the loaded catalog by name, description or
  category (case-insensitive substring) through one shared predicate;
  equal-priced distinct offerings stay distinct and category grouping is
  unchanged. Record in the archived
  [12-refinement-rf-3-offering-search.md](../archive/phase1-complete/12-refinement-rf-3-offering-search.md).
- [x] RF-4 explicit pricing wording: merged in `d6e3552`.
  `offerings.pricing_wording` (migration `0036`) is display-only and mutually
  exclusive with `price_cents`; the storefront and owner editor render it
  verbatim, priced offerings still format through `money.ts`, and the pricing
  engine never reads it. Record in the archived
  [12-refinement-rf-4-pricing-wording.md](../archive/phase1-complete/12-refinement-rf-4-pricing-wording.md).
- [x] RF-5 cover and offering-image workflows: merged in `eda75ec`. One shared
  media field covers the cover band and the offering editor with the same
  empty, uploading, preview, and saved states and an explicit Remove
  affordance; the cover removal is confirm-gated through `DELETE
  /api/business/cover`, shows a local preview while uploading, and restores the
  previous photo on failure. No backend or schema change. Record in the
  archived
  [12-refinement-rf-5-media-workflows.md](../archive/phase1-complete/12-refinement-rf-5-media-workflows.md).
- [x] RF-6 document-review workspace clarification: merged in `684a2bf`. Draft
  rows name their state with the shared status line, the review sheet drops its
  repeated source line and labels the footer secondary by context ("Discard
  draft" / "Remove source"), its two sections render in DOM order, and removing
  a saved source reuses the row-level removal confirmation with the "Removed"
  toast. Publication semantics unchanged; no API or DB change. Record in the
  archived
  [12-refinement-rf-6-document-review-clarity.md](../archive/phase1-complete/12-refinement-rf-6-document-review-clarity.md).
- [x] RF-7 business page composition and contextual owner editing: merged in
  `10c506f` (PR #68). The browse-first business page gains contextual owner
  shortcuts that open the same RF-2 editors from the page - one editor per field
  kind, two entry points, explicit Save and Cancel - with the owner markup gated
  server-side so customers and anonymous visitors never receive it. No API or DB
  change. Record in the archived
  [12-refinement-rf-7-business-page-shortcuts.md](../archive/phase1-complete/12-refinement-rf-7-business-page-shortcuts.md).
- [x] RF-8 desktop customer chat panels and mobile sheets: merged in `b01787e`
  (PR #69). On `lg+` the customer chat is a docked, non-modal right side panel
  (`role="complementary"`, no scrim, no `aria-modal`) that leaves the business
  page visible, scrollable, and interactive; below `lg` it stays the
  full-height modal bottom sheet with focus trap, scrim, Escape and scrim
  close. One `CustomerChat` instance is preserved across both presentations
  and across breakpoint changes. No API or DB change. Record in the archived
  [12-refinement-rf-8-desktop-chat-panel.md](../archive/phase1-complete/12-refinement-rf-8-desktop-chat-panel.md).
- [x] RF-9 offering and price-summary card alignment: merged in `86de712`
  (PR #70). `CatalogCard`, `PriceSummaryCard`, and `QuoteCard` share one
  width (`max-w-[520px]`, the value `design/frontend.md` section 4.7 already
  accepts) and one `Card` chrome, and the quote card's header matches the other
  two and carries `aria-label="Quote"`; the ticket's OPEN (420px versus 520px)
  is resolved at 520px. No API or DB change. Record in the archived
  [12-refinement-rf-9-card-alignment.md](../archive/phase1-complete/12-refinement-rf-9-card-alignment.md).
- [x] RF-10 preferred-name capture, correction, and persisted prompt limits:
  merged in `edab038` (PR #71). During the opening phase the assistant asks for
  a preferred name at most twice, tracked by a persisted, atomic counter
  (migration `0037`); the stored name reaches the customer surface as a
  name-only `contact` SSE event and shows in a display-only chip that is
  correctable in natural language through `set_customer_contact` and survives
  same-tab refresh; after the cap the prompt stops silently. Ticket 19's handoff
  contact capture is unchanged. Record in the archived
  [12-refinement-rf-10-preferred-name.md](../archive/phase1-complete/12-refinement-rf-10-preferred-name.md).
- [x] RF-11 visible human-help action and requested handoff: merged in
  `5e2dc3b` (PR #72). A visible **Ask for a person** control on the customer
  chat posts a new unauthenticated `POST /api/chat/handoff`, which records the
  same escalation row the assistant's `create_escalation` tool records through
  one shared writer and streams the deterministic handoff reply with the one
  contact ask when incomplete; the conversation stays non-terminal and an
  already-open escalation does not hand off twice. No schema change. Record in
  the archived
  [12-refinement-rf-11-ask-for-a-person.md](../archive/phase1-complete/12-refinement-rf-11-ask-for-a-person.md).
- [x] RF-12 same-tab refresh restoration of content, cards, and state: merged in
  `87375d5` (PR #73). The customer-safe `response` card payload rides
  `PublicMessage`/`list_messages` (read from `messages.metadata`; the raw
  owner-only blob never reaches the surface), a formal quote turn captures its
  live `quote` event into `metadata.response`, and `CustomerChat` persists and
  restores the conversation id, unsent composer draft, and handoff/escalated
  banner flags in `sessionStorage`, so cards, draft, and the human-reply poll
  survive a refresh. Restoring `handoffSeen`/`escalated` resumes the poll and
  locks the composer after a limit stop; a malformed persisted card degrades to
  a plain transcript. No schema change. Record in the archived
  [12-refinement-rf-12-refresh-restore.md](../archive/phase1-complete/12-refinement-rf-12-refresh-restore.md).
- [x] RF-13 failed-send recovery and draft preservation: merged in `0652b60`
  (PR #74). A failed send recovers in place: the failed message stores the exact
  payload as a discriminated retry target (send or handoff) and an inline Retry
  replays it once by a stable message id without appending a duplicate customer
  bubble; the draft is held as the in-flight payload and in `sessionStorage`,
  restored after a failure, and cleared only on success, so a newer draft
  survives a retry. The in-stream `error` event is treated as a failed send and
  a handoff failure carries a working inline retry; nothing auto-replays. No API
  or DB change. Record in the archived
  [12-refinement-rf-13-failed-send-recovery.md](../archive/phase1-complete/12-refinement-rf-13-failed-send-recovery.md).
- [x] RF-14 complete-dataset queue filtering, searching, pagination, and
  attention counts: merged in `3d8ca72` (PR #75). `GET /api/conversations`
  answers an envelope `{items,total,counts}` with a `filter`
  (`all`/`needs_you`/`unread`/`human`), a `q` search over name, reference, and
  open-escalation summary, and a derived `handler`; the Chats queue opens on
  Needs you (an open escalation or a human takeover) with per-tab counts and
  a server-backed "Load more", and the console badge is reconciled onto the
  Needs you count, closing the RF-18 follow-up. No migration: every value is
  derived or counted from existing state. Decisions: Unread retained as a
  fourth tab; envelope over `X-Total-Count`; counts respect `q` but not the
  filter. Record in the archived
  [12-refinement-rf-14-complete-queue.md](../archive/phase1-complete/12-refinement-rf-14-complete-queue.md).
- [x] RF-15 desktop split-pane Chats, mobile navigation preserved: merged in
  `24e4dc5` (PR #76). At `lg+` the queue list and the conversation
  thread are one split view with the list kept mounted by a route-persistent
  `chats/layout.tsx`; below `lg` the surface stays list-then-thread with the
  bottom bar, and `/chats/[id]` deep-links into the split. `chats/page.tsx`
  is the desktop placeholder; `--width-queue: 360px` is a new token. No API
  or DB change. Decisions: route-persistent layout; `lg`/1024 boundary in
  CSS; 360px queue token; mobile visibility route-keyed. Record in the
  archived
  [12-refinement-rf-15-chats-split-pane.md](../archive/phase1-complete/12-refinement-rf-15-chats-split-pane.md).
- [x] RF-16 explicit issue resolution in the conversation workspace: merged in
  `c59d4d0` (PR #77). Resolution is an explicit third action in the Chats
  thread (`/chats/[id]`): `ConversationDetail` carries a derived
  `pending_escalation_id`, the thread shows an inline resolve shelf from the
  Handling state whether or not the owner has taken over, with its own
  confirmation and an optional customer-facing message, and
  `POST /api/escalations/{id}/resolve` always writes the owner-only `system`
  stamp `RESOLUTION_STAMP = "You resolved this issue"` before the optional
  `human_agent` message; replying and handing back never resolve. No migration,
  no schema change, no new route. Decisions: resolution is available from
  Handling, not gated on takeover; the stamp is an owner-only `system` message
  reusing the transcript role filter; the stamp is written first at
  `now() + interval '1 microsecond'` for deterministic order; the thread reads
  the escalation id from the derived `pending_escalation_id`; resolving while
  taken over does not clear Needs you, handback does. Record in the archived
  [12-refinement-rf-16-explicit-resolution.md](../archive/phase1-complete/12-refinement-rf-16-explicit-resolution.md).
- [x] RF-17 four-business walkthroughs with visual and behavioral evidence:
  merged in `236000e` (PR #78). The four seeded businesses (cafe `sababa`,
  retail-repair `bytefix`, dental `lumident`, general clinic `wellspring`) are
  walked on identical workflow code with configuration-only differences by a new
  deterministic five-test Playwright spec plus a cross-tenant isolation check;
  24 screenshots map to the named tests in the evidence ledger
  [rf-17-2026-10-03](evidence/rf-17-2026-10-03/README.md). The fourth business is
  a config-only seed, with no API/DB/schema change and no vertical branching.
  Decisions: the general clinic was added as seed data so the domain-agnostic
  invariant holds; evidence runs on the local Docker Compose stack and never
  touches the production-sharing preview; the spec is a permanent regression
  spec with `RF17_CAPTURE` opt-in, viewport-only. Record in the archived
  [12-refinement-rf-17-four-business-walkthrough.md](../archive/phase1-complete/12-refinement-rf-17-four-business-walkthrough.md).
- [x] Chat lifecycle: handoff removal, Waiting, Resolve, and auto-resolve
  (D43-D45). The customer-side "Ask for a person" control and its client-only
  helpers are removed (the deterministic endpoint and the assistant's own
  escalation path stay); Action needed narrows to an open escalation or a
  taken-over thread whose last word came from the customer, with "Waiting on
  customer" for the other side; one owner-only conversation-level resolve
  (`POST /api/conversations/{id}/resolve`, migration `0038`) closes any open
  escalation and reopens on a customer reply; and a throttled lazy sweep
  auto-resolves after seven days of customer silence
  (`config.limits.auto_resolve_days`). Queue tabs are Action needed / Unread /
  All / Resolved. Record in [decisions.md](design/decisions.md) D43-D45.
- [x] Sabbaba demo showcase: the `sababa` seed is rebuilt from the source menu
  document (96 items in 10 categories, 94 priced with one `each` rule each, the
  rest unpriced; hours, allergen, ratings and per-category price docs as
  knowledge) and seeded directly, with no onboarding. 44 item photos plus a
  cover live in the owner's Cloudinary under `demo/sabbaba/` (uploaded once by
  `scripts/seed_sabbaba_images.py`, recorded in `seeds/sabbaba/images.json`);
  items without a reliable photo show the letter tile. The seed stays offline.
  Hosted `sababa` re-seeded 2026-10-08 (96 offerings, 94 rules, 109 embedded chunks; `sababa` only, never `seed_demo`).
- [x] Sabbaba 2 fast-path demo tenant: a fifth demo tenant (`sababa2`) clones
  Sabbaba's full 96-item menu, photos, orders and console conversations with
  the catalog copy summarized to one line per item and the knowledge prose
  condensed, so the whole prompt takes the 2-call fast path instead of hybrid
  retrieval (measured 9,825/11,500 tokens, 1,675 margin, 13 corpus chunks).
  `CORPUS_FAST_PATH_MAX_TOKENS=11500` and `CATALOG_INLINE_MAX_TOKENS=5500` in
  `.env.example` size it for the Gemini primary/paid legs - over Groq's free
  8K TPM, so such turns skip to the OpenRouter failover (documented in
  `deploy.md` and `architecture.md`). The seed fails loudly if the tenant
  would not take the fast path. Standalone `make seed-sababa2`; wired into
  `make seed` with login `owner@sababa2.dev`.
- [x] Pre-demo criticals (branch `fix/pre-demo-criticals`, 2026-10-08), from the
  interim Sabbaba chat eval: the assistant no longer asks for a name on the
  first turn and keeps the reply to its own ask as the customer's name; the
  contract carries a source's caveat with its fact; `sababa2` keeps its five
  most-liked items; the catalog card caps at five rows per category with a
  "+N more" line; spotlight envelopes are stripped from model prose; the
  default step cap is 12 (a redraft-then-escalate walk is 9 supersteps); a turn
  that runs over its time budget hands off without locking the conversation.
  Known residual: allergen caveat wording is model judgement, not a guarantee.
- [x] Sababa2 seed links its owner (branch `feat/sababa2-seed-owner-link`,
  2026-10-08): standalone `make seed-sababa2` now find-or-creates
  `owner@sababa2.dev` and attaches it to the tenant, so the console login lands
  on the pre-onboarded tenant with no interview. The profile and
  `onboarding.completed` were already seeded by `insert_tenant_core`.
- [ ] E2E flake: `chats-takeover` timed out on the RF-3 closeout full
  `make test-e2e` (169 passed, 1 failed) because its freshly created
  conversation arrived `escalated` (terminal) rather than `open`. Reproduced
  with the RF-3 backend files stashed, so it is not an RF-3 defect. Treat as an
  environment/provider flake and investigate separately.
- [ ] Provider-backed `make eval` has no valid baseline: deterministic
  gates pass, LLM legs fail on free-tier quota (Groq 200k TPD 429, four
  attempts). Needs a paid tier or a smaller eval slice.
- [x] Catalog retrieval gate: a catalog whose formatted text exceeds
  `catalog_inline_max_tokens` (default 1500) is no longer pasted into the
  prompt. The package forces the hybrid path, the prompt says the menu is not
  inline, and items are reached through `recommend_items` / `search_knowledge`;
  inspection counts the items a turn fetched as provenance. A measured token
  count, never a branch on business type. No migration.
- [x] Category management and multi-category offerings: controlled category
  objects, explicit owner confirmation, ordered many-to-many membership with
  one primary, multi-shelf storefront and chat rendering, and generic food,
  dental, and repair seeds shipped with migration `0034` and ADR D31.
  Automated gates and responsive owner/storefront visual checks are green;
  evidence is recorded in the archived
  [21-category-management.md](../archive/phase1-complete/21-category-management.md).
- [ ] Ops: configure Brevo SMTP on the hosted project (built-in mailer is
  member-only); automate hosted migrations (`deploy.yml` runs no migrate step).
  Procedure is in [deploy.md](deploy.md).
- [x] Ops: the `VERCEL_TOKEN` repo secret is set, so `registry-cleanup.yml` runs.
  Without it the daily prune failed on purpose from 2026-09-30, the container
  registry filled to the 50-image cap on both repositories, and every
  `development` deployment from `c14ff4f` onward went to ERROR at the image-push
  step (`denied` on `vcr.vercel.com/.../frontend`). Fixed on 2026-10-08:
  `make vcr-prune-apply` brought both repositories back to 5 and 4 images, the
  secret was added, and a manual `workflow_dispatch` prune passed. The
  development preview for `f3ad4b8` then built READY. Validate with
  `make vcr-prune` and a green `Container registry cleanup` run.
- [x] Ops: hosted migration drift caught and closed. The hosted ledger held 34
  migrations while `staging` code expected 36, so `offerings.pricing_wording`
  (0036) was missing: `/api/public/tenant/bytefix/storefront` returned 500 and
  `/bytefix` served the Next error shell with a 200 (the exact silent failure
  `deploy.md` Step 1 warns about, and the smoke test's name assertion catches).
  On 2026-10-08 a dump was taken with `make db-dump` and 0035-0038 were applied
  with the Step 1 runner; the ledger now matches the repo at 38 and both routes
  answer 200. Automation of the hosted migrate step is still open above.

## Spec status

| Location | Status | Contents |
|---|---|---|
| [spec/active/08-deferred.md](spec/active/08-deferred.md) | `Deferred - Phase 2` | B-2, D-1, D-3 |
| [spec/active/12-refinement.md](spec/active/12-refinement.md) | `Active - todo` | R-3, R-4 remainder, R-5 remainder (RF-1 through RF-18 delivered and archived) |
| [spec/active/13-latency.md](spec/active/13-latency.md) | `Active - in progress, merge-ready pending slice 7 and the go` | Latency instrument and model matrix, slices 1-7 stacked on `latency/stack` (slice 1 landed; slice 2 measured, mechanism-inert; slice 3 measured at `2ac8247`, PASS on the mechanism with both founder rulings recorded on 2026-10-19 - citations cited-only and internal only, generation FAIL accepted as a provider level shift with the tolerance unchanged; slice 4 measured at `040a473`, PASS structurally with no clock effect; slice 5 measured at `d99ca54`, gate PASS with the cache proven by non-zero `cached_input_tokens` and no clock claim, the trajectory delta bounded by an identical-code repeat; slice 6 measured at `2004617`/`5a4578a`, CLOSED WITH NO WINNER - cache-adjusted cost shipped, OpenRouter matrix heavily censored, ling has no tool-correctness row, Google swung 10/15 to 2/15 under 429s, so no ranking is supportable; cumulative package for slices 1-6 built - hybrid calls p50 4.0 -> 3.0, fast tenants unchanged, no clock claim; slice 7 deferred, and the merge checklist has two remaining blockers) |
| [archived tickets](../archive/phase1-complete/README.md) | `Done - merged` | All delivered feature, deployment, and supporting phases, including M-7 and the 23-28 refinement batch |

Phase 1 is not called fully complete until the active refinement items
are validated or explicitly accepted as deferred.
