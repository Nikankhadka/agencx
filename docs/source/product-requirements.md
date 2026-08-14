> **NAVIGATION:** Frozen source document (v2.0). This file wins on scope questions only. For implementation detail see `docs/design/`, for progress see `docs/PROGRESS.md`. `docs/conventions.md` governs how work gets done.

# WREN - Charter & Product Requirements Document
> **Version:** 2.0 (domain-agnostic multi-tenant SaaS pivot) | **Type:** Solo portfolio venture - personal learning + capstone-grade artifact
> **Author:** Ronin Khadka | **Build clock:** 30-day polished core, with an explicit phase 2 for the rest of the vision

## 1. Charter

```
IDEA (one sentence)
  A domain-agnostic, multi-tenant SaaS where any business - dentist, deli, butcher,
  phone repair shop, online store - signs up, describes itself in a conversation,
  and gets its own private, branded AI support-and-sales agent that recommends,
  quotes, answers, and escalates to a human when it should.

WHY DOMAIN-AGNOSTIC (the load-bearing decision)
  The code knows nothing about any vertical. Everything domain-specific lives in
  per-tenant config and uploaded knowledge. "Works for any business" is not a
  feature we build - it is what we get by refusing to hardcode any vertical
  anywhere in agent logic. The discipline IS the product.

WHY THIS SHAPE (portfolio-first framing)
  The primary buyer is a hiring panel for a mid-level Full Stack / GenAI Engineer
  role. Every scope call is filtered through "does this prove AI-engineering depth
  and production judgment?" - RAG, agent orchestration, evaluation, observability,
  security, multi-tenancy.

CONSTRAINTS
  Timeline: 30 days for a polished end-to-end core; the rest is documented phase 2.
  Budget:   Bootstrapped. Free/low-cost tiers. AWS backend is the one paid exception.
  Team:     Solo (Ronin) + AI pair-programmer.

DEFINITION OF A WIN
  A working, deployed, demoable multi-tenant SaaS where:
    - a new business self-onboards via a conversation and gets a private agent at its
      own subdomain, with zero code written for that business;
    - the agent recommends, answers from the business's own knowledge, and produces
      deterministic quotes (model selects inputs, code computes the price);
    - a second business in a completely different vertical is onboarded by config
      alone, proving domain-agnosticism;
    - there is a numbers-backed evaluation report and a proven cross-tenant
      isolation guarantee;
    - every deferred item is written up as "considered, out of scope, and why."
```

## 2. The three-surface SaaS model

One application, deployed once, serving three surfaces. NEVER a separate deployment per business - one codebase, one deployment, tenant isolation by data.

### Surface 1 - Platform Owner (you)
A super-admin surface only the platform operator sees: lists every tenant, provisions/suspends them, and (phase 2) handles billing. At core scope it is intentionally minimal - not a billing product.

### Surface 2 - Tenant Admin (each business)
When a business signs up it lands in its own console, scoped to its `tenant_id`: onboard conversationally, upload knowledge, watch conversations, handle escalations, set quoting rules, see costs. A dentist and a butcher get the identical console populated with entirely different data.

### Surface 3 - Customer (each business's customers)
Each tenant gets a private customer chat at `{tenant-slug}.wren.app`. To the customer it looks like that business's own support. It is scoped to exactly one tenant.

> "Private website" does NOT mean a separate deployment. It means one app resolving which tenant a visitor belongs to (by subdomain) and showing only that tenant's world.

## 3. Tenancy & the domain-agnostic principle

- A tenant is a row keyed by `tenant_id`. All tenant data carries it. Postgres Row-Level Security enforces isolation at the database layer.
- A dentist and a butcher run identical code; they differ only in (a) uploaded knowledge and (b) `tenant_config`.
- **Hard rule:** no `if vertical == "dentist"` anywhere in agent, retrieval, pricing, or tool logic. Vertical behavior is data, never code. A single such branch breaks the domain-agnostic claim and is treated as a bug.

## 4. Personas

- **Priya - Tenant Admin (primary buyer).** Runs a small business, not technical. Wants to describe her business in a chat and get a working agent. Success: self-serves setup with zero developer help.
- **Alex - End Customer.** Wants a fast, correct answer or quote, and a real human when needed. Success: answered, quoted, or escalated in one exchange.
- **You - Platform Owner.** See all tenants, provision them, keep the platform healthy. Success: a new tenant goes live without touching code.
- **(Portfolio-only) The Hiring Panel.** In under 10 minutes, evidence of multi-agent orchestration, real tool use and quoting, evaluation, security, and multi-tenant design.

## 5. Reference tenants

