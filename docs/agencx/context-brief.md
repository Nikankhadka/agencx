# Agencx context brief

Paste this file into AI chat when planning Agencx work. Detail lives in
[progress.md](progress.md); product promises in [prd.md](prd.md);
technical ceiling in [architecture.md](architecture.md).

## What Agencx is

Agencx is a domain-agnostic, multi-tenant SaaS: any small business
self-onboards through a conversation and gets a private, branded
support-and-sales agent at `agencx.app/{slug}` that answers from the
business's own knowledge and escalates to a human when it should.

## Phase 1 scope

In: owner onboarding in chat, customer chat grounded in owner material,
Home, Chats, and Business surfaces, offerings and storefront, money
guardrail, escalation and handoff, deploy on one Vercel origin.

Out: quotes, payments, scheduling, invoicing, leads, custom domains,
per-tenant tool registry and toggle UI (B-2, D-1, D-3).

## What is done

Delivered tickets (A through W-13 and M-7: onboarding, chat spine and grounding,
console, finalized storefront, polish, deploy, walkthrough closeout) are
archived in `docs/archive/phase1-complete/README.md`. Detail in
[progress.md](progress.md).

## What is next

U-1 through U-4 shipped, walkthrough remains; R-3 backlog; R-4 remainder
(judge calibration, prod evidence); R-5 remainder (backups, error
tracking, E2E in CI, dep scan); RF-1 through RF-17 product refinement
(design intent); provider-backed eval needs paid tier or smaller slice
(free-tier quota 429). All tracked in
[`spec/active/12-refinement.md`](spec/active/12-refinement.md).

## Invariants

Deterministic pricing: no model ever produces a monetary amount; the
pricing engine computes totals in integer cents. Domain-agnostic: no code
branches on a business vertical; all vertical behavior lives in
`tenant_config` and uploaded knowledge.

Background on the pre-Agencx build: [history.md](history.md).
