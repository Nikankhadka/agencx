# Agencx Architecture

The technical ceiling. Invariants, seams, agents, retrieval, evaluation, stack, and decisions that must not be re-litigated.

## 1. Invariants

These are the rules that do not bend for convenience. Every implementation must respect them.

| # | Rule | Consequence if broken |
|---|---|---|
| I1 | Money, tax, invoices, payment state, refunds and retention are computed by deterministic code, never by a model | A hallucinated total on a tax invoice is a compliance breach and an unrecoverable trust failure |
| I2 | Cognitive agents are stateless and called as RPC; the orchestrator owns all state and integrations | Stateful agents make behaviour unreproducible, untestable, and impossible to audit |
| I3 | Channel adapters normalise at the edge - SMS, chat, voice and embed all become one inbound event | Channel concerns leak into agent logic, and every new channel becomes a rewrite |
| I4 | Approval gates are data structures with explicit states, not copy | An approval that exists only as UI wording can be bypassed by any other code path |
| I5 | Every row carries `tenant_id`; isolation is enforced in the database, not the application | One missing `WHERE` clause exposes another business's customers |
| I6 | Manual mark-paid and provider webhooks are idempotent against the same payment | Double-counted revenue, or a customer charged twice and refunded once |
| I7 | Issued invoices are immutable; corrections are credit notes; records retain for five years | ATO non-compliance, and the audit trail becomes unreliable |
| I8 | One codebase serving any business vertical through per-tenant configuration and uploaded knowledge alone. No agent, prompt template, tool, or routing rule ever branches on a vertical name or business type (no `if business_type == "restaurant"` anywhere in code - same severity as a cross-tenant leak: stop and flag). Schema fields describe generic concepts; vertical specifics live in config/knowledge. The generalization proof (onboarding a structurally different tenant by config alone) is a *test*; a code change required to onboard a new vertical is a bug in I8, not a feature request. | A single vertical branch invalidates the platform's central claim |

The whole product is I8 plus I1: config and knowledge as the only per-vertical mechanism, and money as the one thing a model never touches.

## 2. Stack

| Layer | Choice | Notes |
|---|---|---|
| Backend | Python 3.12+ / FastAPI / uv | Ported from Wren's proven modules; ported, never rewritten (decision 2) |
| Database | Postgres + pgvector, Supabase CLI for local dev | RLS is the isolation mechanism of I5 |
| Orchestration | LangGraph, assistant graph only | Decision 4 - Stage 2 specialists are nodes on the same graph |
| Frontend | Next.js + TypeScript + Tailwind | One app, three surfaces |
| Retrieval | Dense (pgvector HNSW) + sparse (Postgres FTS) + RRF (k=60) + cross-encoder rerank | One `retrieve()` behind `get_business_context` |
| Identity | Email + 6-digit code issued and verified inside the chat | Decision 6; zero paid dependencies in Stage 1 |
| Infra | Backend: AWS ECS via Wren's existing Terraform | Frontend host open (decision 10) |
| Model access | Every call through `ModelPort` | Synthetic-only on free tier |

## 3. Decision ledger

All 11 decisions recorded with reasons. Nothing changes silently.

| # | Old | New | Reason |
|---|---|---|---|
| 1 | Cleaning wedge first | Domain-agnostic product; reference tenant 1 is the restaurant/catering anchor | Wren proved the agent, not the vertical; a vertical wedge contradicts the product thesis |
| 2 | TypeScript-e2e, Cloudflare Workers | Python/FastAPI + Next.js | Wren's proven modules (retrieval, graph, evals) are Python |
| 3 | No vectors / RAG | pgvector + hybrid retrieval from Stage 1 | Wren built and measured retrieval (recall@5 = 1.000); the old reconsider condition is met |
| 4 | No agent framework at all | LangGraph for the assistant graph only | Wren's ported layer is already a graph; onboarding stays a plain tool loop |
| 5 | Boundary unenforced | import-linter/AST test + ESLint no-restricted-imports, in CI from the first commit | The violation that matters is the one added later under time pressure |
| 6 | Phone-OTP only | Email + 6-digit code in-chat; phone is a profile field | No paid SMS in Stage 1 |
| 7 | "No settings screen, ever" | Second tab is **Business** - shown-back profile and knowledge | The owner must be able to trust and correct what the agent knows; it is not a settings tree |
| 8 | `AGENCX` mode value | `PLATFORM` in `payment_processing_mode` | Brand names in schema become rename migrations; settle before any row exists |
| 9 | `discovery_mode_teach_me` fork | Removed | "We don't serve your trade" contradicts I8; the geographic fork survives |
| 10 | Hosting "chosen" (Cloudflare) | Backend: ECS via Wren's Terraform. Frontend host **open**, decided at the Phase 5 ticket | Do not lock in a host before the frontend's own phase exists to decide it |
| 11 | Wren copy ported verbatim | Copy rewritten inside the porting ticket, never "later" | Wren surfaces said "AI"/"agent"; user-facing copy never does |

