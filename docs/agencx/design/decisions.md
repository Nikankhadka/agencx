# Agencx - Design Decisions, ADRs

The decision ledger: every consequential choice, old and new, with the reason it
was made. Nothing changes silently. The 11 decisions below were carried from
the planning phase (reasons condensed); D12-D17 are the decisions that shape the
Agencx build.

## The carried decisions (1-11)

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

## New decisions (D12-D17)

### D12: Lean-first flow - whole-corpus fast path, hybrid RAG deferred

**Decision:** Phase 1 (small business, e.g. Sababa, <~7-8k total context) runs
the lean flow: the tenant's whole corpus goes into the prompt, no retrieval
scoring. Hybrid RAG + the tool loop defer to Phase 2 (mid-large businesses,
>50k corpus + structured commerce).

**Why:** The measured Wren turn was 37s with 3-5 serial LLM calls and a
retrieval round-trip before drafting. For a small corpus the retrieval scoring
adds latency without adding information - the model can read the material
directly. The product promise is a fast grounded answer; the lean flow is how
that is achievable at free-tier cost.

**Boundary:** the corpus-size threshold is **data-driven** (measured token
count, config value), never a business-size branch (I8). The seam
`get_business_context(tenant_id, query)` owns the choice; both paths return the
same shape.

### D13: Supervisor-with-tools from day one (Phase 1 shape)

**Decision:** The customer assistant is a supervisor with tools - one model call
per turn in the common case. Phase 1 ships it with exactly one tool beyond
answering: `escalate`. Phase 2 adds search/recommend/quote/order-status as
tools on the same supervisor.

**Why:** The shape that ships must be the shape that scales. Wren's fixed
five-specialist topology needed a route call before every turn; a supervisor
that can decide and act in one call halves the serial calls from the start.
Tool-driven supervision was already Wren's planned T-044; Agencx makes it the
Phase 1 topology instead of a Phase 5 afterthought. Escalation stays the only
tool until per-tenant gating (D-1/D-2) proves the demand.

### D14: Agent-ready pre-load - context package + knowledge_version invalidation

**Decision:** When a chat opens (any surface), the backend assembles a context
package (system prompt + profile + corpus) and caches it in-process keyed by
`(tenant_id, knowledge_version)`. `knowledge_version` is derived (max document
update timestamp) - no new table. Every customer turn then makes one LLM call
against the package. Re-ingest or profile change bumps the version and
invalidates the cache.

**Why:** Perceived latency is the measured killer (37s knowledge turns). With
the package assembled before the customer ever types, time to first token is
one call away, and provider prompt caching (Groq, Google) discounts the
repeated prefix. The package makes the "agent ready when the chat opens"
pattern literal instead of aspirational.

**Cost:** a slightly stale package between invalidation and the next open -
acceptable because the package is assembled fresh on every open and the
invalidation trigger (re-ingest) is exactly the moment the tenant is actively
editing, where a few seconds of staleness is invisible.

### D15: Provider strategy - Google primary, Groq/Cerebras fallback, OpenRouter failover

**Decision:** Three tiers, all OpenAI-compatible env config:

| Tier | Provider | Model |
|---|---|---|
| Primary | Google AI Studio (free) | `gemini-3.5-flash-lite` (OpenAI-compat endpoint) |
| Fallback | Groq (free) | `openai/gpt-oss-120b` (or `gpt-oss-20b` on tighter budget) |
| Failover | OpenRouter (free) | `google/gemma-4-26b-a4b-it:free` (CI pin) |

Cerebras (llama-3.3-70b, $5+$5 credits) where Groq is unavailable; GitHub
Models excluded (8k input/request cap); the Gemini 3.x reasoning-mandatory
flash family excluded (reasoning tokens break the latency budget and the
structured extract budget). Local dev may run Z.ai GLM; CI pins gemma so gates
run deterministically.

**Why:** Verified on 2026-08-20 across provider docs and the live model list:
Google's free tier is the most generous (1M TPM, 1,500 requests/day, 15-30
RPM) with the fastest small model; Groq's LPU gives the sub-200ms fallback and
cached-prefix tokens free of the TPM count; OpenRouter's free tier is the most
independent third leg and the CI-proven structured-output default. The budget
ceiling for live testing is $10/month.

### D16: Latency budget and first-wins failover

**Decision:** The product promise is time-to-first-token <= 4s primary, 10s
hard cap to a complete answer. On timeout or hard 429 the fallback tier races
the primary; **first-wins** - the losing stream is discarded. A hard 429 skips
that provider for the session. The client shows a typing indicator through the
failover window; the customer never sees a spinner or a provider-switch notice.

**Why:** Free tiers are unreliable by nature (measured: 6x timeouts between two
runs 15 minutes apart). A timeout-based failover converts that variance into a
first-wins race the customer cannot see, and keeps the product promise honest
under free-tier conditions. The 4s/10s numbers come from the PRD speed
contract, not from any single provider's SLA.

### D17: Rebrand - Agencx name, crimson primary, Plus Jakarta Sans

