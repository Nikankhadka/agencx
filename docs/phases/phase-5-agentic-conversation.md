# PHASE 5 - Agentic conversation layer: onboarding copilot + customer chat - T-041..T-044

> **Read first:** `docs/INDEX.md`, root `AGENTS.md`, `docs/conventions.md`. Per-ticket read-lists below.
> **Goal:** replace the hardcoded onboarding state machine and the fixed five-specialist customer-chat supervisor with fully agentic, tool-driven conversations on both surfaces, with strong Python-level guardrails.
> **Scope:** the frozen docs' Phase 2 "open-ended interviewer" is pulled forward per ADR in `docs/archive/decisions-log.md` (2026-07-30). The state machine's structural guarantees are carried explicitly in Python.
> **Verification:** ordered, each stage verified before the next begins. `make check` clean at every stage; `make ci` before each commit. End-to-end: drive the exact failure that prompted this work through the real surfaces.

---

### T-041 `[ ]` Tool calling in the provider abstraction (4h)
**Deps:** none (provider is standalone). **Stories:** US-120 tool plumbing.
**Read:** `backend/app/llm/provider.py`, `backend/app/llm/openai_base.py`, `backend/app/core/limits.py`, `backend/tests/fakes.py`, `backend/app/llm/openai_compat.py`, `backend/app/core/config.py`.

**Files:**
- `backend/app/llm/provider.py` - extend `ChatMessage`, add `ToolSpec`, add `ToolTurn`, add `chat_with_tools` abstract method
- `backend/app/llm/openai_base.py` - native `chat_with_tools` implementation reusing `_with_retry`, plus emulated path via `extract()` for free-model fallback
- `backend/app/core/config.py` - add `LLM_TOOL_CALLING` setting (auto / on / off)
- `backend/app/core/limits.py` - wrap `chat_with_tools` in `TimeLimitedProvider`
- `backend/tests/fakes.py` - add `chat_with_tools` stub to `BaseFakeProvider`, keyed by tool name
- `backend/tests/test_llm_tool_calling.py` - new test file

**Steps:**
1. Extend `ChatMessage` with optional `tool_calls: list[dict[str, Any]]` and `tool_call_id: str` keys (`TypedDict, total=False`).
2. Add `ToolSpec` (name: str, description: str, args_schema: type[BaseModel]) and a `ToolTurn` result (`text: str | None`, `tool_calls: list[ToolCall]`).
3. Add `ToolCall` dataclass (id: str, name: str, args: dict[str, Any]).
4. Add abstract method `chat_with_tools(*, messages, tools, tool_choice) -> ToolTurn` to `LLMProvider`.
5. Implement in `OpenAISDKProvider` (native path, reusing `_with_retry`) and add an emulated fallback via `extract()` for models without native tool support. The emulated path uses a `Literal`-typed union schema naming the chosen tool plus its args, matching the pattern `supervisor.RouteDecision` and `quoting.QuoteSelectionResult` already use.
6. Add `supports_tools: bool` to `OpenAISDKProvider`, driven by `LLM_TOOL_CALLING` env setting.
7. When off, `chat_with_tools` is emulated via the existing `extract()` path; both paths return the same `ToolTurn`.
8. Wrap `chat_with_tools` in `TimeLimitedProvider`.
9. Add `chat_with_tools` to `BaseFakeProvider` keyed by tool name.

**Accept:**
- Both native and emulated paths return identical `ToolTurn` shapes
- Timeout wrapping covers `chat_with_tools`
- Malformed tool-args response surfaces as `UpstreamResponseError`
- `make check` clean (lint + typecheck + test)

**Tests:**
- Unit tests for both native and emulated paths returning identical `ToolTurn` shapes
- Timeout wrapping tests
- Malformed tool-args response raising `UpstreamResponseError`

---

### T-042 `[ ]` Agentic onboarding copilot (8h)
**Deps:** T-041. **Stories:** E6 (conversational onboarding, agentic rework).

