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
screens). **The phase is closed** - E-1, E-4, E-5 and E-2 all
landed. The hamburger drawer is gone, the bottom tab bar below `lg` closes the
long-standing 375px sidebar squeeze, `/chats` and `/settings` render inside the
shell, Home greets the owner with what needs them, Business is a hub with its
Booking page and share link, and the Wren-era operator screens are unlinked
while still serving and still tested. **`06-polish.md` is closed too** - P-5, B-1, B-3,
E-3, D-2, F-2 and G-1 all landed. What remains for Stage 1 is `07-hygiene.md`
(F-1), plus the two findings in Known gaps that want tickets of their own: the
Google tier's `thought_signature` rejection, and the absent everyday owner
Copilot.

**The prototype-parity work is merged** (2026-08-23). `feat/docker-dev-stack`
went to `main` first so both lines shared one base - K-1's containerized dev
stack (`3453b85`, `213f6f6`) plus the deploy runbook (`b3e578d`) - and
`feat/prototype-parity-onboarding` was rebased onto it and fast-forwarded in,
one commit per ticket rather than squashed, so the hashes in the table below
each point at their own ticket. It carries five tickets (O-6, O-7, O-8, E-6,
O-9) and four supporting commits: E-5's live/not-live bullet ruled void
(`c1028ca`), `design/frontend.md` catching up with both (`6ba8a86`), `make
dev-reset` for the Turbopack cache trap that cost an hour during E-6
(`5bcefa1`), and the e2e fix for `next dev` serving a half-rendered page
(`b438b95`). Verified before the merge: `make ci` green - lint, the three
import contracts, typecheck, 78 frontend and 747 backend tests, format-check,
production build - and the full Playwright suite **71 of 71**, where the
baseline before the container fix was 56 passing with 8 failing.

