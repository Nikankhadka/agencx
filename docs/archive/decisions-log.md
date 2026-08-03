# Decisions Log

Historical record of implementation decisions, bug postmortems, and design
tradeoffs discovered during the Wren build. Each entry is a verbatim copy from
`.agents/memory.md` entries that were moved here because they are (a) postmortems
of now-fixed bugs with regression tests guarding them, (b) already recorded in
design docs, (c) superseded by later entries, or (d) too detailed for the
every-session memory reading path.

This file is read-on-need, not every session. Current, actionable facts live in
`.agents/memory.md`.

---

## T-002: Quote protection details (2026-07-10)

- 2026-07-10 (T-002): quote protection strengthened slightly beyond database.md's sample trigger - id/created_at also frozen, and wren_app holds no DELETE on quotes (revoked; FK cascades still work because they run as the table owner) - why: principle 5 "tamper-proof once sent" taken literally after review.

## T-002: Resolver column grants (2026-07-10)

- 2026-07-10 (T-002): wren_resolver gets column-level grants only (tenants: id/slug/name/status; tenant_config: tenant_id/brand) - why: the privilege boundary of the single sanctioned RLS bypass must match resolve_tenant_slug's four-column contract, so a future resolver-owned function cannot widen the pre-auth surface.

## T-004: Auth dependency pattern (2026-07-11)

- 2026-07-11 (T-004): auth dependencies return the authed principal and each route opens `tenant_context(tenant_id, role)` itself, instead of the ticket's "dependency yields the connection" - why: avoids holding a transaction/pooled connection for the whole request; acceptance (API-level cross-tenant isolation) proven in test_auth_api.py. Flagged for founder confirmation.

## T-004: Pre-context resolvers (2026-07-11)

- 2026-07-11 (T-004): pre-context user/platform-admin lookups go through SECURITY DEFINER resolvers `resolve_user_tenant` / `resolve_platform_admin` (migration 0009, wren_resolver-owned, column-level grants) mirroring resolve_tenant_slug - why: keeps the sanctioned RLS bypass surface narrow and auditable.

## T-004: Frontend UI kit decision (2026-07-11)

- 2026-07-11 (T-004): frontend ui kit is hand-built per frontend.md section 6 (no shadcn - its own color-variable layer conflicts with the theme.css token system + check-tokens CI guard); no client state lib yet (supabase-js session + React state suffice; revisit at T-006 if the onboarding panel needs shared state).

## T-005: proxy.ts naming vs middleware (2026-07-11)

- 2026-07-11 (T-005): Next.js 16 renamed the `middleware.ts` convention to `proxy.ts` (function renamed `middleware` -> `proxy`); `middleware.ts` still works but is deprecated. Wrote `frontend/src/proxy.ts` instead of the ticket's literal `middleware.ts` filename - same host-routing behavior, current convention. Deviation from ticket text, not from intent.

## T-005: Route group collision at / (2026-07-11)

- 2026-07-11 (T-005): route groups don't segment URLs, so `(customer)/page.tsx` and any future `(platform)`/`(tenant-admin)` root page would collide at `/`. proxy.ts 404s `/` for the platform/tenant-admin surfaces until those surfaces get real root pages - replace that guard with real routing then, don't just delete it (see proxy.ts comment).

## T-005: vitest addition (2026-07-11)

- 2026-07-11 (T-005): added vitest (frontend had no unit-test runner at all) to cover `lib/tenant.ts`'s `resolveHost` - `npm run test` is now a verified frontend command alongside lint/typecheck/check:tokens/build.

## T-005: asyncpg jsonb decoding (2026-07-11)

- 2026-07-11 (T-005): asyncpg returns `jsonb` columns as raw text, not decoded JSON - no codec was registered anywhere yet, so `app/api/public.py` does `json.loads()` on `tenant_config.brand` by hand. If a jsonb codec gets registered on the pool later, remove this ad hoc decode.

## T-006: LLMProvider abstraction creation (2026-07-11)

