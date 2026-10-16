# Slice 3 design note - the discarded agent call

**Status:** recon and design only. No code. Written before implementing, as the
order requires.

**Source logs are ephemeral.** The evidence below came from
`/tmp/slice2-run1.log` and `/tmp/slice2-run2.log`. They were distilled into
`data/slice2-rounds.md` (with the filtered lines committed as
`data/slice2-run1-lines.jsonl`, `data/slice2-run2-lines.jsonl`), which is now
the record.

## Objective

Remove the redundant model call on tool-using turns. The premise is that a
tool-using turn spends one agent call whose terminal prose is discarded
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
a routing tool was called the prose is discarded (`:1167`) and the draft node
writes the grounded answer. A tool turn is `R + 3` calls, so the order's "4" is
only the `R = 1` case.

## Multi-round tool use is the norm on the hybrid path

Per-turn table: `data/slice2-rounds.md`. In short, across the two slice-2 runs,
sababa (hybrid) called tools on 4 of 5 turns, and 3 of those 4 were multi-round
(2 to 4 agent rounds, `search_knowledge` and `recommend_items` across rounds);
the fast tenants answered in one P-3 round, except bytefix's single
`show_catalog` turn. The test suite's only multi-round sequences are the two
escalation/contact flows (`test_escalation_agent.py:339`, `:413`).

Correction from the first draft: run 1's third sababa row is
**2x search_knowledge + 2x recommend_items**, not "search_knowledge,
recommend_items x2" (see the artifact).

## Slice-3 gate (the slice must be falsifiable)

Slice 3 is judged on **`llm_call_count` on completed turns per tenant**, with its
own band derived by the same documented rule - max over the comparable run
pairings (slice2-run{1,2} vs noise-run{1,2}) of max(|delta p50|, |delta p95|) -
computed over the four existing runs (noise-run1/2, slice2-run1/2):

| tenant | `llm_call_count` band | driver | completed-turn values |
|---|---|---|---|
| bytefix | 1.90 | p95 (2.0 vs 3.9) | [1,2,2,2] / [2,4] / [1,2,2] / [1,2,2,2] |
| sababa2 | 0.00 | none | [2,2,2,2] / [2,2,2] / [2,2,2] / [2,2,2,2] |
| sababa | 0.50 | p50 (3.5 vs 4.0) | [4,3] / [4] / [4] / [] |

The target is a one-call saving (sababa 4 to 3 = -1.0), which exceeds the 0.50
band, so it is detectable. **Timing is corroboration only:** one saved call is
about 0.7s (measured on the observed redraft) and at most ~2s generally, inside
the 2031-2950 ms `total_ms` bands, so an inside-bands timing result is expected
and does not refute the slice. A change in the completion rate / budget-blow
rate is a second supporting signal.

**Censoring caveat.** A timeout kills a turn, truncating its recorded call count
- no committed turn shows 5 or 6 calls even though the round table shows 3 to 4
tool rounds on some turns; the max observed is 4. So the structural claim rests
on completed turns, and a rise in completed turns is itself a positive signal.

**Prompt-growth counter-effect.** A chunk-carrying tool result is re-sent on
every later model round (~1-2k tokens per search; +10-20% input on the terminal
round of the observed 3-4-round turns). The implementation measurement must
report `input_tokens` alongside the saved call.

## Candidate designs

- **(i) Break to the draft node after the first tool round.** Saves one call on
  every tool turn, grounding still from the draft node - but drops tool rounds
  1+ wherever they happen, the norm on the hybrid path. Ruled out: the
  multi-round decision is PRESENT and must be preserved or provably absent.
- **(ii) Keep multi-round, make the terminal call carry no prose.** No call is
  saved - the model still has to be asked to learn it is done - so it saves
  tokens, not the call.
- **(iii) Let the tool result carry the chunks, so the agent's terminal prose is
  the grounded draft (selected).** Saves one call (`R + 2`), multi-round
  untouched.

## Selected design (iii) - completions

**Scope correction.** This is a `search_knowledge`-only change.
`recommend_items` already carries its items in the tool result
(`agent_node.py:836`: `{"found", "items"}`); `search_knowledge` returns only a
count (`:815`). Only the search result needs the chunks.

### Retry semantics

`graph.py:85-89` routes every inspection retry by name to the draft node. With
the draft node skipped on knowledge/recommendation, that edge has no target.
Options, with call accounting:

- **(a) Re-enter the agent** on a failed inspection: another agent pass - R'
  tool rounds + 1 terminal prose - plus inspection, so `R' + 2` more calls, and
  the retry would use the agent prompt, not the draft node's redraft prompt
  (which carries the violation reason). Expensive and loses the redraft
  contract.
- **(b) Keep the draft node reachable only for retries** (recommended): the
  first pass answers from the agent; a failed inspection redrafts through the
  existing draft node, whose redraft prompt already carries the violation. The
  happy path saves the call; the retry path is unchanged. Cost: the draft node
  stays in the graph, reachable only via the retry edge.
- **(c) Escalate on first-pass failure**: cheapest code, but drops the ratified
  redraft-once-then-escalate rule. Rejected.

### What the draft node provides that the terminal prose must take over

- **Citations event** - P-3 shows the pattern (`agent_node.py:1185-1199`) but
  reads `package.chunks`; with (iii) the tool's chunks are what must be cited,
  so the agent must emit the `citations` event from the search tool's chunks.
- **Knowledge/recommendation system prompt + `_with_contract`** - the agent's
  prompt is not the draft prompt. With (iii) the agent's prose ships, so its
  prompt must carry the same contract and route guidance: a contract change,
  not just a grounding change.
- **Refusal paths** - the no-chunks refusal (`draft_node.py:220-228`) and the
  no-selections path (`:256+`) must be reproduced on the agent path.
- **`author_node`** - changes from `draft` to `agent` in the persisted row and
  the Surface-2 trace.

## Blocker (why no code landed)

The change is a behavior change and must clear the evals. `make eval` on the
free chain: money/leakage/retrieval PASS; generation/trajectory/injection FAIL
on a Gemini `503` and a Groq `400` (`data/eval-slice2.log`). Pinned to the paid
OpenRouter `deepseek/deepseek-v4.1-flash`, `run_gate`'s deterministic gates
passed and then the generation eval stalled: the committed log ends mid
`generation_eval` right after the HF weights load
(`data/eval-slice3-deepseek.log`), and the operator observed the container at
0% CPU with no `cost_logs` writes for 14 minutes before killing it. Those two
were the pins attempted; no others were tried.

A latency-only run WAS possible (`make latency` works); it was declined because
it cannot gate a grounding change - the eval is the gate, not the clock. So
slice 3 stops at this note.
