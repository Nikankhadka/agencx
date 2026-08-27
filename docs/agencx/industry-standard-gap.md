# Agencx: Current State vs Industry Standard - Gap Analysis

**Date written:** 2026-08-28
**Pricing last verified:** 2026-08-28 (vendor pages and terms; see Appendix A for the dated log)
**Scope:** the whole Stage 1 stack - data storage, authentication, authorization, knowledge injection (RAG), media uploads, LLM/agent infrastructure, observability, evaluation, CI/CD, deployment, background jobs, data lifecycle.
**Method:** every current-state claim below was read from the repo (file path or ADR given); every industry-standard claim was checked against vendor documentation or the vendor's own pricing page on the date above. Where sources conflict, the report says so and marks the number `[verify at write time]`.
**Status legend used throughout:** `AT STANDARD` - the choice is the same one a well-run team would make today | `NEAR STANDARD` - right shape, one or two seams short | `GAP` - materially below what a competent team would ship | `DELIBERATE` - below standard on purpose, with a documented reason and a trigger to revisit.

## Executive summary

For a solo-founder, stage-1, portfolio venture on Vercel + Supabase, Agencx is at or above industry standard on **authorization** (RLS posture is textbook), **evaluation** (real gates, real baselines), **money handling** (deterministic, machine-checked), and **retrieval architecture** (dense + sparse + rerank is the reference design). It has real gaps in **backups** (there are none), **session mechanics** (self-minted tokens, no refresh), **error tracking** (none), **E2E in CI** (suite exists, never runs), and **synchronous ingestion** (uploads block the request). Nothing here is un-defendable; four things are currently un-defended: data loss, silent production breakage, an expired session story, and a Hobby-plan license that does not allow the venture to earn money.

**Verdict table:**

| Area | Verdict | Top gap | Lands in phase |
|---|---|---|---|
| 1. Data storage & database | NEAR STANDARD | No backups, no RPO/RTO, no restore path | 1 |
| 2. Authentication | GAP | Self-minted 1h HS256 token, no refresh/rotation/revocation | 2 |
| 3. Authorization | AT STANDARD | Dead `users.role` column, unimplemented tool gate | 1 |
| 4. Knowledge injection (RAG) | NEAR STANDARD | Synchronous ingestion inside the upload request | 2 |
| 5. Image/media uploads | GAP | Cover photo bytes in a Postgres `bytea` column | 1 |
| 6. LLM/agent infrastructure | AT STANDARD | Prompts are unversioned string literals | 2 |
| 7. Observability | GAP | Langfuse configured but inert; no error tracking | 1 |
| 8. Evaluation | AT STANDARD | Offline-only; never scores production traffic | 2 |
| 9. CI/CD & E2E | NEAR STANDARD | E2E suite exists, never runs in CI | 1 |
| 10. Deployment & env config | NEAR STANDARD | Vercel Hobby is non-commercial; dormant AWS stack | 1 / 3 |
| 11. Background jobs | DELIBERATE (documented) | Ingestion blocks requests; queue deferred with a trigger | 2 |
| 12. Data lifecycle & compliance | GAP | No retention, no purge, no PII flows; no backups | 1 |

**Three quotable numbers:**
1. Closing Phase 1 (the defensible baseline) costs **$0/month** - every item is free-tier or already-paid-for tooling.
2. Closing Phase 2 (the standard-shaped platform) costs **~$25-55/month** anchored on Supabase Pro, with optional paid tiers for Langfuse and Sentry.
3. The one gap that can destroy the venture is **no backups** - today a bad migration, a Supabase incident, or an accidental `make clean` in prod is unrecoverable by design.

## How to read this report

Each of the twelve area sections follows the same seven-part template:

1. **Verdict line** - one sentence, one of the four statuses, plus the quotable takeaway.
2. **Current state table** - `Component | What Agencx runs | Where | Notes`. Every claim carries a repo reference so it can be re-verified without trusting this report.
3. **Industry standard paragraph** - the 2026 standard practice, named services, dated pricing.
4. **Gap table** - `Gap | Severity | Industry-standard target | Cost to adopt | Effort | Priority | Phase`. Severity is critical/high/medium/low; effort is S/M/L.
5. **Migration path** - numbered steps per gap with `Effort:`, `Risk:`, and `FLAG:` markers. A `FLAG:` means architecturally consequential (auth model change, DB data migration, deployment topology, new external service) and per repo conventions it goes to the founder for a decision, never silently decided mid-build.
6. **Already at standard** - the defensible choices, each citing the repo artifact.
7. **Deliberate deviations** - accepted costs with their upgrade trigger.

The **gap register** (after the twelve areas) is the doc's living part: every gap has an ID (G1.1, G2.2, ...) and a status column that updates as the roadmap tickets land. The **phased roadmap** at the end sequences everything. Appendices hold the dated pricing log, the source list, and a glossary.

---

## 1. Data storage & database design

**Verdict: NEAR STANDARD.** Schema discipline is above the average startup; the operational posture (backups, staging, retention) is the gap.

**Current state:**

| Component | What Agencx runs | Where | Notes |
|---|---|---|---|
| Database | Postgres 16 + pgvector on Supabase (prod), pgvector/pgvector docker image (dev) | docker-compose.yml:94-108; deploy.md:134-140 | Raw asyncpg, no ORM. Supavisor session pooler port 5432 |
| Migrations | 21 forward-only SQL files, custom runner, advisory-locked, transactional per file, no down migrations | backend/app/shared/migrate.py:54-93; test_migrations.py | Applied manually to prod (deploy.md:147-153); 0016 applied out of sequence |
| Schema | 16 tables; tenants, tenant_config, users, platform_admins, documents, knowledge_chunks, conversations, messages, tool_calls, catalog_items, pricing_rules, quotes, orders, escalations, eval_cases/eval_runs, cost_logs, auth_codes, tenant_assets | backend/migrations/0001-0021 | Integer cents + CHECK constraints, quote immutability trigger, composite-FK denormalization |
| Vector index | HNSW cosine on `knowledge_chunks.embedding vector(384)` | 0004_knowledge.sql:31; 0010_embedding_dim.sql | Retargeted 1536 -> 384 in 0010 |
| Caching | In-process dicts: context package (900s TTL), slug (60s), usage/limits | context_package.py:156-181; features/tenants/service.py:120-174; shared/limits.py:141-171 | Per-worker duplication; `ponytail:` comments name shared store as upgrade |
| Backups | None anywhere; no RPO/RTO, no restore procedure, no verification | (absence confirmed by grep of docs/ and infra/) | Supabase free tier pauses after 1 week idle |
| Staging DB | None; one Supabase project, migrations hit live data | deploy.md:97-100 | "Revisit before onboarding a real tenant" |

**Industry standard (2026):** managed Postgres with automatic daily backups and point-in-time recovery, a staging/preview environment with migration smoke gates, connection pooling, and a documented restore drill. For a Vercel + Supabase stack the standard path is Supabase Pro ($25/mo, daily backups retained 7 days, no idle pause) with the PITR add-on ($100/mo per 7-day window, requires Small compute, ~$130/mo all-in; verified 2026-08-28) once sub-24h RPO matters. Off-site backups you own (weekly `pg_dump` to an R2/B2 bucket, ~$0) are the standard for free-tier projects - Supabase's own docs recommend exactly this. Read replicas are standard only at read volume that matters; at stage 1 they are not a gap.

**Gap table:**

| Gap | Severity | Industry-standard target | Cost to adopt | Effort | Priority | Phase |
|---|---|---|---|---|---|---|
| G1.1 No backups, no RPO/RTO, no restore path | **Critical** | Own-bucket weekly `pg_dump` via GH Actions + quarterly restore drill; Supabase Pro daily backups when revenue justifies; PITR only when sub-24h RPO matters | $0 now; $25/mo staged; ~$130/mo PITR later | M | 1 | 1 |
| G1.2 No staging/preview DB; migrations manual to prod | High | Supabase Database Branching or a second free project + migration smoke in CI | $0-25/mo (branching is ~$10/branch/mo billed hourly) | M | 2 | 2 |
| G1.3 `auth_codes` never purged; ~10 tables missing `updated_at` | Medium | Retention cleanup job + column hygiene on mutable tables | Trivial | S | 2 | 1 |
| G1.4 Hardcoded `'english'` FTS config | Low | Per-tenant `ts_config` (config value with english default) | Trivial | S | 3 | 1 |
| G1.5 Hot-path JSONB `config`/`brand` on `tenant_config` | Low | Keep JSONB (standard for config blobs); measure before moving anything | None | - | note | note |
| G1.6 In-process per-worker caches | Low | Shared store (Upstash Redis, free tier ~$0) only when multi-worker drift shows | $0 | M | 3 | 3 |

