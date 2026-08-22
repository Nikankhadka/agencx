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
Foundation (A-1/A-2), login-in-chat (O-2), the lean onboarding re-cut (O-1), and
the onboarding UI port (O-5) are landed. The chat spine (`03-chat-spine.md`) is
landed except P-5.

**Chat grounding (`04-chat-grounding.md`) is closed** on `feat/money-guardrail`:
O-3, O-4, then C-1, C-2, C-3, C-5, C-6, C-4. The assistant can now state a price
the owner published, every reply passes one deterministic figure check, a handoff
no longer ends the conversation, and staff can take a conversation over and hand
it back. **C-6 is a ticket added during the build** (founder request, 2026-08-22)
and is spec'd in the phase file like the rest. `05-business-page.md` is re-cut by **D21**
into four tickets - E-1 (the three-tab shell: Home, Chats, Business), E-4 (Home
and its brief), E-5 (Business hub + Booking page), E-2 (hide the advanced
screens). **E-1, E-4 and E-5 are landed**: the hamburger drawer is gone,
the bottom tab bar below `lg` closes the long-standing 375px sidebar squeeze,
`/chats` and `/settings` render inside the shell, Home greets the owner with
what needs them, and Business is a hub with its Booking page and share link.
Next is E-2, with P-5 still outstanding from the chat spine and the Booking
page's QR waiting on a dependency decision.

