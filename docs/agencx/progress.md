# Agencx - Progress Tracker

**The one page to check to know where the build is.** Every feature is marked
**BUILT** (with the commit evidence from the Wren build), **CHANGING** (built,
and Agencx changes it - the change is described), or **NEW** (not built yet).
The change work itself is ticketed in `spec/`; each ticket's status is tracked
at the bottom.

## How to read this file

- **Statuses:** `BUILT` - shipped in the Wren build, evidence commit given |
  `CHANGING` - built, and an Agencx ticket modifies it (ticket id given) |
  `NEW` - not built, first delivered by an Agencx ticket | `blocked` - waiting
  on an external setup, not a code failure.
- Wren commit hashes are retained verbatim from the archived `docs/archive/PROGRESS.md`.
  Run `git show <hash>` for the full story of any commit.
- The Agencx spec tickets are the work plan; update their status row in the
  final section whenever a ticket ships. The tickets live in `spec/`, grouped
  by build phase into phase files (`01-foundation.md` .. `08-deferred.md`);
  each ticket keeps its id as a section inside its phase file.

## Right now

The Wren build is complete except for external shipping gates (live deploy needs
credentials, clean LLM-judged eval numbers need a paid key, the demo video needs
a human). The Agencx change work - rebrand, money guardrail loosening, tool
gating, three-screen nav, lean flow, provider strategy, pre-load, login-in-chat -
is defined ticket-by-ticket in `spec/`. Phases 1 and 2 of the spec are closed:
Foundation (A-1/A-2), login-in-chat (O-2), and the lean onboarding re-cut (O-1)
are landed. The chat spine (`03-chat-spine.md`) is in progress on
`feat/chat-spine`, in the order P-4 -> O-4 -> P-3 -> P-1 -> P-2 -> P-5 (O-4 is
pulled forward from `04-chat-grounding.md` because P-3's fast path calls its
`get_business_context` seam).

## Feature status matrix

### Foundations & tenancy

| Feature | Status | Evidence / change |
|---|---|---|
| Monorepo scaffold + Makefile | BUILT | `b910a50` |
| Full schema + forward-only migrations | BUILT | `3d070d5`; schema documented in `design/database.md` |
| RLS enforcement + schema audit | BUILT | `c0b798b` (audit teeth), `d1826e4` |
| Auth + tenant provisioning (Supabase) | BUILT | `d1826e4`; **CHANGING** - O-2 adds login-in-chat (email + 6-digit code) on the tenant surface; Supabase stays the identity layer |
| Tenant resolution by slug | BUILT | `075e17a`; **CHANGING** - B-2 points the public domain to agencx.app |
| Onboarding conversation (LLM extract + confirm) | BUILT | `d92ca24`, `0aba966`, `e72de5f`, extraction-robustness fix; re-cut by O-1 to one `save_profile` tool + an LLM turn loop (extract -> save -> ask missing -> deflect). Seven text beats, no chips; confirm writes `tenant_config.config->profile` |
| Login-in-chat email + 6-digit code | BUILT | O-2 (`auth_codes` table 0017, `services/auth_codes.py` + email seam + session mint, `/api/auth/login-code` + `/verify-code`, in-chat login UI) |
| URL scrape knowledge ingest path | NEW | O-3 (document upload path is built; URL fetch is a new ingest route) |

### Knowledge & retrieval

| Feature | Status | Evidence / change |
|---|---|---|
| Knowledge upload (PDFs, text) | BUILT | `8a7b472`; **CHANGING** - O-3 adds document upload + URL scrape into the chat/FileDropzone surface |
| Chunk + embed pipeline | BUILT | `d8b0a43` |
| Hybrid retrieval (dense + sparse + RRF + rerank) | BUILT | `9c27859`, `0dd266e` (reranker score normalization) |
| Golden retrieval set + eval | BUILT | `182985a` |
| `get_business_context` seam | BUILT | O-4 (`app/services/retrieval.py`): whole-corpus fast path under a measured token budget, hybrid pipeline above it, one shape |
| Knowledge version + context-package cache | BUILT | P-4 derivation (0018 + `services/knowledge_version.py`) + P-3 package cache keyed by `(tenant_id, knowledge_version)` |

### Agents & the money boundary