**Migration path:**

- **G1.1 (critical):** (1) pick a bucket you own - Cloudflare R2 ($0.015/GB, 10GB free, zero egress) or Backblaze B2; (2) add a GH Actions workflow: weekly `pg_dump` (plain or custom format) of the Supabase DB to that bucket, retention of N weekly snapshots; `Effort: M`, `Risk: low`. (3) Write the restore runbook (how to restore into a scratch project and point a deployment at it) and execute it once as a drill; quarterly thereafter. (4) When revenue arrives, Supabase Pro for daily managed backups; PITR only when a lost day is unacceptable. `FLAG: none` - additive, no schema change.
- **G1.3:** one cleanup statement on a schedule (purge `auth_codes` older than TTL window) plus one migration adding `updated_at` to the mutable tables that lack it. `Effort: S`.
- **G1.4:** config value `fts_config` defaulting to english, used in `to_tsvector`/`websearch_to_tsquery`. `Effort: S`.
- **G1.2 + G1.5 + G1.6** are Phase 2/3 and each carries its own trigger (traction, measured latency, multi-worker deployment).

**Already at standard (quote these):**

- RLS enabled **and forced** on every table with a single non-BYPASSRLS app role - defense in depth, CI-audited (`0002_roles.sql`; `test_schema_audit.py:143-233`).
- Integer cents everywhere with CHECK constraints, `quotes.total_cents = subtotal_cents + tax_cents` as a DB-enforced invariant (`0006_quotes.sql:56`).
- Quote immutability: DELETE revoked from the app role + trigger that forbids editing line items and money (`0006_quotes.sql:66-95`).
- Forward-only migrations with an advisory lock and transactional application (`migrate.py`) - and no down migrations is a legitimate modern pattern (expand-only schema evolution), not a smell; the repo documents it.
- Denormalized `tenant_id` made safe by composite FKs (`0005_conversations.sql:27`), so isolation never depends on app discipline.
- HNSW vector index + hybrid retrieval (see Area 4).
- No read replicas at stage 1 is correct, not a gap.

**Deliberate deviations:**

- In-process caches (`ponytail:` comments in `context_package.py:20-24`) - upgrade trigger: a deployment with more than one backend worker.
- No retention/archival anywhere - that is a GAP (G1.3, G12.3), not a deviation.

---

## 2. Authentication

**Verdict: GAP.** The login-in-chat UX is a deliberate product choice and is fine; the session mechanics under it (self-minted HS256 tokens, 1h expiry, no refresh, no rotation, no revocation, localStorage storage) are below the standard a competent team would ship.

**Current state:**

| Component | What Agencx runs | Where | Notes |
|---|---|---|---|
| Tenant admin login | "Login-in-chat": 6-digit email code issued and verified by the backend | features/auth/api.py:77-108; services/auth_codes.py | sha-256 hash only, 10-min TTL, 5 attempts, 5 codes/hr per email, no per-IP limit |
| Tenant admin session | Backend-minted HS256 JWT, 1h TTL, no refresh token ever minted | services/identity.py:30-46 | Signed with shared SUPABASE_JWT_SECRET; email verification skipped by design (autoconfirm) |
| Platform admin | GoTrue email + password, GoTrue-issued token | admin/login/page.tsx:41-70 | Verified with the same shared secret |
| Customer surface | No auth at all; conversation continuity by UUID knowledge | features/chat/api.py:3-5, 126-131 | Documented design |
| Token storage | localStorage `agencx.login-session` | lib/auth-session.ts:5,22-24; AuthProvider.tsx | XSS-readable; accepted cost documented in D22 (decisions.md:394-398) |
| Route protection | Client-side useEffect guards only; no middleware.ts, no cookies | (tenant-admin)/(console)/layout.tsx:69-73 | RSC pages not server-protected |
| MFA / reset / OAuth / SSO | None | (absence confirmed) | - |

**Industry standard (2026):** for a Next.js app on Supabase with RLS, the defensible standard is **Supabase Auth (GoTrue) end-to-end**: OTP login is native to GoTrue, refresh tokens rotate automatically, `@supabase/ssr` gives httpOnly cookies and server-side session access, and the backend keeps verifying with the `SUPABASE_JWT_SECRET` it already uses for platform admin. Verification of the 2026 landscape: Clerk is the polished alternative - Hobby is free to 50,000 MRU (raised from 10k MAU on 2026-02-05), Pro $25/mo ($20 annual) with MFA and SSO included; Auth.js v5 is in maintenance-by-Better-Auth mode and fits a FastAPI backend poorly. Because Agencx already runs GoTrue and RLS, moving the tenant-admin flow onto the identity store it already has is the lowest-friction standard path, and it costs nothing extra. Cookie/session hardening note: CVE-2025-29927 proved that middleware-only protection is bypassable - the 2026 posture is defense in depth: middleware for UX, real enforcement server-side, and RLS as the backstop (Agencx already has the backstop, which is a strength to name).

**Gap table:**

| Gap | Severity | Industry-standard target | Cost to adopt | Effort | Priority | Phase |
|---|---|---|---|---|---|---|
| G2.1 Self-minted HS256 JWT, 1h, no refresh/rotation/revocation/server-side logout | High | Supabase Auth end-to-end for tenant admin: OTP, rotating refresh tokens, httpOnly cookies | $0 (included in Supabase) | L | 1 | 2 |
| G2.2 localStorage token + client-side-only route protection | High | httpOnly cookies + edge middleware + server-side enforcement (RLS already the backstop) | $0 | M | 2 | 2 |
| G2.3 No per-IP rate limit on code issuance | High | Per-IP limit + attempt ledger on verify | Trivial | S | 1 | 1 |
| G2.4 Static shared HS256 secret, never rotated | Medium | Rotation plan; or moot once G2.1 moves issuance to GoTrue | Small | S | 2 | 1 |
| G2.5 No MFA / password reset / OAuth / SSO | Low | GoTrue TOTP MFA + OAuth are included; adopt when demanded | $0 when needed | M | 3 | 3 |

**Migration path:**

- **G2.3 (Phase 1, do first):** per-IP issuance cap in `auth_codes.py` alongside the existing per-email cap. `Effort: S`, `Risk: low`.
- **G2.1 + G2.2 (Phase 2):** replace the backend-minted session with GoTrue's OTP flow (`POST /auth/v1/otp`), move the frontend to `@supabase/ssr` cookies, keep `require_tenant_admin` verifying the shared secret (no backend contract change). `Effort: L`, `Risk: medium - one-time re-login for every owner`. **`FLAG: auth-model change`** - this changes the session authority and token storage; per repo rules it is a founder decision, and the ticket must spec the migration (existing localStorage sessions invalidated, dev/E2E login flow updated).

**Already at standard (quote these):**

- Emails live only in GoTrue; the app never stores customer emails (PII-minimizing by construction).
- Codes stored as sha-256 hashes only, 10-min TTL, attempt budget, single-use (`0017_auth_codes.sql:14`; `auth_codes.py:89-115`).
- Deliberate no-account-existence-leak on login-code issuance (`auth/api.py:79-81`).
- Backend verifies tokens with audience check and explicit `exp` requirement (`shared/auth.py:56-93`).
- Customers fully anonymous is a deliberate product shape (database.md:297).

**Deliberate deviations:**

- Email verification skipped (`identity.py:124`) - trigger: platform-admin console gains more than one admin.
- MFA/OAuth deferred - trigger: a real tenant asks, or platform admin handles payment-sensitive data.

---

## 3. Authorization

**Verdict: AT STANDARD.** This is the strongest area of the codebase - a textbook multi-tenant authorization posture that most startups never build.

**Current state:**