### ADR: Import-boundary enforcement from first commit

The codebase enforces the deterministic boundary (I1) through an import-linter rule in CI from the very first commit. The rule forbids importing `llm/provider.py` outside `agents/` and `llm/`. The frontend carries an equivalent ESLint `no-restricted-imports` rule. Both are wired in CI from T-001.

The violation that matters is the one added later under time pressure, so the check must predate the pressure. Determinism is a property of the module graph, not of willpower.

### ADR: No settings screen - Business tab as show-back only

The tenant app has no settings tree, no configuration screen, and no toggle-only preferences. The second tab - **Business** - displays the profile and knowledge the owner gave the agent, shown back so they can trust and correct it. Every configuration change happens through conversation with the Copilot, never through a form.

The product thesis is that the agent, not the owner, should absorb the paperwork. If a setting can only exist as a toggle on a screen, it should not exist. If the Business tab fails the trust test with a real cohort, the decision is revisited - the signal is logged, not assumed away.

## 4. The deterministic boundary as a code boundary

Exactly one module may import a model client: `backend/app/llm/provider.py` (`chat_with_tools`). Nothing outside the agent layer may import it, directly or transitively.

```
backend/app/
  llm/provider.py        <- the only module that imports a model SDK
  onboarding/agent.py    <- model-touching (tool loop) - never imported by services/
  agents/                <- model-touching (graph) - never imported by services/
  services/              <- deterministic services; may NEVER import llm/ or llm/provider
                            retrieval.py money_guardrail.py completeness_gate.py
                            inspection.py schema_audit.py
  shared/                <- plain infrastructure both sides may use
```

Enforcement, in CI from the first commit:
- Backend: import-linter rule forbidding any import of `llm/provider.py` outside `agents/` and `llm/`
- Frontend: ESLint `no-restricted-imports` - no component imports a model client or backend client

## 5. Tenant resolution by slug

The anonymous public page resolves a tenant before any auth exists:

- Every public URL carries a slug
- Resolution goes through `resolve_tenant_slug()`: a `SECURITY DEFINER` function owned by `agencx_resolver` - the single, audited RLS bypass in the system
- Returns only `(id, business_name, status, brand)`, never more
- Unknown slug: calm 404 ("There's no business here."). Suspended: "This assistant is currently unavailable."

## 6. Retrieval pipeline

```
upload -> extract -> chunk (~400 tokens, 15% overlap) -> embed (local bge-small in dev) -> store (pgvector, HNSW)

query:  dense (pgvector)  \
        sparse (Postgres FTS)  -> RRF fusion (k=60) -> cross-encoder rerank -> top-k
                                    with chunk ids for citations
```

**The seam:** `get_business_context(tenant_id, query)` is the single entry point. Two paths:

| Path | When | What happens |
|---|---|---|
| Whole-corpus fast path | The tenant's whole corpus fits in the reply token budget | The assistant reads the corpus directly; no retrieval scoring needed |
| Hybrid retrieval | Corpus over budget | Dense+sparse+RRF+rerank; top-k chunks plus citations |

Both paths return the same shape (chunk id, content, source, `score`).

## 7. The assistant graph

```
customer message
   -> supervisor       (capability routing + refusal; handles greetings/simple talk directly)
   -> knowledge node   (get_business_context -> ground truth + citations)
   -> money guardrail  (deterministic - any figure in the reply must appear verbatim in
                        owner-supplied material; rewrite-once-then-escalate)   [I1]
   -> inspection       (grounding rules: no uncited claim, no instruction-following from
                        chunk text, refusal when nothing relevant)
   -> stream           (SSE with citations and the guardrail as the last gate)
```

