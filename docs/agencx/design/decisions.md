# Agencx - Design Decisions, ADRs

The decision ledger: every consequential choice, old and new, with the reason it
was made. Nothing changes silently. The 11 decisions below were carried from
the planning phase (reasons condensed); D12 onward are the decisions that shape
the Agencx build.

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

**Amended by D21 (2026-08-22):** the manifest is three tabs, not two - Home
joins Chat and Business. Everything else here stands unchanged.

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

### ADR: Import-boundary enforcement in CI

The codebase enforces the deterministic boundary (I1) with machine checks in
CI, because the violation that matters is the one added later under time
pressure. Determinism is a property of the module graph, not of willpower.

**Corrected 2026-08-22 (F-2), on two counts.** This ADR said the rule had been
in CI "from the very first commit". It had not: there was no import-linter
config, no ESLint rule and no AST test anywhere in the repo until F-2 wired
them. The ADR described an intention in the present tense for the length of the
build, which is worse than an admitted gap - nobody goes looking for a check
they have been told exists.

It also described the wrong contract. "Forbid importing `llm/provider.py`
outside `agents/` and `llm/`" fails on a dozen files today, and correctly so:
`features/chat`, `features/knowledge` and `features/onboarding` import
`LLMProvider` as a FastAPI dependency-injection annotation, which is how a
route receives a provider at all. Banning that would not protect determinism,
only wiring.

**What is enforced** (contracts in `backend/pyproject.toml`, run by
`make lint-backend` and CI):

1. **Pricing never reaches a model** - `app.pricing` may not import
   `app.llm`, `app.agents`, `app.onboarding` or `app.retrieval`. This is the
   hard rule itself; `engine.py` has always declared it in a docstring, and now
   a build fails on it.
2. **The deterministic services layer never asks a model for words** -
   `app.services` may not import `app.llm.provider` or `app.agents`.
   `app.llm.embedder` is deliberately allowed: an embedder turns text into a
   vector, and O-4's retrieval seam cannot work without one. The rule is about
   authorship, not arithmetic.
3. **The provider seam is a leaf** - `app.llm` may not import `app.features`,
   `app.agents`, `app.onboarding` or `app.pricing`, so swapping a provider by
   config cannot move anything above it.

The frontend carries the equivalent: `components/ui/**` may not import
`@/lib/api` or `@/lib/useApiQuery` (ESLint `no-restricted-imports`). The shared
library is presentational - a component that fetched its own data would decide
when a request happens from inside a render tree.

All four held on the day they were written, so they lock a property rather than
announce a migration. Each was proven to fail on a deliberately planted
violation before being trusted.

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

---

## D20: an escalation notifies; a takeover is what changes who is replying

**Date:** 2026-08-22 (C-5 / C-6). **Status:** accepted.

The schema had one terminal `escalated` status doing two jobs, and the result
was that any handoff ended the conversation. One unanswerable pricing question
could dead-end a support session that was working fine for everything else.

They are separate concerns and the code now says so:

- **An escalation is a notification** - "a human should look at this". It writes
  a queue row and says nothing about who is replying. The assistant keeps
  helping (C-5).
- **A takeover is a mode** - `conversations.status = 'human'`. A staff member is
  the voice; the assistant is silent until handed back (C-6). Reversible, and
  the interlude stays in the transcript so the assistant reads what the human
  said rather than contradicting it.
- **`'escalated'` means a limit stopped it.** Daily budget, step cap, turn
  budget. Written only by `record_limit_escalation`. This is the one hard stop,
  and it is the behaviour being paid for.

**A provider failure is not a limit.** It was originally routed through the
terminal path because it is another way a turn dies, but an upstream fault the
customer had no part in should not end their conversation - it hands off
non-terminally and invites them to try again. This was found by the C-6 E2E,
which the free-tier provider failed into on its first run.

**Consequence for the owner surface:** the escalations queue stops being a
separate destination - it is the "Action needed" filter on the Chats list, where
the owner already is. The Wren-era `/escalations` and `/conversations` screens
stay mounted for E-2 to hide.

---

## D21: three tabs, and Home is a place

**Date:** 2026-08-22 (pre-E-1, founder). **Status:** accepted. **Amends D18.**

The tenant app has **three** top-level destinations, not two:

- **Home** - the owner's own thread with the assistant, and the surface that
  greets them with what needs them today.
- **Chats** - the customers' threads with the assistant, and where the owner
  steps into one (C-6).
- **Business** - the hub: the show-back of what the assistant knows, the
  booking page and share link, Settings. Its rows are what grows in Stage 2.

Below `lg` these render as the bottom tab bar D18 established; at `lg+` they are
the left sidebar. One nav model, two renderings.

**Why:** two tabs could not name three places, and the prototype shows the
strain. In `agencx-prototype-v6.html` the home Copilot thread - greeting,
morning brief, command pill - is the base layer *underneath* the tab bar with no
tab of its own, and `navBack()` lights the **Chats** tab when you land back on
it. "Your thread with the assistant" and "customers' threads with the
assistant" are different destinations; collapsing them is exactly why that back
behaviour reads as muddled. Naming Home makes the third place addressable and
gives the brief somewhere to live.

**Why not a sidebar/drawer instead of the tab bar.** On a phone a sidebar is a
hamburger drawer: two taps to every destination, and no persistent answer to
"where am I". D18 retired it for that reason, and it is the cause of the
≤375px squeeze still open in `progress.md`. The founder's proposed row list -
Chats, Money, Business page, Settings - is the prototype's **Business hub**
(`renderScreen('business')`), not its top-level nav, and it stays there.

**Boundary:** this amends D18's tab count and nothing else. Mobile-first, the
tab-bar idiom, the retired drawer, and the untouched public page (S3) all stand.
**Money, Schedule and Plan remain Business-hub rows that Stage 2 adds** - they
are never top-level tabs, and until Stage 2 they are absent rather than
disabled (PRD, "never build dead surfaces"). Home's brief carries only item
kinds backed by real state; Stage 2's quote and order approvals arrive as new
kinds in the same list, not as new screens.
