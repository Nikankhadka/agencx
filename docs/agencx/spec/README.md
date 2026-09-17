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
| [active/12-refinement.md](active/12-refinement.md) | R-3, R-4 remainder, R-5 remainder | `Active - todo` |
| [completed/15-ux-consistency.md](completed/15-ux-consistency.md) | U-1 through U-4 | `Active - awaiting review`, misfiled, moves to `active/` |
| [../HiveAgencyXRefinement.md](../HiveAgencyXRefinement.md) | RF proposal, moves to `active/18-refinement-proposal.md` | `Active - todo` |

M-7 storefront redesign ships on `feat/m7-storefront-redesign`; its ticket
file `active/17-storefront-redesign.md` lands with that branch.

## Completed work

| Location | Phase |
|---|---|
| [completed/01-foundation.md](completed/01-foundation.md) | Foundation, `Done - merged` |
| [completed/02-onboarding.md](completed/02-onboarding.md) | Onboarding, `Done - merged` |
| [completed/03-chat-spine.md](completed/03-chat-spine.md) | Chat spine, `Done - merged` |
| [completed/04-chat-grounding.md](completed/04-chat-grounding.md) | Chat grounding, `Done - merged` |
| [completed/05-business-page.md](completed/05-business-page.md) | Business page, `Done - merged` |
| [completed/06-polish.md](completed/06-polish.md) | Polish, `Done - merged` |
| [completed/07-hygiene.md](completed/07-hygiene.md) | Hygiene, `Done - merged` |
| [completed/09-devex.md](completed/09-devex.md) | Developer experience, `Done - merged` |
| [completed/10-deploy.md](completed/10-deploy.md) | Deployment, `Done - merged` |
| [completed/11-offerings-media.md](completed/11-offerings-media.md) | Offerings and media, `Done - merged` |
| [completed/13-walkthrough.md](completed/13-walkthrough.md) | Walkthrough fixes W-1 through W-9, `Done - merged` |
| [completed/14-schema-drop.md](completed/14-schema-drop.md) | Schema drop W-10, `Done - merged` |
| [completed/15-document-review.md](completed/15-document-review.md) | Document review W-11, `Done - merged` |
| [completed/16-auth-otp-reliability.md](completed/16-auth-otp-reliability.md) | Auth OTP W-12 and W-13, `Done - merged` |

Completed R-1 and R-2 records are preserved in
[the archived refinement record](../../archive/phase1-complete/12-refinement-r1-r2.md).

## Prototype currency

| Prototype | Status |
|---|---|
| [agencx-prototype-v6.html](../design/prototypes/agencx-prototype-v6.html) | Current app reference |
| `agencx-storefront-customer-v4.html` | Current storefront reference for M-7, lands with `feat/m7-storefront-redesign` |
| [archived v3 storefront](../../archive/prototypes/agencx-storefront-customer-v3.html) | Interaction vocabulary only |

Port structure, states, spacing, and interaction vocabulary. Use prototype
behaviour, never prototype copy or hex values. Visual values belong in
`frontend/src/styles/theme.css`.

## Phase sequence

Phase 1 delivered onboarding, customer chat, and the business page:

1. Foundation and onboarding
2. Chat spine and grounding
3. Business page and polish
4. Hygiene and containerized developer experience
5. Deployment
6. Offerings and media
7. Phase 1 refinement
8. Walkthrough fixes
9. Document review and privacy workflow
10. Authentication OTP reliability

The walkthrough phase (W-1 through W-9) is a second bug-fix pass on
shipped Phase 1 surfaces, not new product scope. B-2, D-1, and D-3 stay
`Deferred - Phase 2`. Payments, scheduling, invoicing, and leads stay out.

## Maintenance

When every ticket in a phase is complete, move its file from `active/` to
`completed/` with `git mv`, then update [progress.md](../progress.md).