- 2026-07-11 (T-006): added `app/llm/provider.py` (an `LLMProvider.extract(system_prompt, user_input, schema) -> schema` abstract method) plus `app/llm/azure.py` (Azure OpenAI's `chat.completions.parse` with `response_format=<pydantic model>` for structured outputs - NOT under `.beta.` in openai>=2.45, that moved to the main namespace). Tests never touch Azure - they override the `get_llm_provider` FastAPI dependency with a fake. Live-verified in a browser that a real `AzureOpenAIProvider` construction fails cleanly (500, no crash) when AZURE_OPENAI_* are empty, confirming the wiring is correct even though full live extraction stays untestable until the founder provides real Azure credentials.

## T-006: Onboarding pricing spirit (2026-07-11)

- 2026-07-11 (T-006): onboarding's admin-supplied prices ("$120" -> cents) are extracted by the model as a plain float (the admin is the source of the number - the model transcribes, never invents), and the actual `dollars * 100` -> integer-cents arithmetic happens in plain Python (`app/api/onboarding.py:_cents`), never inside the model call. This keeps the deterministic-pricing hard rule's spirit intact even though onboarding (an admin configuring their own catalog) is a different case from the phase-2 quoting agent the rule is really aimed at.

## T-006: "mark tenant live" implementation choice (2026-07-11)

- 2026-07-11 (T-006): "mark tenant live" (the ticket's accept criteria) is implemented as `tenant_config.config->'onboarding'.completed = true`, NOT a `tenants.status` transition - checked the RLS policies first and found no policy lets `tenant_admin` (or `service`, post-signup) update `tenants.status` at all; only `platform_admin_all` can. Tenants already go 'active' at signup (T-004) and stay there. Changing that would need a new migration/policy nothing currently specifies - flagging here rather than inventing one.

## T-006: Frontend Supabase gating (2026-07-11)

- 2026-07-11 (T-006): frontend Supabase-gated pages (login, signup, and now onboarding) can't be driven end-to-end in a real browser locally - `NEXT_PUBLIC_SUPABASE_URL`/`ANON_KEY` are empty (no hosted Supabase project yet, same gap as T-004's memory entry), so `getSupabase()` throws and the page shows its own graceful error state instead of ever calling the backend. Verified the onboarding page renders correctly and fails gracefully; verified the actual backend flow live via direct `fetch` calls with a locally-minted JWT instead (bypassing the React Supabase wiring) - signup and GET /state both worked over real HTTP.

## T-007: apiFetch Content-Type fix (2026-07-11)

- 2026-07-11 (T-007): `frontend/src/lib/api.ts`'s `apiFetch` used to force `Content-Type: application/json` unconditionally - fixed it to skip that header when `init.body instanceof FormData`, otherwise multipart uploads (Knowledge, and anything similar later) would have the wrong Content-Type and fail server-side parsing. Backward compatible: every existing JSON caller is unaffected.

## T-007: Uploaded file path safety (2026-07-11)

- 2026-07-11 (T-007): uploaded files are renamed to `{document_id}{ext}` on disk under `{uploads_dir}/{tenant_id}/` - the admin's original filename is kept only as the `documents.filename` column value, never used to build a filesystem path, so a crafted filename can't path-traverse out of the tenant's directory.

## T-007: Async file I/O in knowledge.py (2026-07-11)

- 2026-07-11 (T-007): the blocking `mkdir`/`write_bytes` calls in `app/api/knowledge.py` are dispatched via `starlette.concurrency.run_in_threadpool` rather than called directly in the async handler - ruff's `ASYNC240` rule (enabled via the `ASYNC` select) has a blind spot when the target path is built with the `/` operator (`Path(...) / str(...) / f"..."`) rather than a bare `Path(...)` call, so it didn't actually catch this on its own; fixed anyway since blocking the event loop on file I/O is a real issue regardless of what the linter catches.

## T-007: Shared UI components created (2026-07-11)

- 2026-07-11 (T-007): added four new shared UI components while building the Knowledge page - `Select`, `Table` (generic columns/rows, loading/empty/error states), `EmptyState`, `Badge` (with `toneForStatus` mapping the exact status vocabulary from database.md section 6's Badge spec). All four are meant for reuse by Conversations/Escalations/Pricing (T-013+), not one-offs for this ticket.

## T-008: pgvector asyncpg registration (2026-07-11)

- 2026-07-11 (T-008): `app/core/db.py`'s `create_pool` now passes `init=register_vector` (pgvector's asyncpg helper) so every pooled connection can encode/decode `vector` columns as plain `list[float]`, never a hand-built `'[...]'::vector` string. `tests/conftest.py`'s `superuser_conn` fixture got the same registration - without it, reading `knowledge_chunks.embedding` back in a test returns a raw string, not a decoded `pgvector.Vector` (`.to_list()`/`.dimensions()`).

## T-008: Provider dependency extraction (2026-07-11)

- 2026-07-11 (T-008): `LLMProvider` grew `chat()` and `embed()` alongside T-006's `extract()`. Extracted `get_llm_provider` (the FastAPI dependency) out of `app/api/onboarding.py` into `app/llm/dependency.py` so `app/api/knowledge.py` could reuse the exact same override point in tests - overriding one callable now stubs the provider for every router at once. Added `tests/fakes.py`'s `BaseFakeProvider` (NotImplementedError stubs for all three methods) so each test file's fake only overrides the method it actually exercises, instead of every fake needing to grow a matching no-op each time the abstraction gains a method.

## T-008: Synchronous document processing scope call (2026-07-11)

- 2026-07-11 (T-008): document processing (chunk + embed) runs synchronously inside the upload request, not as a background job - no queue system exists at core scope and files are capped at 10MB, so this was a deliberate scope call, not an oversight. `documents.status` therefore goes pending -> processing -> ready/failed within the single upload response, not asynchronously after it returns.

## T-008: Chunk token estimation (2026-07-11)

- 2026-07-11 (T-008): "tokens" in the ~400-token chunk target are approximated as whitespace-separated words (no tokenizer dependency added) - documented directly in `chunker.py`'s docstring since it's a real approximation, not the actual BPE token count a model would see.

## T-008: catalog_items ingestion workaround (2026-07-11)

- 2026-07-11 (T-008): catalog_items ingestion (called from onboarding's confirm, T-006) writes into a synthetic `documents` row with `doc_type='catalog'`, `filename='catalog'` - the schema requires every `knowledge_chunks` row to reference a real `documents.id` (NOT NULL FK), so there's no way to attach catalog-item chunks without a backing document row; re-running finds and reuses the existing catalog document rather than creating a new one each time.

## T-009: Service-role seeding constraint (2026-07-11)

- 2026-07-11 (T-009): service-role seeding under `tenant_context(None, "service")` cannot write `documents`/`knowledge_chunks` at all (Shape A's `tenant_id = app_tenant_id()` is never true when `app_tenant_id()` is NULL under service context) - test seeding for those tables must go through `superuser_conn` instead (matches test_rls.py's existing pattern), never through the app pool's service role.

## T-009: LocalCrossEncoderReranker manual verification (2026-07-11)

- 2026-07-11 (T-009): `LocalCrossEncoderReranker` (the default `RERANKER=local` path, not gated behind a missing-credential env var like Azure/Cohere) was manually smoke-tested once outside pytest - `CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')` downloads from HuggingFace (~80MB, unauthenticated - a HF_TOKEN would raise the rate limit but isn't required) and correctly scored a screen-repair chunk far above an unrelated hours chunk for a screen-repair query. Not part of the automated suite (too slow/non-deterministic to run every test pass) - if this ever needs re-verifying, rerun `LocalCrossEncoderReranker().rerank(...)` directly, don't assume it still works untested.

## T-009: sentence-transformers dependency justification (2026-07-11)

- 2026-07-11 (T-009): added `sentence-transformers` (pulls in `torch`, ~100MB+ install) purely for the local reranker fallback - a real, heavy ML dependency, not something to add lightly again elsewhere without the same justification (no API-key-gated alternative exists for the default `RERANKER=local` path).

## T-010: seed_tenant1_phoneshop.py creation (2026-07-11)

- 2026-07-11 (T-010): created `backend/seeds/seed_tenant1_phoneshop.py` - not owned by any ticket's file list through T-009, but T-010's own accept criteria ("Tenant 1's seeded knowledge") can't be met without it, and database.md's seeds section already fully specifies its contents. Flagged this gap rather than silently working around it. Idempotent by wipe-and-recreate (not skip-if-exists) so eval reruns always start from the same known state. The dev DB now has tenant 'bytefix' seeded persistently (not scratch data) - future tickets (T-011 bare chat, phase 2 agents, phase 4 dashboards) can rely on it existing; re-run the seed script any time to reset it.

## T-010: Golden retrieval matching strategy (2026-07-11)

- 2026-07-11 (T-010): golden retrieval cases match "the right chunk" two ways depending on origin, not raw chunk ids (unstable across re-ingest, per the ticket's own instruction): prose/structured document chunks match on `{"source":..., "chunk_index":...}`; catalog_item chunks match on `{"catalog_item_name":...}` since `catalog_item_id` is a DB-generated UUID unknown at authoring time, but `chunk_catalog_item`'s content always starts with the item's name (stable, author-controlled) - see `evals/retrieval_eval.py`'s `is_relevant`.

## T-010: Stub embedder eval run (2026-07-11)

- 2026-07-11 (T-010): ran the real eval script against the seeded Tenant 1 with a stub (all-zero) embedder standing in for the missing Azure credentials - dense search degrades to noise with a constant embedding, but sparse FTS retrieval and the real local cross-encoder reranker don't depend on it at all, so the result (recall@3/@5 = 1.000, MRR = 0.911, nDCG@5 = 0.934, negative_avg_top_score = -10.567) is a genuine sparse+rerank-only baseline, not a fabricated number. Re-run once real Azure embeddings exist to get the true hybrid dense+sparse numbers - expect them to be equal or better, since dense would add signal rather than noise. eval_cases (50 rows) and an eval_runs row are already persisted from this run.

## T-011: CORS bug found and fixed (2026-07-11)

- 2026-07-11 (T-011): **found and fixed a real, previously-latent bug**: `app/main.py` had no CORS middleware at all. Every browser-based fetch from the frontend (port 3000) to the backend (port 8000) was silently broken by this - it just hadn't shown up yet because T-006/T-007's onboarding/knowledge pages fail earlier (at `getSupabase()`, no Supabase project) before ever reaching their `fetch` call. T-011's bare customer chat has no auth at all, so it was the first code path to actually execute a cross-origin fetch and immediately hit `net::ERR_FAILED`. Fixed with `CORSMiddleware` using `allow_origin_regex` (not a fixed origin list - every tenant gets its own subdomain, so the set of valid origins is unbounded and pattern-based: `^https?://([a-z0-9-]+\.)?(localhost|wren\.app)(:\d+)?$`), `allow_credentials=False` (bearer tokens only, no cookies). Regression-tested in `test_health.py` (preflight allowed for various tenant/platform/app origins, rejected for an unrelated origin). Any future ticket adding a new production domain (custom domains per tenant, if that ever lands) needs to update this regex.

## T-011: chat_stream abstractmethod pattern (2026-07-11)

- 2026-07-11 (T-011): `LLMProvider` grew `chat_stream(messages) -> AsyncIterator[str]` (real per-token streaming, distinct from the existing non-streaming `chat()` phase-2 agents will use for tool-calling reasoning) - declared as a plain `def` returning `AsyncIterator[str]`, not `async def`, which is the correct pattern for an abstractmethod whose concrete implementations are async generator functions (mixing `async def`+`yield` overrides under an `async def`-without-yield abstract stub creates a coroutine-vs-async-generator mismatch). `BaseFakeProvider`'s stub matches: `raise NotImplementedError` followed by an unreachable `yield` to keep it a real async generator function.

## T-011: Refusal threshold calibration note (2026-07-11)

- 2026-07-11 (T-011): the refusal threshold (`REFUSAL_SCORE_THRESHOLD = 0.0` in `app/api/chat.py`) is an uncalibrated guess based on the local cross-encoder's observed score range (roughly -11 to +8 in manual testing, T-009/T-010) - real calibration needs generation-eval data that doesn't exist until phase 3. Revisit once real eval numbers exist rather than trusting this constant blindly. (Superseded by the reranker normalization fix of 2026-07-23.)

## T-011: DB connection scope during streaming (2026-07-11)

- 2026-07-11 (T-011): the DB connection for `/api/chat` is only held for two short bursts (retrieval, and the final message persist) - explicitly NOT for the duration of the LLM stream itself, which can take several seconds. Holding a pooled connection across a slow external call would risk exhausting the pool under concurrent chat load; releasing it between bursts costs one extra `tenant_context` acquire but avoids that risk entirely.

## T-012: Knowledge node migration from chat.py (2026-07-11)

- 2026-07-11 (T-012): T-011's retrieval+prompt+streaming logic moved from `app/api/chat.py` into `app/agents/knowledge.py` as a real LangGraph node; `chat.py` now just resolves the tenant/conversation and translates the graph's custom-streamed events into SSE. Node dependencies (DB tenant scope, LLM provider, reranker) are threaded through via `context_schema=GraphContext` + `get_runtime(GraphContext).context` - NOT through state (state must stay plain/serializable) and NOT a single long-lived connection (knowledge.py opens its own short `tenant_context` for retrieval only, same rule T-011 established, still true as a graph node).

## T-012: Token streaming through LangGraph (2026-07-11)

- 2026-07-11 (T-012): token streaming out of a graph node uses `langgraph.config.get_stream_writer()` + `graph.astream(state, context=..., stream_mode="custom")` - the writer's dict is yielded verbatim by `astream`. This is the correct pattern for a custom (non-LangChain-ChatModel) LLM provider; LangGraph's automatic `on_chat_model_stream` events only fire for LangChain-integrated chat models, which this codebase deliberately doesn't use (own `LLMProvider` abstraction).

## T-012: build_graph override for testing (2026-07-11)

- 2026-07-11 (T-012): `build_graph()` takes an optional `supervisor_node` override (production always uses the real `supervisor.run` default) specifically so tests can force a route through the compiled graph without needing real intent-classification logic (T-013) - the module-level compiled singleton (`get_graph()`) can't be monkeypatched after the fact since `add_node` binds the function object at build time, not by name.

## T-012: ABC typing requirement for test doubles (2026-07-11)

- 2026-07-11 (T-012): `LLMProvider`-typed test doubles that are literal ABC subclasses (not just structurally matching) are required wherever a `GraphContext`/`Reranker` type-checks against the real ABC - passing a duck-typed class without inheriting `Reranker` fails mypy strict even though it'd work at runtime (see `tests/test_agent_graph.py`'s `FakeReranker(Reranker)`).

## T-013: Live-model routing verification deferred (2026-07-11)

- 2026-07-11 (T-013): `supervisor.py` now does real routing (one `extract()` call -> `RouteDecision{route, confidence, reason}`), confidence below `tenant_config.escalation_threshold` always overridden to `route="escalation"` - "low confidence never guesses" is enforced in code, not left to the prompt. **The ticket's "small live-model routing smoke set (~10 cases) run manually and noted" was NOT run** - AZURE_OPENAI_* is still empty (same gap since T-006). Routing unit tests cover the deterministic override logic thoroughly with a stubbed provider (8 tests, all 5 routes + threshold boundary + per-tenant threshold), but nothing here proves the model itself classifies utterances correctly across two fake verticals - that specific accept-criteria claim stays unverified until real credentials exist. Don't claim it's done in a status update without this caveat.

## T-013: get_runtime() only works inside graph execution (2026-07-11)

- 2026-07-11 (T-013): `get_runtime()` (langgraph) only works inside an actual node execution inside a running graph - it can't be called directly against a bare node function in a unit test. Tests that need to exercise a node using `get_runtime(GraphContext)` (supervisor.py, knowledge.py) must drive it through `build_graph().ainvoke(...)`/`.astream(...)`, not call `supervisor.run(state)` or `knowledge.run(state)` directly.

## T-014: Knowledge agent test gap filled (2026-07-11)

- 2026-07-11 (T-014): mostly already satisfied by T-012's design (the whole point of moving T-011's logic into a real node immediately, rather than leaving knowledge.py as a stub) - the only actual gap was the ticket's own "node test with stubbed retrieval/provider" line, added in `tests/test_knowledge_agent.py`. A reranker stub returning RRF-fused candidates unmodified doesn't need to force a score - RRF scores (`1/(k+rank)`) are always positive, so the refusal threshold check (`score > 0.0`) behaves correctly without any rescoring.

## T-015: metadata_kind retrieval filter (2026-07-11)

- 2026-07-11 (T-015): `app/retrieval/{dense,sparse,service}.py` grew an optional `metadata_kind` filter (default `None` = no filter, fully backward compatible) so the Recommendation Agent can scope retrieval to `metadata.kind='catalog_item'` chunks only - filtered at the SQL level (`metadata->>'kind' = $N`), not client-side after a broad top-20 fetch, since client-side filtering could starve the candidate pool before rerank ever sees enough real catalog items. Live-verified against the real seeded 'bytefix' catalog: all 5 returned results were genuine catalog items, zero prose leaked in.

## T-015: Recommendation price sourcing (2026-07-11)

- 2026-07-11 (T-015): recommendation.py re-fetches each recommended item's `name`/`description`/`price_cents` fresh from `catalog_items` by id (extracted from the chunk's `metadata.catalog_item_id`) rather than trusting the chunk's embedded text - the DB row is the one source of truth for price, matching the deterministic-pricing hard rule's spirit even though this isn't the phase-2 quoting engine itself (same reasoning as T-006's onboarding money-extraction call).

## T-015: Stub-specialist gain breaks existing tests (2026-07-11)

- 2026-07-11 (T-015): making recommendation.py a real node (not a stub) broke two existing test files that assumed it was a no-op pass-through: `test_agent_graph.py`'s topology tests (needed `pytest.mark.db` added, a real pool fixture, and a `FakeProvider` supporting both `extract()` shapes plus `embed()`) and none in test_chat_api.py (unaffected, since chat.py's supervisor always routes to knowledge). Whenever a stub specialist gains real logic, re-run the FULL suite, not just its own new tests - topology tests built against "stub == free lunch" assumptions are exactly what breaks silently otherwise.

## T-016: applies_to on pricing_rules deferred (2026-07-11)

- 2026-07-11 (T-016): `conditions.applies_to` on pricing_rules is deliberately NOT implemented - database.md only names the key in a comment and defines no semantics anywhere; flagged in the commit body per the flag-not-invent convention. `min_qty` is fully honored. If a future ticket needs applies_to, get the founder to specify what it means first.

