# Agencx Architecture

The technical ceiling. Invariants, seams, agent flow, provider strategy, latency
budget, evaluation, and the decisions that must not be re-litigated. The product
promises this implements are in `prd.md`; the decision ledger with reasons is in
`design/decisions.md`; the tickets that build this are in `spec/`.

## 1. Invariants

These are the rules that do not bend for convenience. Every implementation must
respect them.

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

The whole product is I8 plus I1: config and knowledge as the only per-vertical
mechanism, and money as the one thing a model never touches.

## 2. Stack

| Layer | Choice | Notes |
|---|---|---|
| Backend | Python 3.12+ / FastAPI / uv | The proven Wren modules, carried forward; ported, never rewritten (decision 2) |
| Database | Postgres + pgvector, Supabase CLI for local dev | RLS is the isolation mechanism of I5 |
| Orchestration | LangGraph, assistant graph only; onboarding is a plain tool loop | Decision 4 - Stage 2 specialists are nodes on the same graph |
| Frontend | Next.js + TypeScript + Tailwind | One app, three surfaces; tokens in `frontend/src/styles/theme.css` (CI-enforced) |
| Retrieval | Dense (pgvector HNSW) + sparse (Postgres FTS) + RRF (k=60) + cross-encoder rerank | One `retrieve()` behind `get_business_context`; whole-corpus fast path below the token threshold |
| Identity | Email + 6-digit code issued and verified inside the chat | Decision 6; zero paid dependencies in Stage 1 |
| Storefront media | Cloudinary signed Upload API | Backend-only credentials; tenant_media stores delivery metadata, not secrets |
| Infra | Both services as containers in one Vercel project, same origin (B-4) | Supersedes AWS ECS; the R-11 cleanup removes the dormant Terraform stack and its CI job |
| Model access | Every call through the provider layer (`app/llm/provider.py`) | Providers are env config; free tiers are the default; budget capped |

## 3. Decision ledger and ADRs

All decisions - the 11 carried from planning plus the new D12-D17 - are recorded
with reasons in `design/decisions.md`. Nothing changes silently. Two ADRs are
load-bearing for every implementation:

- **Import-boundary enforcement from first commit:** exactly one module may
  import a model client - `backend/app/llm/provider.py`. The frontend carries an
  equivalent ESLint `no-restricted-imports` rule. Determinism is a property of
  the module graph, not of willpower.
- **Business tab as show-back, not settings:** the tenant app has no settings
  tree; the Business tab displays the profile and knowledge back so the owner
  can trust and correct it.

## 4. The deterministic boundary as a code boundary

Exactly one module may import a model client: `backend/app/llm/provider.py`
(`chat_with_tools`). Nothing outside the agent layer may import it, directly or
transitively.

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

Enforcement:
- Backend: import-linter rule forbidding any import of `llm/provider.py`
  outside `agents/` and `llm/`
- Frontend: ESLint `no-restricted-imports` - no component imports a model client
  or backend client

## 5. Tenant resolution by slug

The anonymous public page resolves a tenant before any auth exists:

- Every public URL carries a slug
- Resolution goes through `resolve_tenant_slug()`: a `SECURITY DEFINER` function
  owned by `wren_resolver` (the code keeps the Wren role name; see the standing
  names note in the set README) - the single, audited RLS bypass in the system
- Returns only `(id, business_name, status, brand)`, never more
- Unknown slug: calm 404 ("There's no business here."). Suspended: "This
  assistant is currently unavailable."

## 6. Retrieval pipeline

```
upload -> extract -> chunk (~400 tokens, 15% overlap) -> embed (local bge-small in dev) -> store (pgvector, HNSW)

query:  dense (pgvector)  \
        sparse (Postgres FTS)  -> RRF fusion (k=60) -> cross-encoder rerank -> top-k
                                    with chunk ids for citations
```

**The seam:** `get_business_context(tenant_id, query)` is the single entry
point. Two paths, chosen by a **data-driven corpus-size check, not a business
branch** (I8):