O-3 pulled the **Settings > Knowledge** slice of S2 forward (D19), the way O-5
pulled B-3 US-1 forward; C-6 has now done the same for the **Chats** screens -
`/chats` and `/chats/[id]` are mounted chrome-free until E-1's tab bar re-homes
them, and the Wren-era `/conversations` and `/escalations` console pages stay
mounted for E-2 to hide (E-2's posture, applied early).

O-5 pulled **B-3 US-1** (the lighter crimson `#C1123F`) forward, because the
prototype the onboarding thread is ported from carries that ramp - B-3 stays
open for US-2, the `STATUS_TONE` map.

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
| Onboarding UI (the prototype thread) | BUILT | O-5: `/login` + `/onboarding` ported from `agencx-prototype-v6.html`'s ONBOARDING screen onto shared `components/ui/Thread.tsx` primitives. Chrome-free, no title, no progress surface; every prototype value a `theme.css` token |
| Login-in-chat email + 6-digit code | BUILT | O-2 (`auth_codes` table 0017, `services/auth_codes.py` + email seam + session mint, `/api/auth/login-code` + `/verify-code`, in-chat login UI); O-5 adds `services/email_address.py` - prose extraction + syntax validation, answered as one calm line |
| URL scrape knowledge ingest path | BUILT | O-3: pasting a link in the onboarding thread scrapes it, ingests it as a `website` document, and reads back what it found; attaching a file works from the command pill's `+`. Images are refused (nothing reads them) |
| Settings > Knowledge screen | BUILT | O-3 / D19: a source is processed into readable sections the owner corrects, held as a draft until they save it. Mobile-first, built from the prototype's destination screens. Pulled forward from S2; E-1 re-homes it in the two-tab shell |

### Knowledge & retrieval

| Feature | Status | Evidence / change |
|---|---|---|
| Knowledge upload (PDFs, text) | BUILT | `8a7b472`; O-3 added `.docx` (stdlib zipfile, no dependency) and put attaching inside the onboarding thread |
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
| Escalation agent + handoff | BUILT | `c10b742`; **no longer terminal** - C-5 made a handoff a notification, C-6 added staff takeover/handback (`'human'` status, migration 0020). Only a tenant limit ends a conversation now |
| Reasoning-inspection layer | BUILT | `e4db924`; stays as the last gate before stream |
| Money guardrail (price provenance) | BUILT | `7247a1c`; C-1 added owner material as a third allowed source (plus a hedge rule), C-2 put the gate on every route, C-3 added the prompt half, C-4 the 21-case matrix in the absolute gate |
| Cross-tenant leakage test | BUILT | `e7be3d2`; stays an absolute gate |
| Spotlight delimiter fence | BUILT | `598f3a7`; stays |

### Eval, observability & operations

| Feature | Status | Evidence / change |
|---|---|---|
| Generation eval (faithfulness, relevancy, citation) | BUILT | `aed2086`; **CHANGING** - G-1 re-cuts cases for the lean toolset |
| Judge calibration | BLOCKED | `19d68e0` - needs founder hand-labeling (circular if agent-generated) |
| Golden agent-task set + trajectory scorer | BUILT | `22f9cae`, `cd868c4`; **CHANGING** - G-1 updates for the supervisor-with-tools shape |
| Prompt-injection defense + adversarial set | BUILT | `598f3a7` |
| Per-tenant cost/step caps + timeouts | BUILT | `ad07483`; P-2 adds the 4s TTFT race and the per-turn `turn_budget_s` cap alongside the existing per-call timeouts |
| CI regression gate | BUILT | `46c3be4`; **CHANGING** - F-2 wires import-boundary enforcement in CI |
| Tracing + cost accounting | BUILT | `e2f5034`; P-2 adds `ttft_ms` / `leg` / `failover_engaged` / `skip_reason` to the turn record |
| Business hub + Booking page | BUILT | E-5: the `.bh-row` hub (Booking page, Settings - Stage 2's Schedule/Money/Plan absent, not disabled) and the booking screen: profile show-back plus the public link, derived from the host via `surfaceUrl()`. **QR outstanding** - needs a dependency decision, see known gaps |
| Home: the greeting and the brief | BUILT | E-4: the prototype's `showMorningBrief()` / `addCard()` ported, carrying only kinds backed by real Stage 1 state (customers waiting, knowledge drafts unsaved, the share nudge). Composed client-side from `/api/conversations` + `/api/knowledge/records`; `BriefItem` is the contract a Stage 2 `/api/brief` inherits |
| Tenant admin console (conversations, escalations, pricing) | BUILT | `daea6d3`, `b9b561f`; C-6 added the prototype's **Chats** list + thread (`/chats`), whose "Action needed" filter is the owner's queue; E-1 re-cut the shell to Home + Chats + Business (bottom tab bar below `lg`, sidebar at `lg+`; D18 as amended by D21), retired the hamburger drawer, and re-homed `/chats` and `/settings` inside it; **CHANGING** - E-2 marks the advanced screens hidden, E-4 fills Home, E-5 builds the Business hub's Booking page |
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
| 4s TTFT timeout + first-wins race + 10s cap | BUILT | P-2 (`llm/failover.py` race + `turn_budget_s` cap; live-verified on Gemini/Groq) |
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
P-1, P-2, P-4, P-5} -> {O-3, O-4, C-1..C-5} -> {E-1, E-2} -> {B-1, B-3, E-3,
D-2, F-2, G-1} -> F-1. D-1/D-3/D-4 and B-2 defer. The E block is four tickets
since D21: E-1 (the three-tab shell) -> E-4 (Home and its brief) -> E-5
(Business hub + Booking page) -> E-2 (hide the advanced screens).

| Ticket | Status | Commit |
|---|---|---|
| A-1 Docs restructure + archive | done | `fce4d71` |
| A-2 Pointer updates (README, AGENTS.md, memory, conventions) | done | `6ad4aa6` |
| B-1 Copy rename to Agencx | not started | |
| B-2 Domain + CORS to agencx.app | deferred (external DNS/Vercel) | |
| B-3 Semantic colour convention + lighter primary | US-1 done (O-5), US-2 not started | |
| C-1 Money guardrail: verbatim owner material | done | `bee1775` |
| C-2 Gate every reply, not just money routes | done | `70a0ea1` |
| C-3 Prompt rule: state figures exactly as listed | done | `6b043b6` |
| C-4 Money guardrail test matrix (absolute gate) | done | `dcd5f59` |
| C-5 Non-blocking escalation (chat continues after handoff) | done | `0137d20` |
| C-6 Human takeover: staff step in, and hand back | done | `e3e9019` |
| D-1, D-3, D-4 Per-tenant tool gating + toggle + tests | deferred (Phase 2) | |
| D-2 Lean default (quoting OFF) | not started (Phase 1) | |
| E-1 Three-tab shell (Home + Chats + Business) | done | this commit |
| E-4 Home: the greeting and the brief | done | this commit |
| E-5 Business hub + Booking page | done (QR outstanding) | this commit |
| E-2 Hide advanced screens, keep code | not started | |
| E-3 Platform admin stays minimal | not started | |
| F-1..F-2 Hygiene + import boundary in CI | not started | |
| G-1 Eval cases for the lean toolset | not started | |
| P-4 knowledge_version + invalidation | done | `9960a9d` |
| P-3 Agent-ready pre-load (context package) | done | `72b4ecb` |
| P-1 Provider layer: Google/Groq/OpenRouter tiers | done | `a8fd09f` |
| P-2 Latency budget + first-wins failover | done | this commit |
| P-5 Typing indicator through the failover window | not started | |
| O-2 Login-in-chat: email + 6-digit code | done | `70ba4f6` |
| O-1 Onboarding: one tool + LLM turn loop | done | `ceb0f77` |
| O-5 Onboarding UI: prototype thread port | done | this commit |
| O-3 Knowledge ingest (URL scrape + upload) | done | `29fd5a5` |
| O-4 Whole-corpus fast path + threshold | done (pulled into the chat spine, before P-3) | this commit |

## Known gaps (not ticket failures - waiting on external setup)

- **The Booking page has no QR** (E-5). The PRD names "share link + QR" and the
  link half shipped; nothing in the repo generates a QR, and QR encoding is a
  spec-defined algorithm with Reed-Solomon error correction and mask selection
  - hand-rolling it would be worse code than a mature ~10KB dependency, and
  adding a dependency is a founder call (conventions: "No new dependency if it
  can be avoided"). Flagged, not decided.

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