**Decision:** The product is **Agencx** on every user-facing surface (B-1, B-2).
The visual identity is the existing Wren Material 3 system with its **crimson
primary** (already the shipped M3 tonal ramps in `frontend/src/styles/theme.css`,
CI-enforced by `check:tokens`) and **Plus Jakarta Sans** via `next/font` (a
token-level swap: `--font-sans` re-point, no component changes). The teal accent
from the Agencx planning design is retired, not carried forward. Copy never says
"AI", "agent", "automated" or "assistant" (PRD copy rules).

**Why:** The merge decision locked "AgenCX PRD/design, Wren's Supabase auth +
crimson primary". The Wren rebrand proved the tokens-only path (a full visual
rebrand with zero component code changes); reusing it keeps the Agencx look
consistent with the platform the code already ships. The repo, roles, and env
names stay `wren` (renaming is churn with no user value - see the set README).
The mobile-first structure does return - see D18.

### D18: Mobile-first revival - the bottom tab bar returns from the planning prototype

**Decision:** The tenant app is mobile-first. On phones (below `lg`) the two-tab
manifest - Chat and Business - renders as an app-style surface with a persistent
**bottom tab bar**; at `lg+` the left sidebar stays. One codebase, responsive; no
native app, no PWA shell in Stage 1. The bottom tab bar pattern from the Agencx
planning prototype is carried forward; the rest of the prototype stays retired
(D17 - teal accent, cleaning copy, Hivee emblem). E-1 owns the implementation.

**Why:** Small-business owners live on phones; the tenant app's two destinations
map exactly onto two bottom tabs. The planning prototype validated the app-style
mobile interaction vocabulary (chat-first, thread as progress, no celebration),
and its screen inventory and states already match the S1/S2 specs. The pattern
also replaces the hamburger drawer and fixes the known narrow-mobile sidebar
squeeze (progress.md) - mobile stops being an afterthought of the desktop shell.

**Boundary:** The customer public page (S3) is untouched - it is a shared web
link, already chat-first and mobile. D17 stands for the prototype's identity
elements (teal, cleaning copy, Hivee emblem). This decision sets the
direction; E-1 delivers the chrome.

### D19: Knowledge is one readable text the owner corrects, held until they save

**Decision:** A knowledge source - a pasted link or an uploaded file - is
extracted, then **processed into a fixed set of readable sections** (About, What
we offer, Prices, Hours, Location and contact, Policies, Other details) and
parked as a **draft**: stored, shown back, and answering nothing. It becomes
answerable only when the owner has read it and saved it, and what they saved -
their edits included - is what gets chunked, embedded and answered from. The
surface is **Settings > Knowledge** (`/settings/knowledge`), reached from a
Settings hub, and it renders the same sections it showed at review time.

**Why:** A list of files with statuses is a document manager, and it does not
scale for a real business: an owner with a dozen sources cannot tell what their
assistant actually believes by reading filenames. One structured text answers the
question they came with - "what does it think my business is?" - and makes
correction a matter of editing a sentence rather than re-uploading a file. The
draft gate exists because the first time an owner sees this text must not be
after it has already answered a customer.

**The money guard:** the processing step is a model rewriting the owner's own
material, and a price list is exactly the material it will handle. Every
monetary figure in the processed text must appear in the source, checked
deterministically with `extract_monetary_figures()` (the pricing gate's own
extractor); on any mismatch the processed version is discarded and the source
text is kept verbatim. This keeps I7 intact - a model still never authors a
monetary amount - and C-1 should adopt the same helper when it lands.

**Boundary:** the headings are the same for every business (I8 - the skeleton
does not branch on a vertical). Long sources keep their tail unstructured rather
than being cut. This decision amends the "no settings screen" ADR below: the
address changed, the substance did not - Knowledge is show-back-and-correct, not
a toggle tree.

## ADRs

### ADR: Import-boundary enforcement from first commit

The codebase enforces the deterministic boundary (I1) through an import-linter
rule in CI from the very first commit. The rule forbids importing
`llm/provider.py` outside `agents/` and `llm/`. The frontend carries an
equivalent ESLint `no-restricted-imports` rule. Both are wired in CI.

The violation that matters is the one added later under time pressure, so the
check must predate the pressure. Determinism is a property of the module graph,
not of willpower.

### ADR: No settings screen - Business tab as show-back only

The tenant app has no settings tree, no configuration screen, and no
toggle-only preferences. The second tab - **Business** - displays the profile
and knowledge the owner gave the agent, shown back so they can trust and
correct it. Every configuration change happens through conversation with the
Copilot, never through a form.

The product thesis is that the agent, not the owner, should absorb the
paperwork. If a setting can only exist as a toggle on a screen, it should not
exist. If the Business tab fails the trust test with a real cohort, the
decision is revisited - the signal is logged, not assumed away.

**Exception:** the Business tab carries the thin, product-required toggles the
PRD names: live/not-live state, the share link + QR, and the enabled-tools
toggle (D-1/D-3). These are scope, not settings-tree creep.

**Amended by D19 (2026-08-22):** a Settings destination does exist, and it holds
the Knowledge screen. It carries no toggles and no preferences - it is the
show-back surface this ADR asks for, at a different address. The rule the ADR
protects ("if a setting can only exist as a toggle on a screen, it should not
exist") is unchanged.