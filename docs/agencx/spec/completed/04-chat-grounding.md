# Phase 1 - Chat grounding (O-3/O-4 + C)

**Status: complete.**

Chat grounding: knowledge ingest into the whole-corpus/retrieval seam, and the
loosened money guardrail (verbatim figures from owner material) run across
every answer path.

Tickets in this file (in build order):

- O-3: Knowledge ingest - URL scrape + document upload
- O-4: Whole-corpus fast path + measured threshold
- C-1: Money guardrail - allow figures verbatim from owner material
- C-2: Route knowledge answers through the same figure check
- C-3: Assistant states figures only exactly as listed - never computes
- C-4: Money guardrail test matrix
- C-5: Non-blocking escalation - the chat continues after a handoff

---

## O-3: Knowledge ingest - URL scrape + document upload

### Summary

Two ingest paths feeding the existing chunk/embed/store pipeline:
document upload (PDF, PNG/JPG, DOCX - already built) polished into the
Business tab/FileDropzone surface, and URL scrape (new) that fetches a
page, extracts text, and stores it as a `website`-type document. Both flow
through the real ingestion pipeline and bump `knowledge_version` (P-4).

### Why

The PRD spine step 4 and the lean flow design: knowledge arrives as
documents or as links ("drop a link to your site and I'll learn the rest").
The `website` doc_type exists (migration 0015) but no route feeds it; the
upload path exists but needs the Business-tab surface polish per the
frontend spec.

### User stories

#### US-1 Paste a link, the site becomes knowledge

**As** Sam pasting his site URL,
**I want** the pipeline to fetch, extract, chunk, embed, and store it,
**so that** the assistant answers from the site without retyping anything.

- [x] URL detection on submit - server-side, in the onboarding turn
  (`_find_url`), so the composer needs no URL mode. The Business tab's own
  entry points land with the Knowledge screen
- [x] Fetch with a timeout and size cap; every fetch failure (bad scheme,
  oversize, non-2xx, DNS/connect/timeout) leaves `app/ingestion/url.py` as
  `ValueError`, so no path hangs and none reaches the owner as a 500
- [x] Stored as `doc_type='website'`; the pipeline's pending -> processing ->
  ready/failed flow is unchanged. The retry affordance ships with the
  Knowledge screen
- [x] Read-back in chat: "Here's what I've got from your site: ... Sound
  right, or anything to fix?" - server-synthesized from the draft, never
  model prose

#### US-2 Upload polish holds the spec

**As** Sam uploading a PDF menu,
**I want** per-file status, retry on failure, and the conversational
acknowledgement,
**so that** uploads read as part of the chat, not a file manager.