| Feature | Status | Evidence / change |
|---|---|---|
| LangGraph graph skeleton | BUILT | `82322b9`; re-cut by P-3 to supervisor-with-tools: a fast-path turn is one call plus inspection, and the draft node is skipped (it still serves tool routes and every redraft) |
| Supervisor routing | BUILT | `731b622`, `27662e8` (conversation capability); **CHANGING** - D-1/D-2 build tools from the tenant enabled set; lean default |
| Knowledge agent | BUILT | `0b99a71` |
| Recommendation agent | BUILT | `c023918`; **CHANGING** - optional per-tenant tool (D-1), off by default |
| Deterministic pricing engine | BUILT | `eda876f`; **CHANGING** - engine runs only for quote-enabled tenants (D-1) |
| Quoting agent | BUILT | `8e6b9e5`; **CHANGING** - optional per-tenant tool, off by default |
| Order/ticket lookup | BUILT | `ecd2b31`; **CHANGING** - optional per-tenant tool, off by default |
| Escalation agent + terminal handoff | BUILT | `c10b742`; stays the one tool in the lean default |
| Reasoning-inspection layer | BUILT | `e4db924`; stays as the last gate before stream |
| Money guardrail (price provenance) | BUILT | `7247a1c`; **CHANGING** - C-1..C-4 loosen the allowed set to include figures verbatim in owner material; engine output becomes one of three allowed sources |
| Cross-tenant leakage test | BUILT | `e7be3d2`; stays an absolute gate |
| Spotlight delimiter fence | BUILT | `598f3a7`; stays |

### Eval, observability & operations

| Feature | Status | Evidence / change |
|---|---|---|
| Generation eval (faithfulness, relevancy, citation) | BUILT | `aed2086`; **CHANGING** - G-1 re-cuts cases for the lean toolset |
| Judge calibration | BLOCKED | `19d68e0` - needs founder hand-labeling (circular if agent-generated) |
| Golden agent-task set + trajectory scorer | BUILT | `22f9cae`, `cd868c4`; **CHANGING** - G-1 updates for the supervisor-with-tools shape |
| Prompt-injection defense + adversarial set | BUILT | `598f3a7` |
| Per-tenant cost/step caps + timeouts | BUILT | `ad07483`; **CHANGING** - P-2 replaces the timeout behavior with the 4s/10s first-wins failover budget |
| CI regression gate | BUILT | `46c3be4`; **CHANGING** - F-2 wires import-boundary enforcement in CI |
| Tracing + cost accounting | BUILT | `e2f5034`; **CHANGING** - P-1/P-2 track per-provider TTFT and failover events |
| Tenant admin console (conversations, escalations, pricing) | BUILT | `daea6d3`, `b9b561f`; **CHANGING** - E-1/E-2 re-cut to Chat + Business (bottom tab bar on mobile, D18); advanced screens hidden from nav |
| Tenant dashboards (cost + eval) | BUILT | `1aab440`, `cb9905c`; **CHANGING** - hidden from the tenant nav (E-2) |
| Platform-owner surface | BUILT | `b8a2f5b`, `07b8b13`; stays minimal (E-3) |
| Customer chat surface (final polish) | BUILT | `c0adc77`; **CHANGING** - P-5 adds the failover typing indicator; rebrand (B-1) |
| Full visual rebrand (M3 system, crimson primary) | BUILT | `cc30fc5`, `86b03d9`, `5d2bb7d`; **CHANGING** - D-17 swaps the font to Plus Jakarta Sans (token-level) |
| Marketing pages | BUILT | `b2c46e9`, `27537d7`; **CHANGING** - B-1 copy rename to Agencx |

### Deployment & portfolio

| Feature | Status | Evidence / change |
|---|---|---|
| Terraform AWS backend | BUILT | `d368b03`; live `terraform apply` is a founder step (needs AWS secrets) |
| Deploy end-to-end (CI image push + Vercel) | BLOCKED | needs founder AWS/Vercel/Supabase credentials; `deploy.yml` no-ops gracefully |
| Generalization proof (dental, config-only) | BUILT | `2b8437d`; evidence in `docs/archive/artifacts/generalization-proof.md` |
| Eval report | BUILT | evidence in `docs/archive/artifacts/eval-report.md` |
| Security write-up | BUILT | evidence in `docs/archive/artifacts/security.md` |
| Demo walkthrough video | NEW | founder step, unticketed |

## Provider & latency (new Agencx work, all NEW until P-tickets land)