| | Anchor: Phone shop & repair (Tenant 1) | Generalization proof: Dental clinic (Tenant 2) | Stretch: Online store (Tenant 3) |
|---|---|---|---|
| Why | Exercises every capability: recommend, quote, status, FAQ/policy, escalation | Maximally different: a health service, no products, no repairs | Classic orders/returns/WISMO |
| Depth | Full build + full eval | Config-only onboarding (the proof) | Only if clock allows |

## 6. MVP scope - MoSCoW

### MUST (the 30-day polished core)
- **M1.** Multi-tenant auth + RLS-enforced isolation on every tenant-scoped table.
- **M2.** Tenant resolution by subdomain.
- **M3.** Conversational onboarding (guided, not an open-ended magic interviewer).
- **M4.** Knowledge ingestion: upload, chunk, embed, store in pgvector.
- **M5.** Hybrid retrieval: dense + sparse + RRF + cross-encoder rerank.
- **M6.** Multi-agent orchestration (LangGraph supervisor + specialists).
- **M7.** Tool calling: `search_knowledge`, `recommend_items`, `lookup_order_or_ticket`, `get_quote_inputs`, `create_escalation`.
- **M8.** Deterministic pricing engine: agents select inputs; a non-LLM engine computes totals in integer cents.
- **M9.** Reasoning-inspection layer over the agent's output before anything reaches the customer.
- **M10.** Human-in-the-loop escalation as a first-class state.
- **M11.** Evaluation harness: retrieval, generation, trajectory, judge calibration.
- **M12.** CI regression gate (GitHub Actions).
- **M13.** Prompt-injection defense with a scored adversarial set.
- **M14.** Cross-tenant isolation proven by an automated leakage test (100%).
- **M15.** Observability: OTel tracing + per-tenant token/cost accounting.
- **M16.** Tenant admin console (Surface 2).
- **M17.** Customer chat surface (Surface 3), streaming.
- **M18.** Platform-owner surface (Surface 1), minimal.
- **M19.** Deployment: AWS ECS Fargate via Terraform; Vercel frontend; GitHub Actions CI/CD.
- **M20.** Generalization proof: onboard Tenant 2 by config + knowledge only.

### SHOULD
- **S1.** Recommendation quality tuning. **S2.** Query rewriting for multi-turn. **S3.** Conversation-simulation eval.

### COULD
- **C1.** Tenant 3 (online store). **C2.** Semantic chunking with before/after numbers. **C3.** Semantic caching. **C4.** Load testing.

### WON'T (30-day core) - with reasoning
| Deferred | Why |
|---|---|
| Subscriptions/billing automation | Phase 2. The platform surface proves the SaaS shape without a billing product eating the clock. |
| SMS/voice/email channels | Phase 2. Extra channels are integration volume, low incremental AI signal. |
| Custom domains (vs subdomains) | Phase 2. Subdomains prove private access; custom domains are DNS/cert plumbing. |
| Open-ended "magic" onboarding interviewer | Guided onboarding proves the concept; a fully open interviewer is itself a hard agent-research problem. |
| Fine-tuning, SSO/SOC2 certs, multi-language | Poor time-to-signal for a solo 30-day core. |

## 7. Timeline reality

The 30 days deliver ONE polished end-to-end path - Tenant 1 fully built across all three surfaces with quoting, eval, and security, plus the Tenant 2 config-only proof. Anything else is phase 2, documented, not half-built. Scope boundaries are fixed; quality within them is not. If a core ticket threatens the clock, flag it rather than silently cutting quality or blowing the date.

## 8. Success metrics

- Retrieval recall@5 >= 0.85 (report actual).
- Generation faithfulness >= 0.85, relevancy >= 0.85.
- Trajectory tool-call correctness >= 90%.
- Quote correctness: 100% of quotes derive every figure from the pricing engine (non-negotiable).
- Cross-tenant leakage test: 100% pass (non-negotiable).
- Prompt-injection set: >= 80% pass, documented honestly.
- Judge calibration: >= 80% agreement with human labels.
- Generalization: Tenant 2 onboarded with zero code changes.

## 9. Release criteria

- All MUST items (M1-M20) pass acceptance.
- Numbers-backed eval report against the golden datasets.
- Cross-tenant leakage test passing in CI.
- Zero model-authored prices (provenance test passing).
- No known lint errors, no failing/flaky tests in CI.
- Live deployment: at least two tenants reachable at their own subdomains.
- README with architecture diagram, setup, and deferral rationale.
- LEARNINGS.md populated per subsystem.
- A recorded 5-10 minute walkthrough.