## T-017: Quote persistence pattern (2026-07-11)

- 2026-07-11 (T-017): quoting.py persists the quotes row with status 'sent' at emit time (the customer sees the QuoteCard immediately - no buffering exists until T-021); the insert is the ONLY code path that writes quotes. The model-facing selection schema (QuoteSelectionResult) has a regression test asserting no money-shaped field name ever appears in it - keep that test in sync if the schema grows. The streamed explanation is instructed to reference the card and state no amounts; T-018's gate enforces it.

## T-017: OpenRouter free-model reality check (2026-07-11)

- 2026-07-11 (T-017): OpenRouter free-model reality check (live key): `google/gemini-2.0-flash-exp:free` no longer exists (404); `openai/gpt-oss-20b:free` ignores json_schema and returns plain text; `nvidia/nemotron-3-super-120b-a12b:free` returns unparseable output for structured calls; `qwen/qwen3-next-80b-a3b-instruct:free` (current backend/.env pick) is correct when reachable but hits upstream 429 congestion at times. Query live availability with the openrouter /models API filtered on supported_parameters containing 'structured_outputs' rather than trusting a hardcoded model list.

## T-018: Price gate redraft mechanism (2026-07-11)

- 2026-07-11 (T-018): the price gate re-prompt does NOT re-run the whole producing node - quoting/recommendation each have a redraft-only path (triggered by `price_violations` in state) that regenerates prose from state (engine_quote line items / DB-sourced selections) without re-selecting, re-computing, or persisting a second quotes row. A `redraft` stream event tells chat.py to reset its persisted-text accumulator and the customer surface to clear the rejected bubble text - interim UX until T-021 buffers everything behind inspection.

## T-018: AgentState NotRequired keys (2026-07-11)

- 2026-07-11 (T-018): AgentState grew NotRequired keys (price_violations, price_gate_attempted, price_gate_decision, escalation_reason) - NotRequired specifically so the many existing full-state constructors in tests/chat.py stay valid under mypy strict. Graph topology changed: recommendation/quoting now route through price_gate before inspection (test_agent_graph.py's order assertions were updated - the exact "stub gains real logic" trap T-015's entry warned about).

## T-019: Order lookup template (2026-07-11)

- 2026-07-11 (T-019): the seed part of this ticket was already done by T-010's seed_tenant1_phoneshop.py (20 orders, 'repair'/'order' kinds, tenant-vocabulary statuses) - net-new work was `app/agents/tools.py::lookup_order_or_ticket` (typed found/not-found result, never an exception) and the real `order_status.py` node. The draft response is fully deterministic (a template filled from the DB row) - no generation call at all - since every fact needed is already in the row; only the ref_code extraction itself needs the model (a regex would hardcode a code-format assumption, violating the domain-agnostic rule).

## T-019: Blank customer_ref fix (Fable review finding) (2026-07-11)

- 2026-07-11 (T-019, Fable review finding, fixed): `lookup_order_or_ticket`'s `customer_ref` filter now treats a blank/whitespace-only string the same as `None` (no filter) - a structured-output model is prone to returning `""` instead of omitting an optional field, and filtering on a literal empty string would spuriously not-find a real order. Regression test: `test_blank_customer_ref_is_treated_as_not_given`.

## T-020: Escalation concurrent-write dedupe (Fable review finding) (2026-07-12)

- 2026-07-12 (T-020, Fable review finding, fixed): the terminal-escalation guarantee was check-then-act, not DB-enforced - two concurrent turns on the same conversation could both read `status='open'` and both escalate, creating duplicate `escalations` rows. Fixed with `migrations/0011_escalations_dedupe.sql` (partial unique index `(tenant_id, conversation_id) where status='open'`) + `ON CONFLICT ... DO NOTHING` on the insert + `... and status <> 'escalated'` on the conditional update. Regression test: `test_concurrent_escalations_on_same_conversation_do_not_duplicate` (two `asyncio.gather`'d graph runs, asserts exactly one open row).

## T-020: Live credentials confirmed end-to-end (2026-07-12)

- 2026-07-12 (T-020, live-credentials confirmed): `backend/.env`'s OpenRouter key is real and live LLM calls now genuinely work end-to-end (routing -> escalation -> DB write -> SSE -> banner) - this is a change from every earlier ticket's "clean 500, no crash" pattern. However the free model (`qwen/qwen3-next-80b-a3b-instruct:free`) hit an upstream 429 rate-limit (Venice provider) during this exact verification; when live-testing hits this, either wait out the `Retry-After` window and retry through the UI, or fall back to seeding/flipping DB state directly to isolate frontend-only behavior from LLM-availability flakiness (both are legitimate, not a code bug).

## T-021: Inspection buffering design (2026-07-12)

- 2026-07-12 (T-021): `inspection.py` is the final gate before a customer sees a draft - one combined structured `extract()` call covers grounding/policy/injection/prompt_leak (every `CheckVerdict` field defaults to `passed=True`, so any pre-T-021 test fake that doesn't know this schema still validates to all-pass instead of erroring - this is why only `test_quoting_agent.py` needed a fix, out of ~6 existing test files that now incidentally exercise this node). price-provenance re-assert is deterministic and scoped to recommendation/quoting only (flagged: a knowledge answer quoting a real KB price is a grounding question, not a price-provenance one). Specialists mark `draft_deterministic` on template/refusal returns so Inspection skips every check for them. `/api/chat` now buffers every graph event and only flushes on Inspection's non-retry decision - nothing streams to the customer until it passes (an accepted latency tradeoff per the ticket).

## T-021: Fable review findings fixed (2026-07-12)

- 2026-07-12 (T-021, Fable review findings, fixed): (1) a retry discard was dropping `citations`/`quote` events that no redraft path ever re-emits - a redrafted quote would silently lose its QuoteCard. Fixed: retry discards now keep structured events, only drop `token`/`refusal`. (2) the escalation-node revisit through Inspection was overwriting the actual failing verdicts with an all-pass placeholder in `messages.metadata` - inverting the trace record for the one message that matters most. Fixed: carry forward `state["inspection"]` on the already-escalated short-circuit. (3) `state.get("price_violations") or state.get("inspection_violations")` in quoting.py/recommendation.py could feed a redraft stale violations from the OTHER gate's earlier pass if both gates fire across a run - fixed by clearing both keys on every redraft-consuming return. (4) quoting's provenance text for the grounding check was near-empty (`selections` has no name/description) - fixed by using `engine_quote["line_items"]` instead. All four have regression tests in `test_inspection.py`.

## T-021: Deploy gotcha - dev DB out of sync with migrations (2026-07-12)

- 2026-07-12 (T-021, deploy gotcha found live): after adding `migrations/0011` (T-020) and `migrations/0012` (T-021), the persistent dev database was still missing BOTH - the `migrated_db` pytest fixture applies every migration fresh per test run, so the test suite passing green gives zero signal about whether the actual dev DB (used by `uv run uvicorn`) has been migrated. Live browser verification hit `UndefinedColumnError: column "metadata" of relation "messages" does not exist` until `uv run python -m app.core.migrate` was run by hand. Always run the migrator against the real dev DB after adding a migration, not just trust the test suite.

## T-022: Leakage eval design details (2026-07-12)

- 2026-07-12 (T-022, phase 2 complete): `seeds/seed_leakage_pair.py` plants a unique nonsense token per surface (knowledge chunk, catalog item + matching catalog-item-kind chunk, pricing rule, order) in two throwaway tenants, via raw inserts (zero embeddings, no ingestion pipeline) - a leakage probe only needs the sparse/FTS channel, and this eval must never depend on a model download to run. `evals/leakage_eval.py` runs structural checks (retrieval both surfaces, `lookup_order_or_ticket`, direct table reads) in both directions, each paired with a positive control (attacker queries for their OWN secret) so a probe finding nothing can't vacuously pass; writes one `eval_runs` row per direction (`run_type='leakage'`). `tests/test_leakage.py` adds an httpx-level full-conversation test using a "parrot" fake provider (`chat_stream` echoes its own system prompt, which includes retrieved context) so any cross-tenant leak into a prompt would surface in the response verbatim, plus a persisted-row sweep (excluding customer-authored message content, which can legitimately quote a secret the attacker already typed - that's not the system disclosing it).

## T-022: Fable review finding - app-side predicate masking RLS (2026-07-12)

- 2026-07-12 (T-022, Fable review finding, fixed): `_check_direct_tables`' negative checks originally carried an app-side `tenant_id = $1` predicate identical to the one being tested - with `where tenant_id = attacker_id and label ilike '%secret%'`, zero rows is guaranteed by the predicate alone regardless of whether RLS works at all, so these three checks (out of 12 per direction) had no teeth. Fixed by dropping the predicate entirely and relying only on RLS under the attacker's `tenant_context` - this is deliberately the one place in the suite where scoping is NOT reinforced by an app-side predicate, since the retrieval/order probes already prove those real paths (which correctly do carry one as defense-in-depth).

## T-022: RLS-weakening proof performed (2026-07-12)

- 2026-07-12 (T-022, RLS-weakening proof performed - the ticket's own accept criterion): in a scratch branch (`scratch/t022-rls-weaken-proof`, based off T-021's commit, never merged/pushed), changed `pricing_rules`' `tenant_isolation` policy in `migrations/0006_commerce.sql` to `using (true) with check (true)`. `test_structural_leakage_checks_all_pass` and `test_leakage_eval_writes_run_and_gates_at_100` correctly went red (11/12 pass rate, gate failure) - confirming the suite has teeth. Branch deleted afterward, real policy restored on the working branch via `git checkout -- <file>` (the edit was never committed). If this ever needs re-proving (e.g. after a major RLS refactor), repeat this exact recipe rather than assuming past passing tests still mean anything.

## T-022: Scope note - quoting/recommendation not directly driven in leakage chat (2026-07-12)

- 2026-07-12 (T-022, scope note, Fable-flagged): the chat-conversation-level leakage probe only drives the `knowledge` route (the fake provider always forces that route) - `recommendation.py`/`quoting.py` are not directly exercised through a full chat turn, only their underlying `retrieve()`/pricing-table reads (already covered by the structural checks). This is defensible since neither node adds tenant-scoping logic beyond what's already probed, but it means "a quoting conversation leaks nothing end-to-end" is proven indirectly, not directly driven. Revisit if a future refactor adds tenant-scoped logic inside recommendation.py/quoting.py itself rather than delegating entirely to retrieve()/the pricing engine.

## T-023: RAGAS-equivalent without ragas package (2026-07-12)

- 2026-07-12 (T-023, phase 3 start): `evals/generation_eval.py` implements RAGAS-equivalent metrics (faithfulness, answer_relevancy) plus this ticket's own citation-faithfulness addition (per-citation: does the SPECIFIC chunk cited at bracket index n support the SPECIFIC sentence it's attached to) using this project's own `LLMProvider.extract()` structured-output pattern - deliberately NOT the real `ragas` package, since real ragas metrics are built around LangChain-wrapped LLMs and this codebase has a standing decision (T-012) to never use LangChain chat-model wrappers. Drives the real graph via `build_graph(supervisor_node=<forced to "knowledge">)`, never `knowledge.run()` directly (get_runtime() constraint, T-013). Unlike T-022's leakage test, this eval genuinely needs a real LLM to produce meaningful numbers and is NOT CI-deterministic by nature - that's an accepted, documented tradeoff, not a gap, since it measures quality rather than proving a structural security invariant.