**Read:** `backend/app/onboarding/flow.py` (schemas + resolve_threshold + the config gate - reduced, not deleted), `backend/app/api/onboarding.py`, `backend/app/api/chat.py` (SSE pattern), `frontend/src/lib/chat-events.ts` (PROGRESS_LABELS), `frontend/src/app/(tenant-admin)/(console)/onboarding/page.tsx`, `backend/seeds/seed_tenant2_dental.py`, `seeds/tenant2_inputs/interview-script.md`, `backend/app/agents/spotlight.py`, `backend/app/pricing/validation_gate.py`.

**New files:**
- `backend/app/onboarding/agent.py` - agentic turn loop: `chat_with_tools` -> Python executes tools -> computes directive -> `chat_stream`
- `backend/app/onboarding/tools.py` - `save_identity`, `save_tone`, `save_services`, `save_pricing_rules`, `save_escalation`, `request_finalize` tools
- `backend/tests/test_onboarding_agent.py` - rewritten against the agent loop with a tool-aware `BaseFakeProvider`

**Modified files:**
- `backend/app/onboarding/flow.py` - reduced to schemas + `resolve_threshold` + the config gate (`_incomplete_rules`). `advance()`, `OnboardingState`, `PROMPTS`, `STAGE_ORDER`, `next_prompt` removed or repurposed.
- `backend/app/api/onboarding.py` - `POST /api/onboarding/message` now agent-backed, keeping current JSON contract; new `POST /api/onboarding/message/stream` returning SSE
- `frontend/src/app/(tenant-admin)/(console)/onboarding/page.tsx` - stream endpoint, formatted per-section summary panel
- `backend/seeds/seed_tenant2_dental.py` - rewritten to drive answers as an ordered pool, not lockstep stages
- `backend/tests/test_onboarding_api.py` - extended for SSE endpoint, resume from persisted history, unchanged JSON contract

**Steps:**
1. Reduce `flow.py` to schemas (`IdentityDraft`, `ToneDraft`, `ServicesDraft`, `PricingRulesDraft`, `EscalationDraft`, `CatalogItemDraft`, `PricingRuleDraft`), `resolve_threshold`, `_POSTURE_THRESHOLDS`, `DEFAULT_ESCALATION_THRESHOLD`, and `_incomplete_rules`. Remove `advance()`, `OnboardingState`, `PROMPTS`, `STAGE_ORDER`, `next_prompt`, `_SYSTEM_PROMPT_PREFIX`, `_EXTRACTION_SCHEMAS`, `_prior_rules_context`, `_MAX_PRICING_FOLLOWUPS`.
2. Build `agent.py` with the agentic turn loop: two model calls per turn - `chat_with_tools(history + new message, tools)` to get zero or more tool calls, then Python executes tools, applies gates, computes a directive, and `chat_stream(...)` composes the reply.
3. Build `tools.py` with `save_identity`, `save_tone`, `save_services`, `save_pricing_rules`, `save_escalation`, `request_finalize`. Args schemas reuse the existing Pydantic drafts from `flow.py` verbatim. `request_finalize` runs a Python completeness gate over the accumulated draft; on failure it returns a typed list of what is missing or unpriced.
4. Add guardrails: spotlight-wrap admin free text, price echo check, redirection budget (`off_topic_count` bounded at 2), bounded tool loop (max 4 tool calls per turn, max ~40 turns total).
5. State and persistence in `tenant_config.config->'onboarding'` jsonb, growing from `{state, completed}` to `{draft, history, off_topic_count, completed}`, with `history` capped at last 20 turns.
6. `POST /api/onboarding/message` keeps current JSON contract (agent-backed). New `POST /api/onboarding/message/stream` returns SSE, sharing one core turn function with the JSON endpoint.
7. Frontend: switch to stream endpoint. Replace raw `JSON.stringify(draft[key])` summary panel with formatted per-section rows.
8. Confirm action gated on Python completeness gate, not stage value.
9. Rewrite `seed_tenant2_dental.py` to drive answers as an ordered pool, feeding the next unused one each turn until the agent reports ready, then asserting final config matches expectations.