**The deploy is B-4** (`spec/10-deploy.md`, 2026-08-24). The whole product
ships as one Vercel project running two container services - `vercel.json`
routes `/api/*` and `/health` to the backend and everything else to the
frontend, so all three surfaces serve from one origin and the browser never
makes a cross-origin request in production. That supersedes both earlier plans:
the AWS ECS/Terraform stack (`infra/*.tf`, kept and dormant, still validated by
CI) and the Google Cloud Run backend `deploy.md` described before. The
production image stays lean, so the deploy embeds through Google's hosted API
(`GoogleEmbedder`, truncated to the schema's 384 dims) and reranks through
Cohere. Two CI/CD breakages were found and fixed in the same ticket: this repo
has `development` and `staging` and no `main`, so `ci.yml`'s `[main]` push
filter meant pushes were never gated and `deploy.yml` had never fired once; and
`deploy.yml` was still deploying the backend to AWS ECS. `staging` is now the
production branch, `deploy.yml` builds nothing (Vercel's Git integration
deploys) and smoke-tests the live origin instead, and the backend suite runs
inside the shipping image's `test` stage so a test that quietly needs
torch/sentence-transformers fails in CI rather than at deploy.

That `test` stage caught something on its very first run, and `54cc0cd` fixed it:
every eval that writes an `eval_runs` row died with `FileNotFoundError: 'git'`. The
lean image carries no git binary and `.dockerignore` keeps `.git/` out of the build
context, so the shell-out cannot succeed there by construction, and the `check=False`
already on it does not help - a missing binary fails at exec, before there is a return
code. The helper had been copy-pasted byte for byte into six eval modules, so the guard
went into one shared `evals/_git.py::git_sha()` and the six copies went: 60 lines
deleted, 18 added, two unit tests pinning both ways a SHA can be unknowable. An eval
run in the image now records an empty SHA instead of crashing.

O-3 pulled the **Settings > Knowledge** slice of S2 forward (D19), the way O-5
pulled B-3 US-1 forward; C-6 has now done the same for the **Chats** screens -
`/chats` and `/chats/[id]` are mounted chrome-free until E-1's tab bar re-homes
them, and the Wren-era `/conversations` and `/escalations` console pages stay
mounted for E-2 to hide (E-2's posture, applied early).

**Offerings + media is designed (D24, `11-offerings-media.md`, 2026-08-28).**
A Codex CLI session on `feat/offerings-media-import` set out to
close G5.1 (the cover photo's Postgres `bytea` storage) and, working through
the actual product need with the founder, widened it into a real design: the
Booking page's "Services" list becomes an owner-writable `Offering` (the
locked domain noun), reusable business media moves to Cloudinary (a capped
5-image gallery + optional per-offering photos), and knowledge ingestion gets
an import-and-confirm step so an uploaded menu/price list can propose
structured offerings the owner reviews once rather than re-typing. That
session hit its Codex usage limit at the exact moment it said it would record
this in the canonical docs - the branch had zero commits and nothing was
written down. This session recovered the design from the session transcript,
cross-checked every claim against the current code, and wrote it up as D24
plus tickets `M-1`/`M-2`/`M-3`. `M-1` is built: the physical table is
`offerings`, the owner edits it from Business, and the catalog projection never
reaches general-knowledge fast paths. **`M-4` followed it** (added during the
build, founder request 2026-08-28) and put what `M-1` made writable in front of
a customer: `/{slug}` is a storefront now - offerings with the owner's own
prices, an About section, links, and the assistant a tap away in a
sheet rather than the whole page - and the owner chooses that address at
go-live instead of keeping the provisional `biz-…` slug. `M-2` is additionally
blocked on the founder provisioning Cloudinary credentials; `M-3` has not
started, and now inherits a price-carrying writer.

**Two abandoned attempts sit behind `M-1`/`M-4`, and the record is the point.**
A Codex session built `M-1` on `feat/offerings-media-import` and renamed
`catalog_items` to `offerings`; a second, on `feat/business-storefront`, built
the storefront but kept `catalog_items`, reversed the rename in its own
migration, and dropped prices from offerings entirely. The founder ruled on
both open questions - the rename stands, and prices are owner-typed facts that
belong on the page (D24) - so the first branch merged to `development` as
`M-1` and the second was rebuilt on top of it as `M-4`. Nothing was thrown
away except the reversal migration. The dev database carried both experiments
plus a `0023_storefront_gallery.sql` that exists in no branch, so it was reset
from schema zero to prove `0001`-`0024` apply in order.

O-5 pulled **B-3 US-1** (the lighter crimson `#C1123F`) forward, because the
prototype the onboarding thread is ported from carries that ramp - B-3 stays
open for US-2, the `STATUS_TONE` map.

## Feature status matrix

### Foundations and tenancy

| Feature | Status | Evidence / change |
|---|---|---|
| Monorepo scaffold + Makefile | BUILT | `b910a50` |
| Full schema + forward-only migrations | BUILT | `3d070d5`; schema documented in `design/database.md` |
| RLS enforcement + schema audit | BUILT | `c0b798b` (audit teeth), `d1826e4` |
| Auth + tenant provisioning (Supabase) | BUILT | `d1826e4`; O-2 added login-in-chat (email + 6-digit code) on the tenant surface; **CHANGED** (2026-08-28) - the auth migration (D23) moved code issuance and session minting onto GoTrue itself (`signInWithOtp`/`verifyOtp` + `@supabase/ssr` cookies), replacing the backend-minted session O-2 shipped |
| Tenant resolution by slug | BUILT | `075e17a`; **CHANGED** - D22 moved the slug from a subdomain to a path (`agencx.app/{slug}`); the resolver itself is untouched |
| Onboarding conversation (LLM extract + confirm) | BUILT | `d92ca24`, `0aba966`, `e72de5f`, extraction-robustness fix; re-cut by O-1 to one `save_profile` tool + an LLM turn loop (extract -> save -> ask missing -> deflect). Seven text beats, no chips; confirm writes `tenant_config.config->profile`. Unticketed founder follow-up (2026-08-22): after the seven fields the interview offers a skippable website/documents ask (paste a link, attach a file, or "skip"), and confirm lands the owner on `/home` in-session rather than stranding them on the go-live line  **O-6 (founder walkthrough, 2026-08-23) put the prototype's chips back**: a chip sends its label as ordinary text on the same route a typed answer uses, so the one-tool loop is untouched and only `Beat.chips` is new. Two chips instead swap the composer - the contact beat's phone pill (ported `initPhone()`, AU/NZ/US/UK/SG) and the ABN beat's welded `.abn-pill`. `abn` and `gst` are new beats; `gst` is conditional on the answer to `abn`, not on the vertical. O-7 made a link that cannot be read say so and log why; O-8 stopped go-live blanking the thread. O-9 gives the two new fields a screen. O-10 gives the interview a clear voice: it introduces the owner-facing “Agencx setup assistant”, acknowledges answers warmly, asks one simple question at a time, and explains that saved links and documents become customer-answer references. **O-11 captures only explicitly named offerings during onboarding and creates deduplicated active catalog rows with blank prices at go-live, rebuilding the catalog once.** The rest of the profile stays frozen after go-live. |
| Onboarding UI (the prototype thread) | BUILT | O-5: `/login` + `/onboarding` ported from `agencx-prototype-v6.html`'s ONBOARDING screen onto shared `components/ui/Thread.tsx` primitives. Chrome-free, no title, no progress surface; every prototype value a `theme.css` token |
| Login-in-chat email + 6-digit code | BUILT | O-2 shipped it backend-owned (`auth_codes` table 0017, `services/auth_codes.py` + email seam + session mint, `/api/auth/login-code` + `/verify-code`); the interaction remains the same, except the resend control now follows GoTrue's 60-second production cadence. The auth migration (2026-08-28, D23) moved issuance and verification onto GoTrue's own OTP (`signInWithOtp`/`verifyOtp`) and deleted that machinery, `auth_codes` (0022) included. O-5's prose-extraction module (`services/email_address.py`) went with it - the login page's existing composer regex plus GoTrue's own rejection cover the same ground client-side |
| URL scrape knowledge ingest path | BUILT | O-3: pasting a link in the onboarding thread scrapes it, ingests it as a `website` document, and reads back what it found; attaching a file works from the command pill's `+`. Images are refused (nothing reads them) |
| Settings > Knowledge screen | BUILT | O-3 / D19: a source is processed into readable sections the owner corrects, held as a draft until they save it. Mobile-first, built from the prototype's destination screens. Pulled forward from S2; E-1 re-homes it in the two-tab shell |

### Knowledge and retrieval

| Feature | Status | Evidence / change |
|---|---|---|
| Knowledge upload (PDFs, text) | BUILT | `8a7b472`; O-3 added `.docx` (stdlib zipfile, no dependency) and put attaching inside the onboarding thread |
| Chunk + embed pipeline | BUILT | `d8b0a43` |
| Hybrid retrieval (dense + sparse + RRF + rerank) | BUILT | `9c27859`, `0dd266e` (reranker score normalization) |
| Golden retrieval set + eval | BUILT | `182985a` |
| `get_business_context` seam | BUILT | O-4 (`app/services/retrieval.py`): whole-corpus fast path under a measured token budget, hybrid pipeline above it, one shape |
| Knowledge version + context-package cache | BUILT | P-4 derivation (0018 + `services/knowledge_version.py`) + P-3 package cache keyed by `(tenant_id, knowledge_version)` |

### Agents and the money boundary

| Feature | Status | Evidence / change |
|---|---|---|
| LangGraph graph skeleton | BUILT | `82322b9`; re-cut by P-3 to supervisor-with-tools: a fast-path turn is one call plus inspection, and the draft node is skipped (it still serves tool routes and every redraft) |
| Supervisor routing | BUILT | `731b622`, `27662e8` (conversation capability); **CHANGING** - D-1/D-2 build tools from the tenant enabled set; lean default |
| Knowledge agent | BUILT | `0b99a71` |
| Recommendation agent | BUILT | `c023918`; **CHANGING** - optional per-tenant tool (D-1), off by default |
| Deterministic pricing engine | BUILT | `eda876f`; **CHANGING** - engine runs only for quote-enabled tenants (D-1) |
| Lean tool default | BUILT | D-2 (migration 0016): `tenant_config.enabled_tools` defaults to `["search_knowledge","create_escalation"]` and legacy rows carrying the old full list were backfilled. Tenant 1 states the full set to demo the commerce tools; tenant 2 inherits the default, which is the I8 proof. **Nothing reads the column until D-1** - the data is made honest first so D-1's arrival cannot silently switch quoting on for existing tenants |
| Quoting agent | BUILT | `8e6b9e5`; **CHANGING** - optional per-tenant tool, off by default |
| Order/ticket lookup | BUILT | `ecd2b31`; **CHANGING** - optional per-tenant tool, off by default |
| Escalation agent + handoff | BUILT | `c10b742`; **no longer terminal** - C-5 made a handoff a notification, C-6 added staff takeover/handback (`'human'` status, migration 0020). Only a tenant limit ends a conversation now |
| Reasoning-inspection layer | BUILT | `e4db924`; stays as the last gate before stream |
| Money guardrail (price provenance) | BUILT | `7247a1c`; C-1 added owner material as a third allowed source (plus a hedge rule), C-2 put the gate on every route, C-3 added the prompt half, C-4 the 21-case matrix in the absolute gate |
| Cross-tenant leakage test | BUILT | `e7be3d2`; stays an absolute gate |
| Spotlight delimiter fence | BUILT | `598f3a7`; stays |

### Eval, observability and operations

| Feature | Status | Evidence / change |
|---|---|---|
| Generation eval (faithfulness, relevancy, citation) | BUILT | `aed2086`; G-1 took the refusal set from 3 obviously-off-topic cases to 12, adding the in-domain-but-unstated kind (crypto, instalments, student discount, Sunday hours) - each verified absent from tenant 1's corpus first |
| Judge calibration | BLOCKED | `19d68e0` - needs founder hand-labeling (circular if agent-generated) |
| Golden agent-task set + trajectory scorer | BUILT | `22f9cae`, `cd868c4`; G-1 added 6 lean cases (30 -> 36) asserting the outcome the lean default produces - answered from the corpus, no quote row, every figure sourced. The step-efficiency table was already current: C-2 and P-3 kept it so |
| Prompt-injection defense + adversarial set | BUILT | `598f3a7` |
| Per-tenant cost/step caps + timeouts | BUILT | `ad07483`; P-2 adds the 4s TTFT race and the per-turn `turn_budget_s` cap alongside the existing per-call timeouts |
| CI regression gate | BUILT | `46c3be4`; F-2 added the import boundary - three import-linter contracts (pricing never reaches a model, services never ask one for words, the provider seam is a leaf) plus the frontend's presentational-UI rule. The ADR claiming this had been enforced "from the very first commit" was corrected: nothing enforced it until F-2 |
| Tracing + cost accounting | BUILT | `e2f5034`; P-2 adds `ttft_ms` / `leg` / `failover_engaged` / `skip_reason` to the turn record |
| "Live" for a self-onboarded tenant | n/a | It is `config->onboarding.completed`, not `tenants.status`. `status` defaults to `active` and self-signup inserts `active`, so it is never anything else for a tenant that onboarded itself - it is a platform-admin lifecycle (suspend/reactivate), read only by the customer page. E-5's "live / not-live state is legible" bullet is void for that reason, recorded in the ticket rather than ticked |
| Business hub + Business page | BUILT | E-5: the `.bh-row` hub (Booking page, Settings - Stage 2's Schedule/Money/Plan absent, not disabled) and the booking screen: profile show-back plus the public link, derived from the host via `surfaceUrl()`. **E-6 finished the screen** against the prototype: cover photo, platform tiles as link slots in `brand->links`, and customer-facing About. **M-4 re-cut the hub into three rows** - Business page (`/business/page`), What you offer (`/business/offerings`), Business details (`/business/details`) - and moved the offerings list off the Business page onto its own screen. **M-6 adds the small first-three offering summary before Preview, while keeping links, About editing, and Share at the end.** `/business/booking` and `/settings` are gone as paths rather than aliased |
| Home: the greeting and the brief | BUILT | E-4: the prototype's `showMorningBrief()` / `addCard()` ported, carrying only kinds backed by real Stage 1 state (customers waiting, knowledge drafts unsaved, the share nudge). Composed client-side from `/api/conversations` + `/api/knowledge/records`; `BriefItem` is the contract a Stage 2 `/api/brief` inherits |
| Advanced screens hidden, not deleted | BUILT | E-2: `/conversations`, `/escalations`, `/pricing` and `/knowledge` are absent from `NAV_ITEMS` and from nothing else - each still serves when typed, renders inside the shell, and is pinned by `e2e/hidden-screens.spec.ts`, which also holds the platform surface unchanged |
| Tenant admin console (conversations, escalations, pricing) | BUILT | `daea6d3`, `b9b561f`; C-6 added the prototype's **Chats** list + thread (`/chats`), whose "Action needed" filter is the owner's queue; E-1 re-cut the shell to Home + Chats + Business (bottom tab bar below `lg`, sidebar at `lg+`; D18 as amended by D21), retired the hamburger drawer, and re-homed `/chats` and `/settings` inside it; **CHANGING** - E-2 marks the advanced screens hidden, E-4 fills Home, E-5 builds the Business hub's Booking page |
| Tenant dashboards (cost + eval) | BUILT | `1aab440`, `cb9905c`; unlinked from the nav (E-2). **E-3 removed the `/dashboards` redirect**: it was the one hidden screen that had stopped serving, and it holds the eval pass/fail view the keep/pivot/stop signals live in |
| Platform-owner surface | BUILT | `b8a2f5b`, `07b8b13`; E-3 verified it against its job and added nothing: `e2e/platform-surface.spec.ts` pins the six columns, the aggregate, the slug-collision refusal, and suspension's effect on the customer's page (the one control whose consequence lands on another surface) |
| Customer storefront + chat | BUILT | **M-4 made `/{slug}` a storefront**: offerings with the owner's own prices, About and links, with the chat in a sheet a tap away instead of occupying the page. **M-5 keeps one prototype-aligned `Ask a question` entry at the top.** `c0adc77`; P-5 pinned the indicator across the whole turn - it was already built out of `ThinkingDots` + `StreamingText`'s `pending`, so the ticket added the tests that keep it unbroken and dropped the unbuilt `turn_started` event from the contract; **CHANGING** - rebrand (B-1) |
| Semantic status colours | BUILT | B-3 US-2: `STATUS_TONE` covers the schema's whole vocabulary plus the tenant-defined order/repair statuses, `pending` moved from neutral to amber, `shipped` stays amber because it is not `delivered`, and `toneForStatus` normalises spelling so one entry answers `in_progress` / `in-progress` / "In Progress". The Chats list's crimson "being handled" dot is documented as the single deliberate exception |
| Full visual rebrand (M3 system, crimson primary) | BUILT | `cc30fc5`, `86b03d9`, `5d2bb7d`; **CHANGING** - D-17 swaps the font to Plus Jakarta Sans (token-level) |
| Marketing pages | BUILT | `b2c46e9`, `27537d7`; superseded - the bare host is login-in-chat now (O-2), so B-1 had no marketing copy left to rename |
| Copy rules enforced on screen | BUILT | B-1: the product is Agencx everywhere a user can see it, and `e2e/copy-rules.spec.ts` sweeps each surface's rendered text for "AI", "agent", "automated", "assistant" and "Wren". Proven to fail on a planted violation before being trusted green |

### Deployment and portfolio

| Feature | Status | Evidence / change |
|---|---|---|
| Deploy runbook ([deploy.md](deploy.md)) | BUILT | `b3e578d`, rewritten by B-4 for the Vercel topology: one project, two container services, hosted Supabase, and the free LLM, embedding and rerank tiers. The status banner is gone because the procedure it warned about is now the current one. Since D22 the auto URL serves all three surfaces. Corrected after the first real deploy (2026-08-26): the `ignoreCommand`-in-`vercel.json` trap (rejects the whole config when `services` is present - three branches failed that way), the Functions region that must match Supabase (`syd1`), the Brevo SMTP vars, and the `SMOKE_TEST_BASE_URL` secret that silently no-op'd both workflows until set - see `fix/staging-deploy-lane`. Corrected after the second (2026-08-27, `fix/customer-page-rsc-fetch`): the frontend service binding was dropped - Vercel's injected internal URL is unreachable from the custom image (its internal CA bundle is absent from `node:bookworm-slim`), which broke the `/bytefix` RSC fetch on every deployment while the smoke test still passed; the RSC lookup now derives the request's own origin instead, and the smoke test asserts the rendered tenant name rather than a bare 200 (Next streams the error shell with a 200) |
| Terraform AWS backend | BUILT | `d368b03`; superseded by B-4 and dormant. `infra/*.tf` is kept as evidence and still validated by the `infra` job in `ci.yml`, so it cannot rot silently, but nothing deploys through it |
| Deploy end-to-end (both services on Vercel) | BUILT | B-4: `vercel.json` (two services plus rewrites), `frontend/Dockerfile` with `output: "standalone"`, `backend/Dockerfile` retargeted with a `test` stage, `GoogleEmbedder`, the 4MB upload cap under the platform body limit, and both workflows pointed at branches that exist. The live deploy happened 2026-08-26 (`558898b` deployed fine twice; `8c0edf5`, `a869169` and `5b68822` failed - see the runbook row). `SMOKE_TEST_BASE_URL` is set, `deploy.yml` smoke-tests and `keep-warm.yml` pings both services. **Live as of 2026-08-27 (`e8ecae5`)**: `staging` is the production branch and deploys green with the smoke test passing (`development` preview is green too); the hosted Supabase is migrated and seeded (`bytefix` resolves and chats end to end with citations and deterministic pricing); the alias `agencx-iota.vercel.app` serves the stack. Founder steps that remain: none known - the dashboard settings (Production Branch, Ignored Build Step, region) and the Brevo SMTP vars are all set |
| Generalization proof (dental, config-only) | BUILT | `2b8437d`; evidence in `docs/archive/artifacts/generalization-proof.md` |
| Eval report | BUILT | evidence in `docs/archive/artifacts/eval-report.md` |
| Security write-up | BUILT | evidence in `docs/archive/artifacts/security.md` |
| Demo walkthrough video | NEW | founder step, unticketed |

## Provider and latency (new Agencx work, all NEW until P-tickets land)

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
D-2, F-2, G-1} -> F-1 -> B-4. D-1/D-3/D-4 and B-2 defer. The E block is four
tickets since D21: E-1 (the three-tab shell) -> E-4 (Home and its brief) -> E-5
(Business hub + Booking page) -> E-2 (hide the advanced screens).

| Ticket | Status | Commit |
|---|---|---|
| A-1 Docs restructure + archive | done | `fce4d71` |
| A-2 Pointer updates (README, AGENTS.md, memory, conventions) | done | `6ad4aa6` |
| B-1 Copy rename to Agencx | done | `99e95c3` |
| B-2 Point agencx.app at the deployed stack | deferred (founder buys the domain) | rewritten by D22 - one DNS record, no wildcard |
| B-3 Semantic colour convention + lighter primary | done | US-1 `969bfdd` (O-5), US-2 `97740d4` |
| B-4 Deploy as two containers behind one Vercel origin ([10-deploy.md](spec/10-deploy.md)) | done | `21da213` + `54cc0cd` (eval git shell-out); supersedes the Cloud Run plan in [deploy.md](deploy.md) and the AWS ECS target in [architecture.md](architecture.md); live deploy happened 2026-08-26, dashboard settings and Brevo vars stay founder steps (`fix/staging-deploy-lane` records the follow-up fixes) |
| C-1 Money guardrail: verbatim owner material | done | `bee1775` |
| C-2 Gate every reply, not just money routes | done | `70a0ea1` |
| C-3 Prompt rule: state figures exactly as listed | done | `6b043b6` |
| C-4 Money guardrail test matrix (absolute gate) | done | `dcd5f59` |
| C-5 Non-blocking escalation (chat continues after handoff) | done | `0137d20` |
| C-6 Human takeover: staff step in, and hand back | done | `e3e9019` |
| D-1, D-3, D-4 Per-tenant tool gating + toggle + tests | deferred (Phase 2) | |
| D-2 Lean default (quoting OFF) | done | `3b3a46a` (migration 0016) |
| E-1 Three-tab shell (Home + Chats + Business) | done | `172e573` (shell `4063434`) |
| E-4 Home: the greeting and the brief | done | `ebc9b78` |
| E-5 Business hub + Booking page | done | `ac01cf0` + QR `e1f2f76` (QR later removed by E-6) |
| E-6 Booking page: cover, services, link slots; QR out | done | `f984612` (backend) + `166a49b` |
| O-6 Onboarding chips + ABN/GST + contact widgets | done | `c905e1d` + `a491f85` (shared with O-8) |
| O-7 URL ingest: browser headers, logged reasons | done | `1534049` |
| O-8 Go-live transition | done | `39e019f` + `a491f85` (shared with O-6) |
| O-9 Settings: an ABN the owner can read and correct | done | `f4088af` |
| E-2 Hide advanced screens, keep code | done | `ac6199a` |
| E-3 Platform admin stays minimal | done | `ecdaffb` |
| F-2 Import boundary in CI | done | `1684a42` |
| F-1 Hygiene | not started | |
| G-1 Eval cases for the lean toolset | done | `acd2328` |
| K-1 Everything runs in containers (`docs/agencx/spec/09-devex.md`) | done | `3453b85` |
| P-4 knowledge_version + invalidation | done | `9960a9d` |
| P-3 Agent-ready pre-load (context package) | done | `72b4ecb` |
| P-1 Provider layer: Google/Groq/OpenRouter tiers | done | `a8fd09f` |
| P-2 Latency budget + first-wins failover | done | `0cdff0c` |
| P-5 Typing indicator through the failover window | done | `be24802` |
| O-2 Login-in-chat: email + 6-digit code | done | `70ba4f6` |
| O-1 Onboarding: one tool + LLM turn loop | done | `ceb0f77` |
| O-5 Onboarding UI: prototype thread port | done | `969bfdd` |
| O-3 Knowledge ingest (URL scrape + upload) | done | `29fd5a5` |
| O-4 Whole-corpus fast path + threshold | done (pulled into the chat spine, before P-3) | `2d48fa6` |
| G2.1/G2.2 Auth migration: GoTrue OTP + `@supabase/ssr` cookies | done | `8e78165` (backend), `4a6b59f` (frontend); D23 in `design/decisions.md` |
| M-1 Offerings become a real, owner-writable structured item | done | `040e2cf` (merged to `development`) |
| M-4 The public storefront, and the address the owner chooses | done | see `spec/11-offerings-media.md` |
| M-5 Single storefront chat entry | done | `aa97ba6` |
| M-6 Business page summary preview | done | `62a94da` |
| M-3 Import offerings from reviewed knowledge | done | deterministic candidates and editable confirmation through the existing Knowledge review sheet; changed prices require explicit confirmation and never auto-delete |

## Known gaps (not ticket failures - waiting on external setup)

- **~~The platform console (`/admin`) does not work on the hosted Supabase
  project~~ - resolved 2026-08-28 by the auth migration (D23).** This was
  logged 2026-08-26: the hosted project issues ES256 session tokens while
  `shared/auth.py::verify_token` only verified HS256, so every hosted console
  request 401ed. `verify_token` now reads the token's `alg` header and verifies
  ES256/RS256 via the project's JWKS (`pyjwt[crypto]`, added for exactly this)
  with HS256 kept for local GoTrue - the fix this entry said would need "its
  own ticket" landed as part of the OTP migration, since GoTrue-minted sessions
  are the same tokens platform admin was already getting. Not yet re-verified
  against a live hosted project (no hosted deploy has run since); flag if the
  next hosted deploy still 401s.
  The `platform_admin` **database** role is unaffected and stays: it is created
  in migration 0002, carries live RLS policies, and `tests/test_rls.py` asserts
  on it.

- **A platform-provisioned tenant is stuck at `provisioning`** (found while
  closing E-5's live/not-live bullet, 2026-08-23). `POST /api/platform/tenants`
  inserts `status='provisioning'` (`features/platform/service.py:66`) pending a
  founder decision on the claim mechanism, and the admin table renders an action
  only for `active` (Suspend) and `suspended` (Reactivate) - a provisioning row
  gets `null` (`admin-surface/(console)/page.tsx`). The API already accepts the
  change (`_VALID_STATUSES` covers all three), so this is a missing control, not
  a missing capability. Self-signup is unaffected: it inserts `active`.

- **`enabled_tools` has no reader yet** (D-2). The column now says lean and
  `agents/agent_node.py::_tools_for` still offers every tool to every tenant -
  D-1 wires the two together in Phase 2. The data change lands first on
  purpose: doing it after D-1 would mean a window where quoting was on for
  tenants who never asked for it.

- **There is no everyday owner Copilot** (found during E-4, deferred by founder
  2026-08-22). S1 promised that after go-live the owner's chat tab holds an
  ongoing conversation with their assistant. No route answers one:
  `POST /api/onboarding/message` 409s once onboarding is confirmed and nothing
  replaces it. Home ships without a composer rather than with one that errors
  on every send, and `design/frontend.md` S1 has been corrected to stop
  promising it. This is a new agent route, not a screen - too large for a
  polish ticket. Revisit after Stage 1 reports back.


- **Google's tier rejects our multi-tool turns** (found by G-1's live run,
  2026-08-22). `openai.BadRequestError: 400 - Function call is missing a
  thought_signature in functionCall parts ... function call
  `default_api:lookup_order_or_ticket`, position 2`. Gemini now requires a
  `thought_signature` echoed back on function-call parts, and it surfaces
  through the OpenAI-compat endpoint we speak to. It fires on turns with more
  than one tool call, so `generation_eval`, `trajectory_eval` and
  `injection_eval` all error out against the primary tier; the deterministic
  gates are unaffected.
  **Failover does not absorb it**: `_FAILOVER_ERRORS` in `app/llm/failover.py`
  covers rate limits, connection faults, upstream errors and validation errors
  - not `BadRequestError`. That default is right in general (a 400 usually
  means the request is wrong, and retrying it elsewhere would hide a real bug),
  and wrong for a *provider-specific* 400 like this one, which the same request
  survives on Groq or OpenRouter. Needs its own ticket: either echo the
  signature in the provider shim, or classify provider-specific 400s as
  failover-eligible. Not fixed inside G-1 - it is an `app/llm/` change, not an
  eval one.

- **Live LLM calls run against free-tier models** (Google AI Studio primary,
  Groq fallback in the local env; OpenRouter gemma in CI) and are prone to
  upstream 429 rate-limiting; all LLM-touching code paths are proven with
  stubbed providers in CI.
- ~~**Login-in-chat needs a relay account provisioned** (O-2), a Brevo account +
  `EMAIL_SMTP_*` vars.~~ **Superseded 2026-08-28 (D23):** the backend no longer
  sends this mail at all - GoTrue does, via `signInWithOtp`. The relay setup
  moved with it: it is now the Supabase dashboard's own SMTP configuration
  (Auth > SMTP Settings), which the hosted deploy needs regardless of vendor,
  and Supabase's built-in mailer is not a substitute (it sends only ~2
  emails/hour, to project members) - see `deploy.md`'s auth section for the
  required dashboard steps.
- **Business type does not vary the interview (O-1, US-2).** The PRD glossary
  describes a `business_types` row carrying "a profile template and prompt
  fragments"; neither half has a consumer in Phase 1, and none of the seven
  lean fields is one a vertical should skip (a solo trader's "just me" and an
  online store's "24/7" are both useful answers). O-1 therefore captures
  `business_type` as a profile field and feeds it to the tenant's system
  prompt, and asks every tenant the same seven questions - which keeps I8
  cleanly satisfied, since no vertical name appears anywhere. Revisit when a
  real vertical needs a question the generic set does not cover.