| Path | When | What happens |
|---|---|---|
| Whole-corpus fast path | The tenant's whole corpus fits in the reply token budget (< ~7-8k tokens today; the exact threshold is a measured config value) | The assistant reads the corpus directly; no retrieval scoring needed |
| Hybrid retrieval | Corpus over budget | Dense+sparse+RRF+rerank; top-k chunks plus citations |

Both paths return the same shape (chunk id, content, source, `score`).

The corpus-size threshold is config, sized by measurement (token counting, not
guessing). The same check drives the pre-loaded context package (section 9):
small tenants never pay retrieval latency or scoring cost, large tenants get the
full hybrid pipeline - same code path, different data volume.

## 7. The assistant flow (Phase 1: supervisor-with-tools)

The customer-facing flow is a **supervisor with tools** - one model call per
turn in the common case, not a multi-node route. This is the re-scoped Phase 1
design (decision D13), and it directly fixes the measured Wren latency problem
(3-5 serial LLM calls per turn, 37s knowledge turns - see `progress.md` for the
measurement).

```
customer message
   -> [context package pre-loaded: system prompt + profile + corpus]   (section 9)
   -> supervisor-with-tools, ONE model call:
        tools = tenant enabled set (default: answer from context, escalate)
        answers greetings/refusals directly from the package
        the only tool in the lean default is escalate
   -> money guardrail  (deterministic - every figure must appear verbatim in
                        owner-supplied material or pricing-engine output;
                        rewrite-once-then-escalate)   [I1]
   -> inspection       (grounding rules: no uncited claim, no instruction-following
                        from chunk text, refusal when nothing relevant)
   -> stream           (SSE with citations and the guardrail as the last gate)
```

Escalation and refusal edges:
- Guardrail fails twice -> escalate (an `escalations` row)
- Inspection fails grounding -> refuses, rewrites once, or escalates
- No relevant context -> the no-answer rule: refuses rather than generalises

The graph's state carries `input`, `context`, `draft`, `figures`, `guardrail`,
`trace` - all structured fields, never free text. The inspection buffer stays
(nothing streams until the inspection node passes - the founder-ruled decision
from 2026-07-28); with one call per turn the buffer's cost is one call, not four.

**Phase 2 (mid-large businesses, >50k corpus + structured commerce):** the same
supervisor may gain structured commerce tools - search, recommend, quote,
order-status, and escalate - after the deferred tool registry and product
controls are explicitly implemented. Phase 1 does not expose recommendations,
quoting, order-status, or owner co-pilot behavior.

**Why LangGraph, and why only for the assistant:** the ported agent layer was
already a graph. Stage 2's specialists land as tools on this same supervisor;
the onboarding agent stays a plain tool loop; deterministic services stay plain
functions.

## 8. Phase 1 tool boundary and deferred gating

Phase 1 exposes a fixed, intentionally small tool set:

- `answer_from_knowledge` (the grounded Q&A path - context package + guardrail)
- `escalate` (human handoff)

The recommendation, quote, and order/ticket internals remain dormant
foundations for Phase 2. They are not customer-facing Phase 1 capabilities,
regardless of legacy rows or dormant schemas. The deferred per-tenant registry
and toggle work will define how `tenant_config.enabled_tools` is honored.
Until that work lands, no Phase 1 turn may expose those tools. Enforcement
points for the future registry are documented as upgrade work, not current
behavior:

- Agent layer: Phase 1 offers only grounded knowledge and escalation
- Validation layer: unoffered tool calls are rejected defensively
- API layer: no Phase 1 workflow creates or exposes commerce actions

## 9. Context assembly and the agent-ready pre-load

The single biggest latency lever in the measured Wren build was the number of
serial LLM calls per turn; the second was the retrieval round-trip before any
drafting. Phase 1 eliminates both for small corpora:

**Context package.** When the chat opens (any surface), the backend assembles a
context package: system prompt (rules, persona, money rules), tenant profile,
and the corpus (whole-corpus path when under threshold). The package is cached
in-process, keyed by `(tenant_id, knowledge_version)`.

