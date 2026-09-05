# Agencx build dashboard

## Current status

The Stage 1 product is deployed on Vercel and the production smoke test is
green. Feature delivery is complete. Phase 1 refinement remains open for
schema/type safety, judge calibration, production evidence, and operational
hardening.

| Environment | Value |
|---|---|
| Production branch | `staging` |
| Live origin | `https://agencx-iota.vercel.app` |
| Preview branch | `development` |
Production database: hosted Supabase, migrated and seeded with `bytefix`

## What's done

| Area | Tickets and evidence |
|---|---|
| Foundation and tenancy | A-1, A-2; schema, RLS, auth, tenant resolution |
| Onboarding and login | O-1, O-2, O-5, O-6, O-7, O-8, O-9, O-10, O-11, O-12 |
| Chat spine and providers | P-1, P-2, P-3, P-4, P-5; Google primary, fallback tiers, latency race, preload, invalidation, typing indicator |
| Grounded chat | O-3, O-4; hybrid retrieval, URL/document ingest, context package |
| Money and escalation safety | C-1, C-2, C-3, C-4, C-5, C-6; deterministic pricing, figure gate, non-terminal handoff, staff takeover |
| Tenant console | E-1, E-2, E-4, E-5, E-6; Home, Chats, Business, Booking, responsive navigation |
| Storefront and media | M-1, M-2, M-3, M-4, M-5, M-6; owner offerings, prices, Cloudinary media, reviewed imports |
| Product polish and hygiene | B-1, B-3, D-2, E-3, F-1, F-2, F-3, G-1 |
| Developer experience and deployment | K-1, B-4; containerized development, two Vercel services, same-origin routing, hosted embedding and reranking |
| Security and API reliability | R-1, R-2, R-4 US-1, R-5 US-1; Problem Details, safe SSE errors, request correlation, SSRF protection, Google tool-history fix |

Detailed records live in [`spec/completed/`](spec/completed/).

## What's next

- [ ] R-3: audit success schemas and explicit unknown-field policies.
- [ ] R-4: complete founder judge calibration and record additional production-smoke evidence.
- [ ] R-5: decide and validate backups/restore, error tracking, E2E-in-CI, and dependency scanning.
- [ ] Add the GitHub `VERCEL_TOKEN` secret so registry cleanup can run. The local Vercel token is not a repository secret.
- [ ] Record the QA pass, root-cause fixes, regression tests, and measured optimization results.
- [x] W-1: cap the home escalation queue by screen size, not a fixed row count, and keep it fresh without a manual reload.
- [x] W-2: stop the onboarding interview from re-asking a filled slot.
- [ ] W-3: keep the onboarding thread clear and responsive - empty placeholders, stable composer geometry, one pending indicator, animated upload processing, and a proven SSE/ordinary-request transport split.
- [ ] W-4: complete go-live address handling - the suggested slug on every confirm-opening path, actionable field errors, owner-typed addresses preserved, and recoverable network failures.
- [ ] W-5: ground one customer chat answer in both the confirmed offerings catalog and uploaded knowledge together, using the existing context package.
- [ ] W-6: extract accurate offerings from the complete source - distinct items, source-backed descriptions, deterministic item-bound prices, complex-price preservation, and possible-match proposals.
- [x] W-7: make the interview read like a person - challenge junk input, drop the
  skip chip, keep replies short, address-only go-live, priced offering cards.
- [ ] W-8: review a large import without losing information - five-item preview, five-per-page editor, combine/keep-both duplicate decisions, and readable editable knowledge sections.
- [ ] W-9: correct captured information conversationally - conservative wording cleanup, explicit corrections on any beat, offering correction operations, and a single acknowledgement for a captured or corrected name.

**Phase 13 specification amended 2026-09-05** (`docs/phase13-walkthrough-refinement`): a second walkthrough round and its planning refined W-3 through W-6, added W-8 and W-9, and corrected the phase introduction to nine tickets. This is a specification update, not implementation delivery. W-1, W-2, and W-7 remain shipped with their records preserved; W-3 through W-6, W-8, and W-9 keep their software delivery statuses open, and no runtime fix is claimed from the repository scans.

## Known gaps and deliberate deferrals

- The owner Copilot route is deferred to Phase 2.
- Per-tenant tool gating and its toggle UI are deferred to Phase 2; advanced tools remain built but off by default in the lean configuration.
- `agencx.app` is deferred until the founder buys and binds the domain. The Vercel origin is the current stand-in.
- Judge calibration needs founder labels to avoid circular evaluation.
- The Hobby deployment has cold starts and Supabase can pause after inactivity; keep-warm mitigates this for the portfolio deployment.
- No real customer data should use the free-tier LLM and embedding providers until the provider decision changes.
- Custom SMTP (Brevo) is not yet configured on the hosted Supabase project. Its built-in mailer delivers only to project members at ~2/hour, so no real tenant owner can receive a login code until Brevo is set (`deploy.md` Step 1.5) - found 2026-09-04 while fixing the login OTP misconfiguration below.