**Accept:**
- Off-topic question does not advance or pollute the draft
- Volunteered-early data is captured without re-asking
- Completeness gate refuses premature finalize with useful message
- Redirect budget escalates firmness and terminates
- Price-echo check catches an invented figure
- SSE endpoint streams the conversation
- Resume from persisted history works
- Tenant 2 onboarding succeeds with zero code changes (domain-agnostic proof)
- `make check` clean

**Tests:**
- Agent loop unit tests with tool-aware fake provider
- Off-topic redirect, early volunteer, completeness gate, price echo, redirect budget cases
- API tests: SSE endpoint, resume, unchanged JSON contract
- Rewritten `test_onboarding_flow.py` -> `test_onboarding_agent.py`

---

### T-043 `[ ]` Conversational customer chat route (2h)
**Deps:** T-041 (needs `chat_with_tools` for the new supervisor). **Stories:** E11 conversational chat.

**Read:** `backend/app/agents/graph.py`, `backend/app/agents/supervisor.py`, `backend/app/agents/state.py`.

**New files:**
- `backend/app/agents/conversation.py` - conversation node for greetings/thanks/meta questions
- `backend/tests/test_conversation_route.py` - new test file

**Modified files:**
- `backend/app/agents/graph.py` - add `conversation` to `_SPECIALISTS`, add node registration, add conditional edge from supervisor
- `backend/app/agents/supervisor.py` - add `conversation` to `RouteDecision.route` Literal, add to routing prompt

**Steps:**
1. Add a sixth capability, `conversation`, to `RouteDecision.route` and `_SPECIALISTS`.
2. Add the routing description: "conversation: greetings, thanks, meta questions about the assistant, or off-topic chat that does not fit a business capability."
3. Build `conversation.py` node: answers only about itself and the interaction, never about the business, ends by offering help. Sets `draft_deterministic: True` so inspection is skipped. Not in `_PRICE_GATED`.
4. Confidence gate fix: the existing `confidence < threshold` force-escalation applies to task routes only. `conversation` requires its own high confidence to be selected; an ambiguous message still escalates.
5. Add `conversation` to `_PROGRESS_STAGES`.

**Accept:**
- "hi", "what's your name?", "thanks" all route to `conversation` and get a friendly reply
- None reaches a human escalation
- An ambiguous/mixed message still escalates (confidence gate works for task routes)
- `conversation` node never answers business questions
- Real quote request still routes to quoting and produces a pricing-engine-computed number
- `make check` clean

**Tests:**
- Supervisor tests for `conversation` route (high-confidence classification)
- Explicit test that ambiguous message does NOT get absorbed into `conversation` but escalates
- Conversation node unit tests

---

### T-044 `[ ]` Tool-driven supervisor (6h)
**Deps:** T-043. **Stories:** E11 conversational chat, M7 tool set.

**Read:** `backend/app/agents/graph.py`, `backend/app/agents/supervisor.py`, `backend/app/agents/knowledge.py`, `backend/app/agents/recommendation.py`, `backend/app/agents/quoting.py`, `backend/app/agents/order_status.py`, `backend/app/agents/escalation.py`, `backend/app/agents/state.py`, `backend/app/agents/price_gate.py`, `backend/app/agents/inspection.py`, `backend/app/agents/spotlight.py`, `backend/app/agents/tools.py`, `backend/app/pricing/engine.py`.

**New files:**
- `backend/app/agents/tracing.py` - extracted `_traced`, `_span_attrs`, `_PROGRESS_STAGES` from `graph.py`

