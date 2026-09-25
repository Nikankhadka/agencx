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

## What is next

- [ ] Production hardening (ticket 22, T-022 to T-033): per-IP rate limit and
  a 2000-character chat cap (T-022, built, ADR D32) and CI hygiene (T-023,
  built), Sentry on both surfaces (T-024 and T-025, built, ADR D33),
  security headers and a report-only CSP (T-026, built, ADR D34; enforcing it is
  T-027, after a real-deploy walkthrough), conversation delete backend
  (T-028, built, ADR D35) and its console action (T-029, built), retention
  (T-030, built, ADR D36), operator export and offboard (T-031, built),
  privacy and terms pages (T-032, built; placeholders in
  `frontend/src/lib/legal.ts` still to fill, lawyer review before real clients),
  then backups. Billing and notifications are out of scope. Ticket file
  [22-production-hardening.md](spec/active/22-production-hardening.md).
- [ ] Required services, price-aware overview, knowledge Skip chip: `services`
  joins the required set and asks for a rough price with it, no beat renders
  "Skip for now" any more (`__skip__` and `SkipPayload` deleted), the
  knowledge ask keeps one always-visible Skip chip, and the storefront and its
  owner preview read the overview back when nothing is priced yet. Built on
  `feat/20-required-services` off M-7's base; ticket file
  [20-required-services.md](spec/active/20-required-services.md), ADR D30.
  Merged to `development` as PR #45; founder preview walkthrough remains.
- [ ] Intent architecture and escalation-scoped contact capture: three intent
  families (information/offer/support) and four actions
  (respond/offer_followup/escalate/handoff) classified by the existing
  inspection call and persisted on the escalation row and message metadata;
  contact is captured at handoff (one name+email ask, never blocking). Code
  merged to `development` and `staging` as `5300586` (PR #43); ticket file
  [19-intent-and-identity.md](spec/active/19-intent-and-identity.md). Founder
  preview walkthrough remains.
- [ ] Resumable owner input and offering normalization: optional beats can
  be skipped and stay skipped (ticket 20 retired the chip that did it), name
  proposals are confirmed rather than
  assumed, services are a normalized list, offering suggestions stay private
  until the owner reviews them, and categories are tenant-scoped rows
  (migration `0031`). Code in `development`, founder walkthrough on the
  preview deploy remains; record in
  [12-refinement.md](spec/active/12-refinement.md), ADR D28.
- [ ] U-1 through U-4 UX consistency: shared nav idiom, button feel,
  shared confirm dialog, toasts. Code in `development`, founder
  walkthrough remains; record folded into
  [12-refinement.md](spec/active/12-refinement.md) Part 3.
- [ ] R-3 schema and type safety: `Active - todo`, not yet scoped. See
  [12-refinement.md](spec/active/12-refinement.md).
- [ ] R-4 remainder: founder judge calibration plus production-smoke
  evidence. See [12-refinement.md](spec/active/12-refinement.md).
- [ ] R-5 remainder: backups and restore drill, error tracking, E2E in
  CI, dependency scanning. See
  [12-refinement.md](spec/active/12-refinement.md).
- [ ] RF-1 through RF-17 product refinement: `Active - todo`, design
  intent in [12-refinement.md](spec/active/12-refinement.md) Part 2.
- [ ] Provider-backed `make eval` has no valid baseline: deterministic
  gates pass, LLM legs fail on free-tier quota (Groq 200k TPD 429, four
  attempts). Needs a paid tier or a smaller eval slice.
- [x] Category management and multi-category offerings: controlled category
  objects, explicit owner confirmation, ordered many-to-many membership with
  one primary, multi-shelf storefront and chat rendering, and generic food,
  dental, and repair seeds shipped with migration `0034` and ADR D31.
  Automated gates and responsive owner/storefront visual checks are green;
  evidence is recorded in
  [21-category-management.md](spec/active/21-category-management.md).
- [ ] Ops: add the GitHub `VERCEL_TOKEN` secret; configure Brevo SMTP on
  the hosted project (built-in mailer is member-only); automate hosted
  migrations (`deploy.yml` runs no migrate step). Procedure is in
  [deploy.md](deploy.md).

## Spec status

| Location | Status | Contents |
|---|---|---|
| [spec/active/08-deferred.md](spec/active/08-deferred.md) | `Deferred - Phase 2` | B-2, D-1, D-3 |
| [spec/active/12-refinement.md](spec/active/12-refinement.md) | `Active - todo` | R-3, R-4 remainder, R-5 remainder, RF-1 through RF-17, shipped U-1 through U-4 and onboarding-normalization records |
| [spec/active/19-intent-and-identity.md](spec/active/19-intent-and-identity.md) | `Active - awaiting review` | Intent families and actions, escalation-scoped contact capture |
| [spec/active/21-category-management.md](spec/active/21-category-management.md) | `Done - verified` | Category management and multi-category offerings (migration `0034`, ADR D31) |
| [spec/active/22-production-hardening.md](spec/active/22-production-hardening.md) | `Active - in progress` | Abuse control, data lifecycle, error tracking, security headers, backups (T-022 to T-033, ADRs D32-D36) |
| [archived tickets](../archive/phase1-complete/README.md) | `Done - merged` | All delivered feature, deployment, and supporting phases, including M-7 |

Phase 1 is not called fully complete until the active refinement items
are validated or explicitly accepted as deferred.