| Feature | Status | Ticket |
|---|---|---|
| Google AI Studio primary provider | BUILT | P-1 (gemini-3.5-flash-lite, documented tier matrix in `.env.example`) |
| Groq / Cerebras fallback + OpenRouter failover tiers | BUILT | P-1 (`LLM_FAILOVER_*` third leg; legs nest into one chain, Cerebras documented as a candidate) |
| 4s TTFT timeout + first-wins race + 10s cap | NEW | P-2 |
| Context-package pre-load on chat open | BUILT | P-3 (`services/context_package.py`, primed by the public tenant lookup) |
| knowledge_version derivation + invalidation | BUILT | P-4 (migration 0018 + `services/knowledge_version.py`) |
| Failover typing indicator (client) | NEW | P-5 |

## Spec ticket status

Tracked as the work lands. One ticket = one commit; commit message starts with
the ticket id.

**Phase 1 target (three pillars only):** (1) business onboarding, (2) customer
chat query handling, (3) the business page. Everything else defers to Phase 2 /
Stage 2 backlog (payments, quoting, scheduling, invoicing, leads, money screens
are unticketed Stage 2 - not built now). Build order: A -> {O-1, O-2} -> {P-3,
P-1, P-2, P-4, P-5} -> {O-3, O-4, C-1..C-4} -> {E-1, E-2} -> {B-1, B-3, E-3,
D-2, F-2, G-1} -> F-1. D-1/D-3/D-4 and B-2 defer.

| Ticket | Status | Commit |
|---|---|---|
| A-1 Docs restructure + archive | done | `fce4d71` |
| A-2 Pointer updates (README, AGENTS.md, memory, conventions) | done | `6ad4aa6` |
| B-1 Copy rename to Agencx | not started | |
| B-2 Domain + CORS to agencx.app | deferred (external DNS/Vercel) | |
| B-3 Semantic colour convention + lighter primary | not started | |
| C-1..C-4 Money guardrail allowed-set loosening | not started | |
| D-1, D-3, D-4 Per-tenant tool gating + toggle + tests | deferred (Phase 2) | |
| D-2 Lean default (quoting OFF) | not started (Phase 1) | |
| E-1..E-3 Three screens (Chat + Business + Public) | not started | |
| F-1..F-2 Hygiene + import boundary in CI | not started | |
| G-1 Eval cases for the lean toolset | not started | |
| P-4 knowledge_version + invalidation | done | `9960a9d` |
| P-3 Agent-ready pre-load (context package) | done | `72b4ecb` |
| P-1 Provider layer: Google/Groq/OpenRouter tiers | done | this commit |
| P-1, P-2, P-3, P-5 Providers, failover, pre-load, indicator | not started | |
| O-2 Login-in-chat: email + 6-digit code | done | `70ba4f6` |
| O-1 Onboarding: one tool + LLM turn loop | done | `ceb0f77` |
| O-3 Knowledge ingest (URL scrape + upload) | not started | |
| O-4 Whole-corpus fast path + threshold | done (pulled into the chat spine, before P-3) | this commit |

## Known gaps (not ticket failures - waiting on external setup)

- **Live LLM calls run against free-tier models** (Google AI Studio primary,
  Groq fallback in the local env; OpenRouter gemma in CI) and are prone to
  upstream 429 rate-limiting; all LLM-touching code paths are proven with
  stubbed providers in CI.
- **No hosted Supabase project yet**: real email/password login from the browser
  is blocked until it exists; backend auth is fully tested with locally minted
  tokens. The login-in-chat (O-2) work also needs an email-sending provider for
  real delivery.
- **Business type does not vary the interview (O-1, US-2).** The PRD glossary
  describes a `business_types` row carrying "a profile template and prompt
  fragments"; neither half has a consumer in Phase 1, and none of the seven
  lean fields is one a vertical should skip (a solo trader's "just me" and an
  online store's "24/7" are both useful answers). O-1 therefore captures
  `business_type` as a profile field and feeds it to the tenant's system
  prompt, and asks every tenant the same seven questions - which keeps I8
  cleanly satisfied, since no vertical name appears anywhere. Revisit when a
  real vertical needs a question the generic set does not cover.
- **Console sidebar squeeze below ~375px** (pre-existing, surfaced by the
  rebrand's 375px e2e check): resolved by design - E-1 replaces the tenant
  app's mobile nav with the bottom tab bar (D18) - but the code fix ships with
  E-1, not before.