## Spec status

**Two abandoned attempts sit behind `M-1`/`M-4`, and the record is the point.**
A Codex session built `M-1` on `feat/offerings-media-import` and renamed
`catalog_items` to `offerings`; a second, on `feat/business-storefront`, built
the storefront but kept `catalog_items`, reversed the rename in its own
migration, and dropped prices from offerings entirely. The founder ruled on
both open questions - the rename stands, and prices are owner-typed facts that
belong on the page (D24) - so the first branch merged to `development` as
`M-1` and the second was rebuilt on top of it as `M-4`. Nothing was thrown
away except the reversal migration. The dev database carried both experiments
plus a `0023_storefront_gallery.sql` that exists in no branch, so it was reset
from schema zero to prove `0001`-`0024` apply in order.

O-5 pulled **B-3 US-1** (the lighter crimson `#C1123F`) forward, because the
prototype the onboarding thread is ported from carries that ramp - B-3 stays
open for US-2, the `STATUS_TONE` map.

**Phase 1 refinement (`12-refinement.md`) has opened.** R-1 (documentation
truth), R-2 (the standard API contract), R-4 (reliability and provider, US-1),
and R-5 (operations and security, US-1) are closed: every JSON error is RFC
9457 Problem Details, SSE streams fail safely with a typed `error` event,
`api-contract.md` documents the shape, D-4 and other stale documentation is
reconciled against the code, Google's tool-history bug is fixed, and the
URL-ingest path is hardened against SSRF. **R-3 (schema and type safety) is
open as a backlog entry**, not yet scoped into a full ticket; R-4 and R-5 each
keep an open second half (judge calibration/production-smoke evidence;
backups, error tracking, E2E-in-CI, dependency scanning). No Phase 2 feature
work happens as a side effect of this phase - recommendation, quoting, and
order/ticket lookup stay exactly where D-2 left them: built, exposed to every
tenant today because D-1's per-tenant gating hasn't landed yet, not deleted or
deferred out of the codebase.

