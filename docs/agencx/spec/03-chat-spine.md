# Phase 1 - Chat spine (P)

The customer chat spine: provider layers, latency/failover, agent-ready
pre-load, knowledge versioning, and the typing indicator. These re-cut the
chat to the supervisor-with-tools, one-call-per-turn shape.

Tickets in this file (in build order):

- P-3: Agent-ready pre-load (context package) - keystone
- P-1: Provider layer - Google / Groq / Cerebras tiers
- P-2: Latency budget + first-wins failover
- P-4: knowledge_version + invalidation
- P-5: Failover typing indicator (client)

---

## P-3: Agent-ready pre-load (context package)

### Summary

Assemble the context package - system prompt + tenant profile + corpus
(whole-corpus path when under the token threshold) - when the chat opens,
cache it in-process keyed by `(tenant_id, knowledge_version)`, and make
each customer turn a single LLM call against the package. This is the
supervisor-with-tools turn shape (D-13) and the main latency lever (D-14).

### Why

The measured 37s knowledge turn was 3-5 serial LLM calls plus a retrieval
round-trip before any drafting. Pre-loading removes the retrieval latency
from the customer-visible path for small corpora and collapses the calls to
one. It is also the structural prerequisite for the failover budget (P-2)
to have something fast to protect.

### User stories

#### US-1 The package exists before the first message

**As** the maintainer,
**I want** the context package assembled on chat open (not on first send),
**so that** the agent is ready the moment the customer types.

- [ ] Chat open (public page load, tenant chat load) triggers assembly
  behind the request: profile + system prompt + corpus (fast path) or
  retrieval-ready state (hybrid path)
- [ ] The package is cached in-process with a TTL and the
  `(tenant_id, knowledge_version)` key

#### US-2 One call per turn in the common case

**As** Alex,
**I want** my question answered in one round trip,
**so that** the answer is fast.

- [ ] A customer message = one LLM call: supervisor-with-tools against the
  package + message history; no route call, no retrieval call, no separate
  draft node
