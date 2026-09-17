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

| Area | Tickets |
|---|---|
| Onboarding and login | O-1, O-2, O-5 through O-12, `Done - merged` |
| Chat spine and grounding | P-1 through P-5, O-3, O-4, C-1 through C-6, `Done - merged` |
| Console, storefront, polish | E-1 through E-6, M-1 through M-6, B-1, B-3, D-2, `Done - merged` |
| Walkthrough and closeout | W-1 through W-13, `Done - merged` |

## What is next

M-7 storefront redesign (`Active - in progress`); U-1 through U-4 UX
consistency (`Active - awaiting review`); R-3 backlog; R-4 remainder
(judge calibration, prod evidence); R-5 remainder (backups, error
tracking, E2E in CI, dep scan); provider-backed eval needs paid tier or
smaller slice (free-tier quota 429).

## Invariants

Deterministic pricing: no model ever produces a monetary amount; the
pricing engine computes totals in integer cents. Domain-agnostic: no code
branches on a business vertical; all vertical behavior lives in
`tenant_config` and uploaded knowledge.

Background on the pre-Agencx build: [history.md](history.md).
