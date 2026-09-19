# Agencx specs and user stories

The spec set records the Agencx change build. Each ticket holds intent,
acceptance criteria, implementation constraints, verification, and
definition of done. One ticket equals one commit, and commit messages
start with the ticket id.

## Status vocabulary

Every ticket header uses one of these labels. This table owns them.

| Label | Meaning |
|---|---|
| `Active - todo` | Ticket written, work not started |
| `Active - in progress` | Branch exists, work under way |
| `Active - PR open` | PR open to `development`, checks listed |
| `Active - awaiting review` | Code complete, founder walkthrough remains |
| `Done - merged` | Merged to `development` or `staging`, commit or PR cited |
| `Deferred - Phase 2` | Explicitly out of Phase 1 |

Per-ticket header pattern:

```md
**Status:** Active - PR open on feat/example.
**Phase 1 area:** Storefront and media.
```

## Active work

| Location | Contents | Status |
|---|---|---|
| [active/08-deferred.md](active/08-deferred.md) | B-2, D-1, D-3 | `Deferred - Phase 2` |
| [active/12-refinement.md](active/12-refinement.md) | R-3, R-4 remainder, R-5 remainder, RF-1 through RF-17, shipped U-1 through U-4 record | `Active - todo` (U part shipped, walkthrough remains) |
| [active/17-storefront-redesign.md](active/17-storefront-redesign.md) | M-7 storefront redesign: no-image-first base, Uber Eats-style mature state, one persistent chat entry | `Active - awaiting review` (PR #41; founder preview walkthrough remains) |
| [active/19-intent-and-identity.md](active/19-intent-and-identity.md) | Intent families and actions, escalation-scoped contact capture | `Active - awaiting review` (merged as 5300586, PR #43; founder walkthrough remains) |

## Completed work

All delivered tickets live in
[the phase-1-complete archive](../../archive/phase1-complete/README.md):
foundation, onboarding, chat spine, chat grounding, business page, polish,
hygiene, developer experience, deployment, offerings and media, R-1/R-2
refinement, walkthrough fixes W-1 through W-9, schema drop W-10, document
review W-11, and auth OTP W-12/W-13 - with the walkthrough evidence logs.

## Prototype currency

| Prototype | Status |
|---|---|
| [agencx-prototype-v6.html](../design/prototypes/agencx-prototype-v6.html) | Current app reference |
| `agencx-storefront-customer-v4.html` | Current storefront reference (M-7: no-image-first base, Uber Eats-style mature state, single header chat entry) |
| [archived v3 storefront](../../archive/prototypes/agencx-storefront-customer-v3.html) | Interaction vocabulary only |

No v7 prototype exists - the refinement design intent in
[active/12-refinement.md](active/12-refinement.md) Part 2 was specified
against a v7 that was never built; shipped refinement was implemented
against v6 plus `design/frontend.md`.

Port structure, states, spacing, and interaction vocabulary. Use prototype
behaviour, never prototype copy or hex values. Visual values belong in
`frontend/src/styles/theme.css`.

## Phase sequence

Phase 1 delivered onboarding, customer chat, and the business page; the
walkthrough phase (W-1 through W-9) is a second bug-fix pass on shipped
Phase 1 surfaces, not new product scope. B-2, D-1, and D-3 stay
`Deferred - Phase 2`. Payments, scheduling, invoicing, and leads stay out.
Full scope boundary is in [the PRD](../prd.md); current status is in
[progress.md](../progress.md).

## Maintenance

When every ticket in a phase is complete, move its file to
`docs/archive/phase1-complete/` with `git mv`, index it in that folder's
`README.md`, then update [progress.md](../progress.md).