## T-023: Fable review findings fixed (2026-07-12)

- 2026-07-12 (T-023, Fable review findings, fixed): (1) the eval used a literal placeholder `conversation_id="eval"` in graph state - harmless until a case's draft failed Inspection twice and routed to escalation.py, which does `UUID(state["conversation_id"])` and crashes on a non-UUID string, aborting the whole run mid-eval after burning every prior LLM call on earlier cases. Fixed by inserting one real `conversations` row per case. (2) an escalation/refusal handoff message (no verifiable claims, no citations) was scored as a perfect 1.0 on both gated metrics via the empty-list defaults - inverting exactly the case that should fail hardest. Fixed by treating `{REFUSAL_MESSAGE, inspection.ESCALATION_MESSAGE, escalation.HANDOFF_MESSAGE}` as non-answers scored 0.0/0.0/0.0 on a positive case. (3) the LLM judge returning fewer verdicts than claims/citations submitted silently shrank the denominator toward a passing score (zero verdicts -> faithfulness 1.0) - fixed by padding missing verdicts as `supported=False` (fail closed) rather than trusting the judge's count.

## T-023: Flagged citation/sentence edge cases (2026-07-12)

- 2026-07-12 (T-023, flagged for founder decision, not fixed): (a) `extract_cited_sentences`' regex sentence-splitter can mis-bind a citation marker placed AFTER the sentence-ending period (e.g. "Repairs take 3 days. [2]") to the wrong fragment - always deflates the score (spurious gate failure), never masks a real one, so left as a documented edge case rather than growing a full sentence segmenter. (b) the dataset's `reference_facts`/`expected_sources` fields are loaded and persisted into `eval_cases` but never actually scored against - faithfulness only checks claims against *retrieved* context, not against the authored reference facts. Arguably a stronger check (LLM-judged grounding vs. a fixed string-diff) but there's currently no answer-*correctness* metric independent of what retrieval happened to return. Revisit if real-LLM runs show retrieval quietly compensating for wrong answers.

## T-024: Judge calibration blocked on founder labels (2026-07-12)

- 2026-07-12 (T-024, ticket marked `[!]` blocked, not `[x]` done - genuinely unresolvable without the founder): the ticket's own text requires ~30 cases hand-labeled by the founder BEFORE the LLM judge (from T-023) ever sees them, specifically to measure whether the automated judge agrees with real human judgment. No founder was available in this autonomous session, and an agent generating its own "ground truth" via another LLM call would be circular (self-consistency between two model calls, not agreement with a human) - so the actual measurement T-024 wants cannot be produced right now. Resolution: shipped the full working pipeline (`evals/judge_calibration.py` - agreement %, Cohen's kappa per-type and pooled, eval_runs write, `--gate`) and a real 29-case dataset (`evals/datasets/judge_calibration.jsonl`, each row real content from Tenant 1's seeded docs with ~25-28% deliberately corrupted claims/citations for signal), but every row carries `label_source: "agent_placeholder"` and `--gate` structurally fails whenever `founder_labeled_fraction < 1.0` regardless of the agreement score - so a run against placeholder labels can never silently read as a passing (or even a real) calibration. To close this ticket: `uv run python -m evals.judge_calibration --print-blind`, hand-label fresh (don't peek at the placeholder verdicts first, to avoid anchoring), flip each row's `label_source` to `"founder"`, then `--gate` for real.

## T-024: Frozen claims + duplicate citation label bug (2026-07-12)

- 2026-07-12 (T-024): claim/citation units are FROZEN in the calibration dataset rather than re-extracted at judge time - `judge_claims()` was split out of `score_faithfulness()` in generation_eval.py specifically so the calibration script can hand the judge a fixed claim list (extraction is itself an LLM call and is nondeterministic; re-extracting would silently break positional alignment with hand-labels on every run). Citations need no such split since `extract_cited_sentences()` is a pure regex function - but a real bug bit this anyway: a single sentence carrying the same `[n]` marker twice (e.g. "X is a [1], and Y is b [1].") is ONE judged unit (`score_citation_faithfulness` pairs by (sentence, chunk), not by individual marker occurrence), so labeling the two marker positions `[true, false]` for per-clause intent is incoherent - both label slots map to the identical judge input, capping agreement at 50% on that row regardless of the judge's actual quality. Fixed 5 dataset rows by splitting into two sentences; `load_cases()` now rejects any future row with conflicting labels on an identical (sentence, index) unit. Lesson: when authoring per-citation-position labels, always check whether two markers land in the same sentence before assuming they're independent judged units.

## T-025: Trajectory dataset coupling (2026-07-12)

- 2026-07-12 (T-025): the trajectory dataset (`evals/datasets/tenant1_trajectory.jsonl`) is coupled to `seeds/seed_tenant1_phoneshop.py` in three deliberate ways: order cases pin `ref_code` + `status` to the seed's deterministic `REPAIR_STATUSES[i % 5]` / `ORDER_STATUSES[i % 3]` assignment (change the seed loop and the dataset silently rots - the ticket-level tests only check structure, not seed agreement); selections are keyed by pricing-rule `code` / catalog `item_name` (never catalog UUIDs, which regenerate every reseed); `expected_route` is an any-of matcher because mixed-intent turns have more than one defensible first route. Gate-driven escalations (price_gate/inspection double-failure) are deliberately NOT in the dataset - they need rigged fake providers and are already covered by T-018/T-021's unit tests; only directly-triggerable escalations (explicit human request, anger, legal threat) are cases here. T-026's scorer must import `TrajectoryCase`/`load_cases` from `evals/trajectory_dataset.py`, not re-author the schema.

## T-026: Trajectory scorer architecture (2026-07-12)