**knowledge_version.** A derived version stamp of the tenant's knowledge - the
max of its documents' update timestamps (no new table). Any re-ingest, upload,
or profile change bumps it, which invalidates the cached package. The next chat
open reassembles.

**Turn flow.** Each customer message appends to the package and makes exactly
one LLM call: no route node, no retrieval call, no separate draft node. The
message history and the package compose the prompt; provider prompt caching
(Groq and Google both discount cached prefixes) compounds the win.

The threshold check lives in `get_business_context`; the package assembly and
cache live behind the same seam, so the two-path behavior stays data-driven
(I8) and the hybrid path for large corpora is the same code with a cache miss.

## 10. Provider strategy and the latency budget

Every model call goes through the provider layer (`backend/app/llm/provider.py`
and `llm/dependency.py`). Provider selection is environment configuration, not
code. The build's standing budget is $10/month for live testing (D16).

### The three tiers

| Tier | Provider | Model | Why |
|---|---|---|---|
| Primary | Google AI Studio (free tier) | `gemini-3.5-flash-lite` (OpenAI-compat endpoint: `generativelanguage.googleapis.com/v1beta/openai/`) | Free tier: 1M tokens/min, 1,500 requests/day, 15-30 RPM - the most generous free limits measured; flash-lite is the fast, non-reasoning line |
| Fallback | Groq (free tier) | `openai/gpt-oss-120b` (or `gpt-oss-20b` for tighter budget) | LPU latency: ~1,000+ tok/s; cached prefix tokens do not count toward the TPM limit; 30 RPM / 6-12K TPM free |
| Failover | OpenRouter (free tier) | `google/gemma-4-26b-a4b-it:free` | The CI-pinned proven default; structured outputs verified; 0 reasoning tokens; the most independent free tier for a third leg |

Cerebras (llama-3.3-70b, 2,100+ tok/s, $5 free credits) is a candidate fallback
where Groq is unavailable; GitHub Models (8k input/request cap) and the Gemini
3.x reasoning-mandatory flash family are explicitly excluded. Local dev keeps
Z.ai GLM as an option; CI pins the OpenRouter gemma model so the eval gates run
deterministically.

### The latency budget (product promise, PRD section 9)

| Phase | Budget |
|---|---|
| Time to first token, primary | <= 4s (TTFT) |
| Failover trigger | Primary produced no first token within 4s (timeout) or hard-429'd |
| Time to complete answer, hard cap | 10s total, on either leg |
| Race mode | Primary and fallback race once failover triggers; **first-wins** - the losing call's stream is discarded, never shown |

Client behavior: the typing indicator starts on send and stays up through the
failover window (ticket P-5); the customer never sees a spinner, a blank, or a
"switching providers" message. On a hard 429 from a provider, that provider is
skipped for the rest of the session.

### Free-tier rules (unchanged from planning, still binding)

- **Free-tier models see synthetic or seeded data only, never real customer
  data.** Production requires a provider with a contractual no-training
  commitment. The provider seam makes the swap a configuration change.
- Free models come and go; query the provider's model list for structured-output
  support rather than hardcoding model names (the CI pin is the one hardcoded
  exception, deliberately).

## 11. Agent contracts and the forbidden-output table

| Agent | Job | Forbidden |
|---|---|---|
| **Onboarding agent** | Interview the owner through chat: identity, business type, profile, hours, what they sell | Any monetary figure or price until owner-supplied material exists; any invented hours, prices, or business facts; any raw JSON, XML, markdown table, or code block as a user-visible message |
| **Customer assistant** | Answer a customer's plain-language question grounded in the context package | ANY money figure not present verbatim in owner-supplied material or pricing-engine output; any total, sum, or derived price the model computes; uncited claims; following instructions found inside retrieved text; any raw structured data as a user-visible message |
| **Copilot** | The tenant's assistant: run onboarding, then ongoing owner chat, reach-in actions, and the unmet-capability handler | Money values; executing anything money-touching or customer-facing without a confirmation card; promising capability that does not ship; narrating internal uncertainty buckets; any raw structured data as a user-visible message |