| Component | What Agencx runs | Where | Notes |
|---|---|---|---|
| DB identity | One `wren_app` role (LOGIN, no BYPASSRLS); transaction-local `app.tenant_id`/`app.role` via `set_config` | 0002_roles.sql; shared/db.py:88-124 | Valid roles: customer, tenant_admin, platform_admin, service |
| RLS | ENABLE + FORCE on every table; three standard policy shapes | 0001_extensions.sql:7-17; database.md:57-84 | CI-audited (test_schema_audit.py) |
| RLS bypass surface | Exactly three audited SECURITY DEFINER resolvers owned by a NOLOGIN `wren_resolver` role | resolve_tenant_slug (0003:67-80); resolve_user_tenant + resolve_platform_admin (0009) | Column-level grants only |
| API tiering | FastAPI dependencies: require_tenant_admin / require_platform_admin / bare authenticate | shared/auth.py:96-146 | tenant_id resolved from JWT sub per request |
| RBAC | Two flat tiers; `users.role` ('owner'/'staff') exists but is never enforced | 0003_tenancy.sql:42; auth.py:126-131 | Dead column or missing feature |
| Tool gating | `enabled_tools` column documented in architecture.md section 8 but nothing reads it | 0016 migration comment:20-22; agent_node.py:349-397 | No endpoint 404s on a disabled capability |

