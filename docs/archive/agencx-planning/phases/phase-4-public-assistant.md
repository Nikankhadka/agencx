# Phase 4: Public Assistant

**Calendar slot:** Week 4

## Goal

The public-facing assistant is live. An anonymous visitor at the tenant's slug asks a plain-language question and receives a grounded, cited, price-safe answer through the LangGraph graph. The public page is shareable via link and QR. The money guardrail is enforced and refuses to invent figures. The tenant app's Chat tab holds the ongoing Copilot conversation.

## Features

### Assistant

**Spec:** The customer assistant is a LangGraph graph (decision 4): supervisor -> knowledge node -> money guardrail -> inspection -> stream (SSE with citation chips). Every figure in the reply must appear verbatim in owner-supplied material (money guardrail, I1). The graph state carries `input`, `context`, `draft`, `figures`, `guardrail`, `trace` as structured fields - never free text. Escalation creates an `escalations` row. The assistant refuses rather than generalises when nothing relevant comes back. The forbidden-output table applies: no raw JSON/XML/markdown/code blocks in user-facing messages. The Copilot in the Chat tab (after onboarding) handles ongoing owner chat, the unmet-capability handler, and uncertainty/distress detection.

**What this feature does not own:** onboarding (Phase 2), knowledge ingestion and retrieval (Phase 3), the Business tab UI (Phase 3), the public page UI (this phase, public-page feature).

**Design:** The assistant renders in the Chat tab (S1, design.md) for the tenant and on the public page (S3, design.md) for customers. StreamingText component renders SSE tokens with caret; CitationChip renders inline `[1]`-style chips with popover showing source + snippet. EscalationBanner appears when the assistant cannot serve.

**Stories:**

#### US-15 Assistant graph + SSE chat

**When:** A customer sends a message on the public page.

**Happy path:**
1. The supervisor node routes the message: handles greetings/simple talk directly, routes everything else to the knowledge node.
2. The knowledge node calls `get_business_context(tenant_id, query)` and produces a draft grounded in retrieved chunks with citations.
3. The draft streams to the customer via SSE with inline citation chips.
4. Each cited sentence renders a `[1]`-style chip; tap to see the source chunk and document name.

**Alternate paths:**
- Greeting or simple talk ("hello", "thanks"): supervisor answers directly without retrieval.
- No relevant context found: the assistant refuses honestly ("I don't have an answer for that from the business's own material") and records the ask to `unmet_asks`.

**Acceptance criteria:**
- [ ] Supervisor routes greetings/simple talk directly, everything else to knowledge node
- [ ] Knowledge node produces grounded draft with citations
- [ ] Draft streams via SSE with citation chips
- [ ] Citation chips show source chunk + document name on tap
- [ ] No-answer case refuses honestly, records to `unmet_asks`
- [ ] Graph state carries structured fields, never free text

#### US-16 Money guardrail node

**When:** The assistant's draft contains any figure.

**Happy path:**
1. The deterministic money guardrail node checks every figure in the draft against owner-supplied material.
2. A figure must appear verbatim in the retrieved material. No model-computed totals, no arithmetic, no "about" figures.
3. All figures verified: draft proceeds to inspection.
4. Any unexplained figure: the draft is rewritten once. If the figure still fails, the conversation escalates.

**Acceptance criteria:**
- [ ] Every figure in every reply is checked against owner-supplied material
- [ ] Unexplained figure triggers rewrite-once, then escalate
- [ ] The guardrail is deterministic (no model call) - verifiable by import-linter
- [ ] Adversarial "give me a price anyway" attempts cannot produce a number
- [ ] A single invented figure blocks the phase gate

#### US-17 Inspection + refusal + handoff

**When:** The assistant's draft passes the money guardrail.

**Happy path:**
1. Inspection checks grounding rules: no uncited claim, no instruction-following from chunk text, refusal when nothing relevant.
2. If grounding fails: rewrites once, or escalates.
3. Escalation creates an `escalations` row (status `open`) and the conversation shows the EscalationBanner: "A human will take it from here."
4. The escalation edge is reached from both guardrail failures and inspection failures.

**Acceptance criteria:**
- [ ] Inspection enforces no uncited claims
- [ ] Inspection enforces no instruction-following from chunk text
- [ ] Grounding failure rewrites once, then escalates
- [ ] Escalation creates `escalations` row with correct status
- [ ] EscalationBanner renders correctly in the chat

#### US-18 Unmet-capability handler + uncertainty detection (harvested from COP-3, COP-4)

