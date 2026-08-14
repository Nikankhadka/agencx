> **NAVIGATION:** Frozen source document (v2.0). This file wins on scope questions only. Schema detail lives in `docs/design/database.md`, UI detail in `docs/design/frontend.md`, progress in `docs/PROGRESS.md`. `docs/conventions.md` governs how work gets done.

# WREN - Technical Architecture Document
> **Version:** 2.0 (domain-agnostic multi-tenant SaaS). Read before writing code.

## 1. Stack

| Layer | Choice | Notes |
|---|---|---|
| Frontend (all 3 surfaces) | Next.js / React / TypeScript, Tailwind | One app serves platform, tenant-admin, and customer surfaces via routing + subdomain |
| Backend | Python / FastAPI | GenAI toolchain (LangGraph, RAGAS) is Python-native |
| Auth | Supabase Auth | Integrates with Postgres RLS |
| Database | Supabase Postgres + pgvector | Dense retrieval + relational data + RLS in one service |
| LLM | Provider abstraction (Azure / OpenAI-compatible) | Model is a config value, not hardcoded |
| Orchestration | LangGraph | Explicit, inspectable supervisor/specialist graph |
| Retrieval | pgvector (dense) + Postgres FTS (sparse) + RRF + cross-encoder rerank | No separate search engine |
| Eval | RAGAS + custom trajectory scorer | |
| Observability | Langfuse, OTel-based | Vendor-neutral |
| Deployment | AWS ECS Fargate + Terraform (backend), Vercel (frontend) | |
| CI/CD | GitHub Actions | |

## 2. Three-surface / multi-tenant architecture

```
  PLATFORM OWNER            TENANT ADMIN (per business)      CUSTOMER (per business)
  admin.wren.app            app.wren.app (authed, scoped)    {slug}.wren.app (public, scoped)
        |                            |                                |
        +------------- Next.js app (one deployment, Vercel) ----------+
                                     |  HTTPS/REST + SSE
                                     v
                        FastAPI backend (one service, ECS Fargate)
                        auth + tenant-context, onboarding, ingestion,
                        agent graph, pricing engine, eval, metrics
                                     |
              +-----------------------+------------------------+
              v                       v                        v
         Supabase                 LLM provider            Langfuse
         Postgres+pgvector        (chat + embed)          (tracing, cost)
         Auth + RLS
```

One backend deployment, one database. Tenants are isolated by `tenant_id` + RLS, never by separate deployments.

**Tenant resolution:**
- Customer: `{slug}.wren.app` resolves to a `tenant_id` via `tenants.slug`; that id becomes the RLS key before any query runs.
- Tenant-admin: `tenant_id` comes from the authenticated user's membership.
- Platform-owner: a distinct privileged role reading across tenants through explicit, audited admin queries.
- Local/dev: subdomains via `*.localhost`; production via a Vercel wildcard domain.

**Domain-agnostic enforcement:** all vertical behavior is `tenant_config` + uploaded knowledge. No vertical branch in agent, retrieval, pricing, or tool code. A test asserts the agent codebase contains no vertical-name conditionals.

## 3. Data model (core entities)

```
tenants(id, slug UNIQUE, name, status, created_at)
tenant_config(tenant_id UNIQUE, system_prompt, tone, enabled_tools, escalation_threshold, brand, config)
users(id, tenant_id, role)                         -- 'owner' | 'staff'
platform_admins(user_id)

documents(id, tenant_id, filename, doc_type, status, uploaded_at)
knowledge_chunks(id, tenant_id, document_id, content, embedding, metadata, tsv)

catalog_items(id, tenant_id, name, description, attributes, price_cents, active)
pricing_rules(id, tenant_id, code, label, unit_amount_cents, unit, conditions, active)
quotes(id, tenant_id, conversation_id, line_items, subtotal_cents, tax_cents, total_cents, status)

conversations(id, tenant_id, customer_ref, channel, status, created_at)
messages(id, tenant_id, conversation_id, role, content, agent_node, created_at)
tool_calls(id, tenant_id, message_id, tool_name, arguments, result, success, latency_ms)
orders(id, tenant_id, ref_code, kind, status, details)         -- seeded mock data
escalations(id, tenant_id, conversation_id, reason, status, created_at)

eval_runs(id, tenant_id, run_type, metrics, git_sha, created_at)
eval_cases(id, tenant_id, case_type, input, expected)
cost_logs(id, tenant_id, conversation_id, model, input_tokens, output_tokens, cost_usd)
```