- [x] Attach from inside the command pill (the prototype's `+`), not a
  dropzone: PDF, DOCX, MD, TXT, CSV, JSON. **PNG/JPG are refused** - nothing
  in the stack reads an image (no OCR, no vision call), so accepting one
  would promise an answer that never comes (founder ruling, 2026-08-22).
  A vision call on the provider seam is the upgrade path
- [x] Attachment stamp in the thread; "Got your menu.pdf - I'll answer from
  it now." on ready
- [x] Unreadable/unsupported files: one calm line each, naming the way
  forward, no error chrome
- [x] Multiple files in sequence: each its own stamp and line

#### US-3 Ingest invalidates the cache

**As** the maintainer,
**I want** every completed ingest to bump the knowledge version,
**so that** the pre-load cache (P-3/P-4) cannot serve the old knowledge.

- [x] Both paths write through `process_document`; the 0018 touch trigger
  bumps `documents.updated_at` on every status write, so completion moves
  the knowledge version (P-4 contract)

### Design reference

The upload/scrape surface lives inside the onboarding thread, so the reference
is **`docs/agencx/design/prototypes/agencx-prototype-v6.html`**'s ONBOARDING
section: `buildCmdPill()`'s attach affordance and
the in-thread confirmation pattern (`.thr-pill` stamps, agent message then
chip). There is no separate uploads screen in the prototype - do not build one.

### Technical spec

- `backend/app/routes/ingest.py` (or extend the existing upload route):
  URL fetch/extract path
- Extraction: the existing extractor + a page-to-text step (html2text-style,
  no new heavy dependency; `ponytail:` plain text extraction now, PDF-ified
  rendering later if a real site needs it)
- Frontend: URL paste detection + chip states in the chat composer

### Tests

- API: URL ingest happy path + fetch-failure -> failed doc + retry
- Pipeline: website doc chunks/embeds; version bump after completion
- E2E: paste URL in chat -> status -> assistant answers from it

### Files touched

- `backend/app/routes/**`, `backend/app/ingestion/**`
- `frontend/src/**` (composer URL detection, chips), `frontend/e2e/**`

### Definition of done

- [x] URL scrape path end to end
- [x] Upload polish per spec (attach from the pill; images refused by ruling)
- [x] Ingest bumps the knowledge version
- [x] E2E: site-derived answer works (`frontend/e2e/onboarding-url.spec.ts`,
  scraping a static fixture this app serves - the app's own pages are
  client-rendered and carry no text to extract)

### Notes from the build

- Knowledge is never a blocking beat: a page that cannot be read offers a
  file or a sentence instead, and says it can wait for Settings > Knowledge.
- The upload stamps are client-side only; the ingested document persists, its
  stamp does not survive a reload.
- **Settings > Knowledge** (`/settings/knowledge`) ships with this ticket,
  pulled forward from S2 on the founder's direction and recorded as D19: a
  source is processed into fixed readable sections, held as a draft until the
  owner saves it, and shown back as the same sections afterwards. Not a
  document table - the owner's question is "what does it think my business
  is?", which a list of filenames cannot answer.
- The processing step is model-written text over owner material, so it carries
  a deterministic money guard: any figure it produces that is absent from the
  source discards the whole processed version (see D19).

---

## O-4: Whole-corpus fast path + measured threshold

### Summary

Implement the two-path `get_business_context` seam: when the tenant's whole
corpus fits the reply token budget (measured, ~7-8k today, a config value),
return the full corpus directly - no retrieval scoring. Above the threshold,
run the existing hybrid pipeline (dense + sparse + RRF + rerank). Both paths
return the same shape. The threshold is a measured token count, never a
business-size branch.

### Why

The lean flow (D-12) and the pre-load (P-3) depend on this seam. For small
corpora the retrieval scoring adds latency without adding information; the
model reading the material directly is faster and more faithful. The
threshold check keeps the behavior data-driven so I8 holds (a large
restaurant and a small dental clinic both get whichever path their corpus
size earns).

### User stories

#### US-1 The fast path fires for small corpora

**As** the maintainer,
**I want** a corpus that fits the budget to be returned whole,
**so that** no scoring cost is paid when the model can read everything.

- [x] `get_business_context(tenant_id, query)` checks: profile tokens +
  system prompt + full corpus + expected answer budget < context window
  budget (config `CORPUS_FAST_PATH_MAX_TOKENS`, default ~7500)
- [x] Fast path returns all chunks with `score = None`-equivalent (the
  shared shape allows unscored entries)

#### US-2 The hybrid path fires above the threshold

**As** the maintainer,
**I want** a corpus over budget to run the existing pipeline unchanged,
**so that** large tenants keep their measured recall.

- [x] Above threshold: dense + sparse + RRF(k=60) + rerank -> top-k with
  scores
- [x] Same return shape; same citation contract

#### US-3 The threshold is measured, not guessed

**As** the maintainer,
**I want** the token-count check to be a real tokenizer count with a safety
margin,
**so that** the path switch is a number, not a heuristic.

- [x] Token estimation is a conservative 3.0 chars/token (below real English
  prose, so it over-counts) plus an 800-token answer reserve; callers pass
  their prompt/profile length as `overhead_chars`. No tokenizer dependency
  was added for a number that only needs to be conservative
- [x] The threshold is config; the budget math is documented in the code

#### US-4 Citations still work on the fast path

**As** Alex reading a grounded answer,
**I want** citation chips even when the corpus was read whole,
**so that** trust does not depend on the path.

- [x] Fast-path chunks carry source metadata (chunk id, content, source);
  ordering is deterministic (document, then `chunk_index`) so citation
  numbering is stable for the life of a cached package. The rendering half
  is wired when P-3 puts the package on the turn

### Technical spec

- `backend/app/services/retrieval.py`: threshold check + fast path; the
  hybrid `retrieve()` stays the second path
- P-3's context-package assembly calls this seam at open time

### Tests

- Unit: below/above threshold routing with seeded corpora (deterministic
  token counts via a fixed estimator)
- Unit: shared return shape on both paths
- Retrieval eval: fast path does not regress recall on the small golden
  set (the whole corpus trivially contains the answer - assert the refusal
  behavior still works when the answer is absent)

### Files touched

- `backend/app/services/retrieval.py`, `backend/app/shared/config.py`
- `backend/tests/**`

### Definition of done

- [x] Two paths behind one seam, both shapes identical
- [x] Threshold measured + config, not a branch on business size
- [x] Citations work on both paths
- [x] Retrieval gates green

---

## C-1: Money guardrail - allow figures verbatim from owner material

### Summary

Extend the deterministic money guardrail's allowed-figure set: a figure in an
assistant reply is allowed when it appears **verbatim** in the tenant's own
supplied material (uploaded documents, profile, pricing rules, catalog).
Today the check only accepts figures that reconcile to pricing-engine output;
knowledge answers stating "catering from $12 a head" get flagged even when the
menu says exactly that.

### Why

The PRD guardrail contract (section 7) makes owner-supplied material a
first-class allowed source. The current engine-only provenance check was built
for the quoting route; the lean Phase 1 assistant mostly answers from
knowledge, where the honest, grounded answer IS the verbatim figure. The
guardrail must permit what the material states exactly, and nothing else.

### User stories

#### US-1 Verbatim figures pass

**As** Alex asking "how much is catering?",
**I want** the assistant to state the figure exactly as the owner's material
states it,
**so that** I get the real answer without the assistant refusing or
escalating a fact it is allowed to say.

- [ ] A figure passes when the exact string appears in the context package
  (documents, profile, pricing rules, catalog)
- [ ] Normalization is conservative: `$12` matches `$12` and `12 dollars` and
  `12.00` (cents-normalized equivalence) but NOT `about 12`, `12-ish`, or
  `around $12`

#### US-2 Engine output stays an allowed source

**As** a quote-enabled tenant's customer,
**I want** engine-computed totals to keep passing,
**so that** quotes still work.

- [ ] The existing engine-reconciliation path is untouched (regression-tested)

#### US-3 The guardrail stays deterministic

**As** the maintainer,
**I want** the allowed-set check to be a plain function with no model call,
**so that** I1 and the import boundary hold.

- [ ] The allowed-set membership check is in `services/` (no `llm/` import)

### Technical spec

- Extend `price_gate.py` / the money guardrail node: collect the allowed
  figure set from (a) owner material present in the retrieved context, (b)
  pricing-engine output, (c) tenant pricing rules/catalog verbatim values
- Figure extraction: reuse the existing figure tokenizer; equivalence via
  integer-cents normalization (I1)
- `tenant_config.enabled_tools` gates whether the engine source exists for
  the tenant (see D-1; the guardrail reads the enabled set, not a global flag)

### Tests

- Unit: verbatim match table (exact, dollar variants, cents-normalized) and
  non-match table (qualifiers, off-by-one, computed)
- Unit: engine-output source still passes; disabled-quote tenant has no
  engine source
- Determinism: guardrail module importable without `llm/` (import-linter)

### Files touched

- `backend/app/agents/price_gate.py` (or its successor), guardrail node
- `backend/tests/test_price_gate*.py`

### Definition of done

- [ ] Verbatim owner-material figures pass the guardrail
- [ ] Engine-output path regression-green
- [ ] Guardrail remains deterministic and import-bounded

---

## C-2: Route knowledge answers through the same figure check

### Summary

Make the knowledge answer path (the grounded Q&A flow, which in the lean
Phase 1 shape is the assistant's main path) run every reply through the same
money guardrail the quoting/recommendation routes already use. Today a
knowledge draft can carry a figure the guardrail never sees.

### Why

The guardrail is only as strong as its coverage. A figure invented in a
knowledge answer is the same stop-the-panel failure as one invented in a
quote; leaving the knowledge path unchecked is a hole, not a scope cut.

### User stories

#### US-1 Every assistant reply passes the guardrail

**As** the platform owner,
**I want** the guardrail to run on every customer-facing assistant reply
regardless of which tool or path produced the draft,
**so that** no reply can carry a figure the allowed set does not contain.

- [ ] The knowledge/answer path inserts the guardrail node after drafting
  (the one-call supervisor flow: draft -> guardrail -> inspection -> stream)
- [ ] Greetings and refusals (no figures) pass through without overhead but
  still traverse the node (uniform pipeline)

#### US-2 Failures escalate, never silently pass

**As** the maintainer,
**I want** a draft with an unexplained figure to rewrite once, then escalate,
**so that** a bad figure can never reach a customer.

- [ ] Rewrite-once-then-escalate behavior is identical to the quoting route's
  existing behavior (shared node, no duplicated logic)
- [ ] The `escalations` row carries the guardrail reason

#### US-3 The figure check uses the tenant's enabled set

**As** a lean tenant,
**I want** engine-sourced figures to be impossible (engine disabled),
**so that** the lean default cannot be widened accidentally.

- [ ] The allowed-set assembly reads `tenant_config.enabled_tools` (C-1
  contract); a lean tenant's allowed set is owner material only

### Technical spec

- The supervisor-with-tools flow (P-3) wires the guardrail as the mandatory
  post-draft node for all tool paths; until P-3 lands, C-2 wires it into the
  existing knowledge route
- Shared node implementation; no per-route copies

### Tests

- Trajectory: knowledge-path reply with a verbatim figure passes; with an
  invented figure rewrites then escalates
- Greeting path: guardrail traverses with no-op result (no cost spike)
- Enabled-set test: lean tenant draft citing an engine figure fails the check

### Files touched

- `backend/app/agents/graph.py`, knowledge route wiring
- `backend/tests/**` (guardrail coverage tests)

### Definition of done

- [ ] Knowledge answers traversed by the guardrail
- [ ] Rewrite-once-then-escalate verified on the knowledge path
- [ ] Lean tenant cannot pass engine-sourced figures

---

## C-3: Assistant states figures only exactly as listed - never computes

### Summary

Add the prompt-side contract that makes the guardrail hold: the assistant's
system prompt and drafting instructions say figures may be stated only
exactly as they appear in the provided material, never computed, summed,
multiplied, rounded, or "about"-ed. The deterministic guardrail remains the
enforcement; this ticket makes the instruction so the model mostly complies
and the guardrail mostly passes instead of mostly rewriting.

### Why

The guardrail catches violations but every catch costs a rewrite or an
escalation - wasted latency and a worse conversation. A crisp instruction
reduces violations at the source; the guardrail stays the floor. Both halves
of the contract are needed for the latency budget (PRD section 9).

### User stories

#### US-1 The prompt states the rule plainly

**As** the assistant (prompt level),
**I want** the system prompt to say: state a figure only when the material
contains exactly that figure; never compute, sum, estimate, round, or hedge a
number,
**so that** I do not invent figures in the first place.

- [ ] The rule appears in the customer assistant's system prompt (context
  package, P-3) and the Copilot's prompt
- [ ] The rule names the failure consequence conversationally ("if you are
  not sure of a price, say so and offer to have the owner confirm")

#### US-2 Verbatim phrasing carries over

**As** Alex,
**I want** the answer to restate prices/allergens/terms exactly as written,
**so that** what I read matches the owner's material.

- [ ] Eval cases assert verbatim restatement for price-bearing questions
  (G-1 wires them)

#### US-3 The guardrail is unchanged in authority

**As** the maintainer,
**I want** the deterministic node to remain the sole arbiter,
**so that** prompt compliance never substitutes for enforcement.

- [ ] No relaxation of the guardrail; this ticket is prompt text only plus
  the eval cases that measure compliance

### Technical spec

- Prompt edits in the context-package assembly (or the current system-prompt
  templates until P-3 lands)
- No deterministic-code changes

### Tests

- Generation eval: price-bearing cases produce verbatim figures at the same
  or better rate as before (regression gate)
- Guardrail rewrite-rate metric optionally logged for the dashboards (P-2
  tracing hooks)

### Files touched

- `backend/app/agents/**` (prompt templates), context-package assembly
- `backend/evals/**` (case updates, coordinated with G-1)

### Definition of done

- [ ] Prompt rule in both assistant surfaces
- [ ] Verbatim-restatement eval cases green
- [ ] Guardrail authority untouched

---

## C-4: Money guardrail test matrix

### Summary

The full adversarial test matrix for the loosened guardrail: verbatim figures
pass; invented, computed, off-by-one, hedged, and reworded figures fail; an
invented price escalates. This ticket is the teeth - it proves the guardrail
cannot be talked around.

### Why

The money guardrail is the product's stop-the-panel property (PRD section 7).
C-1/C-2/C-3 change its allowed set and coverage; C-4 is the suite that keeps
every one of those changes honest. A single invented figure blocks the phase
gate.

### User stories

#### US-1 The pass matrix

**As** the maintainer,
**I want** every legitimate verbatim case to pass,
**so that** the loosening did not break honest answers.

- [ ] `$12` stated when material says `$12`
- [ ] `$12.00` stated when material says `12 dollars`
- [ ] Engine-computed totals on quote-enabled tenants (regression)
- [ ] Replies with no figures

#### US-2 The fail matrix

**As** the maintainer,
**I want** every invented-figure case to fail (rewrite once, then escalate),
**so that** no model-authored number can reach a customer.

- [ ] Invented price with no source in material
- [ ] Computed total (two menu items summed by the model)
- [ ] Off-by-one / rounded ("about $40", "$39-ish", "roughly twelve")
- [ ] Tax or discount computed by the model
- [ ] Figure from a DIFFERENT tenant's material (cross-tenant figure)
- [ ] Figure injected via chunk text instructions (indirect injection + money)

#### US-3 The escalation contract

**As** the platform owner,
**I want** the second failure to escalate with a guardrail reason,
**so that** the handoff is visible and auditable.

- [ ] Rewrite-once: first violation rewrites; second violation creates an
  `escalations` row with the guardrail reason and records the handoff per C-5
  (honest customer message; the conversation itself stays open)
- [ ] The customer sees the honest handoff, never a raw figure

#### US-4 The suite has teeth and is never skipped

**As** the maintainer,
**I want** the matrix wired into the absolute gate (100/100 money air-gap),
**so that** a red matrix blocks CI and the phase.

- [ ] Deterministic (no LLM judge) - the matrix is a pure function suite
- [ ] A deliberately weakened guardrail (test doubles) fails the suite
- [ ] No CI flag skips it

### Technical spec

- Parameterized test matrix over the guardrail node: (draft, allowed set,
  enabled tools) -> expected verdict
- Reuses the Wren "teeth test" pattern (break-then-restore)

### Tests

- This ticket IS the tests; plus the eval-gate wiring (`make eval` runs it)

### Files touched

- `backend/tests/test_money_guardrail*.py`
- `backend/evals/run_gate.py` (absolute-gate wiring)

### Definition of done

- [ ] Pass matrix green
- [ ] Fail matrix green (every invented figure fails)
- [ ] Escalation contract verified
- [ ] Suite wired into the absolute gate, never skippable

---

## C-5: Non-blocking escalation - the chat continues after a handoff

### Summary

Change escalation from a terminal conversation state into a recorded handoff
that does not stop the chat. When the assistant escalates (supervisor route,
`create_escalation` tool, or the money guardrail's second violation), it says
so honestly and keeps the door open ("I need to check with the owner on that -
meanwhile I can help with other things"), writes the `escalations` row for the
owner queue, and the conversation stays active: the customer's next message
gets a full agent turn. Only limit/cap escalations (T-028) keep the terminal
behavior.

### Why

Today every agent-side escalation flips `conversations.status` to
`'escalated'`, and from then on each customer message gets a bare
`{"type": "escalated"}` with no agent turn; the customer surface disables the
composer. One unanswerable pricing question can therefore dead-end an entire
support session even though the assistant works fine for everything else. The
product promise is a support-and-sales agent that keeps helping - a handoff on
one topic should not end the session. Founder request, 2026-08-21. This ticket
supersedes the terminal-flip wording in C-2 US-2 and C-4 US-3.

### User stories

#### US-1 A handoff does not lock the customer out

**As** Alex asking "how much for X?" when the figure is not in the owner's
material,
**I want** the assistant to say it will check with the owner and then keep
chatting,
**so that** one missing price does not end my whole conversation.

- [ ] Agent/tool/guardrail escalations write the `escalations` row and the
  conversational handoff message; `conversations.status` stays `'active'`
- [ ] The next customer message gets a normal agent turn (knowledge, tools,
  guardrail all live)
- [ ] Handoff copy names the topic and offers to continue; never "the owner
  will reply here" as a conversation-ending sign-off

#### US-2 The owner still sees and answers the handoff

**As** Sam checking his escalations queue,
**I want** pending escalations listed with their conversations,
**so that** my answer reaches the customer while the chat is still open.

- [ ] The escalations queue surface is unchanged (rows carry reason +
  conversation)
- [ ] The resolve flow's `human_agent` message reaches the open chat (the
  existing polling path, extended to non-terminal escalations)

#### US-3 Caps stay hard stops

**As** the platform owner,
**I want** limit/cap escalations to stay terminal,
**so that** over-budget usage actually stops.

- [ ] The T-028 path is unchanged: status flips, composer locks, the
  `{"type": "escalated"}` stream behavior is preserved for this reason only

#### US-4 Guardrail authority is unchanged

**As** the maintainer,
**I want** the second guardrail violation to escalate just as reliably as
today,
**so that** C-5 softens only what happens after the escalation, never whether
it happens.

- [ ] The C-4 matrix stays green with the new post-escalation behavior
  asserted (conversation still `'active'` after a second violation)

### Technical spec

- `backend/app/agents/agent_node.py`: `create_escalation` no longer flips
  `conversations.status`; the graph routes past an escalation to a normal
  reply turn instead of ending it; the system prompt gains the
  continue-the-conversation rule (C-3 pattern: prompt text, guardrail stays
  the floor)
- `backend/app/agents/price_gate.py`: `GATE_ESCALATION_MESSAGE` becomes the
  conversational handoff; drop `escalated=True` from the decision (keep
  `escalation_reason` for the row)
- `backend/app/features/chat/controller.py`: `stream_escalated_response`
  remains for limit escalations only; agent escalations emit a non-terminal
  handoff notice event (contract change documented in the api docstring)
- `frontend/src/app/(customer)/CustomerChat.tsx`: composer locks only on a
  limit escalation; human-reply polling keys off unresolved escalations
  instead of conversation status
- `'escalated'` remains a valid `conversations.status` value (limit path and
  legacy rows); agent/guardrail paths stop writing it

### Tests

- Trajectory: escalate, then ask something else -> normal grounded answer on
  the same conversation
- Guardrail: second violation -> `escalations` row + handoff text + status
  still `'active'`
- Limit-escalation regression: still terminal end to end
- E2E: pricing question -> handoff bubble -> follow-up question answered;
  owner resolve inserts the human message into the open chat

### Files touched

- `backend/app/agents/**` (agent_node, price_gate, supervisor routing, prompts)
- `backend/app/features/chat/**` (controller, service)
- `frontend/src/app/(customer)/CustomerChat.tsx`, `frontend/src/lib/chat-events.ts`
- `backend/tests/**`, `frontend/e2e/**`, escalation trajectory evals

### Definition of done

- [ ] No agent/guardrail path writes `conversations.status = 'escalated'`
- [ ] The chat verifiably continues after every non-limit escalation
- [ ] Owner queue + resolve flow work against an open conversation
- [ ] Limit escalation still terminal; C-4 matrix green

---

## C-6: Human takeover - staff step in, and hand back

### Summary

Give the owner the other half of a handoff. C-5 stopped the customer's side of
the conversation from dying; the owner's side is still a table row with a Claim
button and a single canned Resolve message. C-6 makes the escalation carry a
one-line note of what the customer actually wants, lets a staff member take the
conversation over and talk to that customer directly with the assistant silent,
hand it back when they are done, and makes "can I speak to a person?" a
first-class request rather than something that happens to work.

### Why

Founder requirement raised during C-block planning (2026-08-22). A support
agent a business cannot step into is not a support agent a business will put in
front of its customers. Today the owner sees a reason string and can send
exactly one message; there is no way to have a conversation, and no way to give
it back. The distinction the code has never made is the whole ticket:

- **An escalation is a notification** - "a human should look at this". It
  creates a queue item. It does not change who is replying; the assistant keeps
  helping (that is C-5).
- **A takeover is a mode** - a staff member is the voice now, and the assistant
  is silent until handed back.

Separating them is what makes all four requirements fall out of one change.

### User stories

#### US-1 The owner sees what the customer wants, not a reason code

**As** Sam, glancing at his phone between jobs,
**I want** each waiting conversation to say what it is about in one line,
**so that** I can tell a price question from a complaint without opening it.

- [ ] `create_escalation` captures a `summary` alongside `reason` - one plain
  line of what the customer wants ("Catering for 20 on Friday, wants a price")
- [ ] The summary is written in the tool call the model already makes; no
  extra LLM call and no second prompt pass
- [ ] Owner-facing only: returned by the escalations API, never by any public
  chat endpoint. The money guardrail deliberately does not apply to it - no
  customer reads it, and it restates the customer's own request (founder
  ruling, 2026-08-22)
- [ ] Falls back to `reason` when the model omits it

#### US-2 Staff take the conversation over

**As** Sam, seeing a question only he can answer,
**I want** to reply to that customer myself with the assistant out of the way,
**so that** I am not fighting my own agent for the conversation.

- [ ] Any conversation can be taken over, not only a flagged one - the
  prototype's pill is always present
- [ ] Takeover sets `conversations.status = 'human'`; while it holds, a
  customer message is stored and no agent turn runs
- [ ] A stamp lands in the transcript ("You took over this conversation") so
  the history reads honestly to whoever scrolls it later
- [ ] Staff replies post as `human_agent` and reach the customer's open chat
  through the existing poll (C-5)

#### US-3 Staff hand it back

**As** Sam, done answering,
**I want** to give the conversation back to the assistant,
**so that** I do not have to keep watching it.

- [ ] Handback returns the status to `'open'` and appends the symmetrical stamp
- [ ] The next customer message gets a full agent turn
- [ ] The takeover interlude stays in the history, so the assistant reads what
  the human said and does not contradict it

#### US-4 The customer can ask for a person

**As** Alex, who would rather talk to a human,
**I want** asking for one to actually summon one,
**so that** I am not stuck negotiating with a bot.

- [ ] The prompt instructs: if the customer asks to speak to a person, call
  `create_escalation` immediately, say a human has been notified, and keep
  helping in the meantime
- [ ] Produces the same queue item and the same C-5 continue-the-chat behaviour

#### US-5 Caps stay hard stops

- [ ] `'escalated'` still means a limit stopped the conversation; the composer
  locks and no takeover applies

### Design reference

The prototype's **Chats** screens in
`docs/agencx/design/prototypes/agencx-prototype-v6.html` - both of them, not
just the buttons. Port them; do not design from this text.

- **List** (`renderScreen('chats')`): topbar + search (`openChatsSearch` /
  `filterChats`, "No conversations found." empty state); filter row **All /
  Action needed / Unread**, where "Action needed" is the escalation flag and so
  *is* the owner's queue; `chat-row` with name, relative time, status dot, and a
  one-line preview - the preview line is the summary note. Dots: `bdot-a` amber
  = needs the owner, `bdot-t` teal = the assistant is handling it, none = idle.
- **Thread** (`renderThreadScreen`, `alexTko`, `alexHbk`): `thr-st` status
  reading "Handling" (teal) / "You're replying" (muted); `h-bar` pill "Take over
  this conversation" swapping to `tko-bar` with "Hand back to Agencx" plus a
  composer; `thr-pill` stamps both ways with `pillTime()` timestamps
  (`thr-pill` is for stamps, `thr-pill-action` for actions - do not mix);
  sent/read ticks on outgoing bubbles.

Build on `ChatBubble`, never on `Thread.tsx`: `frontend.md` is explicit that the
operator thread's two-bubble idiom and the onboarding thread's are different
designs and must not be unified.

### Technical spec

- Migration **0020**: widen `conversations.status` to
  `('open', 'human', 'escalated', 'closed')` and add `escalations.summary text`.
  Strictly additive - no existing row changes meaning. (`0016` stays reserved
  for D-2.)
- `_CreateEscalationArgs` (`app/agents/agent_node.py`) gains `summary`; the
  insert carries it.
- `app/features/chat/service.py`: `resolve_conversation` reports the `'human'`
  state; the chat API stores the message and returns without invoking the graph.
- Takeover/handback are conversation-scoped, not escalation-scoped:
  `POST /api/conversations/{id}/takeover` and `.../handback`. Each appends its
  stamp as a transcript message.
- Owner UI: Chats list and thread, mounted chrome-free (`CHROME_FREE_PREFIXES`,
  the posture O-3 set for `/settings`) until E-1 builds the tab bar to hold
  them. Every prototype value lands as a `theme.css` token.

### Tests

- Takeover: status `'human'`, customer message stored, graph never invoked, no
  `escalated` event on the wire
- Handback: status `'open'`, the next message gets a full agent turn, and that
  turn's history contains the human's messages
- Stamps present in both directions
- Summary on the escalations API response and absent from every public chat
  response (asserted, not assumed)
- Leakage: a takeover on tenant A's conversation is invisible and unreachable
  from tenant B
- E2E: customer asks for a person -> queue item with the summary -> owner takes
  over -> types a reply -> customer sees it in the open chat, composer never
  locked -> owner hands back -> assistant answers the next question. This also
  carries C-5's deferred E2E: the same UI contract, with no model in the loop.

### Files touched

- `backend/migrations/0020_conversation_human_takeover.sql`
- `backend/app/features/chat/{api,service,controller}.py`
- `backend/app/features/escalations/{api,controller,service}.py`
- `backend/app/agents/agent_node.py`
- `frontend/src/app/(tenant-admin)/(console)/conversations/**`
- `docs/agencx/design/frontend.md` (S1 state table), `design/decisions.md` (D20)

### Definition of done

- [ ] An escalation carries a readable summary, owner-facing only
- [ ] Staff can take over any conversation and reply directly
- [ ] Handback restores the assistant, with the interlude in its history
- [ ] Asking for a person summons one
- [ ] Limit escalations still terminal; the C-4 matrix green
