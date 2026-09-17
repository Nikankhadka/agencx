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

| Area | Tickets |
|---|---|
| Foundation and tenancy | A-1, A-2 |
| Onboarding and login | O-1, O-2, O-5 through O-12 |
| Chat spine and providers | P-1 through P-5 |
| Grounded chat | O-3, O-4 |
| Money and escalation safety | C-1 through C-6 |
| Tenant console | E-1, E-2, E-4 through E-6 |
| Storefront and media | M-1 through M-6 |
| Product polish and hygiene | B-1, B-3, D-2, E-3, F-1 through F-3, G-1 |
| Developer experience and deployment | K-1, B-4 |
| Security and API reliability | R-1, R-2, R-4 US-1, R-5 US-1 |
| Walkthrough fixes | W-1 through W-9, `Done - merged` |
| Schema drop | W-10, `Done - merged`, migration `0029` |
| Document review | W-11a, W-11b, W-11c, `Done - merged` |
| Auth OTP reliability | W-12, W-13, `Done - merged`, hosted-verified |

Detailed records live in [the completed specs](spec/README.md).
Verification narratives live in the ticket files, not here.

## What is next

- [ ] M-7 storefront redesign: no-image-first rebuild with one persistent
  chat entry. `Active - in progress` on `feat/m7-storefront-redesign`;
  ticket file lands with that branch. Founder mobile and desktop
  walkthrough is the remaining step before merge.
- [ ] U-1 through U-4 UX consistency: shared nav idiom, button feel,
  shared confirm dialog, toasts. `Active - awaiting review` on
  `feat/ux-consistency`; see
  [15-ux-consistency.md](spec/completed/15-ux-consistency.md).
- [ ] R-3 schema and type safety: `Active - todo`, not yet scoped. See
  [12-refinement.md](spec/active/12-refinement.md).
- [ ] R-4 remainder: founder judge calibration plus production-smoke
  evidence. See [12-refinement.md](spec/active/12-refinement.md).
- [ ] R-5 remainder: backups and restore drill, error tracking, E2E in
  CI, dependency scanning. See
  [12-refinement.md](spec/active/12-refinement.md).
- [ ] Provider-backed `make eval` has no valid baseline: deterministic
  gates pass, LLM legs fail on free-tier quota (Groq 200k TPD 429, four
  attempts). Needs a paid tier or a smaller eval slice.
- [ ] Ops: add the GitHub `VERCEL_TOKEN` secret; configure Brevo SMTP on
  the hosted project (built-in mailer is member-only); automate hosted
  migrations (`deploy.yml` runs no migrate step). Procedure is in
  [deploy.md](deploy.md).

## Spec status

| Location | Status | Contents |
|---|---|---|
| [spec/active/08-deferred.md](spec/active/08-deferred.md) | `Deferred - Phase 2` | B-2, D-1, D-3 |
| [spec/active/12-refinement.md](spec/active/12-refinement.md) | `Active - todo` | R-3, R-4 remainder, R-5 remainder |
| [spec/completed/15-ux-consistency.md](spec/completed/15-ux-consistency.md) | `Active - awaiting review` | U-1 through U-4, misfiled, moves to `active/` |
| [HiveAgencyXRefinement.md](HiveAgencyXRefinement.md) | `Active - todo` | RF proposal, moves to `active/18-refinement-proposal.md` |
| [spec/completed/](spec/completed/) | `Done - merged` | All delivered feature, deployment, and supporting phases |
| [archived R-1 and R-2](../archive/phase1-complete/12-refinement-r1-r2.md) | Historical | Completed refinement records |

Phase 1 is not called fully complete until the active refinement items
are validated or explicitly accepted as deferred.