- [ ] Greetings, refusals, and grounded answers all flow through this single
  call (tools available per the tenant's enabled set - D-1)

#### US-3 The guardrail and inspection still gate

**As** the maintainer,
**I want** the one-call shape to keep the full safety pipeline,
**so that** speed never trades against the money boundary.

- [ ] draft -> guardrail (C-2) -> inspection -> stream, unchanged in order
  and authority
- [ ] The inspection buffer rule (nothing before inspection passes) is
  untouched

#### US-4 Cache invalidation is version-driven

**As** Sam uploading a new menu,
**I want** the next chat open to answer from the new material,
**so that** the cache never serves stale knowledge.

- [ ] Package lookup validates the current `knowledge_version` (P-4); a
  mismatch reassembles
- [ ] A freshly assembled package is served for the very next turn (no
  TTL-wait staleness in the same session after an upload)

### Technical spec

- `backend/app/services/context_package.py` (deterministic assembly - no
  model calls; sits in `services/`)
- In-process cache (module-level dict + lock; single-worker dev is fine,
  `ponytail:` note: per-process cache means multi-worker ECS will
  reassemble per worker - acceptable at Stage 1 scale, upgrade path is a
  shared cache keyed identically)
- The whole-corpus path reuses the O-4 threshold check

### Tests

- Unit: package assembly content and shape; cache hit/miss on version bump
- Unit: one-call turn flow with a fake provider (tool call + direct answer
  paths)
- Unit: guardrail + inspection still run on the one-call draft

### Files touched

- `backend/app/services/context_package.py`
- `backend/app/agents/**` (turn orchestration), routes
- `backend/tests/**`

### Definition of done

- [ ] Package assembled on chat open, cached by version key
- [ ] One LLM call per common turn
- [ ] Safety pipeline unchanged and green
- [ ] Stale-cache behavior verified

---

## P-1: Provider layer - Google / Groq / Cerebras tiers

### Summary

Extend the provider configuration so the three-tier strategy (D-15) is a
pure env swap: Google AI Studio primary (OpenAI-compat endpoint), Groq
fallback (native), Cerebras as a candidate third leg, OpenRouter gemma as
the CI-pinned failover. The existing provider classes (`openai_compat`,
`zai`, `azure`) already cover the wire format; this ticket adds the
third-leg slot and documents/locks the tier config.

### Why

The provider strategy needs three legs: a generous free primary (Google),
a fast LPU fallback (Groq), and an independent failover (OpenRouter). The
current config has primary + one fallback. The latency budget (P-2) needs a
leg to fail over TO and a leg to fail over FROM; P-1 makes the leg
structure exist without a code change per provider.

### User stories

#### US-1 Providers are env config, not code

**As** the founder,
**I want** to swap the provider lineup by editing env vars,
**so that** free-tier churn never means a code change.

- [ ] `LLM_PROVIDER`/`LLM_BASE_URL`/`LLM_MODEL` (+ fallback pair) cover
  Google (openai_compat), Groq (openai_compat), Cerebras (openai_compat),
  OpenRouter (openai_compat), Z.ai (zai) - each documented in
  `.env.example` with the exact base URL and known quirks
- [ ] A third-leg slot (`LLM_FAILOVER_*` or equivalent) exists for the
  independent tier (OpenRouter gemma)

#### US-2 Provider quirks stay encapsulated

**As** the maintainer,
**I want** each provider's documented quirks handled inside its class,
**so that** a swap never breaks structured extract silently.

- [ ] Groq: json_schema structured outputs only on gpt-oss models
  (llama-3.3-70b is json_object-only and breaks extract) - documented +
  guarded
- [ ] Google: the OpenAI-compat endpoint quirks documented; gemini flash
  line verified for structured outputs + tool calling
- [ ] Free-tier reality: query the provider model list for
  structured-output support at startup or config-check time (the CI pin
  stays hardcoded by design)

#### US-3 The budget ceiling is enforced

**As** the founder,
**I want** the $10/month testing budget to be a tracked number, not a hope,
**so that** the build never silently burns money.

- [ ] Cost logs already track per-call tokens; add a per-month budget
  assertion to the cost dashboard (warning at 80% of $10)

### Technical spec

- `backend/app/llm/dependency.py` + `backend/app/shared/config.py`:
  third-leg settings; `get_llm_provider()` returns the tier chain
- `.env.example` rewritten with the tier matrix
- No new wire formats - everything speaks OpenAI-compat (the proven
  default); Google AI Studio's OpenAI-compat endpoint is the URL, not a new
  class

### Tests

- Config tests: each documented tier parses and constructs its provider
- Structured-output guard tests for the Groq/gpt-oss pairing

### Files touched

- `backend/app/llm/dependency.py`, `backend/app/shared/config.py`
- `backend/.env.example`, `backend/tests/**`

### Definition of done

- [ ] Three-tier chain configurable by env alone
- [ ] Quirk guards in place per provider
- [ ] Budget tracking assertion wired

---

## P-2: Latency budget + first-wins failover

### Summary

Implement the latency contract (D-16, PRD section 9): time to first token
<= 4s on the primary; on timeout or hard 429, the fallback leg races the
primary and **first-wins** - the losing stream is discarded; 10s hard cap
to a complete answer; a hard 429 skips that provider for the rest of the
session. Replaces the current blind-retry behavior.

### Why

The measured Wren story: free-tier variance defeated timing, and the
inspection buffer meant customers saw silence then a blob. The budget plus
first-wins turns provider variance into a race the customer cannot see, and
makes the speed contract (PRD section 9) honest under free-tier conditions.
The 4s/10s numbers are the product promise, not a provider SLA.

### User stories

#### US-1 The primary gets 4 seconds to first token

**As** Alex,
**I want** an answer to start appearing fast,
**so that** the assistant feels responsive.

- [ ] TTFT monitored on every provider call; primary timeout at 4s triggers
  the failover leg (both legs run concurrently; either may win)
- [ ] TTFT is measured from request send to first streamed token (not to
  completion)

#### US-2 First-wins, loser discarded

**As** the maintainer,
**I want** the faster leg's stream to own the answer and the slower leg's
to be cancelled,
**so that** the customer never sees two answers or a torn stream.

- [ ] The losing call is aborted client-side (provider close) and its
  partial output discarded
- [ ] The inspection buffer still gates the winner (nothing reaches the
  customer uninspected - the buffer rule from 2026-07-28 is unchanged)

#### US-3 10 seconds to a complete answer

**As** Alex,
**I want** the whole answer within 10 seconds or an honest handoff,
**so that** a slow provider never means an abandoned conversation.

- [ ] If no leg completes within the 10s cap, the turn degrades to the
  escalation message (existing graceful-degradation path)
- [ ] The cap is per turn, not per leg

#### US-4 Hard 429 skips the provider for the session

**As** the maintainer,
**I want** a provider that hard-rate-limits to sit out the session,
**so that** the failover does not thrash against a brick wall.

- [ ] Hard 429 (quota exhausted) marks the provider skip-for-session;
  transient 429s keep the existing retry/backoff
- [ ] Skip state is per conversation/session, not global (another session
  may use it)

#### US-5 The budget is observable

**As** the founder,
**I want** per-turn TTFT, leg outcomes, and failover events in the cost/trace
pipeline,
**so that** the latency signal in the PRD is measurable, not anecdotal.

- [ ] Scalar attributes on the existing tracing: `ttft_ms`, `leg`,
  `failover_engaged`, `skip_reason` - no cross-tenant content, no PII

### Technical spec

- `backend/app/llm/failover.py` extended: TTFT timers, concurrent-leg race,
  first-wins arbitration, session skip set
- `TimeLimitedProvider` already exists for per-call caps; the budget is
  layered on top (TTFT + wall clock)
- SSE: the client receives one stream (the winner's), post-buffer

### Tests

- Unit: fake providers with programmable delays - primary slow (wins by
  fallback), primary fast, both slow (cap -> escalation), hard 429 skip
- Unit: loser stream discarded (no interleaved tokens)
- Integration: tracing attributes present on failover events

### Files touched

- `backend/app/llm/failover.py`, `backend/app/llm/openai_base.py`
- `backend/app/agents/**` (turn orchestration), `backend/tests/**`

### Definition of done

- [ ] 4s TTFT timeout + first-wins race proven with fakes
- [ ] 10s turn cap degrades to handoff
- [ ] Hard 429 session skip works
- [ ] TTFT/failover observable in tracing

---

## P-4: knowledge_version + invalidation

### Summary

Derive `knowledge_version` for a tenant as the max document update
timestamp (design/database.md section 4) and wire it into the context
package cache (P-3): any upload, re-ingest, or document status change
invalidates the cache on the next lookup. No new table.

### Why

The pre-load cache is only safe if it cannot serve stale knowledge. The
version stamp is the smallest possible invalidation mechanism - a derived
max timestamp with no schema addition, no new writes to maintain.

### User stories

#### US-1 The version is derivable in one query

**As** the maintainer,
**I want** `knowledge_version(tenant_id)` to be one SQL max over
`documents`,
**so that** no new table or write path exists to drift.

- [x] One query, as built over `documents.updated_at` (migration 0018) rather
  than the insert-only `uploaded_at`: `greatest(coalesce(max(documents
  .updated_at), 'epoch'), coalesce(tenant_config.updated_at, 'epoch'))`
- [x] Profile changes also bump (the profile lives in `tenant_config`; its
  `updated_at` joins the derivation: version = max(documents.max,
  tenant_config.updated_at))

#### US-2 Uploads and re-ingests invalidate

**As** Sam adding a menu,
**I want** the cached package replaced at the next open or turn,
**so that** answers use the new material.

- [x] Ingest completion moves the row timestamp: `uploaded_at` was
  insert-only, so 0018 adds `updated_at` + the shared `touch_updated_at()`
  trigger, and the pipeline's existing `status` writes bump it on every
  (re-)ingest - verified against the real pipeline, not the UPDATE text
- [x] P-3's lookup compares versions; mismatch reassembles the package

#### US-3 The version is cheap and safe

**As** the maintainer,
**I want** the version check to add no meaningful latency,
**so that** the pre-load gain is not eaten by the invalidation check.

- [x] One indexed max query per package lookup (documents is already
  indexed by tenant)
- [x] No tenant data crosses the process boundary in the version value

### Technical spec

- `backend/app/services/knowledge_version.py` (or inside
  `context_package.py`): the derivation
- Verify the ingestion pipeline writes `uploaded_at`/`updated_at` on
  re-ingest; fix the pipeline if it does not (that is a bug the cache would
  silently hide)

### Tests

- Unit: version changes on upload, on re-ingest, on profile change; stable
  otherwise
- Unit: P-3 cache invalidates when versions differ
- Pipeline test: re-ingest updates the document row timestamp

### Files touched

- `backend/app/services/**`, `backend/app/ingestion/**` (timestamp fix if
  needed)
- `backend/tests/**`

### Definition of done

- [x] One-query derivation including profile changes
- [x] Upload/re-ingest/profile change invalidate
- [x] Pipeline timestamp behavior verified (fixed if missing)

---

## P-5: Failover typing indicator (client)

### Summary

Add the `TypingIndicator` component (three pulsing dots, 600-800ms, reduced-
motion aware) and wire it to the turn lifecycle: active from send through
the failover window until the inspected stream arrives. The indicator never
stops mid-turn to reveal a provider switch; there is no spinner and no
provider-switch copy.

### Why

The speed contract (PRD section 9) promises the customer never sees a
spinner, a blank, or a switching-providers message. Today the inspection
buffer means silence until the full draft passes - the indicator turns that
silence into natural pacing, and P-2's failover happens invisibly behind
it.

### User stories

#### US-1 The indicator spans the turn

**As** Alex,
**I want** to see the assistant "typing" from the moment I send until the
answer streams,
**so that** the wait reads as thinking, not a hang.

- [ ] `turn_started` (send) activates the indicator
- [ ] The indicator stays active through the 4s primary window and any
  failover leg (P-2 events do not pause it)
- [ ] First inspected token of the winner's stream swaps the indicator for
  `StreamingText` (never both)

#### US-2 Never a spinner, never a switch notice

**As** Alex,
**I want** no "switching providers", no loading spinner, no blank bubble,
**so that** the mechanics stay invisible.

- [ ] No provider names or status copy rendered in chat (trace/cost
  surfaces only - P-2's scalar attributes)
- [ ] Error/disconnect states use the inline-retry pattern (existing), not
  the indicator

#### US-3 Motion discipline holds

**As** the maintainer,
**I want** the indicator to honor the motion tokens and reduced motion,
**so that** the frontend spec's motion rules hold.

- [ ] Three dots, `--duration-base` cadence in the 600-800ms range, tokens
  only
- [ ] `prefers-reduced-motion`: dots static, no pulse animation

### Technical spec

- `frontend/src/components/ui/TypingIndicator.tsx`; semantic tokens only
- SSE contract additions: `turn_started` (documented in
  design/frontend.md section 8); the chat hook owns indicator state
- Bubbles: indicator renders as an assistant-position bubble placeholder
  (surface token), then swaps to the streaming bubble

### Tests

- Component tests: activate on send, swap on first token, reduced-motion
  behavior
- E2E: send a question against the seeded tenant; assert indicator appears
  and answer follows (timing-tolerant assertions)

### Files touched

- `frontend/src/components/ui/TypingIndicator.tsx`
- `frontend/src/hooks/useSSE.ts` (or chat hook), chat surfaces
- `frontend/e2e/**`

### Definition of done

- [ ] Indicator spans the full turn including failover
- [ ] No spinner/provider copy anywhere
- [ ] Motion discipline + reduced-motion verified
- [ ] E2E green
