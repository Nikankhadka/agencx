# Merge AgenCX into Wren - the "Agencx" re-scoped initial phase

Turn the shipped Wren build into the **Agencx** product: AgenCX's PRD/design,
Wren's Supabase auth + crimson primary, advanced Wren features made optional
per-tenant. Not a rebuild - every ticket maps to the existing system.

## Locked decisions

- Name = **Agencx** (surface only); repo/roles/env stay `wren`.
- Auth = Supabase, unchanged. Design = AgenCX, red primary.
- 3 screens: Chat + Business + Public. Advanced screens hidden, not deleted.
- Advanced tools (quote/recommend/order-status/engine) = per-tenant toggle, default lean.
- Money = guardrail default (verbatim in owner material or engine output); engine runs only when the quote tool is enabled.
- Deliverable = docs (PRD + architecture + phases + tickets) + code.

## Flow design (under discussion - finalize next session)

Phase 1 (small business, e.g. Sababa, <7k total context) - lean flow:

- Onboarding: one tool to save profile fields + an LLM turn loop (extract -> save -> ask missing -> deflect otherwise). No graph.
- Knowledge: two ingest paths (URL scrape of website/ubereats; document upload) -> chunk + store. Corpus <7k -> no retrieval scoring; whole corpus concatenated into the prompt.
- Customer agent: single call, no tool loop. System prompt = business profile + full knowledge + rules (answer only from provided info, refuse if absent, never invent facts/figures, restate prices/allergens verbatim). Only tool = escalate to human.
- Money: deterministic guardrail + grounding inspection still run, catching fabricated figures / uncited claims.

Size separation: data-driven corpus-size threshold, not a hardcoded business-size branch. Small corpus -> whole corpus in prompt; large corpus (> ~50k) -> hybrid RAG. Consistent with the domain-agnostic invariant.

Phase 2 (mid-large business, >50k context + structured commerce): hybrid RAG + the full tool loop (search, recommend, quote, order-status, escalate) + per-tenant tool gating.

Open questions to resolve before finalizing:
- Exact onboarding field set + system prompt.
- Corpus-size threshold value.
- Whether Phase 1 customer agent needs any tool beyond escalate.
- Whether per-tenant tool gating lands in Phase 1 or Phase 2.

This re-scopes the money-guardrail and tool-gating work: Phase 1 = money guardrail + whole-corpus prompt; tool gating + tool loop + hybrid RAG defer to Phase 2.

## Phases and tickets

### Phase A - Docs
- **A-1** Write merged PRD: Agencx = Stage 1 spine (onboard -> knowledge -> grounded assistant) on Supabase + crimson; quoting/recommendation/order-status/pricing deferred-and-optional.
- **A-2** Write merged architecture: runtime flow, invariants mapped to the existing build, tool-gating mechanism, money-guardrail contract.
- **A-3** Re-cut phases + tickets + user stories.
- **A-4** Retire the frozen planning docs; make the Agencx set canonical; update docs pointers.

### Phase B - Rebrand
- **B-1** Rename user-facing copy to Agencx (brand mark, titles, login, greeting).
- **B-2** Point the public domain to agencx.app (CORS + slug resolution).

### Phase C - Money guardrail
Core rewrite: today only the recommendation/quoting routes are figure-checked, and only against engine + catalog figures. Loosen it to also allow figures stated verbatim in the business's own material; engine output becomes one of three allowed sources.

- **C-1** Allow figures verbatim from the business's uploaded material in the allowed set.
- **C-2** Route the knowledge answers through the same figure check.
- **C-3** Let the assistant state figures, but only exactly as listed - never compute.
- **C-4** Tests: verbatim figure passes; invented/computed/off-by-one fails; invented price escalates.

### Phase D - Per-tenant tool gating (may move to Phase 2 per flow discussion)
- **D-1** Build the assistant's available tools from the tenant's enabled set, not a fixed list. Lean default: knowledge + escalate.
- **D-2** New-tenant default = lean; legacy rows get the lean default.
- **D-3** Business-tab toggle UI for enabled tools.
- **D-4** Tests: gated tenant cannot quote; enabled tenant can.

### Phase E - 3 screens
- **E-1** Tenant console -> Chat (onboarding) + Business (profile + knowledge + pricing toggle).
- **E-2** Hide advanced screens (conversations/dashboards/escalations) from nav; keep code.
- **E-3** Platform admin stays minimal.

### Phase F - Hygiene
- **F-1** Delete dead agent code left over from the old multi-specialist topology.
- **F-2** (Optional) import-boundary enforcement in CI.

### Phase G - Eval
- **G-1** Update eval cases for the lean toolset + money-guardrail defaults; keep the recall, leakage, and injection gates.

## Verification

1. Full local CI (lint + typecheck + test + build).
2. Seed + demo: grounded conversation; a restated owner price passes; "invent a price" escalates.
3. Lean tenant refuses a quote; enabling the quote tool re-enables it.
4. Eval gate green: money air-gap + recall.
5. E2E: 3-screen nav, Agencx brand, crimson primary.