**Modified files:**
- `backend/app/agents/graph.py` - new graph shape: `START -> agent (tool loop) -> draft -> price_gate -> inspection -> END | retry | escalation`. Imports `_traced` from `tracing.py`.
- `backend/app/agents/supervisor.py` - replaced with `agent.py` node that loops over tools, then drafts
- `backend/app/agents/knowledge.py` - search_knowledge tool (retrieval logic intact)
- `backend/app/agents/recommendation.py` - recommend_items tool
- `backend/app/agents/quoting.py` - select_quote_items tool (still calls `pricing/engine.py:compute_quote`)
- `backend/app/agents/order_status.py` - lookup_order_or_ticket tool (already in `tools.py`)
- `backend/app/agents/escalation.py` - create_escalation tool
- `backend/app/agents/state.py` - may gain tool-loop keys if needed
- `backend/app/api/chat.py` - may need updates for new graph shape
- `backend/tests/test_agent_graph.py` - updated for new topology
- All specialist test files - updated for tool-based rather than node-based execution

**Steps:**
1. Extract `_traced`, `_span_attrs`, `_PROGRESS_STAGES` from `graph.py` into `backend/app/agents/tracing.py` so the onboarding agent from T-042 can reuse them.
2. Build new agent node (`agent.py`) that loops over `chat_with_tools` with the tool set PRD M7 specifies: `search_knowledge`, `recommend_items`, `lookup_order_or_ticket`, `get_quote_inputs`, `create_escalation`. Returns `route` + whatever the tools produced.
3. Build single draft node that takes the agent node's output and produces the final response prose.
4. New graph shape: `START -> agent (tool loop) -> draft -> price_gate -> inspection -> END | retry | escalation`. Remove the five specialist nodes as graph nodes.
5. Move specialist logic into tool implementations (largely intact):
   - `search_knowledge` <- `knowledge.py` retrieval
   - `recommend_items` <- `recommendation.py`
   - `select_quote_items` <- `quoting.py` selection, still calling `pricing/engine.py:compute_quote`
   - `lookup_order_or_ticket` <- already at `agents/tools.py`
   - `create_escalation` <- `escalation.py`
6. What must survive unchanged: `price_gate` and `inspection` still run on the final draft, with the same retry-once-then-escalate shape. The chat SSE loop keeps buffering prose until inspection approves. `_traced` still wraps every node. `_PROGRESS_STAGES` gains keys for tool-loop phases.
7. Update all specialist test files for tool-based execution.

**Accept:**
- Customer chat still routes correctly for all prior intents
- Price gate still blocks invented figures
- Inspection still buffers and clears
- "hi", "what's your name?", "thanks" route to conversation as before (T-043 regression)
- Tool-loop progresses through tools correctly
- `make check` clean; `make eval` not regressed

**Tests:**
- Updated agent graph topology tests
- Tool-driven agent node tests
- Specialist tool tests (search_knowledge, recommend_items, select_quote_items, create_escalation)
- End-to-end chat tests verifying all prior routes work
- Regression: conversation route still works

---

## Phase 5 Definition of Done

- [ ] All four tickets committed with `T-041:` through `T-044:` prefixes
- [ ] `make check` clean at every stage
- [ ] `make ci` before each commit
- [ ] ADR recorded in `docs/archive/decisions-log.md`
- [ ] `.agents/memory.md` updated: onboarding state machine retired, guarantees recorded
- [ ] `.agents/map.md` refreshed
- [ ] `docs/PROGRESS.md` rows updated per ticket
- [ ] `make eval` not regressed on customer surface after T-044
- [ ] End-to-end: onboarding failure (off-topic question, early volunteer, premature confirm) verified
- [ ] End-to-end: customer chat greetings/thanks no longer escalate
- [ ] Tenant 2 onboarding succeeds with zero code changes
- [ ] Free-model fallback verified: `LLM_TOOL_CALLING=off` works end-to-end