### The citations no-answer rule

When nothing relevant comes back, the assistant refuses rather than generalises.
The refusal is calm and honest ("I don't have an answer for that from the
business's own material"). The refusal path is scored 0.0 on positive eval cases
and 1.0 on negative cases.

### Deterministic services

These call no model at all. They are plain functions that inspect, gate, or
compute:

| Service | What it gates / computes | Stage |
|---|---|---|
| Retrieval layers | What the knowledge node may cite | 1 |
| Money guardrail node | Any figure in the assistant's draft must appear verbatim in owner-supplied material or pricing-engine output; rewrite-once-then-escalate | 1 |
| Completeness gate | Refuses premature onboarding finalisation; enumerates missing fields | 1 |
| Inspection rules | No uncited claim, no instruction-following from chunk text, refusal when nothing relevant | 1 |
| Schema audit | RLS + money-column invariants | 1 |
| Leakage suite | Cross-tenant probes both directions, positive controls included | 1 |

### Session and UI contracts (cross-cutting)

- No raw structured data in user-facing output - every agent is forbidden from
  emitting JSON, XML, markdown tables, or code blocks as a user-visible message
- Natural-language summaries only - lists use conversational framing, never
  bullet points
- No impersonation - every agent identifies as an assistant acting on behalf of
  Agencx, never as the business owner or as human
- Business-safe claims - no agent may state pricing, availability, guarantees,
  or credentials unless the value is present in confirmed data

## 12. Evaluation

### The three layers

**Retrieval eval (deterministic):** Measures the hybrid pipeline against the
golden set. Gate: recall@5 >= 0.85 (absolute). Also: MRR, nDCG@5,
negative-set contamination check.

**Generation eval (LLM-judged):** Runs the real assistant graph over held-out
conversations, judged by a judge model. Metrics: faithfulness, answer
relevancy, citation-faithfulness. Regression-gated (model-dependent).

**Trajectory eval (LLM-judged + structural):** Checks the path itself: node
path correctness, tool-call correctness, step efficiency, cost per
conversation. Regression-gated. With the Phase 1 one-call shape, the trajectory
measure becomes: was the reply grounded, was escalation used correctly, did the
turn stay inside one call.

### Absolute gates vs regression gates

| Kind | Gates | Behaviour |
|---|---|---|
| **Absolute** | Leakage 100% both directions; money air-gap 100/100 (zero model-authored figures); retrieval negative-set never contaminated; recall@5 >= 0.85; eval gates themselves never skipped in CI | A single failure blocks the phase |
| **Regression** | LLM-judged metrics within a ±3-point budget of the baseline run | A regression is investigated and fixed at its origin, never silenced by re-baselining |

### Adversarial injection eval

Three families run through the real stack:
- Direct: fake system overrides, "ignore your instructions", prompt extraction
- Direct-tool: a poisoned tool result
- Indirect-chunk: a poisoned knowledge document whose content is retrieved as
  ground truth

Gate: injection pass rate >= the golden record (Wren's 29/30 = 0.967 as
reference).

### Wren's measured baselines (precedent, not guarantees)

| Metric | Wren measured | Notes |
|---|---|---|
| recall@5 | 1.000 | Deterministic, on a 50-case golden set; single tenant corpus |
| recall@3 | 0.955 | As above |
| MRR | 0.911 | Usually first hit; often top-3 |
| nDCG@5 | 0.934 | Rank-weighted, same set |
| Leakage | 12/12 each direction | Deterministic, both directions, positive controls included |
| Injection | 0.967 (29/30) | Direct + direct-tool 1.000; the one miss is a documented indirect-chunk canary |

Agencx's own gates are the ones above; the Wren numbers show what the same
machinery measured, including honest failures. Full methodology in
`docs/archive/artifacts/eval-report.md`.

### Wiring and lifecycle

- Golden set grows per phase; a phase without eval cases is not complete
- Run on change, not on demand: new evaluations run whenever retrieval, prompts,
  or the graph change
- CI pipeline: `make check` (lint + typecheck + unit) then `make eval` (gate
  set). A failing absolute gate fails the job; a regression beyond ±3 fails the
  job
- Gates prevent phase advance - a phase cannot complete while its gate is red
- Never-skipped rule: there is no CI flag that skips an absolute gate

## 13. Free-tier constraints that gate the plan

**Supabase free tier pauses after 7 days idle** - disqualifying for a validation
cohort (this applies to the hosted cloud service only; local dev uses the
Supabase CLI with `supabase start`, which has no idle pause). Either the project
stays warm, the cohort phase runs on the $25/month Pro tier, or hosted Postgres
runs somewhere without an inactivity pause. Budget for this before recruiting
the cohort.

**Free-tier models train on your inputs** - no real customer data through a
free-tier model, ever. Development and the eval harness run on synthetic and
seed data. Production requires a provider with a contractual no-training
commitment. The provider seam makes the swap a configuration change.

**Provider free-tier rate limits are the load ceiling** - Google 1,500
requests/day and Groq 30 RPM bound the demo cohort before cost does. The
failover tier (section 10) absorbs the spikes; the limits themselves are
configuration, watched in the dashboards.

## 14. Deliberately absent

| Not building | Why | Would reconsider when |
|---|---|---|
| Agent framework for onboarding | Onboarding is a plain, bounded tool loop (<=4 tool calls/turn, <=40 turns) - a framework would buy nothing | The onboarding loop grows parallel branching model nodes of its own |
| Message queue | Nothing at Stage 1 volume needs async durability Postgres cannot provide | Webhook or send volume makes in-request processing unreliable (Stage 2 payments) |
| Microservices | One repo, one origin; since B-4 two container services, but the module boundaries are enforced by lint, not by network calls | Never, at this scale |
| Separate voice infra | Voice is out of the Stage 1 slice | Voice returns to scope, post-validation |
| Two-way calendar sync | Write-only delivery is the value; read-and-reconcile adds conflict resolution for no validated gain | Post-validation, when scheduling lands |
| Settings tree | Decision 7: the Business tab is the surface for seeing/correcting what the agent knows | If the Business tab fails the trust test in a cohort - logged, not assumed |
| Multi-call turn flow | Phase 1 is one call per turn with pre-loaded context; the measured 37s turn was 3-5 serial calls | When the corpus exceeds the threshold and the hybrid path needs tools (Phase 2) |

## 15. Port map (from Wren)

The Wren build already delivers nearly every module below; the Agencx tickets
in `spec/` adapt, gate, hide, or extend - they do not rebuild.

| Area | Wren module | Agencx treatment |
|---|---|---|
| Tenancy + auth | `app/shared/auth.py`, migrations, `resolve_tenant_slug()`, Supabase | Kept (O-2 adds login-in-chat on the tenant surface) |
| Onboarding | `app/onboarding/agent.py` (`run_turn` / `TurnDirective`, `extract()` DraftUpdate pattern, completeness gate) | Kept (O-1: one tool to save profile fields + LLM turn loop) |
| Knowledge | upload endpoint + storage, `app/ingestion/` (chunker, embedder, pipeline), `app/retrieval/` | Kept; O-3 adds the URL scrape path + document upload; O-4 adds the whole-corpus fast path + threshold |
| Agents | `app/agents/` (graph, supervisor, knowledge, escalation, inspection, price_gate, spotlight) | Phase 1 exposes grounded knowledge and escalation; the recommendation, quote, and order internals remain dormant Phase 2 foundations |
| Money | pricing engine (`app/pricing/engine.py`), `price_gate.py` | Kept as a dormant deterministic foundation; no Phase 1 customer flow invokes quoting |
| Eval | `evals/` (retrieval, generation, trajectory, injection, leakage, run_gate) | Kept; G-1 re-cuts the case set for the lean toolset |
| Observability | `app/observability/{cost,tracing}.py`, Langfuse | Kept |
| Infra | `deploy.yml` | Re-cut by B-4; R-11 removes the obsolete Terraform stack and CI job. `deploy.yml` is a smoke test, not an ECS deploy |