**Owner-home escalation queue is unticketed UI polish** (founder request,
2026-09-04, `feat/owner-escalation-panel`), not a spec ticket. Home's
`WaitingPanel` replaces the single collapsed "waiting" `BriefItem` with one
row per customer who needs the owner (name, relative time, the assistant's
one-line summary), sorted oldest escalation first and capped to 3 with a
"Show all N" expand; a row links straight to `/chats/:id` rather than the bare
list. The Chats tab badge (bottom bar and sidebar) now carries the count
instead of a bare dot. `escalations.summary` is only ever written today by the
`create_escalation` tool - the price_gate/inspection/limit paths leave it
NULL - so a new async summariser (`app/agents/escalation_summary.py`) fills it
from the last few messages after the customer's turn is already on the wire
(never inside it: T-028's 10s turn budget has no room for an extra LLM call at
the point an escalation fires). `ConversationSummary` gained `pending_since`
(the escalation's own timestamp) alongside the existing `pending_summary`.
Also fixed in passing: the Chats-list attention dot and the new count badges
disagreed on which amber to use (`--color-warning`'s amber-500, a "kept from
the prior system" holdover that reads brown at text weight and fails 4.5:1
against its own subtle background, versus `--color-highlight`'s amber-400,
the prototype's actual notification colour). W-1 points `--color-highlight`
at that prototype literal, with 8.6:1 dark-text-on-solid-fill contrast, and
every "wants the owner" indicator in the app uses it consistently.

**Hosted login OTP was misconfigured, not a code bug** (found 2026-09-04,
`fix/hosted-otp-sends-link`). Staging's login-in-chat mailed a magic LINK to
Supabase's default Site URL (`http://localhost:3000`) instead of the
six-digit code the UI asks for - `auth_logs` showed `POST /otp` 200 followed
by `GET /verify` **303** (a clicked link, not a typed code, which is a `POST
/verify` 200), and `auth.users.recovery_sent_at` was stamped instead of
`confirmation_sent_at`, confirming the Magic Link template's link-only
default had rendered. `signInWithOtp`/`verifyOtp` (`login/page.tsx`) were
already correct; the hosted project's Auth config (Site URL, URI allow list,
Magic Link and Confirm signup email templates) had simply never been set per
`deploy.md`'s own Step 1.5, which calls this "blocking, not optional." Fixed
by PATCHing the project's Management API config directly - `deploy.md` Step
1.5 now gives literal field values and `curl` commands instead of
dashboard-click prose, and `docker-compose.yml` gained
`GOTRUE_MAILER_TEMPLATES_CONFIRMATION` so local dev mirrors both templates
hosted needs. Custom SMTP (Brevo) is a separate, still-open gap (above): this
fix restores the founder's own login, but a real tenant owner receives
nothing until Brevo is configured.

**Phase 13 (walkthrough fixes) has opened** (`13-walkthrough.md`, 2026-09-04).
A founder walkthrough of the deployed build found defects across the home
escalation queue, the onboarding interview, and customer chat grounding. Two
of the six tickets, W-1 and W-5, refine work this same session already
shipped (the escalation queue above, and `fix/customer-offering-context`'s
offerings-grounding fix) rather than building it fresh. W-2 is the largest
ticket: the onboarding interview's next question has always been chosen
deterministically but composed by a second, unconstrained LLM call, which let
it re-ask a business name already on file - the fix makes the server emit the
question verbatim, the same way the chip-answer path already does, and adds a
flow-change confirmation rule to `conventions.md` so a working conversational
flow is not altered again without a flagged before/after. The phase was
extended to nine tickets by a second walkthrough round and its planning
(`docs/phase13-walkthrough-refinement`, 2026-09-05) - refined W-3 through
W-6, new W-8 and W-9 - as a specification update only; those tickets remain
open for implementation.

**W-2 shipped** (2026-09-05, `fix/w-2-onboarding-repeat`). Building it surfaced
that the ticket named a symptom the spec had mis-sized: there was no repeat cap
anywhere to raise or lower - `next_beat` was a stateless rescan and
`off_topic_count` was incremented but read by nothing - and every one of the
nine beats was a hard gate, so an unanswerable one looped forever and blocked
go-live. The diagnosis that shaped the fix is that *adjacency*, not count, is
what made the transcript infuriating: three business-name questions back to
back. So each beat now gets two asks, and then resolves rather than repeating -
a skippable beat takes a default or is dropped, a required one is deferred to a
second pass that returns only once every other beat is done. Which beats are
which follows one rule: skippable means nothing downstream reads it, or the
owner can still edit it after go-live. On the final pass the owner's own words
are never stored as a fallback: an unresolved required field pauses the
interview, survives reload, and offers a retry with a fresh two-ask allowance.
Go-live stays blocked until it has a valid value. A skipped beat deliberately
writes no sentinel into the profile - `profile_tagline` renders `services` and
`hours` straight into the public storefront subtitle, so a "skipped" string
there would have shown to customers.

Still open from this ticket's edges: `hours` and `contact` are required only
because no post-go-live editor exists for them. A profile editor at
Business > details would let them become skippable, and is the natural
follow-up.

**W-5 shipped** (2026-09-05, `fix/w-5-combined-grounding`). The customer chat
answered "what do you offer?" from the confirmed catalog and stopped there,
surfacing uploaded knowledge only on a second, more insistent question. Three
mechanisms caused it and all three were prompt-level: the offerings block told
the model to "enumerate the complete catalog before offering to share more
detail", the tool guidance said that answer "is in the material above", and on
the hybrid path the catalog could never reach the same generation as the
retrieved chunks because `_build_knowledge_prompt` only ever saw
`retrieved_chunks`. The catalog now rides in state as `offerings_text`, set
beside the existing `owner_material` on both of the agent node's return paths,
so the draft node can put both sources in front of one generation without a
second query.

The ticket missed one thing that would have made the fix backfire: the
grounding judge's only evidence is `_provenance_text`, which read
`retrieved_chunks` alone, and catalog rows are stripped from retrieval on both
paths on purpose (M-1). A reply naming a confirmed offering therefore had no
provenance in front of the judge, so doing exactly what W-5 asks for would have
failed grounding and escalated. The offerings block is appended there too. The
price gate needed nothing - `owner_material` already carried the catalog
string, which is why the money guardrail never showed the same gap.

Verified through the real customer chat with a live model rather than a mocked
turn: the repo's E2E convention deliberately scripts customer turns through
`page.route` (`e2e/typing-indicator.spec.ts` header) because a free-tier model
makes timing non-deterministic, and a mocked `/api/chat` would mock away the
server-side prompt assembly that is the whole change. Before and after were run
twice each against `bytefix`.

| Location | Status | Contents |
|---|---|---|
| [`spec/active/08-deferred.md`](spec/active/08-deferred.md) | Deferred | B-2, D-1, D-3 |
| [`spec/active/12-refinement.md`](spec/active/12-refinement.md) | Open | R-3, R-4, R-5 |
| [`spec/active/13-walkthrough.md`](spec/active/13-walkthrough.md) | Open | W-1 through W-9 (W-1, W-2, W-5, W-7 delivered; amended 2026-09-05) |
| [`spec/completed/`](spec/completed/) | Complete | All delivered feature, deployment, and supporting phases |
| [`docs/archive/phase1-complete/`](../archive/phase1-complete/) | Historical | Completed R-1 and R-2 records |

Phase 1 is not called fully complete until the active refinement items are
validated or explicitly accepted as deferred. QA and optimization are separate
from the documentation closeout and must be evidence-driven.