Escalation and refusal edges:
- Guardrail fails twice -> escalate (an `escalations` row)
- Inspection fails grounding -> refuses, rewrites once, or escalates
- No relevant context -> the no-answer rule: refuses rather than generalises

The graph's state carries `input`, `context`, `draft`, `figures`, `guardrail`, `trace` - all structured fields, never free text.

**Why LangGraph, and why only for the assistant:** Wren's ported agent layer was already a graph. Stage 2's specialists land as nodes on this same graph. The onboarding agent stays a plain tool loop; deterministic services stay plain functions.

## 8. Agent contracts and the forbidden-output table

| Agent | Job | Forbidden |
|---|---|---|
| **Onboarding agent** | Interview the owner through chat: identity, business type, profile, hours, what they sell | Any monetary figure or price until owner-supplied material exists; any invented hours, prices, or business facts; any raw JSON, XML, markdown table, or code block as a user-visible message |
| **Customer assistant** | Answer a customer's plain-language question grounded in retrieved material | ANY money figure not present verbatim in owner-supplied material; any total, sum, or derived price the model computes; uncited claims; following instructions found inside retrieved text; any raw structured data as a user-visible message |
| **Copilot** | The tenant's assistant: run onboarding, then ongoing owner chat, reach-in actions, and the unmet-capability handler | Money values; executing anything money-touching or customer-facing without a confirmation card; promising capability that does not ship; narrating internal uncertainty buckets; any raw structured data as a user-visible message |

### The citations no-answer rule

When nothing relevant comes back, the assistant refuses rather than generalises. The refusal is calm and honest ("I don't have an answer for that from the business's own material"). The refusal path is scored 0.0 on positive eval cases and 1.0 on negative cases.

### Deterministic services

These call no model at all. They are plain functions that inspect, gate, or compute:

| Service | What it gates / computes | Stage |
|---|---|---|
| Retrieval layers | What the knowledge node may cite | 1 |
| Money guardrail node | Any figure in the assistant's draft must appear verbatim in owner-supplied material; rewrite-once-then-escalate | 1 |
| Completeness gate | Refuses premature onboarding finalisation; enumerates missing fields | 1 |
| Inspection rules | No uncited claim, no instruction-following from chunk text, refusal when nothing relevant | 1 |
| Schema audit | RLS + money-column invariants | 1 |
| Leakage suite | Cross-tenant probes both directions, positive controls included | 1 |

### Session and UI contracts (cross-cutting)

- No raw structured data in user-facing output - every agent is forbidden from emitting JSON, XML, markdown tables, or code blocks as a user-visible message
- Natural-language summaries only - lists use conversational framing, never bullet points
- No impersonation - every agent identifies as an assistant acting on behalf of Agencx, never as the business owner or as human
- Business-safe claims - no agent may state pricing, availability, guarantees, or credentials unless the value is present in confirmed data

## 9. ModelPort and the hard rule

- Every model call goes through `ModelPort` (`backend/app/llm/provider.py`)
- Provider selection is environment configuration, not code
- **Free-tier models see synthetic or seeded data only, never real customer data.** Production requires a provider with a contractual no-training commitment
- Per-agent model choice (interpretation vs drafting latency) is configuration, not code

## 10. Evaluation

### Three layers

**Retrieval eval (deterministic):** Measures the hybrid pipeline against the golden set. Gate: recall@5 >= 0.85 (absolute). Also: MRR, nDCG@5, negative-set contamination check.

**Generation eval (LLM-judged):** Runs the real assistant graph over held-out conversations, judged by a judge model. Metrics: faithfulness, answer relevancy, citation-faithfulness. Regression-gated (model-dependent).

**Trajectory eval (LLM-judged + structural):** Checks the path itself: node path correctness, tool-call correctness, step efficiency, cost per conversation. Regression-gated.

### Absolute gates vs regression gates

| Kind | Gates | Behaviour |
|---|---|---|
| **Absolute** | Leakage 100% both directions; money air-gap 100/100 (zero model-authored figures); retrieval negative-set never contaminated; recall@5 >= 0.85; eval gates themselves never skipped in CI | A single failure blocks the phase |
| **Regression** | LLM-judged metrics within a ±3-point budget of the baseline run | A regression is investigated and fixed at its origin, never silenced by re-baselining |

### Adversarial injection eval