RLS on every table carrying `tenant_id`. Full DDL: `docs/design/database.md`.

## 4. Agent architecture (LangGraph)

```
 customer msg -> Supervisor (classify + route)
                    |-> Knowledge Agent    (RAG, cited answers)
                    |-> Recommendation Agent (catalog retrieval)
                    |-> Quoting Agent       (selects pricing rules/items + quantities)
                    |-> Order/Status Agent  (lookup_order_or_ticket tool)
                    |-> Escalation Agent    (human handoff, terminal)
                    v
                 Reasoning-Inspection layer
                    (grounding, policy, price-provenance, injection, prompt-leak)
                    v
                 streamed to customer + logged + cost-tracked
```

- Supervisor routes on intent; low confidence escalates rather than guessing.
- Quoting Agent NEVER emits a price. It emits `pricing_rules.code` values + quantities + `catalog_items` refs; the pricing engine computes money.
- The inspection layer is a second pass over the primary output. It is the single most important reliability pattern.

## 5. Deterministic pricing / quoting engine

The safety centerpiece.

- **Input:** the Quoting Agent passes structured selections - `[{rule_code, quantity}, {catalog_item_id, quantity}, ...]` plus tenant tax flags.
- **Computation:** a pure, non-LLM function reads the tenant's `pricing_rules`/`catalog_items`, computes each line in integer cents, applies tax, returns line items + subtotal + tax + total.
- **Validation gate:** asserts (a) every monetary figure in the response derives from the engine's output, (b) no number was authored by the model, (c) totals reconcile. Failure re-prompts up to a limit, then escalates. A model-authored price is a contract violation.
- **Rules editing:** tenant admins edit `pricing_rules` in the console; changes apply to new quotes only.

## 6. Security & privacy (OWASP LLM Top 10, right-sized)

- **LLM01 Prompt injection:** spotlight/delimit retrieved content and tool output as data; input-scan user messages; scored adversarial set.
- **LLM08 Vector/tenant isolation:** `tenant_id` filter on every retrieval + RLS on all tenant tables; the cross-tenant leakage test must pass 100%.
- **LLM10 Unbounded consumption:** per-tenant per-day token/cost budgets, agent step caps, tool/LLM timeouts.
- **LLM07 System-prompt leakage:** the inspection layer checks outgoing responses; secrets live in env/secret manager.
- **Classic web security:** Supabase auth, tenant-scoped route protection, input validation, no committed secrets.
- **Deliberately deferred:** full guardrails framework, formal red-team beyond the adversarial set, SSO/compliance certs.

## 7. Observability & cost

- OTel tracing via Langfuse over every agent run (routing, retrieval, tool calls, pricing, generation, inspection).
- Per-LLM-call cost logged to `cost_logs`; aggregated per tenant/day/conversation and per quote; surfaced in the tenant and platform consoles.

## 8. Deployment (AWS)

```
 Internet
   |-- Vercel (Next.js: all 3 surfaces; wildcard *.wren.app for tenant subdomains)
   |-- Application Load Balancer (public, TLS) --> ECS Fargate task (FastAPI backend,
   |         0.25 vCPU / 0.5GB, public subnet, no NAT) --> Secrets Manager, CloudWatch Logs
  External: Supabase, LLM provider, Langfuse.
```

- Terraform root module: ECR, ECS cluster/service/task-def, ALB + target group + listener, security groups, least-privilege IAM, Secrets Manager. `terraform apply` brings it up.
- No NAT Gateway (public subnet + SG lock-down) - a documented cost-driven simplification.
- Vercel wildcard domain resolves tenant subdomains; the frontend passes the resolved slug to the backend.

## 9. Retrieval pipeline

Query (optionally rewritten) -> dense (pgvector) top-N + sparse (FTS) top-N -> RRF fuse -> cross-encoder rerank to top-k -> generation with required citations -> citation-faithfulness validation. Recommendation runs the same retrieval over `catalog_items`. Every stage is swappable and every swap is run through retrieval eval with a before/after number.
