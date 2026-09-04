# Agencx specs and user stories

The spec set records the Agencx change build. Each ticket includes its intent,
acceptance criteria, implementation constraints, verification, and definition
of done. One ticket equals one commit, and commit messages start with the
ticket id when a ticket is implemented.

## How to read a ticket

| Section | Purpose |
|---|---|
| Summary | What the ticket delivers |
| Why | The product promise or measured problem |
| User stories | Persona-specific acceptance criteria |
| Design reference | The prototype screen for UI work |
| Technical spec | The intended implementation shape |
| Tests | The checks required for completion |
| Definition of done | The final completion checklist |

Tickets are written before implementation. Amendments are written after a
founder walkthrough exposes a change inside a closed phase. Amendments retain
their checked acceptance criteria and do not gain invented retrospective
technical sections. The amendments are O-6 through O-12 and E-6.

## Active and completed work

Active phase files contain unresolved tickets only:

| Location | Contents |
|---|---|
| [`active/08-deferred.md`](active/08-deferred.md) | B-2, D-1, D-3 |
| [`active/12-refinement.md`](active/12-refinement.md) | R-3, R-4, R-5 |

Completed phase files preserve the detailed records for shipped work:

| Location | Phase |
|---|---|
| [`completed/01-foundation.md`](completed/01-foundation.md) | Foundation |
| [`completed/02-onboarding.md`](completed/02-onboarding.md) | Onboarding |
| [`completed/03-chat-spine.md`](completed/03-chat-spine.md) | Chat spine |
| [`completed/04-chat-grounding.md`](completed/04-chat-grounding.md) | Chat grounding |
| [`completed/05-business-page.md`](completed/05-business-page.md) | Business page |
| [`completed/06-polish.md`](completed/06-polish.md) | Polish |
| [`completed/07-hygiene.md`](completed/07-hygiene.md) | Hygiene |
| [`completed/09-devex.md`](completed/09-devex.md) | Developer experience |
| [`completed/10-deploy.md`](completed/10-deploy.md) | Deployment |
| [`completed/11-offerings-media.md`](completed/11-offerings-media.md) | Offerings and media |

Completed R-1 and R-2 refinement records are preserved in
[`docs/archive/phase1-complete/12-refinement-r1-r2.md`](../../archive/phase1-complete/12-refinement-r1-r2.md).

When a phase's tickets are complete, move its file from `active/` to
`completed/` with `git mv`, then update [progress.md](../progress.md).

## Building UI

The current prototype is
[`agencx-prototype-v6.html`](../design/prototypes/agencx-prototype-v6.html).
Port its structure, states, spacing, and interaction vocabulary. Use prototype
behaviour, not prototype copy or hex values. Visual values belong in
`frontend/src/styles/theme.css`.

The former storefront prototype is preserved at
[`agencx-storefront-customer-v3.html`](../../archive/prototypes/agencx-storefront-customer-v3.html)
for interaction vocabulary only. It is not a current navigation reference.

## Phase sequence

Phase 1 delivered onboarding, customer chat, and the business page. The
supporting phases landed in this order:

1. Foundation and onboarding
2. Chat spine and grounding
3. Business page and polish
4. Hygiene and containerized developer experience
5. Deployment
6. Offerings and media
7. Phase 1 refinement

The active refinement phase is hardening, not new product scope. B-2, D-1, and
D-3 remain deferred to Phase 2. Payments, scheduling, invoicing, leads, and
other Stage 2 work remain outside this spec set.
