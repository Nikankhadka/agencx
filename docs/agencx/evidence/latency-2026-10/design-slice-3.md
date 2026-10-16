# Slice 3 design note - the discarded agent call

**Status:** recon and design only. No code yet. This note is written before
implementing, as the order requires.

## Objective

Remove the redundant model call on tool-using turns. The order's premise is that
a tool-using turn spends one agent call whose terminal prose is discarded
(`agent_node.py:1167` requires no routing tools), then the draft node
regenerates a grounded answer - hybrid `llm_call_count` 4 to 3.

## Per-path call accounting (current code)

| Path | Agent model rounds | Draft | Inspection | `llm_call_count` |
|---|---|---|---|---|
| fast, no tool (P-3) | 1 (prose) | 0 | 1 | 2 |
| fast, structured (show_catalog / calculate_quote) | 1 (tool) | 0 (deterministic) | 0 (passthrough) | 1 |
| tool-using (hybrid, or fast with tool calls) | R tool rounds + 1 terminal prose round | 1 | 1 | R + 3 |

The tool loop (`agent_node.py:763`) keeps calling `chat_with_tools` until a round
returns no tool calls; that terminal round's prose is the completion signal. When
any routing tool was called, the prose is discarded (`:1167`) and the draft node
writes the grounded answer. So a tool-using turn is `R + 3` calls, not a fixed 4:
the order's "4" is the `R = 1` case.

## Multi-round tool use is the norm on the hybrid path

Captured from the slice-2 run logs (`/tmp/slice2-run1.log`, `slice2-run2.log`),
mapped to tenant by the `latency turn` payload's `tenant_id`:

| run | tenant | agent rounds | tool rounds | tools |
|---|---|---|---|---|
| 1 | sababa | 2 | 1 | recommend_items |
| 1 | sababa | 3 | 2 | search_knowledge x2, recommend_items x2 |
| 1 | sababa | 3 | 2 | search_knowledge, recommend_items x2 |
| 1 | sababa | 4 | 3 | search_knowledge x4, recommend_items |
| 2 | sababa | 2 | 1 | recommend_items |
| 2 | sababa | 3 | 2 | search_knowledge x2, recommend_items x2 |
| 2 | sababa | 3 | 2 | search_knowledge x3, recommend_items x2 |
| 2 | sababa | 3 | 2 | search_knowledge, recommend_items |

Four of five hybrid turns per run are tool-using, and three of those four are
multi-round. The fast tenants (bytefix, sababa2) answered in one round (P-3), and
bytefix's one tool turn was a single `show_catalog` round. The test suite's only
multi-round sequences are the two escalation/contact flows
(`test_escalation_agent.py:339`, `:413`).

## Candidate designs

- **(i) Break to the draft node after the first tool round.** Saves exactly one
  call on every tool turn (all become 3), grounding still comes from the draft
  node. But it drops tool rounds 1+ wherever they happen, which is the norm on
  the hybrid path - three of four tool-using hybrid turns. Ruled out: the
  multi-round decision is PRESENT, and the order requires it be preserved or
  provably absent.
- **(ii) Keep multi-round, make the terminal call carry no prose.** No call is
  saved - the model still has to be asked to learn it is done - so it saves
  tokens, not the call the order targets.
- **(iii) Let the tool result carry the chunks, so the agent's terminal prose is
  the grounded draft.** `search_knowledge` currently returns a match *count* and
  keeps the chunks in state, so prose after it is ungrounded and must be
  discarded. If the tool result carried the (spotlight-wrapped) chunks, the
  terminal round's prose would be grounded, the draft node could be skipped on
  the knowledge/recommendation routes, and multi-round tool use is untouched.
  Money routes (`get_quote_inputs`, `calculate_quote`) keep the draft node - a
  figure must still only come from the engine. Saves one call: `R + 2` instead of
  `R + 3` (`R = 1` gives the target 3).

## Selected design

**(iii)**, the only call-saving design that preserves multi-round tool use. It
changes the grounding seam: the agent's own terminal prose would ship on
non-money tool routes, so it must be proven that the tool result carries the
chunks the prose is grounded in, and it must clear the evals - injection in
particular, because tenant chunk text would then sit in the agent prompt on the
same footing as the draft prompt.

## Gate (this is the blocker to clear before any code lands)

The change is a behavior change and must be measured. A scored `generation`
(and injection) run is required before it can be judged. `make eval` is
provider-blocked on the free chain (Gemini `503`, Groq `400`); the eval is being
retried pinned to the paid OpenRouter `deepseek/deepseek-v4.1-flash`. If no
scored run is achievable, slice 3 stops here and reports the blocker - an
unmeasured behavior change must not ship.
