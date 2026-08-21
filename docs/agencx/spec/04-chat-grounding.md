# Phase 1 - Chat grounding (O-3/O-4 + C)

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

- [ ] URL detection on submit (chat composer + Business tab)
- [ ] Fetch with a timeout and size cap; extraction failures become a
  failed document with retry, never a hang
- [ ] Stored as `doc_type='website'`; status flow pending -> processing ->
  ready -> failed with retry affordance
- [ ] Read-back in chat: "Here's what I found: [summary]. Sound right, or
  anything to fix?"

#### US-2 Upload polish holds the spec

**As** Sam uploading a PDF menu,
**I want** per-file status, retry on failure, and the conversational
acknowledgement,
**so that** uploads read as part of the chat, not a file manager.

- [ ] FileDropzone: PDF, PNG/JPG, DOCX; drag + click; per-file progress
- [ ] Attachment chip in chat; "Got your menu - I'll answer from it now."
  on ready
- [ ] Unreadable/unsupported files: one calm message each, no error chrome
- [ ] Multiple files in sequence: each its own chip and status

#### US-3 Ingest invalidates the cache

**As** the maintainer,
**I want** every completed ingest to bump the knowledge version,
**so that** the pre-load cache (P-3/P-4) cannot serve the old knowledge.

- [ ] Both paths write through the shared pipeline (single code path);
  document rows update timestamps on completion (P-4 contract)

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

- [ ] URL scrape path end to end
- [ ] Upload polish per spec
- [ ] Ingest bumps the knowledge version
- [ ] E2E: site-derived answer works

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
  `escalations` row with the guardrail reason and flips the conversation
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