**Industry standard (2026):** multi-tenant SaaS standard is database-enforced isolation (RLS or row-scoping) as the backstop with an application tier for product logic - exactly the shape here. The common commercial pattern adds a tenant claim to the JWT (GoTrue's Custom Access Token Hook embeds it) so the app layer need not resolve the tenant per request; that is an optimization, not a correctness gap. Role-based permission models (owner/staff/agent with per-capability grants) are the norm once more than one human works a tenant - Agencx's schema already has the column for it.

**Gap table:**

| Gap | Severity | Industry-standard target | Cost to adopt | Effort | Priority | Phase |
|---|---|---|---|---|---|---|
| G3.1 `users.role` dead column (owner/staff never enforced) | Medium | Decide: implement staff-role policies (policy branch on role) or drop the column | Small either way | S | 1 | 1 |
| G3.2 `enabled_tools` gating unimplemented | Medium | Implement the documented gate at tool-selection time, or delete column + amend doc | Small | S | 1 | 1 |
| G3.3 Tenant resolved per request (no claim in JWT) | Low | GoTrue Custom Access Token Hook embedding a tenant claim | $0 | M | 3 | 3 |

**Migration path:**

- **G3.1:** either (a) add a `role = 'owner'` branch to the tenant RLS policies plus a `require_staff`-style dependency for the endpoints staff should reach, or (b) one migration dropping the column and a doc note. `Effort: S`, `Risk: low`. **`FLAG: none`** - but it is a product decision (do staff exist in stage 1?), so the ticket asks the founder.
- **G3.2:** wire `enabled_tools` into `_tools_for` at tool-selection time (agent_node.py:349-397) and add the API-layer 404s architecture.md section 8 promises. `Effort: S-M`.
- **G3.3** is an optimization with a trigger (request latency or multi-tenant admin volume).

**Already at standard (quote these):**

- FORCE RLS (matters because `postgres` owns tables on Supabase) with a single non-privileged app role - database.md:11-13.
- The three SECURITY DEFINER resolvers are the entire bypass surface, owned by a NOLOGIN role with column-level grants, and test-pinned (test_migrations.py:94-133) - this is the correct way to do the two pre-context lookups (slug and user) the product genuinely needs.
- Cross-tenant leakage probed by an eval suite in both directions, zero tolerance (leakage_eval.py).
- Deterministic money rule enforced at agent, validation, and API layers with machine-checked import boundaries (import-linter, pyproject.toml:101-136) - above the industry norm.

**Deliberate deviations:**

- Two flat tiers with no per-tenant roles - trigger: a tenant asks to add staff (ticket O-3 already shipped staff takeover, so this trigger is near).
- `orders.kind`/`orders.status` as unconstrained text - deliberate domain-agnosticism (0007:7-9), not a gap.

---

## 4. Knowledge injection (RAG)

**Verdict: NEAR STANDARD.** The retrieval pipeline is ahead of the curve (dense + sparse + rerank is exactly the 2026 reference architecture); the ingestion path is behind (synchronous, no queue).

**Current state:**

| Component | What Agencx runs | Where | Notes |
|---|---|---|---|
| Formats | md, txt, pdf, csv, json, docx; 4MB cap | features/knowledge/api.py:27-32 | No OCR; images refused at the edge (chunker.py:44-47) |
| Chunking | 400-word target, 15% overlap, paragraph-aware; structured docs one chunk per record | ingestion/chunker.py:28-29, 70-133 | Words approximated as whitespace tokens - no tokenizer |
| Embeddings | bge-small-en-v1.5 384-dim (local dev), gemini-embedding-001 (prod free tier) | shared/config.py:137-141; llm/embedder.py | Batch 64 |
| Vector store | pgvector HNSW cosine, tenant-scoped | 0004_knowledge.sql:25-32; retrieval/dense.py:35-52 | RLS is "the net, not the filter" (dense.py:1-7) |
| Retrieval | dense top-20 + FTS top-20 -> RRF k=60 -> cross-encoder rerank -> top-5 | retrieval/service.py:30-73; fuse.py:16,30; rerank.py | Cohere rerank-v3.5 or local MiniLM |
| Fast path | Whole-corpus unscored below 7,500 tokens (deliberate, D12) | services/retrieval.py:100-166; config.py:160 | Hybrid deferred past 50k corpus |
| Ingestion | Synchronous chunk+embed+structure inside the upload request | ingestion/pipeline.py:46-93; knowledge/service.py:71-73 | No queue, no retry machinery |
| Metadata filtering | Only `metadata->>'kind'` exact match | dense.py:44-52; sparse.py:39-50 | No recency/date/doc-type filters |
| SSRF guard | Scheme allowlist only; no private-IP blocking | ingestion/url.py:67-69 | `ponytail:` comment names the upgrade |
| Freshness | `knowledge_version` = max(documents.updated_at), context cache 900s | services/knowledge_version.py:32-37; context_package.py:52 | Re-embed on change = replace-chunks pipeline |

**Industry standard (2026):** ingestion is an asynchronous pipeline: upload API -> durable queue -> stateless worker, idempotent per-document upsert (content-hash keys, orphan delete on re-ingest), statuses tracked (Agencx already has draft/pending/processing/ready/failed). The standard serverless fit for this stack is **QStash** (HTTP-push queue: free 1,000 msgs/day, then $1/100K) or **Inngest** (durable functions: free 50k executions/mo, Pro $99/mo) - both need no broker to run and tolerate Vercel scale-to-zero. Celery is legacy-weight for this stack; ARQ is maintenance-only in 2026. Retrieval-side 2026 practice: hybrid (dense + sparse/BM25) + fusion + rerank is the reference architecture (already in place), with recency/date pre-filters and, optionally, contextual chunk embeddings (Anthropic-style, documented 15-30% precision gains) - the latter only when evals show a recall gap, which this repo can measure.

**Gap table:**

| Gap | Severity | Industry-standard target | Cost to adopt | Effort | Priority | Phase |
|---|---|---|---|---|---|---|
| G4.1 Synchronous ingestion inside the HTTP request | High | Upload -> queue (QStash/Inngest) -> worker; idempotent replace-chunks | $0 free tiers | L | 1 | 2 |
| G4.2 No recency/date metadata filtering at query time | Medium | Preserve `documents.updated_at` on chunks; pre-filter before dense/sparse | Small | S | 2 | 2 |
| G4.3 SSRF guard is scheme-only | Medium | Block RFC1918/link-local/loopback targets in the URL scrape tool | Trivial | S | 1 | 1 |
| G4.4 Word-count token approximation (no tokenizer) | Low | tiktoken-class tokenizer for chunk sizing and corpus budgets | Small | S | 1 | 1 |
| G4.5 No contextual chunk embeddings | Low | Eval-gated adoption (Anthropic contextual-retrieval pattern) | Model calls (cheap tier) | M | 3 | 3 |

**Migration path:**

- **G4.3 (Phase 1, do first):** resolve host, reject private ranges, in `ingestion/url.py`. `Effort: S`, `Risk: low`.
- **G4.4 (Phase 1):** swap the word-count estimate in `chunker.py` and `services/retrieval.py:52` for a real tokenizer. `Effort: S`.
- **G4.1 (Phase 2):** split `upload_document` into (1) persist + enqueue, (2) a worker endpoint that runs the existing `pipeline.process_document`; add idempotency keyed on document id and a retry with backoff. `Effort: L`. **`FLAG: new external service`** (QStash or Inngest) - founder decision.
- **G4.2:** thread `document.updated_at` into chunk metadata and pre-filter in `retrieval/`. `Effort: S`.

**Already at standard (quote these):**

- Dense (pgvector HNSW) + sparse (Postgres FTS) + RRF k=60 + cross-encoder rerank - the 2026 reference architecture, in production (`retrieval/service.py`).
- Whole-corpus fast path is a deliberate lean-first ADR (D12, decisions.md:26-42) with a documented hybrid-deferral threshold - not an accident.
- Citations as `[n]` markers parsed from the answer and emitted as events (agent_node.py:400-418, 701-713).
- Tool results spotlight-wrapped against prompt injection (agent_node.py:118-129).
- Knowledge versioning + cache invalidation without a table (D14, decisions.md:58-76).
- Format allowlist and 4MB cap are reasonable; status state machine exists.

**Deliberate deviations:**

- No async queue (architecture.md:368) - trigger: "first upload that blocks the request past ~2s" (G4.1).
- No OCR - product-scope call, not infra; trigger: tenants upload photographed documents.

---

## 5. Image/media uploads

**Verdict: GAP.** One real gap (cover photo bytes in Postgres), one deliberate deferral (CDN/transformations).

**Current state:**

| Component | What Agencx runs | Where | Notes |
|---|---|---|---|
| Cover photo write | `PUT /api/business/cover`, 2MB cap, jpeg/png/webp | features/business/api.py:26-27, 157-179 | Upsert into `tenant_assets (kind='cover', mime, bytes)` |
| Cover photo storage | Postgres `bytea` column | 0021_tenant_assets.sql:19-26 | `ponytail:` comment:9-13 names object storage as the upgrade path |
| Cover photo read | Bytes served behind the owner's bearer token, ETag + private cache-control | business/api.py:182-200 | No public URL, no CDN |
| Client handling | Downscale client-side: max 1600px edge, JPEG q0.82 | frontend .../CoverPhoto.tsx:19-48, 94-109 | `createImageBitmap` + canvas |
| Document uploads | Storage abstraction: LocalStorage (dev, `var/uploads`) or SupabaseStorage (prod, private bucket) | shared/storage.py:73-138, 148-162 | Key = `{tenant_id}/{document_id}{ext}`; Vercel ephemeral disk makes the bucket required in prod (deploy.md:287-292) |

**Industry standard (2026):** user-generated images live in object storage, not the database - the DB holds a reference (the object key, not the full URL, so rehosting never breaks the data). Delivery goes through a CDN with caching and on-the-fly transformations. The standard options: **Supabase Storage** (already in the stack; free 1GB, 100GB on Pro), **Cloudflare R2** ($0.015/GB, 10GB free, zero egress) with Workers/Images for transforms, or **Cloudinary** (free 25 credits/mo, then ~$89-99/mo - only worth it for serious transformation needs). For private tenant images, signed URLs or an authenticated proxy (which Agencx already has) are the standard. Best practice is to store the object key, not an absolute URL - this repo already does that for documents (`storage.py:165-167`).

**Gap table:**

| Gap | Severity | Industry-standard target | Cost to adopt | Effort | Priority | Phase |
|---|---|---|---|---|---|---|
| G5.1 Cover photo in Postgres `bytea` | High | Supabase Storage via the existing storage abstraction (reuses the document path) | $0 (free 1GB; 100GB on Pro) | S-M | 1 | 1 |
| G5.2 No CDN / transformations / public URLs | Low | Correct at stage 1 (client-side downscale + ETag caching); R2 + Workers or Cloudflare Images when public delivery matters | $0 now; ~$5/mo later | M | 3 | 3 |
| G5.3 No OCR / image analysis in documents | Low | OCR-first ingestion (tesseract or cloud OCR) - a product-scope call | - | - | defer | defer |

**Migration path:**

- **G5.1 (Phase 1):** (1) add `put`/`get`/`delete` calls for the cover through `shared/storage.py` (the abstraction exists; SupabaseStorage backend exists); (2) migration 0022: `alter table tenant_assets alter column bytes drop not null` (or drop `bytes` and keep `kind`/`mime`/key); (3) write the current 16 rows to the bucket once in the same deploy; (4) update `write_cover`/`read_cover`/`delete_cover` and the GET proxy (keep serving behind auth, same as today). `Effort: S-M`, `Risk: low - one data migration of a few rows`. **`FLAG: data migration`** - founder sign-off on the column fate.

**Already at standard (quote these):**

- Storage abstraction with Local/Supabase backends selected by config (`storage.py:148-162`) - the seam the migration reuses.
- Private bucket + bearer-token serving; never a public URL for tenant assets.
- Vercel ephemeral-disk constraint handled correctly (`UPLOADS_BUCKET` required in prod).
- Client-side downscaling before upload (bandwidth + storage hygiene).

**Deliberate deviations:**

- No CDN/transforms (`ponytail:` documented) - trigger: more image surfaces (logos, galleries) or a public asset delivery need.

---

## 6. LLM/agent infrastructure

**Verdict: AT STANDARD** for the agent core; two hygiene gaps (prompt versioning, dead code).

**Current state:**

| Component | What Agencx runs | Where | Notes |
|---|---|---|---|
| Provider abstraction | OpenAI wire format to any endpoint; Azure supported | llm/provider.py; openai_compat.py; azure.py | One class for OpenRouter/Groq/Gemini-compat/Ollama/OpenAI |
| Model chain | 3-tier: Google AI Studio gemini-3.5-flash-lite (primary), Groq gpt-oss-120b (fallback), OpenRouter gemma-4 free (failover) | llm/dependency.py:47-136 | D15/D16 ADRs (decisions.md:78-113) |
| Reliability | Retry with Retry-After, 4s TTFT first-wins race, 10s turn budget, per-tenant daily cost/token budgets | llm/openai_base.py:131-177; llm/failover.py:150-331; shared/limits.py | - |
| Structured output | Strict `json_schema` `response_format`; json_object fallback; Pydantic validation | openai_base.py:444-512 | Malformed output joins retry path |
| Tool calling | Native or emulated via `extract()` with Literal union schema | openai_base.py:280-409 | `supports_tools` flag |
| Graph | LangGraph: START -> agent -> (draft) -> price_gate -> inspection -> END/escalation; fast path = exactly 1 LLM call/turn | agents/graph.py:59-91; agent_node.py:681-728 | History window 10 messages |
| Money rule | Deterministic pricing engine; LLM never produces a monetary amount | app/pricing/engine.py; import-linter (pyproject.toml:101-136) | Machine-checked boundary |
| Prompts | Python string literals in code; tenant `system_prompt`/`tone` from config | agent_node.py:74-115; draft_node.py; context_package.py:100-107 | No registry, no versioning |
| Dead code | Legacy nodes (supervisor.py, knowledge.py, quoting.py, ...) unused by the compiled graph | agents/ | Referenced only by tests/evals |

**Industry standard (2026):** the industry standard is OpenAI/Anthropic-class hosted models with a documented provider strategy; for a $0 budget the defensible variant is exactly what this repo has - a documented multi-tier chain with latency budgets and failover, which is present and ADR'd (D15/D16). Standard hygiene around the agent core: versioned prompt management (Langfuse prompt management, free tier, or a local prompts module with explicit version keys), response/query caching (Upstash Redis free tier) at higher traffic, and no dead code. Structured outputs via strict JSON schema and tool calling are table stakes - both present.

**Gap table:**

| Gap | Severity | Industry-standard target | Cost to adopt | Effort | Priority | Phase |
|---|---|---|---|---|---|---|
| G6.1 Prompts unversioned string literals | Medium | Langfuse prompt management (free tier) or local prompts module with version keys | $0 | M | 2 | 2 |
| G6.2 Legacy unused agent nodes | Low | Delete (supervisor.py and friends); rewrite or drop the tests that reference them | Small | S | 1 | 1 |
| G6.3 No semantic/response cache | Low | Upstash Redis free tier when repeat queries appear | $0 | M | 3 | 3 |

**Migration path:**

- **G6.2 (Phase 1):** delete the legacy node files; move their unique test assertions into the graph-level tests or drop them. `Effort: S`.
- **G6.1 (Phase 2):** extract prompts into a versioned module (or Langfuse, riding G7.1's platform). `Effort: M`.

**Already at standard (quote these):**

- Deterministic money engine with machine-checked import boundaries - **above** the industry norm, where LLM-generated prices are the usual failure (import-linter ADR, decisions.md:191-234).
- Strict JSON-schema structured outputs with resampling on malformed output.
- One LLM call per turn on the fast path with inspection gating before anything reaches the customer (chat/controller.py:239-273).
- Latency budget: 4s TTFT race, Retry-After honoring, per-tenant daily limits (limits.py:150-172) - a real production posture.
- Tool results injection-wrapped (agent_node.py:118-129).

**Deliberate deviations:**

- Free-tier model chain (D15) - trigger: revenue, or a tenant with real customer data (free tiers must never see it; architecture.md:353-356).

---

## 7. Observability

**Verdict: GAP.** Logging is at standard; tracing is configured but inert; errors are unmonitored.

**Current state:**

| Component | What Agencx runs | Where | Notes |
|---|---|---|---|
| LLM tracing | Langfuse seam + NoOpTracer only; env keys exist, SDK not in pyproject | observability/tracing.py:54-104 | Logs "traces are NOT being emitted" when keys are set |
| Logging | Structured JSON with request correlation IDs, access logs, rich app logs | observability/logging.py:46-154 | Genuinely good |
| Error tracking | None - no Sentry, no aggregation, no alerting | (absence confirmed) | Bugs surface via founder email |
| Metrics | Only `cost_logs` for the in-app cost dashboard; price table has 2 entries | observability/cost.py:41-113 | No OTel/Prometheus export |

**Industry standard (2026):** LLM observability is **Langfuse** - the de-facto standard, MIT core, OTel-native (acquired by ClickHouse, Jan 2026; self-host story unchanged). Cloud Hobby is free: 50k units/mo, 30-day data access, no credit card; Core $29/mo (100k units, 90 days); Pro ~$199/mo. Self-hosting (Postgres + ClickHouse + Redis) is not justified at stage-1 volume. Error tracking is **Sentry** - Developer tier free (5k errors/mo, 1 user), Team $26/mo (50k errors, unlimited users); SDKs exist for both Next.js and FastAPI. Metrics/alerting (Prometheus/Grafana or hosted) is standard only when there is an SLO to protect; at stage 1, uptime monitoring via a free monitor (or the existing keep-warm probe) suffices.

**Gap table:**

| Gap | Severity | Industry-standard target | Cost to adopt | Effort | Priority | Phase |
|---|---|---|---|---|---|---|
| G7.1 Langfuse inert (NoOpTracer only) | High | Wire the `langfuse` SDK into the existing tracer seam + LangGraph integration | $0 (Hobby free) | M | 1 | 1 |
| G7.2 No error tracking | High | Sentry (Developer free; Team $26/mo past 5k errors) | $0 | S | 1 | 1 |
| G7.3 No metrics export / uptime alerting | Low | BetterStack free uptime or the existing keep-warm probe as monitor | $0 | S | 3 | 3 |

**Migration path:**

- **G7.2 (Phase 1, do first - smallest and highest value):** add `sentry-sdk` to backend and `@sentry/nextjs` to frontend, wire DSN from env, ship the structured 500s it already logs. `Effort: S`.
- **G7.1 (Phase 1):** add `langfuse` to pyproject, implement the tracer selection in `tracing.py:85-104` (replace NoOpTracer when keys are present), keep the existing turn/spans shape (chat/controller.py:185-202; agents/tracing.py:55-77). `Effort: M`.

**Already at standard (quote these):**

- Structured JSON logs with X-Request-ID correlation and access logging (`logging.py`) - verified good, not invented for this report.
- The tracing seam itself (tracer interface + span attributes for route, confidence, gates, chunks, verdicts) - the wiring is one PR away.

**Deliberate deviations:**

- No Prometheus/Grafana - trigger: an SLO or a paying tenant with expectations.

---

## 8. Evaluation

**Verdict: AT STANDARD.** The most industry-conformant area of the codebase - real gates, real baselines, real trajectory scoring on the compiled graph.

**Current state:**

| Component | What Agencx runs | Where | Notes |
|---|---|---|---|
| Gate harness | Absolute gates (money, leakage, retrieval recall@5 >= 0.85) + regression gates vs previous run (faithfulness, tool_correctness >= 0.90, injection, 3% tolerance) | evals/run_gate.py:49-191 | Baselines from `eval_runs` table, git sha recorded |
| Metrics | Recall@3/5, MRR, nDCG@5; RAGAS-equivalent faithfulness/relevancy implemented natively (deliberately no `ragas` dep) | evals/retrieval_eval.py:94-116; generation_eval.py:6-17 | LLM-judged via the app's own `extract()` |
| Datasets | ~193 cases across 5 jsonl files (retrieval 50, generation 45, trajectory 37, injection 31, judge calibration 30) | evals/datasets/*.jsonl | Seed tenant: bytefix |
| Trajectory | Drives the real compiled graph; route correctness, selections, terminal DB state, step efficiency, cost | evals/trajectory_eval.py:300 | Rate-limit retry harness |
| CI | eval-gate job in CI with pinned gemma-4-free model; absolute gates never skipped | .github/workflows/ci.yml:139-199 | LLM-dependent parts skip when no key |
| Baselines | recall@5 1.000, MRR 0.911, nDCG@5 0.934, leakage 12/12, injection 0.967 | architecture.md:318-327 | - |

**Industry standard (2026):** offline golden-set evaluation with CI gates is the minimum bar (present); the standard extension is continuous evaluation over production traffic - Langfuse evals (LLM-as-judge over real traces) plus user feedback capture (thumbs up/down), which rides the same platform as tracing. Dataset versioning in git is standard for small teams; Langfuse datasets are the upgrade. Frameworks (DeepEval, ragas, LangSmith) are tools, not standards - a native harness with explicit metrics is defensible and documented as a choice here.

**Gap table:**

| Gap | Severity | Industry-standard target | Cost to adopt | Effort | Priority | Phase |
|---|---|---|---|---|---|---|
| G8.1 Offline-only; never scores production traffic | Medium | Langfuse evals + user feedback over real traces (rides G7.1) | $0 | M | 2 | 2 |
| G8.2 Datasets versioned in git only | Low | Acceptable; document the convention (optionally Langfuse datasets) | $0 | S | 2 | 2 |
| G8.3 LLM-judged metrics need a paid key for clean numbers | Low | Keep pinned free model for CI determinism; document paid-key trigger | $0 | - | note | note |

**Migration path:**

- **G8.1 (Phase 2):** once Langfuse emits traces (G7.1), attach LLM-as-judge scores in the platform and a feedback widget on the customer page; feed results back into `eval_runs`-style regression tracking. `Effort: M`.

**Already at standard (quote these):**

- Absolute gates that never skip (money, leakage, retrieval) + regression gates with tolerance vs the previous run - a real CI eval posture (run_gate.py; architecture.md:282-342).
- Trajectory eval on the real compiled graph including terminal DB state and cost - rare at any stage.
- Judge calibration dataset (30 cases) for the LLM judge.
- Native metrics over a framework dependency - documented, deliberate (generation_eval.py:6-12).

**Deliberate deviations:**

- No online/traffic evals - trigger: real traffic exists (G8.1).

---

## 9. CI/CD & E2E

**Verdict: NEAR STANDARD.** The gates exist and are strong; the E2E suite is the missed step.

**Current state:**

| Component | What Agencx runs | Where | Notes |
|---|---|---|---|
| Frontend gate | lint, check:tokens, typecheck, vitest, build | ci.yml:31-57 | Node 24 pinned |
| Backend gate | ruff, mypy strict, import-linter, format check, pytest in the shipping image's test stage | ci.yml:59-120 | pgvector service container |
| Infra gate | terraform fmt/init/validate | ci.yml:122-137 | Keeps dormant stack from rotting |
| Eval gate | seed + run_gate in CI | ci.yml:139-199 | - |
| Deploy | Vercel Git integration from `staging`; deploy.yml = smoke tests only | deploy.yml; deploy.md:40-91 | - |
| E2E | Playwright, 18 spec files / 71 tests, runs locally via make test-e2e only | frontend/e2e/; Makefile:189-190 | **No CI job runs it** |
| Security scanning | None (no Dependabot, no audit in CI) | (absence confirmed) | - |
| Preview deploys | Disabled - Ignored Build Step means PRs never build | deploy.md:65-77 | - |

**Industry standard (2026):** E2E in CI, gated before deploy; dependency scanning (Dependabot/renovate + `npm audit`/`uv audit`); preview deployments per PR so the human sees a real build before merge. Everything else in this repo's CI is at or above the norm.

**Gap table:**

| Gap | Severity | Industry-standard target | Cost to adopt | Effort | Priority | Phase |
|---|---|---|---|---|---|---|
| G9.1 E2E never runs in CI | High | Wire Playwright into ci.yml using the repo's own container pattern (backend + db services, loopback mirrors already exist) | $0 (GH Actions minutes) | M | 1 | 1 |
| G9.2 No dependency scanning / SAST | Medium | Dependabot + `npm audit` / `uv audit` in CI; CodeQL optional later | $0 | S | 1 | 1 |
| G9.3 No preview deployments | Medium | Enable Vercel preview deploys per PR (free on Hobby) | $0 | S | 2 | 2 |
| G9.4 Deploy is staging-branch Git integration, smoke-only | Low | Acceptable at stage 1; promote-to-main gating when a second environment exists (ties to G1.2) | $0 | - | 2 | 2 |

**Migration path:**

- **G9.1 (Phase 1):** add an `e2e` job to ci.yml that starts backend + db services (the eval-gate job already shows the pattern), seeds, runs the Playwright suite, and gates on green. `Effort: M`, `Risk: flake management - keep the existing local-only pattern so runs stay reproducible`.
- **G9.2 (Phase 1):** enable Dependabot; add the two audit commands to the existing jobs. `Effort: S`.

**Already at standard (quote these):**

- Full local gate: `make ci` runs lint + typecheck + tests + format + build on one command - most startups lack this.
- Eval gate with a pinned model and absolute gates that never skip.
- Deploy smoke tests that catch an error-shell-with-200 (deploy.yml:88-92).
- Keep-warm cron, documented as a workaround with a delete trigger (keep-warm.yml).

**Deliberate deviations:**

- No SAST - trigger: a real tenant's data or a security review (G9.2 covers the cheap first step).

---

## 10. Deployment & environment config

**Verdict: NEAR STANDARD.** The Vercel container pattern works and is well documented; two edges are unexamined (license posture, dormant stack).

**Current state:**

| Component | What Agencx runs | Where | Notes |
|---|---|---|---|
| Topology | Two container services on one Vercel project, same origin, rewrites | vercel.json; deploy.md:11-22 | No CORS surface in prod |
| Branches | `staging` = production branch; no `main`; Ignored Build Step | deploy.md:40-91 | Fixed in B-4 |
| Cold starts | Scale-to-zero, ~11s boot, fought by keep-warm cron | keep-warm.yml:3-11; deploy.md:402-407 | Region-matched DB (deploy.md:177-188) |
| Config | One pydantic Settings class, env-sourced; startup guard refuses placeholder secrets | shared/config.py:9-191; shared/startup.py; .env.example | Full env list in deploy.md:210-252 |
| Migrations | Manual one-time application | deploy.md:147-153 | Not automated (ties to G1.2) |
| Dormant stack | AWS ECS Terraform (7 files), CI-validated, deployed by nothing | infra/*.tf | No RDS/S3/NAT; DB was always Supabase |

**Industry standard (2026) + the license fact:** Vercel's Hobby plan is **restricted to non-commercial personal use** - the terms and fair-use page are explicit that any deployment "used for the purpose of financial gain of anyone involved" (including a portfolio venture that earns money) requires Pro ($20/mo). Hobby caps: 1M function invocations, 4 CPU-hrs, 360 GB-hrs, 100GB transfer (verified 2026-08-28). The standard posture for a solo venture that might earn: document the trigger to move to Pro, or move the backend container to Railway ($5/mo incl. usage) / Render ($7/mo per web service) / Fly.io when revenue or cold-start economics flip - the frontend can stay on Vercel either way. Everything else here (same-origin, session pooler, region matching) is standard practice.

**Gap table:**

| Gap | Severity | Industry-standard target | Cost to adopt | Effort | Priority | Phase |
|---|---|---|---|---|---|---|
| G10.1 Vercel Hobby is non-commercial; cold starts ~11s | Medium | Document the trigger: Vercel Pro $20/mo, or backend to Railway/Render when revenue starts | $0 now; $5-20/mo when triggered | S (decision) | 1 | 3 |
| G10.2 Cold starts fought by keep-warm cron | Low | Accept + document; always-on container is the G10.1 path | $0 | S | 3 | 3 |
| G10.3 Dormant AWS ECS Terraform stack | Low | Decide: delete it or mark it dormancy-explicit in docs | Small | S | 1 | 1 |
| G10.4 Manual migration application | Medium | Migration smoke in CI + second environment (ties to G1.2) | $0-25/mo | M | 2 | 2 |

**Migration path:**

- **G10.3 (Phase 1):** a one-line decision in deploy.md (or delete the stack + the CI job). The stack invites the question "what is this for?" at the wrong moment. `Effort: S`. **`FLAG: deployment topology`** (if deleted, this reverses a documented ADR - D10/B-4 already superseded it, so the decision is whether to retire the artifact).
- **G10.1 (Phase 3):** one sentence trigger in deploy.md - first revenue, or cold-start complaints from a real tenant.

**Already at standard (quote these):**

- Same-origin rewrites eliminate the CORS surface in prod (vercel.json; D22).
- Containerized dev stack with one-command make targets - matches the shipped prod images.
- Startup guard refuses placeholder/empty secrets outside local/CI (startup.py:26-50).
- Supabase session pooler port 5432 with region matching documented (deploy.md:134-140, 177-188).

**Deliberate deviations:**

- Keep-warm cron (documented workaround) - trigger: always-on container (G10.1).
- Free-tier Supabase idle pause - trigger: Supabase Pro (G1.1).

---

## 11. Background jobs & async processing

**Verdict: DELIBERATE (documented absence).** Nothing at stage-1 volume needs async durability Postgres cannot provide - that is a legitimate ADR stance, and the entry path is named.

**Current state:**

| Component | What Agencx runs | Where | Notes |
|---|---|---|---|
| Jobs | None - ingestion (chunk+embed+structure) runs inside the upload request | ingestion/pipeline.py:46-93; knowledge/service.py:71-73 | The one job that hurts |
| Async today | One fire-and-forget `asyncio.create_task` (context-package cache priming) | features/tenants/controller.py:82 | Best-effort by design |
| Scheduling | Vercel cron only (keep-warm ping) | keep-warm.yml | Vercel Cron does not retry |
| Queue tech | None (no Celery/RQ/arq/Redis) | (absence confirmed) | architecture.md:368 documents the deferral |

**Industry standard (2026):** durable queues with retries and dead-letter handling for anything user-facing that takes longer than a request budget; for this serverless stack the entry path is **QStash** (HTTP-push, free 1,000 msgs/day, then $1/100K) or **Inngest** (durable functions, free 50k executions/mo, Pro $99/mo). Celery's ops weight is unjustified against async FastAPI; ARQ is maintenance-only in 2026. Vercel Cron (free) does not retry - any future scheduled handler must be idempotent.

**Gap table:**

| Gap | Severity | Industry-standard target | Cost to adopt | Effort | Priority | Phase |
|---|---|---|---|---|---|---|
| G11.1 Synchronous ingestion (cross-ref G4.1) | High | QStash/Inngest queue + worker endpoint | $0 free tiers | L | 1 | 2 |
| G11.2 Cache priming best-effort only | Low | Fine; shared cache when multi-worker drift appears (G1.6) | $0 | - | 3 | 3 |
| G11.3 No scheduled jobs beyond keep-warm | Low | Vercel Cron (idempotent handlers) or QStash schedules (10 free) | $0 | S | 3 | 3 |

**Migration path:**

- **G11.1 = G4.1** (see Area 4). The trigger is stated in the ADR: "first upload that blocks the request past ~2s" or any Stage 2 webhook/send volume.

**Already at standard (quote these):**

- The documented decision itself (architecture.md:368) - "nothing at Stage 1 volume needs async durability Postgres cannot provide" - is the correct way to defer a queue: named, reasoned, with a trigger.

**Deliberate deviations:**

- No queue (see trigger above). No Redis - rides G1.6's trigger.

---

## 12. Data lifecycle, backups & compliance

**Verdict: GAP.** The venture's single biggest un-defended risk: there is no way to recover the database today.

**Current state:**

| Component | What Agencx runs | Where | Notes |
|---|---|---|---|
| Backups | None - no policy, no RPO/RTO, no restore procedure, no verification | (absence confirmed by grep of docs/ and infra/) | Free tier pauses after 1 week idle |
| Retention | None - `auth_codes` rows never purged; messages/conversations/cost_logs grow unbounded | auth_codes.py:97-105 | No cleanup job exists anywhere |
| PII | Thin by design: codes hashed, emails only in GoTrue, no customer accounts | 0017_auth_codes.sql:14; database.md:297 | `messages.content` and `tenant_config.config` hold owner/customer text |
| Export/deletion flows | None (no GDPR-style data-subject flows) | (absence confirmed) | - |

**Industry standard (2026):** every production database has a backup policy with defined RPO/RTO, off-site copies, and a periodically exercised restore. Managed platforms provide it (Supabase Pro: daily backups, 7-day retention, $25/mo; PITR $100/mo for 7-day windows, ~$130/mo all-in with Small compute; verified 2026-08-28), and free tiers require you to own the export (Supabase's own docs say exactly this: free-tier projects should regularly `db dump` off-site). Retention policies exist for every table that accumulates; PII lifecycle (export, deletion, masking) is standard whenever the product is consumer-facing or EU-adjacent. Note the honest restore windows on Supabase free tier: in-place restore available ~90 days, downloadable backups ~1 year - an own-bucket backup makes a pause or project loss a non-event.

**Gap table:**

| Gap | Severity | Industry-standard target | Cost to adopt | Effort | Priority | Phase |
|---|---|---|---|---|---|---|
| G12.1 No backup policy, RPO/RTO, restore verification (= G1.1) | **Critical** | RPO 24h / RTO 1 day at stage 1; weekly own-bucket pg_dump; quarterly restore drill; Supabase Pro when revenue justifies | $0 now; $25/mo staged; ~$130/mo PITR later | M | 1 | 1 |
| G12.2 Free-tier idle-pause risk | Medium | Own-bucket backups make a pause a non-event; keep-warm covers today | $0 | S | 1 | 1 |
| G12.3 `auth_codes` never purged; no retention decisions for chat history | Medium | Purge job (Phase 1) + a written retention decision for conversations (product call: keeping history forever is defensible if stated) | Small | S | 1/2 | 1/2 |
| G12.4 No PII export/deletion flows | Low | Consciously deferred compliance item - document "no flow until an enterprise tenant asks" | - | - | 3 | 3 |

**Migration path:**

- **G12.1 = G1.1** (Area 1) - the backup workflow and the drill.
- **G12.3 (Phase 1):** scheduled purge of expired `auth_codes` (same job as G1.3); Phase 2: the founder writes the retention decision into this doc's gap register (status: decided) with the chosen window.

**Already at standard (quote these):**

- PII minimized by construction: auth codes hashed, user emails live only in GoTrue, customers have no accounts at all.
- The one soft-delete FK in the schema (`cost_logs.conversation_id SET NULL`) shows deletion semantics were thought about (0008:38).

**Deliberate deviations:**

- No data-subject flows (G12.4) - trigger: enterprise tenant or consumer-market regulation.

---

## Gap register (living table)

Status: `open` | `decided` (founder ruled, ticket optional) | `done` | `ticket` (spec ticket filed).

| ID | Area | Gap | Severity | Effort | Phase | Status |
|---|---|---|---|---|---|---|
| G1.1 | 1 | No backups / RPO / RTO / restore path | Critical | M | 1 | open |
| G1.2 | 1 | No staging DB; migrations manual | High | M | 2 | open |
| G1.3 | 1 | auth_codes never purged; missing updated_at | Medium | S | 1 | open |
| G1.4 | 1 | Hardcoded english FTS config | Low | S | 1 | open |
| G1.5 | 1 | Hot-path JSONB config/brand | Low | - | note | open |
| G1.6 | 1 | In-process per-worker caches | Low | M | 3 | open |
| G2.1 | 2 | Self-minted tokens, no refresh/rotation | High | L | 2 | open |
| G2.2 | 2 | localStorage + client-side-only protection | High | M | 2 | open |
| G2.3 | 2 | No per-IP rate limit on codes | High | S | 1 | open |
| G2.4 | 2 | Static shared HS256 secret | Medium | S | 1 | open |
| G2.5 | 2 | No MFA/reset/OAuth/SSO | Low | M | 3 | open |
| G3.1 | 3 | users.role dead column | Medium | S | 1 | open |
| G3.2 | 3 | enabled_tools gating unimplemented | Medium | S-M | 1 | open |
| G3.3 | 3 | No tenant claim in JWT | Low | M | 3 | open |
| G4.1 | 4 | Synchronous ingestion | High | L | 2 | open |
| G4.2 | 4 | No recency/date filtering | Medium | S | 2 | open |
| G4.3 | 4 | SSRF scheme-only guard | Medium | S | 1 | open |
| G4.4 | 4 | Word-count token approximation | Low | S | 1 | open |
| G4.5 | 4 | No contextual embeddings | Low | M | 3 | open |
| G5.1 | 5 | Cover photo in Postgres bytea | High | S-M | 1 | open |
| G5.2 | 5 | No CDN/transformations | Low | M | 3 | open |
| G5.3 | 5 | No OCR | Low | - | defer | open |
| G6.1 | 6 | Prompts unversioned | Medium | M | 2 | open |
| G6.2 | 6 | Legacy agent nodes | Low | S | 1 | open |
| G6.3 | 6 | No response cache | Low | M | 3 | open |
| G7.1 | 7 | Langfuse inert | High | M | 1 | open |
| G7.2 | 7 | No error tracking | High | S | 1 | open |
| G7.3 | 7 | No metrics/alerting | Low | S | 3 | open |
| G8.1 | 8 | Offline-only evals | Medium | M | 2 | open |
| G8.2 | 8 | Dataset versioning convention | Low | S | 2 | open |
| G8.3 | 8 | Paid key for clean LLM-judged numbers | Low | - | note | open |
| G9.1 | 9 | E2E never in CI | High | M | 1 | open |
| G9.2 | 9 | No dependency scanning | Medium | S | 1 | open |
| G9.3 | 9 | No preview deploys | Medium | S | 2 | open |
| G9.4 | 9 | Smoke-only deploy gating | Low | - | 2 | open |
| G10.1 | 10 | Hobby non-commercial; cold starts | Medium | S | 3 | open |
| G10.2 | 10 | Keep-warm cron workaround | Low | S | 3 | open |
| G10.3 | 10 | Dormant AWS ECS stack | Low | S | 1 | open |
| G10.4 | 10 | Manual migration application | Medium | M | 2 | open |
| G11.1 | 11 | Synchronous ingestion (= G4.1) | High | L | 2 | open |
| G11.2 | 11 | Best-effort cache priming | Low | - | 3 | open |
| G11.3 | 11 | No scheduled jobs | Low | S | 3 | open |
| G12.1 | 12 | No backup policy (= G1.1) | Critical | M | 1 | open |
| G12.2 | 12 | Idle-pause risk | Medium | S | 1 | open |
| G12.3 | 12 | No retention decisions/purge | Medium | S | 1/2 | open |
| G12.4 | 12 | No PII flows | Low | - | 3 | open |

---

## Phased target-state roadmap

### Phase 1 - "Defensible baseline" (now, ~2-4 weeks, $0/month)

**Goal:** no single point of total data loss; every technology choice answerable; invisible defects (E2E, errors, traces) made visible; every lie-in-waiting removed.

Lands here: **G1.1 + G12.1 + G12.2** (backups, RPO 24h/RTO 1 day, restore drill), **G1.3 + G12.3** (purge job + missing timestamps), **G1.4** (FTS config), **G2.3** (per-IP rate limit), **G2.4** (key rotation plan), **G3.1 + G3.2** (dead-column decisions), **G4.3 + G4.4** (SSRF + tokenizer), **G5.1** (cover to Supabase Storage - FLAG data migration), **G6.2** (delete legacy nodes), **G7.1** (Langfuse wiring), **G7.2** (Sentry), **G9.1** (E2E in CI), **G9.2** (Dependabot + audits), **G10.3** (ECS stack decision).

**Ordering rationale:** every Phase 1 item is free, and each prevents a specific bad outcome - data loss (G1.1), undiagnosed breakage (G7.2, G9.1), an indefensible "why" (G3.1, G3.2, G10.3), or a security sharp edge (G2.3, G4.3). Backups and Sentry come first because they are the cheapest insurance; the two dead-column decisions come early because they block future schema work.

### Phase 2 - "Standard-shaped platform" (on traction, ~$25-55/month)

**Goal:** sessions, ingestion, environments, and evaluation match the standard shape.

Lands here: **G1.2 + G10.4** (staging DB + migration smoke; Supabase Pro $25/mo anchors this phase), **G2.1 + G2.2** (Supabase Auth end-to-end - FLAG auth-model change; refresh tokens, httpOnly cookies, middleware), **G4.1 + G11.1** (async ingestion via QStash/Inngest - FLAG new external service), **G4.2** (recency filtering), **G6.1** (prompt versioning on the Langfuse platform), **G8.1** (production-traffic evals + user feedback), **G9.3** (preview deploys). Optional paid tiers if usage demands: Langfuse Core $29/mo, Sentry Team $26/mo.

**Ordering rationale:** gated on traction because every item either costs money or changes a user-visible/architectural seam. Auth first within the phase (highest-severity gap left, and it unblocks G3.3); ingestion second (the only job that hurts today); everything else rides platforms already adopted (Langfuse for prompts + evals, Supabase Pro for staging).

### Phase 3 - "Scale readiness" (trigger-only, $0-150/month)

**Goal:** nothing in this phase is scheduled; each item has a written trigger.

Lands here: **G10.1** (backend off Hobby when revenue or cold-start economics flip - FLAG topology; Vercel Pro $20/mo or Railway $5/mo / Render $7/mo), **G1.1's PITR upgrade** (~$130/mo when sub-24h RPO matters), **G5.2** (R2/Cloudflare Images when public media delivery appears), **G2.5** (MFA when demanded), **G3.3** (tenant claim in JWT when per-request resolution shows), **G6.3** (semantic cache when repeat queries appear), **G4.5** (contextual embeddings when evals show a recall gap), **G11.3** (real scheduling when there is something to schedule), **G12.4** (PII flows when an enterprise tenant asks), read replicas when query volume justifies them.

**Roadmap mechanics:** each phase maps to tickets in `spec/` when work starts (the gap register is the source list); `progress.md` gets a row per ticket as it lands; the register's status column is the board.

---

## How to verify this report

Check five things before trusting any number here:

1. **Accuracy against the repo.** Every current-state claim carries a reference (file path, ADR number, migration name). Spot-check the load-bearing ones: 16 tables / 21 migrations, the 4MB upload and 2MB cover caps, the 10-min TTL / 5-attempt / 5-per-hour figures, port 5432, the 7,500-token fast-path threshold, the eval baselines. If a claim has no reference, it was either verified externally (and is in Appendix A) or is an error - flag it.
2. **Cost sanity.** All prices are date-stamped (2026-08-28) in Appendix A with source type. Pricing moves quarterly; re-verify any number before it becomes a purchase decision. The three to re-check hardest before spending: Supabase PITR all-in (~$130/mo), Sentry Team $26/mo, Langfuse Core $29/mo.
3. **Priorities match the goal.** For every Phase 1 item ask: "what specific bad outcome does this prevent?" If there is no answer, demote it. For every Phase 2/3 item ask: "what triggers this?" If the trigger is vague, tighten it. The solo-founder/stage-1/portfolio constraints are the tiebreaker for every severity call.
4. **Flag audit.** Every architecturally consequential item (auth model change, DB data migration, deployment topology, new external service) carries a `FLAG:` in its migration path. Verify each has been consciously accepted - per repo conventions these are never silently decided.
5. **Living-doc check.** The gap register has a status column; confirm it is updated when tickets land, and that `progress.md` rows exist for each shipped ticket.

---

## Appendix A: pricing verification log (verified 2026-08-28)

| Vendor | Plan / item | Price | Source type |
|---|---|---|---|
| Vercel | Hobby (non-commercial; 1M invocations, 4 CPU-hrs, 360 GB-hrs, 100GB transfer) | $0 | vendor terms + fair-use page |
| Vercel | Pro | $20/mo | vendor pricing page |
| Supabase | Pro (daily backups 7 days, 100GB storage, no pause) | $25/mo | vendor pricing page |
| Supabase | PITR add-on (7-day window; requires Small compute ~$15/mo vs $10 credit) | ~$100/mo (~$130 all-in) | vendor docs + third-party |
| Supabase | Database Branching | $0.01344/branch/hr (~$10/mo) | vendor pricing page |
| Supabase | Free tier: no backups, pauses after 1 week idle | $0 | vendor pricing page |
| Langfuse | Cloud Hobby (50k units, 30-day retention, 2 users) | $0 | vendor pricing page |
| Langfuse | Core (100k units, 90-day retention) | $29/mo | vendor pricing page + third-party |
| Langfuse | Pro (100k units, 3-year retention) | ~$199/mo | third-party (conflicts on exact tiers - `[verify at write time]`) |
| Sentry | Developer (5k errors/mo, 1 user) | $0 | vendor pricing page |
| Sentry | Team (50k errors included, unlimited users) | $26/mo (annual) | vendor pricing page |
| Clerk | Hobby (50k MRU; raised from 10k on 2026-02-05) | $0 | vendor pricing page |
| Clerk | Pro (50k MRU, MFA, SSO included) | $25/mo ($20 annual) | vendor pricing page |
| QStash | Free (1,000 msgs/day) | $0 | vendor pricing page |
| QStash | Pay-as-you-go | $1/100K messages | vendor pricing page |
| Inngest | Hobby (50k executions/mo) | $0 | vendor pricing page |
| Inngest | Pro | $99/mo | vendor pricing page |
| Cloudflare R2 | Storage (10GB free, then ~$0.015/GB, zero egress) | ~$0-5/mo | vendor pricing page |
| Cloudinary | Free 25 credits/mo, then | ~$89-99/mo | third-party (not re-verified - `[verify at write time]`) |
| Railway | Hobby (includes $5 usage) | $5/mo | vendor site (not re-verified - `[verify at write time]`) |
| Render | Web service | $7/mo | vendor site (not re-verified - `[verify at write time]`) |

## Appendix B: sources

- **Vendor primary (verified this date):** vercel.com/docs/limits/fair-use-guidelines, vercel.com/legal/terms, vercel.com/pricing; supabase.com/pricing, supabase.com/docs/guides/platform/backups, supabase.com/docs/guides/platform/manage-your-usage/point-in-time-recovery; langfuse.com/pricing; sentry.io/pricing, docs.sentry.io/pricing; clerk.com/pricing, clerk.com/changelog/2026-02-05-new-plans-more-value; upstash.com/pricing/qstash; inngest.com/pricing.
- **Third-party comparisons (marked as such, used only to cross-check):** backupdrill.com (Supabase PITR, 2026-08-23); sentrial.com and budgetforge.dev (Langfuse, 2026-05/07); markaicode.com and cubeapm.com (Sentry, 2026-06/08); apiscout.dev (QStash vs Inngest vs SQS, 2026-03); clerk.com/articles/clerk-pricing-explained.
- **Repo primary (every current-state claim):** file paths and ADR references inline in each area section; the canonical docs are docs/agencx/architecture.md, docs/agencx/design/database.md, docs/agencx/design/decisions.md, docs/agencx/deploy.md.

## Appendix C: glossary

- **RPO / RTO** - recovery point objective (how much data loss is acceptable) / recovery time objective (how fast you must be back). Stage-1 proposal: RPO 24h, RTO 1 day.
- **PITR** - point-in-time recovery: restore to any second within a retention window, not just the last daily backup.
- **RRF** - reciprocal rank fusion: merges ranked lists (dense + sparse) into one ranking; k=60 here.
- **MRU / MAU** - monthly retained user / monthly active user; Clerk bills MRU (users who return after 24h), Supabase bills MAU.
- **SSRF** - server-side request forgery: the URL-scrape tool fetching internal addresses; blocked by scheme allowlist today, private-IP blocking is the fix.
- **HNSW** - hierarchical navigable small worlds: the pgvector index type for approximate nearest-neighbor search.
- **bytea** - Postgres binary column type; where the cover photo currently lives.
- **SECURITY DEFINER** - a Postgres function that runs with the owner's privileges (here, the RLS-bypassing resolver role).
- **OTel** - OpenTelemetry, the tracing standard Langfuse ingests.