- 2026-07-12 (T-026): the scorer captures node-by-node trajectories via `graph.astream(stream_mode="updates")` (one event per node, `{node: update}`) - NOT app instrumentation. Two state keys were added purely so external scoring can see decisions that were previously trapped inside nodes: `supervisor.py` now returns `route_reason` (the model's own stated justification, judged by an LLM reasoning-quality grade) and `order_status.py` returns a structured `lookup` dict (ref_code/found/status/kind). `cost_usd` per case sums `cost_logs` for the conversation - real query, but honest 0.0 until T-030 wires cost accounting. `normalize_selections()` flattens quoting's engine-quote line items and recommendation's DB-refetched selections into one shape so one matcher covers both money routes. Min-steps table (`_MIN_STEPS_BY_ROUTE`) encodes graph topology: knowledge/order_status/escalation = 3 (supervisor+specialist+inspection), recommendation/quoting = 4 (+price_gate).

## T-027: Injection eval live result (2026-07-12)

- 2026-07-12 (injection eval live result): the T-027 adversarial set scored 29/30 (96.7%) against the seeded probe tenant with the gemma-4 free model - well above the 80% target. The single failure was `indirect-chunk-canary-02` (a poisoned turnaround chunk got the model to append the canary and Inspection's weak-model injection judge missed it). Poisoned-chunk (indirect_chunk) category was 5/6; direct and indirect_tool were 100%. This is an honest documented number for the T-038 eval report, NOT a bug to chase to 100% - the layered defense works, the residual leak is a real limitation of a free-tier judge.

## T-028: Limits architecture (2026-07-12)

- 2026-07-12 (T-028): all three limit protections live in `app/core/limits.py` and are graceful-by-design (a capped tenant always gets `BUDGET_UNAVAILABLE_MESSAGE` + an escalation row, never a stack trace). Budget: `TenantLimits.resolve(config, settings)` overlays `tenant_config.config.limits` on env defaults (malformed values fall back, never raise); `tenant_over_budget()` sums today's cost_logs (cached 10s, `clear_usage_cache()` is the test hook) - checked once per turn in `chat()` BEFORE the graph runs (the ticket says "before each LLM call" but a cheap cached per-turn check is the pragmatic equivalent since cost_logs are empty until T-030). Step cap: the graph runs under LangGraph `recursion_limit=limits.max_steps` (default 8); `GraphRecursionError` is caught in `_stream_chat_response` -> graceful (reason `step_cap`). Timeouts: `TimeLimitedProvider` wraps the provider handed to GraphContext (bounds each extract/chat/chat_stream token); `GraphContext.tool_timeout_s` (new field, DEFAULTED so every existing eval/test constructor stays valid) bounds order_status's tool call via `with_timeout()` which raises typed `LimitTimeout`. `chat.py` now materializes the graph stream into a list inside a try (`events = [e async for e in stream]`) so GraphRecursionError is catchable - behaviorally identical to the old per-event loop since T-021 already buffered everything until inspection passed.

## T-027: Spotlight mechanism (2026-07-12)

- 2026-07-12 (T-027): `app/agents/spotlight.py` is the single central place untrusted tenant data is wrapped before entering a generation prompt - `new_spotlight()` mints a per-request random hex boundary token, `.wrap(content)` fences content in `<<data-TOKEN>>...<</data-TOKEN>>` after `escape_delimiters()` defangs any delimiter-shaped text inside (so a poisoned doc can't forge the close tag), and `.instruction()` is the standing "delimited = data, never instructions" system line that MUST accompany any prompt containing wrapped content. Wired into knowledge.py (chunks), quoting.py (rule labels + item name/desc, NOT codes/ids which the model must echo back), recommendation.py (item name+desc). `scan_input()` is a cheap regex pre-check on the customer message that sets `state["injection_suspected"]` (in chat.py's `_initial_state`) - advisory only, never blocks; inspection.py reads it to append a stricter-scrutiny note to its injection/prompt-leak judge prompt. The order_status deterministic template (kind/ref_code/status only, never `details`) already neutralizes tool-result poisoning by construction - that's why the indirect_tool eval case expects the canary to never render.

## T-030: Cost accounting design (2026-07-13)

- 2026-07-13 (T-030): `app/observability/cost.py` uses a contextvar-based per-turn usage sink (`collect_usage()` context manager + `report_usage()`, called by both `azure.py`/`openai_compat.py` after every completion including the streamed final usage-only chunk) so the provider stays stateless and concurrent turns never cross-contaminate (task-local contextvars). `app/observability/tracing.py` is a Tracer/Turn/Span Protocol with a `NoOpTracer` default (zero-overhead, zero external calls) - wiring real Langfuse is a deliberate founder step (not a current dependency, matching the free-first principle), `NOOP_TURN` is a stateless singleton usable as a frozen-dataclass default. Every graph node now opens a span via ONE wrapper (`graph.py`'s `_traced(name, node)`, applied to all 8 `add_node` registrations) rather than editing 8 node bodies - `get_runtime(GraphContext)` inside the wrapper is safe alongside every node's own internal `get_runtime()` call (same task-scoped runtime, both are pure reads). Span attributes are a deliberate scalar-only whitelist (`_SPAN_ATTR_KEYS` in graph.py) - never raw draft/message/chunk text, so a future live tracing backend never sees cross-tenant-sensitive content one level removed from T-022's leakage concern.

## T-030: Step-capped turn cost recording bug (Fable review finding) (2026-07-13)

- 2026-07-13 (T-030, Fable review finding, fixed): a turn that tripped T-028's step cap (`GraphRecursionError`) made real LLM calls before overflowing - by definition MORE calls than a normal turn - but the exception handler returned without ever calling `record_costs()`, so exactly the highest-usage, most-pathological turns were invisible to `tenant_over_budget()`'s daily sum. Fixed by recording `usages` (already collected via `collect_usage()`, guaranteed bound by the time `GraphRecursionError` can fire) inside the except branch too. Regression test: `test_step_capped_turn_still_records_its_llm_costs` in `test_limits_api.py`.

## T-030: route_reason in span attributes flagged (2026-07-13)

- 2026-07-13 (T-030, flagged, not fixed): `route_reason` (the supervisor's own free-text justification for its route pick, added in T-026) is included in the span-attribute whitelist, but it's the one field there that can carry customer-message-derived text (paraphrasing what they asked about) rather than a fixed enum/count - every other whitelisted key is a literal or a derived number. Harmless today (no-op backend), but worth a conscious keep-or-drop call once Langfuse is actually wired.

## T-031: cost_logs message attribution (2026-07-13)

- 2026-07-13 (T-031): `cost_logs` has no `message_id` column (only `conversation_id`) - `conversations.py`'s detail endpoint attributes each row to the assistant message immediately preceding it via a lateral join on `created_at` (`cl.created_at >= m.created_at and < next-message.created_at`). This is exact, not approximate, because every code path in chat.py inserts the assistant message and then calls `record_costs()` in the same transaction, so no two writes can straddle the window - the one gap (concurrent turns on the same `conversation_id`, which can't happen in this codebase's chat flow) is called out in the module docstring rather than silently assumed. A real `message_id` column is the durable fix if that assumption ever changes; not built here since the ticket didn't call for a migration.

## T-031: Escalation polling design (2026-07-13)

- 2026-07-13 (T-031): no push/websocket mechanism exists anywhere in this codebase, so a resolved escalation's `human_agent` reply reaches an already-open customer tab via a new public, unauthenticated `GET /api/chat/{conversation_id}/messages?slug=&after=&limit=` endpoint (tenant-scoped by slug, same trust model as the rest of the login-free customer surface: knowing the UUID is the capability). `CustomerChat.tsx` polls it every 5s using the `after` cursor, but ONLY while `escalated && conversationId` - never on a normal open conversation, to keep this off the backend's back by default. Escalation resolve deliberately leaves `conversations.status` at `'escalated'` (T-020's terminal design was kept as-is; flagged, not silently changed) - a resolved escalation still shows as "escalated" in the Conversations list, which is expected today, not a bug.

## T-036: CI/CD split (2026-07-13)

- 2026-07-13 (CI/CD, T-036 skeleton): split GitHub Actions into two flows per founder request - `ci.yml` (unchanged, the development gate on every PR/push) and a new `deploy.yml` (production pipeline, `workflow_run` on CI completing on `main`, pinning `actions/checkout` to `github.event.workflow_run.head_sha` so a commit landing after CI finishes can't sneak into the deployed image). Every AWS/Vercel step is gated behind a `check-readiness` job testing whether the relevant secrets exist (same pattern as `eval-gate`'s `LLM_API_KEY` check) - it no-ops with an `::notice::` instead of failing, since T-035 (Terraform, not started) hasn't provisioned ECR/ECS/ALB yet and no secrets are set. Created the "production" GitHub environment now (empty, no protection rules) so the founder can attach required reviewers once real infra exists. Added `backend/Dockerfile` (multi-stage uv build) + `backend/.dockerignore` (without it a local `docker build` would bake real `.env` secrets and the host's macOS `.venv` into the image - caught by review, not written correctly the first time) and a `terraform fmt/validate` job in ci.yml against the `infra/main.tf` stub.

## T-036: No staging environment (architecture note) (2026-07-13)

- 2026-07-13 (architecture note, not a gap): docs/source/architecture.md section 9 specifies exactly ONE backend deployment/environment (single ECS service, single DB) - there is no separate "staging AWS" tier in the design. Interpreted the founder's "development and production CI/CD flows" ask as: development = the existing CI gate (lint/test on every push/PR), production = the new deploy.yml (gated on main, post-CI). Did not invent a second AWS environment (real cost + scope creep beyond what's specced) - flag to the founder if a genuine staging tier is wanted later.

## Dev tooling: .claude/launch.json port management (2026-07-13)

- 2026-07-13 (dev tooling): `.claude/launch.json` now uses `autoPort: true` + `${PORT:-default}` substitution for both backend (uvicorn `--port`) and frontend (`next dev -p`) - a prior hardcoded-port config collided whenever another session's dev server was already running against the same repo directory. Note: Next.js's dev server refuses to run twice against the same `.next` directory even on a different port (a directory-level lock, not just a port conflict) - if another session's frontend dev server is already up, you can't start a second one from the same checkout; either reuse the existing one (the Browser pane CAN reach a server it didn't start itself, e.g. `http://localhost:3000`, despite an early-session warning implying otherwise) or work from an isolated git worktree. When reusing another session's frontend server, remember it read `NEXT_PUBLIC_API_URL` at its own startup - writing a fresh `frontend/.env.local` takes effect on Next's live env-reload without a full restart (observed working under Next 16/Turbopack), so pointing it at your own freshly-started backend port is safe.

## T-032: Brand accent AA-contrast verification method (2026-07-13)

- 2026-07-13 (T-032): the seeded bytefix tenant's brand accent (`#D97757`) is architecturally identical to `--clay-500`, the platform's own default light-mode accent (both come from the same "one confident terracotta accent" design intent) - so a live check of `getComputedStyle(...).getPropertyValue('--color-accent')` cannot distinguish "override applied" from "fallback used" for this tenant. Proved the AA-contrast-fallback path actually fires by checking the DOM directly for the injected `<style>` override tag instead (absent, as expected, since `#D97757` fails the 4.5:1 AA gate against white per `brand.test.ts`) - if this ever needs re-verifying, check for the style tag, not the resolved CSS variable value.

## T-032: Fable review fixes (2026-07-13)

- 2026-07-13 (T-032, Fable review findings, fixed): (1) the "Answering..." `aria-live="polite"` hint was conditionally mounted (`{busy ? <p aria-live=...> : null}`) - screen readers generally only announce content *changing inside* an already-present live region, not one that appears/disappears with its content, so the hint likely went silently unannounced. Fixed by always rendering the `<p>` and toggling only its text. (2) `TenantResolution.customer` and `customerSurfaceConfig()` didn't tolerate a missing `customer` key (pre-T-032 backend still deployed, frontend rolled out first) - would throw and 500 the whole customer page. Made `customer` optional on the interface and `customerSurfaceConfig` default it to `{}`, so frontend/backend deploy order is safe either way. (3) starter chips keyed by `question` text - a tenant configuring two identical starter questions would produce duplicate React keys; keyed by index instead. (4) abort detection required `instanceof DOMException`; loosened to `instanceof Error && err.name === "AbortError"` since not every runtime surfaces fetch aborts as a DOMException.

## T-035: Lean production Docker image (local-ml group) (2026-07-13)

- See `backend/pyproject.toml` `[dependency-groups]` section for the architecture; see `backend/Dockerfile` for the `--no-group local-ml` exclusion.

## Demo: GoTrue compose-native setup details (2026-07-13)

- See `docker-compose.yml` auth service comments and `scripts/demo.sh` for the full GoTrue compose-native setup with all four live-discovered gotchas (auth schema creation, search_path collision, required env vars, nginx resolver/runtime URL).

## Demo: env-file ordering (duplicate keys) (2026-07-13)

- 2026-07-13 (demo seed, env-file duplicate keys): pydantic-settings (python-dotenv) takes the FIRST occurrence of a duplicate key in a `.env` file. `backend/.env` copied from `.env.example` has `SUPABASE_URL=` (empty); appending `SUPABASE_URL=http://localhost:54321` as a second line does NOT override the empty first one - `settings.supabase_url` stays `''`. `scripts/demo.sh`'s `ensure_env_key` replaces an existing empty value IN PLACE (awk, not append) for exactly this reason. Never append a duplicate KEY= to an env file expecting it to win.

## Demo: Change-me password and JWT secret handling (2026-07-13)

- 2026-07-13 (demo seed, the `change-me` WREN_APP_DB_PASSWORD and JWT secret): the migrate runner fails closed on the `.env.example` `change-me` placeholder (and on empty/unsafe values - 8+ chars, no quotes/backslashes/dollar signs). `scripts/demo.sh` generates a real password (`wren` + `openssl rand -hex 12`) only when creating a fresh `backend/.env`; it never overwrites an existing one. `SUPABASE_JWT_SECRET` is generated (`openssl rand -hex 32`) only if absent. Both are append-only/replace-empty - the script never clobbers a developer's real values.

## Demo: Persistent dev DB has leftover eval probe tenants (2026-07-13)

- 2026-07-13 (demo seed, persistent dev DB has leftover eval probe tenants): `seeds/seed_demo` only wipes bytefix + lumident (by slug). The platform tenants table (`GET /api/platform/tenants`) also shows `leakpair-a`, `leakpair-b`, `injection-probe` - throwaway tenants from T-022/T-027 eval self-seeding that persist in the dev DB volume. They're harmless for the demo (the walkthrough focuses on bytefix + lumident) and wiping them would break eval reruns (leakage/injection evals self-seed their own tenants). Don't add a "wipe all non-demo tenants" step to the seed.

## Demo: Commit hygiene convention (2026-07-13)

- 2026-07-13 (commit hygiene): the demo work is NOT a phase ticket (no T-XXX number) - it's a demo-readiness plan that cuts across the existing stack without touching `app/**`, `frontend/src/app/admin-surface/**`, `proxy.ts`, or `infra/**` (acceptance criterion #6). Committed as three subject-prefixed `demo:` commits, not the `T-XXX:` ticket style, to keep it distinguishable from phase work.

## Marketing landing page (2026-07-18)

- 2026-07-18 (marketing landing page, founder-requested, unticketed): new "marketing" surface at the bare apex/www host. `resolveHost` now maps bare `localhost`/`wren.app` (and any `www.` form) to surface `marketing` (previously null -> 404; and `www.wren.app` previously resolved as customer slug "www" - a real latent bug, now fixed and pinned by tests). `proxy.ts` rewrites the marketing surface into `app/marketing-surface/` - same segment+rewrite pattern as `admin-surface/`, because `(customer)/page.tsx` owns `/`. Cross-surface links are built by `surfaceUrl()` in `lib/tenant.ts` (pure inverse of resolveHost: preserves base domain + port, strips any existing surface subdomain, http only for localhost) - never hardcode a subdomain URL in a component. `BASE_HOSTS` in tenant.ts mirrors the backend CORS regex's domain list (app/main.py); a future production base domain must be added in BOTH places. Landing e2e lives in `frontend/e2e/landing.spec.ts`; the demo-chat CTA targets the persistent `bytefix` seed tenant.

## LuxeStay visual rebrand (2026-07-20)

- 2026-07-20 (LuxeStay visual rebrand, founder-requested, unticketed - commits cc30fc5/86b03d9/cb9905c/5d2bb7d/27537d7): full move to a Material 3 style tonal system. Layer 1 primitives are now **tonal role ramps** (`--primary-*` crimson, `--secondary-*` teal, `--tertiary-*` green, `--error-*`, `--neutral-*`, `--neutral-variant-*`), each a set of M3 tone steps (higher number = lighter) - why: dark mode becomes a systematic derivation (Layer 2 dark just picks a lighter tone of the same ramp) instead of a hand-tuned parallel palette, and WCAG AA can be verified pair-by-pair against the ramp. The old sand/clay/ink/green/red/blue ramps were deleted (nothing outside theme.css referenced Layer 1 names).

## Rebrand: Dark blocks kept duplicated ON PURPOSE (2026-07-20)

- 2026-07-20 (rebrand - dark blocks kept duplicated ON PURPOSE): theme.css has the dark Layer 2 written twice, in `:root[data-theme="dark"]` AND the `prefers-color-scheme: dark` media query, kept literally identical (header comment says "edit both or neither"). NOT deduplicated via CSS `light-dark()` - why: `src/lib/brand.ts` scopes a tenant's runtime accent override to light mode only and its selector strategy is coupled to this two-block structure; collapsing to `light-dark()` (or a single shared block) would change how the override cascades and could silently break dark mode for one entry path but not the other. If you edit one dark block, edit the other identically.

## Rebrand: Vendored SVG icons (2026-07-20)

- 2026-07-20 (rebrand - icons are vendored SVG, not an icon font): `frontend/src/components/ui/Icon.tsx` inlines ~20 Material Symbols Outlined SVG paths (Apache 2.0, attribution in header, `viewBox="0 -960 960 960"`, `fill="currentColor"`) - why: chosen over a webfont for bundle size (only the ~20 glyphs actually used ship), no flash-of-ligature-text on load, license-clean, and guard-safe (currentColor means no color literal ever appears, so `check:tokens` stays happy). `filled` variants exist for the 7 nav icons; `aria-hidden` by default.

## Rebrand: Type scale + radii as churn-free lever (2026-07-20)

- 2026-07-20 (rebrand - type scale + radii were the churn-free lever): re-pointing the `--text-*` size/leading tokens (body 17->16, added body-lg 18/28, display 34/42 -> 48/56, title-1 28/36 -> 32/40, tracking on display/title-1/caption) and the radius scale (6/10/14 -> 8/12/16) carried almost the entire visual rebrand WITHOUT touching component code - why: components only ever reference the semantic `text-*`/`rounded-*` utility names, never raw values, so the token system did exactly what it was built for. Weight 700+ is now reserved for hero/marketing display use only.

## Rebrand: Console sidebar not collapsing (KNOWN GAP) (2026-07-20)

- 2026-07-20 (KNOWN GAP, flagged for a future ticket - NOT fixed in the rebrand): the shared console shell's left sidebar (tenant-admin + platform surfaces, built in T-031/T-033, structurally untouched by the rebrand) does not collapse into a mobile drawer below ~375px - content squeezes/clips at narrow viewports on every console page. Pre-existing, not a rebrand regression; newly visible because chunk 3's `dashboards.spec.ts` added a 375px overflow check (which passes, since content clips rather than overflowing the page - but it still looks wrong). Per the "architecturally consequential changes get flagged, not silently decided mid-build" convention, recorded here + in docs/PROGRESS.md rather than patched. Future ticket idea: a responsive console-shell chunk adding a hamburger/drawer nav pattern to the shared `(console)/layout.tsx` on both surfaces.

## T-037: seed_tenant2_dental.py as a proof driver (2026-07-21)

- 2026-07-21 (T-037, generalization proof): `seeds/seed_tenant2_dental.py` is NOT a seed like its neighbours - it never writes rows on the provisioning path, it drives the public API (GoTrue signup -> POST /api/tenants -> /api/onboarding/message x7 -> /confirm -> /api/knowledge/upload x3) as a browser would, and it fails loud on any step the API cannot complete. That restriction is the proof; a workaround inside the driver would defeat it. Its `--teardown` flag is the one direct-SQL path and is explicitly excluded from the proof. The words posted at each stage live in `tenant2_inputs/interview-script.md` and are parsed from its fenced `## stage: <name>` blocks (a `<stage>.followup` block is used when the flow re-asks), so the document a reader sees is exactly what was sent - no second copy in Python to drift.

## T-037: The required-numeric-field bug class (2026-07-21)

- 2026-07-21 (T-037 - the bug class it found, worth watching for elsewhere): a REQUIRED numeric field on an LLM extraction schema gives the model no way to say "they described this but never gave a number", so it fabricates one and the fabrication is silently authoritative. Bit twice in onboarding: (a) `PricingRuleDraft.unit_amount_dollars` -> rules stored at $0.00, which would make the deterministic pricing engine quote a real service as free (the hard rule held - no LLM authored a price - but the number the engine READ was wrong, which is the same outcome); (b) `EscalationDraft.threshold` -> 0.0 one run and 1.0 the next from a prose answer, and 0.0 means NEVER escalate (supervisor compares `confidence < threshold`), silently inverting a "be cautious" request in the safety-relevant direction. Fix pattern for both: make absence expressible (`| None`), have the model transcribe only what was actually said (a `posture` literal, not a number), and let Python own the number (`resolve_threshold`) - the principle money already had, now applied to every stored number.

## T-037: Merging LLM extractions by key does NOT work (2026-07-21)

- 2026-07-21 (T-037 gotcha - merging LLM extractions by key does NOT work): the first fix for the unpriced-rule re-ask merged the follow-up's rules into the prior ones by `code`, and the stage never converged, because the model renames codes between turns (`wisdom_teeth` -> `wisdom_tooth_removal`). No key-based merge can reconcile that. What works: feed the running set back INTO the follow-up extraction (`_prior_rules_context`) and ask for the COMPLETE corrected list, then replace wholesale. Also bound the re-asks (`_MAX_PRICING_FOLLOWUPS = 1`) and drop-rather-than-zero on giving up, so the stage always terminates.

## T-037: Local-run gotchas (2026-07-21)

- 2026-07-21 (T-037 local-run gotchas): the `auth`/`auth-proxy` compose services need `SUPABASE_JWT_SECRET` exported into the shell (`set -a; . backend/.env; set +a` before `docker compose up -d auth auth-proxy`), otherwise GoTrue dies with "non-empty []byte key required" - scripts/demo.sh does this for you. Also watch for TWO uvicorns bound to :8000 (a `--reload` one and a plain one); the plain one shadows the reloader, so code edits appear not to take effect. Run a private backend on :8001 for proof runs, and remember a non-reload server must be restarted after editing `app/`.

## T-037: Honest state - knowledge answering on free-tier model (2026-07-21)

- 2026-07-21 (T-037 honest state - knowledge answering is the weak link, BOTH tenants): four in-domain questions to the new dental tenant were refused/escalated (`inspection:grounding`) despite the answers being plainly in the uploaded docs. The control matters: the same class of question to `bytefix` also refuses ("what is your warranty policy" -> refusal, from a doc with a Warranty section), and chunking is equivalent across the upload API and the seed path (1.3k-2.0k chars/chunk on both). So this is retrieval precision + grounding strictness on the free-tier model, NOT a generalization failure - but it does mean end-to-end answer quality is unproven for either tenant until a stronger model is provisioned. Every miss refused or escalated; none invented an answer.

## Reranker score normalization bug (2026-07-23)

- 2026-07-23 (retrieval refusal bug, found while verifying T-037, FIXED): the knowledge agent was refusing in-domain questions whose answer is plainly in the docs ("what is your warranty policy" for bytefix, "cancellation policy"/"do you treat children" for northgate), emitting the retrieval-layer refusal "I don't have information about that". Root cause: the two Reranker backends returned scores on DIFFERENT scales but the knowledge agent applied ONE absolute cutoff (`score > 0.0`) to both. `CohereReranker` returns a [0,1] `relevance_score`; `LocalCrossEncoderReranker` (ms-marco-MiniLM, the free/local default) returned RAW LOGITS, which are routinely negative even for a genuinely relevant passage. The reranker was correctly ranking the right chunk #1 (warranty passage at logit -0.11, treat-children FAQ at -1.45) and the `>0.0` gate then discarded it. Net: local refused almost everything, Cohere would refuse nothing - same code, opposite failure. Fix: made the Reranker contract return a NORMALIZED [0,1] relevance probability on every backend (sigmoid over the cross-encoder logit in `app/retrieval/rerank.py`, order preserved since sigmoid is monotonic so recommendation/quoting which use rank-only are unaffected), and set `REFUSAL_SCORE_THRESHOLD = 0.05` in `app/agents/knowledge.py` - sits in the wide gap between correctly-ranked matches (0.19-0.95 post-sigmoid) and noise (<0.002). "Where can I park" still refuses correctly (best chunk 0.0004, a real retrieval miss - parking buried in a big faq chunk). Regression guard: `tests/test_rerank_normalization.py`. Diagnose retrieval scores directly with a probe that calls `retrieve()` and prints per-chunk scores rather than going through the flaky chat stream.

## PassthroughReranker test double fix (2026-07-23)

- 2026-07-23 (gotcha - PassthroughReranker test doubles): ~12 test files (+ evals/leakage_eval.py) define a `PassthroughReranker`/`_PassthroughReranker` that did `return candidates[:top_k]`, leaking the RRF-FUSED score (~0.0164 = 1/(60+1)) as the "relevance". That happened to pass the old `>0.0` gate but VIOLATES the new [0,1] relevance contract and falls below the 0.05 threshold, so any test where the knowledge node retrieves+generates (test_inspection, test_leakage via leakage_eval, test_generation_eval_run) broke. Fix pattern for a passthrough double that KEEPS a chunk: it's asserting the chunk is relevant, so `return [replace(c, score=1.0) for c in candidates[:top_k]]` (RetrievedChunk is a frozen dataclass, needs `dataclasses.replace`). Only the 3 knowledge-retrieving tests needed it; the other doubles route to non-knowledge agents so their RRF-score passthrough is harmless and was left alone. If you touch reranker scoring again, expect these doubles to need the same treatment.

## T-038/039/040 artifacts written (2026-07-23)

- 2026-07-23 (T-038/039/040 artifacts written - phase 4 near-complete): wrote `docs/artifacts/eval-report.md` (T-038), `docs/artifacts/security.md` (T-039), `LEARNINGS.md` + README architecture-diagram/deferrals/artifact-links (T-040). Key honest-state facts for whoever picks up shipping: (1) the persisted `generation` eval_runs row `6bc4618c` is at git_sha `2332ebf`, which PREDATES the reranker-refusal fix `0dd266e` - so its faithfulness 0.484 / relevancy 0.407 are a PESSIMISTIC FLOOR (in-domain answers were being wrongly refused and scored 0.0/0.0 as non-answers). Re-ran RETRIEVAL on HEAD to refresh its row (`fda874a3`, sha 0dd266e - rank metrics identical since sigmoid is monotonic; negative_avg_top_score now 0.0000730, a real probability). (2) A HEAD re-run of generation AND trajectory both abort on sustained free-tier `gemma-4:free` 429s (upstream congestion, retry_after ~27s, retries exhausted) - the eval persists a row only on completion so no partial/HEAD generation or trajectory row exists. There is currently NO trajectory eval_runs row at all; the live 0.667 tool_correctness is from T-026 verification, reported as a live observation not a traceable row. A clean HEAD sweep of the LLM-judged evals needs a paid/Azure key. (3) The two remaining ship gates are BOTH external: T-036 live deploy (AWS/Vercel/Supabase secrets) and the demo-video recording (founder step, flagged in README). Deterministic bars all pass on HEAD: retrieval recall@5 1.000, leakage 100%x2, injection 96.7% (`d6aced91`), quote provenance enforced+tested. These docs are written but NOT yet committed (was on `main`; commit needs a branch per the harness rule).

## ADR: chat latency root cause + US-060 vs US-110 scope contradiction (2026-07-28)

- 2026-07-28 (chat latency ADR - ROOT CAUSE IS ARCHITECTURAL, NOT THE MODEL): the customer chat feels slow, but the founder verified a *single* call to the same free OpenRouter model is fast in other harnesses (Hermes, opencode). So "the free model is slow" is NOT the cause. One customer message is a serial chain of 3-5 LLM calls: `supervisor.run()` route extract -> `retrieve()` -> specialist streamed draft -> `inspection.run()` compliance extract (-> redraft + re-judge on failure). Recommendation/quoting add a preference/selection extract. Three compounding facts, in order of impact on PERCEIVED speed: (1) `app/api/chat.py`'s buffering loop withholds every `token` event until inspection returns a non-retry decision, so perceived time-to-first-word = `route + retrieve + FULL draft + inspect` and the user gets "silence, then a blob" - the frontend `CustomerChat.tsx` is a true SSE streamer with no artificial delay, it just receives nothing until the end; (2) nothing overlaps - retrieval sits inside the specialist, after routing, so all stages are strictly serial; (3) `max_tokens` is unset on every call in `app/llm/openai_base.py`, so drafts run arbitrarily long, plus the local embedder/reranker pay a one-time cold start on the first message after restart.

- 2026-07-28 (GENUINE FROZEN-DOC CONTRADICTION, founder-ruled - do not silently reopen): US-060 (`source/product-requirements.md:237`) requires the second-pass supervisor to check grounding/policy/price-provenance/injection/prompt-leak "before any customer-facing send". US-110/M17 (`source/product-requirements.md:254`, `:152`) and `source/architecture.md:112` require the customer surface to be STREAMING. Streaming a token IS a customer-facing send, so read literally the two frozen requirements conflict: US-060 makes live streaming of model prose impossible. The existing code had already resolved this SILENTLY in US-060's favour (stream the SSE transport, withhold the content). Per `INDEX.md` precedence rule 3 a genuine scope contradiction must be flagged, not picked, so it was flagged. **Founder ruling: US-060 stays authoritative** - inspection clears every draft before any customer-facing send, and the transport-level reading of "streaming" is now the explicit ratified interpretation rather than an implicit one. Two alternatives were considered and REJECTED: segmented inspection (inspect in chunks, release each verified chunk - holds US-060's letter and gives real streaming, but weakens grounding across segment boundaries) and stream-then-retract (best feel, contrary to US-060, lets a customer briefly see text that is then pulled). If perceived latency is still unacceptable after the latency work below is measured, REOPEN the ADR rather than improvising at the code level: changing when a customer sees model prose is a scope decision, not an implementation one.

- 2026-07-28 (MEASURED baseline + what the measurement disproved): instrumented per-node wall-clock (`_traced` in `graph.py`) and first-token/first-prose timing (`_stream_chat_response`), then ran 5 representative turns against `bytefix`. Knowledge turn: 37.1s total = supervisor 2.4s + knowledge (retrieve+draft) 23.3s + inspection 11.5s; prose existed at 24.7s but the buffer released it at 37.1s, so `buffer_hold_ms` = 12.4s. Knowledge turn that failed inspection once: 50.1s (2 drafts + 2 inspections). CONTROL: the escalation route - one LLM call, deterministic draft, no retrieval - returned in 2.1s on the same model and network. 2.1s vs 37.1s is the entire finding: per-call speed is fine, the serial chain is not. THREE THINGS THE MEASUREMENT CHANGED: (1) **D3 (max_tokens caps) is DISPROVEN and was reverted to off.** The configured model is a REASONING model - it spends ~300 hidden thinking tokens before emitting anything (`reasoning_tokens` 297/311/314, observed directly). A 256-token extract cap was consumed entirely by thinking, so no JSON was ever emitted and every turn died with `LengthFinishReasonError`. `LLM_MAX_TOKENS_DRAFT`/`_EXTRACT` now default to 0 (uncapped, i.e. prior behavior) and are documented as per-model knobs that must never be set blindly. (2) **D2 (overlap routing and retrieval) was not implemented**: retrieval is a local embed + pgvector/FTS + cross-encoder rerank measured in the low hundreds of ms against a 37s turn, so overlapping it buys <1% while forcing a speculative retrieval before the route is known (and the specialists use different `metadata_kind` filters, so the speculative result is often the wrong one). Not worth the complexity; revisit only if retrieval grows. (3) free-tier latency variance is large enough to defeat A/B timing - a rerun 15 minutes later hit the 45s `llm_timeout` six times on turns that had just succeeded. Measure structure (per-node timings, `buffer_hold_ms`), not absolute deltas, unless on a paid key.

- 2026-07-28 (BUG FOUND AND FIXED while measuring - hung customer streams): the quoting turn in the baseline run died with `TypeError: 'NoneType' object is not iterable` raised from inside the OpenAI SDK's `parse_chat_completion`. Cause: OpenRouter forwards an upstream provider failure as a 200 whose body has `choices: null`; the SDK iterates that null before any of our code sees the response. It was neither a `RateLimitError` nor a `ValidationError`, so it escaped `_with_retry`, propagated out of the graph, and killed the SSE generator - the stream ended with NO terminal event, leaving the customer's chat bubble spinning forever (reads as infinite latency). Two-part fix: `app/llm/openai_base.py` gained `UpstreamResponseError` (+ `_require_choices`, + a narrow `TypeError` conversion in `extract`) which is retried like a 429; and `app/api/chat.py` gained a catch-all `except Exception` that records a `provider_error` escalation and always emits `refusal`/`escalated`/`done`, so a turn can never again end without a terminal event. Regression tests in `tests/test_llm_provider_retry.py`. This handler proved itself immediately - it is what turned the `LengthFinishReasonError` storm above into graceful escalations instead of five hung browser tabs.

- 2026-07-29 (free-model benchmark - and why NO model swap is recommended on latency grounds): queried `openrouter.ai/api/v1/models` per the standing rule rather than hardcoding a list. Of 14 free models, only 4 support `structured_outputs`, and ALL FOUR advertise `reasoning` - so "switch to a non-reasoning model" is simply not available on the free tier. Benchmarked all 4 back to back in one window (same prompt, Wren's own two workloads - a routing extract and a short draft), which is the only fair way given free-tier variance: `gemma-4-26b` extract 2.6s / draft 2.4s with **0 reasoning tokens**; `nemotron-3-super-120b` (the demo default) 2.0s / 4.7s with 110/78 reasoning tokens; `nemotron-nano-9b` 6.1s / 5.8s with 256/214 (SMALLER IS NOT FASTER on free tier - it was the slowest and thought the most); `gpt-oss-20b` FAILED structured output entirely with a ValidationError, which disqualifies it for Wren since every route/inspection call is an `extract`. HOWEVER: an end-to-end 5-turn run on gemma-4 came out SLOWER through the real graph (55.9s and 107.9s on the knowledge turns) than the 120B's earlier baseline, because free-tier queueing dominates and swamps the per-call difference. Conclusion: the isolated benchmark does NOT translate into an end-to-end win, so no model change is justified by this evidence. Revisit on a paid/Azure key, where per-call speed would actually be the thing being measured. Recorded because the per-call numbers (especially gemma-4's zero reasoning tokens and gpt-oss-20b's structured-output failure) are durable facts worth not re-deriving.

- 2026-07-29 (CI vs demo model drift - worth fixing for consistency, not speed): `.github/workflows/ci.yml:133` pins `LLM_MODEL: google/gemma-4-26b-a4b-it:free`, but `backend/.env` runs `nvidia/nemotron-3-super-120b-a12b:free` and `.env.example:23` suggests the nemotron as THE OpenRouter option. So CI validates one model while the demo and the documented setup path use another - and the two differ in a way that matters (zero vs non-zero reasoning tokens, different structured-output behavior under a token cap). Not changed here because model choice is the founder's call and the latency evidence above does not support a swap; flagged so the divergence is deliberate rather than accidental.

- 2026-07-28 (latency work that IS legal under the ruling): four changes, all pure implementation detail, none touching an invariant. D2 overlap routing and retrieval (the retrieval query is the customer message, independent of the route, so it need not wait for the supervisor); D3 cap `max_tokens` (draft ~400, structured extracts ~256, configurable); D4 warm `LocalEmbedder`/`LocalCrossEncoderReranker` in the FastAPI lifespan so the first real message does not pay cold start; D5 stream non-prose progress events (`searching knowledge base`, `checking answer`) alongside the `citations`/`quote` events that already stream live - these are deterministic app events, NOT model prose, so US-060 is untouched, and they convert dead silence into a narrated wait. Instrument FIRST (per-node wall-clock via the existing `_traced` wrapper in `graph.py`, plus a first-token timestamp in `_stream_chat_response`) and capture a baseline, so the gains are measured rather than asserted. Note the deterministic-pricing invariant (`conventions.md:44-52`, "outranks convenience, speed") independently forbids showing any money-carrying draft before the price gate clears, under any latency argument.

## ADR: Agentic conversation layer - onboarding copilot + customer chat (2026-07-30)

### The problem

Both of Wren's chat surfaces treat conversation as classification into task buckets. Neither handles the human parts of talking.

**Onboarding** (`backend/app/onboarding/flow.py`) is a seven-stage state machine with seven hardcoded prompt strings and one `extract()` call per stage. `advance()` passes exactly one user message to the model with no conversation history, then increments the stage index. An admin asking "what's your name?" at the identity stage gets `IdentityDraft(description="what's your name?")` stored as the tenant's system prompt. It cannot redirect, rephrase, answer a question, or skip ahead when the admin volunteers something early.

**Customer chat** has the same shape one level up. `supervisor.py:36-39` routes to exactly five specialists: knowledge, recommendation, quoting, order_status, escalation. There is no route for a greeting, a meta question, or thanks. "What's your name?" either scores low confidence and is force-escalated to a human, or lands in `knowledge` and gets answered from the business's RAG index. Escalating a greeting to a human is a visible product defect.

### Scope precedent

Three frozen planning docs defer "a more open-ended interviewer" to Phase 2 and list "open-ended 'magic' onboarding interviewer" under EXPLICIT PHASE 2:

- `docs/source/architecture.md:142` -- "Phase 2: a more open-ended interviewer that infers structure from freeform description and existing-website ingestion."
- `docs/source/sprint-plan.md:122` -- "open-ended 'magic' onboarding interviewer + existing-website ingestion" under EXPLICIT PHASE 2.
- `docs/source/product-requirements.md` WON'T table (line 173) -- "Open-ended 'magic' onboarding interviewer | Guided-conversational onboarding proves the concept; a fully open interviewer that reliably configures any business is itself a hard agent-research problem, deferred."

The working doc `docs/phases/phase-1-foundations.md` line 99 also specifies: "a guided state machine (explicit ordered stages), NOT an open-ended interviewer."

Per `docs/INDEX.md` precedence rule 2, frozen docs win on scope, and `conventions.md` section 4 requires architectural changes to be flagged to the founder rather than decided mid-build. The founder has ruled: proceed with the fully agentic, tool-driven design, pulling forward the deferred Phase 2 interviewer.

### What changes

The onboarding state machine is retired and replaced with an agentic copilot that uses tool calling. The customer chat gains a `conversation` route for greetings/thanks/meta questions, and the supervisor moves from a fixed five-specialist topology to a tool-driven agent loop.

### What supersedes the frozen-doc position

This ADR supersedes the three frozen-doc positions listed above. The Phase 2 "open-ended interviewer" is being pulled forward into the current implementation phase. The frozen docs are NOT edited; this ADR is the authoritative record of the scope change.

### Guarantees that replace the state machine's structural ones

The state machine was carrying real structural guarantees. Each is now carried explicitly in Python rather than implicitly in the machine:

1. **Completeness is Python's call, never the model's.** The agent may *request* finalize; a Python gate verifies every required config section is present and valid and refuses with a typed reason the agent must act on. The model never decides "done".
2. **Money arithmetic stays in Python.** `_cents()` is unchanged. Tool args carry admin-transcribed dollar floats only.
3. **Optional numerics stay optional.** The `| None` design on `price_dollars` and `unit_amount_dollars` and the `posture` enum encode production failures; tool schemas preserve this, and Python re-asks rather than stores a placeholder.
4. **`resolve_threshold()` and `_POSTURE_THRESHOLDS` are reused unchanged.** The model never produces the threshold number.
5. **Deterministic pricing hard rule holds on both surfaces.** No tool schema on the quoting path gains a money field.
6. **Domain-agnostic hard rule.** No prompt, tool, or route branches on a vertical. Tenant 2 must still onboard by config alone.
7. **Termination.** Every loop is bounded in Python: tool-call iterations per turn, consecutive off-topic turns, and total turns.
8. **Atomic commit.** The confirm write stays one transaction inside `db.tenant_context`.

### Calendar impact (Phase 4 context)

Phase 4 is Ship (8/9 done as of 2026-07-30; T-036 deploy + T-040 demo video remain, both founder-blocked on external credentials). These four tickets inject scope into a nominally-completing phase. Impact:

- **T-041** (provider tool-calling): ~1 day, self-contained, all existing tests pass alongside.
- **T-042** (agentic onboarding): ~1.5 days, largest single-scope item. Seeds + tests rewrite.
- **T-043** (conversation route): ~0.5 day, small diff, fixes a visible defect independently.
- **T-044** (tool-driven supervisor): ~1.5-2 days, highest risk - rewrites graph topology, 24+ test files and 4 evals affected. Seeks safe completion before T-036 deploy lands.

Total injection: ~4.5-5 days. This does NOT block T-036/T-040 - those remain founder-gated on external credentials. This work completes alongside them. The 30-day clock is treated as a calendar envelope; quality within it is per `conventions.md` §4.

### Design decisions ratified during review (2026-07-30)

Before any code lands, the following design refinements are recorded as settled:

1. **Admin-facing prose and the deterministic-pricing hard rule.** `conventions.md` §8 targets customer-facing surfaces (no LLM ever produces a monetary amount that reaches a customer). Onboarding is admin-facing; the admin IS the source of every price. The copilot may echo back a price the admin stated ("I've saved screen repair at $89") as part of a confirmation - this is transcription/confirmation, not computation. If an admin restates a figure the admin never gave (price echo check catches this) the figure is dropped. This is the same spirit as the T-006 ADR entry (2026-07-11): "the model's job is transcription of a number they already said, never invention of one."

2. **Spotlight-wrapping on the admin path is scoped to injection scanning only.** `spotlight.py`'s `wrap()` fences untrusted third-party content from reaching the model. The admin IS the instruction-giver, not an attacker against themselves. Spotlight's `scan_input()` (the regex pattern check) still runs on admin messages as defence-in-depth (advisory flag, never blocks), but `wrap()` is NOT applied - admin text enters the prompt directly, as it does today in `advance()`.

3. **Seeds bypass the copilot, not drive through it.** `seed_tenant2_dental.py` pre-populates the new jsonb state format directly (simulated completed tool calls), same pattern as the current seed bypasses the API. Driving answers through the copilot API would make seeds LLM-dependent, slow, and non-deterministic. The confirm endpoint validates and writes to relational tables regardless of how state was populated, so no LLM dependency is introduced.

4. **State format migration: version key for backward compatibility.** The onboarding record in `tenant_config.config->'onboarding'` jsonb gains a `version` key (set to `2` for the agentic format). On read, if `version` is absent or `1`, the record is treated as a legacy state-machine record. A legacy record with `completed: false` triggers a one-time migration prompt (the copilot resumes from captured draft fields if any exist, re-asks for missing ones). A legacy record with `completed: true` is left as-is. This avoids bricking partially-onboarded tenants.

5. **Confidence gate semantics for the conversation route.** The conversation route uses the same single threshold as task routes. The supervisor's system prompt is updated to assign HIGH confidence (>= 0.8) to clear greetings/thanks/meta questions and LOW confidence to genuinely ambiguous messages. This preserves the threshold-as-escalation-posture behaviour without a second threshold. An ambiguous message below threshold still escalates - the only path into `conversation` is a high-confidence classification, which a greeting inherently is.

6. **Tool-calling abstraction follows OpenAI's API contract, not a custom shape.** `chat_with_tools(messages, tools) -> ToolTurn` where `ToolTurn` carries `text: str | None` (a model reply in the same response) + `tool_calls: list[ToolCall]`. The "directive" pattern is a prompt-engineering layer ABOVE the provider, not inside it. The provider never knows about directives - it only knows about tools and messages. The onboarding agent composes the directive from tool results and feeds it as the system/user prompt to `chat_stream`.

### Verification strategy

Ordered, each stage verified before the next begins. Automated: `make check` clean at every stage; `make ci` before each commit. End-to-end: drive the exact failure that prompted this work, verify tenant 2 generalizes with zero code changes, `make test-e2e` with the first Playwright spec for onboarding. Free-model check: run the full onboarding flow once with `LLM_TOOL_CALLING=off` to prove the emulated path works on a free OpenRouter model.

### Tickets

- Phase file: `docs/phases/phase-5-agentic-conversation.md` - tickets T-041 through T-044
- `docs/PROGRESS.md` - new Phase 5 section, one row per ticket, updated at commit time
- `.agents/memory.md` - record that the onboarding state machine is retired, which guarantees replaced it, and that tool calling has a free-model emulation path
- `.agents/map.md` - refreshed for new modules (`backend/app/onboarding/{agent,tools}.py`, `backend/app/agents/{conversation,tracing}.py`)

## gpt-oss-20b:free re-check - still NOT a gemma replacement (2026-08-03)

- 2026-08-03 (free-model re-check - gpt-oss-20b:free re-verified as DISQUALIFIED, gemma stays): requested swap of the pinned model to `openai/gpt-oss-20b:free`. OpenRouter's live `/models` API advertises `structured_outputs` and `tool_choice` for it, so a live probe drove Wren's own provider (`OpenAICompatProvider` + the production `RouteDecision` schema) against the real key, rather than trusting either the old records or the API metadata. Result - unchanged since 2026-07-11 and 2026-07-29: the FIRST routing `extract()` returned markdown prose (`**Route:** ... **Confidence:** 0.95`) instead of JSON, failing pydantic validation after both internal resample retries (29.5s to fail); a second extract with an optional field failed identically. Plain `chat()` prose works (4.0s), but that is not the requirement - every route/inspection call is a strict `extract()`. Native `chat_with_tools()` is also dead on the free tier right now: OpenRouter returns `model_unavailable` - "no online provider for model gpt-oss-20b advertises inference-time tool_choice enforcement" (Darkbloom). Conclusion: keep `google/gemma-4-26b-a4b-it:free` as the pinned model in CI, `.env.example`, `backend/.env`, and the Terraform default. No files were changed by this re-check beyond this log entry and the memory note. The API metadata advertising structured_outputs does not translate to behavior on the free tier - a reminder to keep the standing rule (verify live, never trust the model list).

## ADR: Z.ai glm-4.7-flash becomes the direct primary; gemma fails over (2026-08-03)

- 2026-08-03 (provider-routing change, live-verified, local scope): requested "directly route to Z.ai instead of setting it as fallback". Live probe against the real Z.ai key through Wren's own provider classes, before any code changed: `ZaiOpenAICompatProvider` (json_object extract, thinking disabled) did 5/5 routing extracts OK (1.2-4.9s, sensible routes incl. escalation), plain chat 0.8s, and native `chat_with_tools` returned a correct `lookup_order(ref_code="R-1042")` tool call. A control probe proved Z.ai rejects strict json_schema (returns markdown prose) - so the swap MUST keep the Zai provider class; a plain env change to `openai_compat` would break every extract. Free-tier rate limiting (error code 1305) kicked in after ~10 rapid calls - the failover exists for exactly this. Founder-ruled: Z.ai primary, OpenRouter gemma as failover, local + docs scope only (CI and infra still run OpenRouter gemma because their `LLM_API_KEY` secret is an OpenRouter key; flipping them needs a Z.ai key in GitHub secrets / AWS Secrets Manager first).
- 2026-08-03 (implementation): provider classes gained a `fallback` role flag so each can serve either position - both `ZaiOpenAICompatProvider` and `OpenAICompatProvider` default `fallback=False` (primary is the sane default role; one shared default, no per-class asymmetry), read the `llm_*` settings when False and the `llm_fallback_*` settings when True, and `dependency.py` passes the flag EXPLICITLY at all four construction sites. `get_llm_provider()` (app/llm/dependency.py) now routes on `LLM_PROVIDER` (`zai` added alongside `openai_compat`/`azure`) and `LLM_FALLBACK_PROVIDER` (new setting, `zai` default = prior behavior, `openai_compat` for a non-Z.ai fallback). Config default drift caveat: `Settings.llm_provider` still defaults to `azure`; every runnable config sets it explicitly. `backend/.env` cross-swapped: `LLM_PROVIDER=zai`, primary block = Z.ai base URL/model/key, fallback block = OpenRouter URL/gemma/OpenRouter key, `LLM_FALLBACK_PROVIDER=openai_compat`. Tests: `tests/test_llm_dependency.py` (new - pins all three wiring combinations hermetically) + `test_llm_zai.py` primary-role test; two pre-existing problems fixed along the way: `test_quoting_agent.py` called `_initial_state()` missing its required `conversation_id` (mypy + runtime TypeError), and the repo's committed state failed `ruff format --check` on 25 files (drift from the T-041-44 era) - both fixed in a separate chore commit.
- 2026-08-03 (post-swap live verification): re-ran the probe through the REAL factory (`get_llm_provider()` on the swapped `.env`): 5/5 extracts via Z.ai (1.1-3.0s), chat 0.9s, chat_with_tools OK; a forced-failure check proved the LIVE gemma fallback answers a strict extract (2.3s) through `OpenAICompatProvider`. Full suite: 482 backend tests, ruff lint/format, mypy strict, 38 frontend tests all green. Z.ai measured faster than gemma's per-call baseline (1.1-3.0s vs ~2.6s) with thinking disabled - but per the 2026-07-29 ADR, free-tier variance means per-call deltas are not a real speed claim; the reason for this swap is resilience (two independent free tiers, primary first) rather than measured latency.