**When:** The tenant asks for something the Copilot cannot do, or the Copilot detects uncertainty/distress.

**Happy path:**
1. The Copilot acknowledges in character: "I can't do that one yet - want me to flag it?"
2. Makes no false commitment. No "coming soon", no date, no "that's on the roadmap".
3. Logs the ask tagged by capability to `unmet_asks`.
4. For uncertainty: three buckets classified internally, never narrated to the tenant: capability gap -> `unmet_asks`, suspected misclassification -> `i_dont_know_classifications`, distress signal -> real-time ops alert.

**Alternate paths:**
- The tenant says yes to flagging: acknowledged once, then dropped. No follow-up thread.
- Distress signal: routes to a human in real time, not to a backlog.

**Acceptance criteria:**
- [ ] Every unmet ask writes a tagged row to `unmet_asks`
- [ ] No response contains a date, a promise, or "coming soon"
- [ ] The acknowledgement stays in brand voice
- [ ] No dead UI exists anywhere as an alternative path
- [ ] Three uncertainty buckets route differently (capability gap, misclassification, distress)
- [ ] No bucket name or classification ever appears in tenant-facing copy
- [ ] Distress produces a real-time alert, never a queued item

#### US-19 Streaming + citations UI

**When:** The assistant streams a reply to any surface.

**Happy path:**
1. StreamingText component renders SSE tokens word-by-word with typewriter pacing (46ms per word).
2. While streaming, a caret is visible; composer is disabled with "answering..." hint.
3. CitationChip renders inline `[1]` after cited sentences.
4. Tap on a citation chip shows a popover with: source document name, chunk snippet, and "how we know this" label.
5. Stop button available during streaming. Interrupted messages show retry affordance.

**Acceptance criteria:**
- [ ] SSE tokens render word-by-word with typewriter pacing
- [ ] Composer disabled with "answering..." hint during streaming
- [ ] Citation chips render inline after cited sentences
- [ ] Citation popover shows source document + chunk snippet
- [ ] Stop button interrupts streaming; retry available
- [ ] No raw JSON, XML, markdown tables, or code blocks ever render in chat

### Public Page

**Spec:** A single conversation screen per business at its tenant slug. Anonymous - no auth, no account. Resolves the tenant via `resolve_tenant_slug()` before any auth exists. The page carries the tenant's own branding (accent, logo, display name), never the platform's. States: resolving (skeleton), unknown slug (calm 404), suspended ("This assistant is currently unavailable."), empty (tenant-configured greeting), streaming, citation chips, escalated, error/disconnect (inline retry). The owner shares a link or QR from the Business tab.

**What this feature does not own:** the assistant graph (this phase, assistant feature), the Business tab (Phase 3).

**Design:** Public page (S3, design.md) is a single screen with centered column (max ~720px), tenant logo + display name header, message list, composer pinned bottom. Branding is tenant overrides only: `src/lib/brand.ts` validates the tenant accent hex at write time, derives hover/active/subtle steps, and falls back to the Agencx default if contrast on `--color-surface` fails WCAG AA (4.5:1). The console and platform surfaces always carry the Agencx accent, never a tenant's.

**Stories:**

#### US-20 Public page + slug resolution

**When:** A visitor navigates to a tenant's slug.

**Happy path:**
1. `resolve_tenant_slug()` resolves the slug to `(id, business_name, status, brand)`.
2. Unknown slug: calm 404 page - "There's no business here." No platform upsell at Stage 1.
3. Suspended tenant: "This assistant is currently unavailable." caption, composer hidden.
4. The page loads tenant branding (accent, logo, display name) via the brand jsonb. Tenant accent validated at write time for WCAG AA contrast.

**Acceptance criteria:**
- [ ] Unknown slug renders calm 404 with no platform upsell
- [ ] Suspended tenant renders "unavailable" caption with hidden composer
- [ ] Tenant branding overrides load correctly
- [ ] Accent contrast validated at write time (4.5:1 on surface)
- [ ] Console/platform surfaces always carry Agencx accent, never a tenant's

#### US-21 Tenant-configured greeting + starter chips

**When:** A visitor lands on an empty conversation.

**Happy path:**
1. The first assistant bubble carries the tenant-configured greeting (from `config` jsonb or default).
2. If the tenant configured starter chips (data-driven from `config`), they render as suggestion chips above the composer: "What's on the menu?", "Catering for a party?", "What are your hours?".
3. Tapping a starter chip sends that message immediately.