Three families run through the real stack:
- Direct: fake system overrides, "ignore your instructions", prompt extraction
- Direct-tool: a poisoned tool result
- Indirect-chunk: a poisoned knowledge document whose content is retrieved as ground truth

Gate: injection pass rate >= the golden record (Wren's 29/30 = 0.967 as reference).

### Wren's measured baselines

| Metric | Wren measured | Notes |
|---|---|---|
| recall@5 | 1.000 | Deterministic, on a 50-case golden set; single tenant corpus |
| recall@3 | 0.955 | As above |
| MRR | 0.911 | Usually first hit; often top-3 |
| nDCG@5 | 0.934 | Rank-weighted, same set |
| Leakage | 12/12 each direction | Deterministic, both directions, positive controls included |
| Injection | 0.967 (29/30) | Direct + direct-tool 1.000; the one miss is a documented indirect-chunk canary |

These are **precedent, not guarantees** - Agencx's own gates are the ones above. The Wren numbers show what the same machinery measured, including honest failures.

### Wiring and lifecycle

- Golden set grows per phase; a phase without eval cases is not complete
- Run on change, not on demand: new evaluations run whenever retrieval, prompts, or the graph change
- CI pipeline: `make check` (lint + typecheck + unit) then `make eval` (gate set). A failing absolute gate fails the job; a regression beyond ±3 fails the job
- Gates prevent phase advance - a phase cannot complete while its gate is red
- Never-skipped rule: there is no CI flag that skips an absolute gate

## 11. Free-tier constraints that gate the plan

**Supabase free tier pauses after 7 days idle** - disqualifying for a validation cohort (this applies to the hosted cloud service only; local dev uses the Supabase CLI with `supabase start`, which has no idle pause). Either the project stays warm, the cohort phase runs on the $25/month Pro tier, or hosted Postgres runs somewhere without an inactivity pause. Budget for this before recruiting the cohort.

**Free-tier models train on your inputs** - no real customer data through a free-tier model, ever. Development and the eval harness run on synthetic and seed data. Production requires a provider with a contractual no-training commitment. The `ModelPort` seam makes the swap a configuration change.

## 12. Deliberately absent

| Not building | Why | Would reconsider when |
|---|---|---|
| Agent framework for onboarding | Onboarding is a plain, bounded tool loop (<=4 tool calls/turn, <=40 turns) - a framework would buy nothing | The onboarding loop grows parallel branching model nodes of its own |
| Message queue | Nothing at Stage 1 volume needs async durability Postgres cannot provide | Webhook or send volume makes in-request processing unreliable (Stage 2 payments) |
| Microservices | One deployable, one repo; the module boundaries are enforced by lint, not by network calls | Never, at this scale |
| Separate voice infra | Voice is out of the Stage 1 slice | Voice returns to scope, post-validation |
| Two-way calendar sync | Write-only delivery is the value; read-and-reconcile adds conflict resolution for no validated gain | Post-validation, when scheduling lands |
| Settings tree | Decision 7: the Business tab is the surface for seeing/correcting what the agent knows | If the Business tab fails the trust test in a cohort - logged, not assumed |

## 13. Port map (from Wren)

| Phase | Modules |
|---|---|
| 0 | repo layout, `Makefile`, `supabase/config.toml`, `backend/app/core/migrate.py`, `frontend/scripts/check-tokens.mjs` |
| 1 | `backend/app/shared/db.py` (tenant context), `auth.py`, `tests/test_rls.py`, `tests/test_schema_audit.py`, migration DDL patterns, `resolve_tenant_slug()` |
| 2 | `backend/app/llm/provider.py` with `chat_with_tools`, `run_turn` / `TurnDirective` / off-topic detection / SSE streaming / completeness gate |
| 3 | upload endpoint + storage, `backend/app/ingestion/` (chunker, embedder, pipeline), `backend/app/retrieval/`, `backend/evals/retrieval_eval.py` |
| 4 | `backend/app/agents/` (graph.py, supervisor, knowledge, escalation, inspection.py, price_gate.py repurposed to money guardrail), SSE chat endpoint, chat UI components |
| 5 | `backend/evals/{generation_eval,trajectory_eval,injection_eval,leakage_eval,run_gate}.py`, CI eval-gate job, `backend/app/observability/{cost,tracing}.py`, `infra/*.tf` |