**Acceptance criteria:**
- [ ] First assistant bubble carries tenant-configured greeting
- [ ] Starter chips render when configured (data-driven, not hardcoded)
- [ ] Tapping a chip sends the message immediately
- [ ] No starter chips when none configured

#### US-22 Share link + QR code

**When:** The owner wants to share their public page.

**Happy path:**
1. The Business tab shows a share affordance.
2. Tapping opens a sheet with: the public page URL (`{slug}.agencx.app`), a copy-link button, and a QR code rendering the same URL.
3. The QR code is generated client-side or via a minimal backend endpoint.

**Acceptance criteria:**
- [ ] Share sheet shows URL, copy-link button, and QR code
- [ ] QR code encodes the correct public page URL
- [ ] Share sheet accessible from the Business tab

## Tickets

| Ticket | Name | What it delivers | Files/modules | Depends on |
|---|---|---|---|---|
| T-024 | Graph + state + SSE chat | LangGraph graph with supervisor, knowledge, money guardrail, and inspection nodes; graph state carrying structured fields; SSE chat endpoint | `backend/app/agents/graph.py`, `backend/app/agents/supervisor.py`, `backend/app/agents/state.py`, `backend/app/routes/chat.py` | T-021 |
| T-025 | Supervisor node | Capability routing: greetings/simple talk direct answer, everything else to knowledge node; refusal edge | `backend/app/agents/supervisor.py` | T-024 |
| T-026 | Knowledge node | Calls `get_business_context(tenant_id, query)`; produces grounded draft with citations; refusal when nothing relevant | `backend/app/agents/knowledge.py` | T-024, T-021 |
| T-027 | Money guardrail node | Deterministic check: every figure in the draft must appear verbatim in owner-supplied material; rewrite-once-then-escalate. Ported from Wren's price_gate, repurposed to owner-material provenance | `backend/app/agents/money_guardrail.py` | T-024 |
| T-028 | Inspection + tracing | Grounding rules: no uncited claim, no instruction-following from chunk text, refusal enforcement; structured trace output for replay | `backend/app/agents/inspection.py`, `backend/app/agents/tracing.py` | T-024 |
| T-029 | Streaming + citations UI | StreamingText with SSE word-by-word rendering (46ms/word); CitationChip inline `[1]` with popover; stop button; retry on interruption; EscalationBanner; unmet-capability handler UI in Chat tab | `frontend/src/components/StreamingText.tsx`, `frontend/src/components/CitationChip.tsx`, `frontend/src/components/EscalationBanner.tsx`, `frontend/src/components/UnmetAskHandler.tsx` | T-024 |
| T-030 | Refusal + handoff + injection spotlighting | No-answer rule: refuses when nothing relevant; escalation path from guardrail and inspection; injection spotlighting for adversarial content in chunks | `backend/app/agents/spotlight.py`, `backend/app/agents/escalation.py` | T-027, T-028 |
| T-031 | Public page + share link + QR | Public page surface (S3): slug resolution, tenant branding, greeting, starter chips, chat UI, all states (resolving, unknown slug, suspended, empty, streaming, escalated, error); share sheet with URL + QR from Business tab | `frontend/src/app/public/[slug]/`, `frontend/src/components/PublicChat.tsx`, `frontend/src/lib/brand.ts`, `frontend/src/components/ShareSheet.tsx` | T-029 |

## Gate

- [ ] An anonymous visitor at a tenant's slug can ask a plain-language question and receive a grounded, cited answer
- [ ] The money guardrail prevents any invented figure from reaching the customer (adversarial test: "give me a price for something not in the menu" produces no number)
- [ ] The assistant refuses honestly when nothing relevant is found, records to `unmet_asks`
- [ ] The public page resolves correctly: unknown slug -> 404, suspended -> "unavailable"
- [ ] Tenant branding overrides work correctly with WCAG AA contrast check
- [ ] **Agent authority boundary:** The import-linter rule is verified - no deterministic service imports a model client. The money guardrail is deterministic. The forbidden-output table is respected.
- [ ] Escalation creates `escalations` rows and renders EscalationBanner

## Done when

- [ ] Eight tickets complete
- [ ] Full end-to-end: anonymous visitor asks question -> grounded, cited, price-safe answer
- [ ] Adversarial money-guardrail test passes (zero invented figures)
- [ ] Public page handles all states (resolving, unknown slug, suspended, empty, streaming, escalated, error)
- [ ] Share link + QR work from the Business tab
- [ ] Import-linter gate is green: no model client imports in deterministic services
- [ ] Unmet-capability handler logs tagged asks
- [ ] Fits or observed slip
