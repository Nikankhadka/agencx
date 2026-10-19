# 13 - Latency instrument

**Status:** In progress - slice 1 landed (instrument, noise floor, model
matrix). Slice 2 (draft output cap, 4096) measured: mechanism inert - the cap
never bound, so no latency effect is attributable. Slice 3 (drop the discarded
agent call) is **implemented, measured and through its after-eval**: the code
landed (`cbad1b0`, measured at `2ac8247`) and the structural gate is carried by
the mechanism - `agent grounded tool answer` fired 8 times (4 per run, only on
sababa's tool turns) and that line exists only inside the new branch, while the
fast tenants' completed call counts did not move (p50 delta 0; sababa2's 0.00
band held). Hybrid sababa has a single completed turn, at 3 calls against 4,
0.50 from one baseline p50 and 1.0 from the other, so the sample is thin. The
after-eval shows no attributable regression but is blind to the change
(`_tools_for` never offers the retrieval tools on the fast path), and its
generation faithfulness drift (-0.0311) is NOT noise - the identical-code repeat
spread is +0.0019 - so `run_gate` fails that key by 0.001. Founder ruling
2026-10-19: the FAIL is accepted as a provider level shift and closed, the 0.03
tolerance is unchanged and it is not reclassified as noise; the citations-event
narrowing is ratified cited-only with no fallback to all retrieved chunks, and it
is internal only (the customer surface renders no chip on either path). Slice 3
verdict: **pass on the mechanism**; see
`docs/agencx/evidence/latency-2026-10/report-slice-3.md` and the corrections in
`data/eval-noise-repeat.md`. Slice 4 (overlap the retrieval steps) is
**implemented and measured**: the code landed (`040a473`), the mechanism is
proven structurally (sparse starts inside the embedding window; dense waits for
both, because one connection runs one operation at a time), and the timing
verdict is **no-measurable-effect** - the saved work is the sparse query's own
duration, measured at median 0.38 ms, far below what this instrument resolves at
3-4 hybrid turns per run. No scored eval was run: the change is output-preserving
and both eval tenants are fast-path, so `retrieve()` never runs there; the
deterministic gate that does call it passes unchanged. **The cumulative
comparison for slices 1-4 - baseline vs stack tip per tenant, and the eval trio -
is `docs/agencx/evidence/latency-2026-10/report-cumulative.md` (raw tables and
provenance in `data/cumulative.md`).** Slice 5 (prompt caching, replacing the
per-request spotlight nonce) is **implemented, measured and gate-passing**: the
code landed (`7613091`, review hardening and the measured tip `d99ca54`), the
injection gate PASSED at 29/30 = 0.967 against 0.9667 with the same single leak,
and the cache is proven by non-zero `cached_input_tokens` in both runs (run 1
cold, 20.6% of input tokens cached; run 2 warm, 64.5%; each tenant's turn 1
always cold). There is **no clock claim** - 10 of 15 turns per run hit the 10 s
turn budget and are censored out, so the completed samples are thin; see
`docs/agencx/evidence/latency-2026-10/report-slice-5.md`. Slice 6 (paid-tier
A/B across the matrix) is **implemented and measured, with NO WINNER**: the
cache-adjusted cost model shipped (`2004617`); ling's trajectory is impossible
because its providers reject structured outputs (Novita 400, then a retry that
forwarded an upstream error with no choices), so no tool-correctness row exists;
the OpenRouter matrix x2 is heavily censored (12-14 of 15 turns per model per
run); and the production primary Google gemini-3.5-flash-lite was added
(`5a4578a`, no published price), completing 10/15 in a good window then 2/15
under 429s. No latency or correctness ranking is supportable; see
`docs/agencx/evidence/latency-2026-10/report-slice-6.md`,
`data/slice6-matrix.md` and `data/slice6-google.md`. The cumulative package for
slices 1-6 is `report-cumulative.md` with raw tables and provenance in
`data/cumulative.md`. Slice 7 (streaming) remains deferred and needs the founder
to reopen scope.
**Phase 1 area:** Performance (post-launch).
**Branch:** `latency/stack` (all slices stack here; one merge to
`development` at the end, on the founder's go).

## Objective

Measure a real customer turn's latency with one command, on the app's own
telemetry, so a later change is judged against a measured noise floor rather
than a guess. The work changes no prompt, route, or budget and leaves the
platform `DEFAULT_*` limits untouched; the only settings it moves are the demo
tenants' own daily limits, raised so a matrix day does not hit them (see
`docs/agencx/evidence/latency-2026-10/data/tenant-limits.md`).

## Protocol

All slices stack on one branch, `latency/stack`. Each slice carries its own
commits, its own test, and one measurement run at that slice's commit against
the frozen slice-1 baseline (`data/noise-run1.json`, `data/noise-run2.json`)
and its tolerance bands (`data/noise-floor.md`). A slice whose metric does not
exceed the bands is written up as no-measurable-effect - findings are recorded
pass or fail either way, never dropped. Nothing is pushed. One merge to
`development`, then `staging`, happens only when the cumulative result is
validated and the founder says go.

## Slice backlog

1. The instrument: per-turn record, percentile math, runner, `make latency`;
   DoD includes the noise floor and the model matrix - landed (instrument,
   noise floor, matrix; see
   `docs/agencx/evidence/latency-2026-10/report.md`).
2. Cap output tokens: `LLM_MAX_TOKENS_DRAFT` is 0 (uncapped); cap the draft
   prose first, and cap extract only after the schemas shrink - a reasoning
   model spends its cap on hidden thinking and dies with
   `LengthFinishReasonError`. Done: `llm_max_tokens_draft` ships at 4096
   (raised from a first 2048 that sat near the observed max); measured
   mechanism-inert - per-call output stayed under the cap, so it never
   truncated - see
   `docs/agencx/evidence/latency-2026-10/report-slice-2.md`.
3. Kill the discarded agent call (`backend/app/agents/agent_node.py:1167`):
   the hybrid path makes a call whose result is thrown away, so
   `llm_call_count` 4 to 3; the grounding/money reason the call exists for must
   be preserved. Recon (see
   `docs/agencx/evidence/latency-2026-10/design-slice-3.md`) found the loop runs
   until a round returns no tool calls - that terminal round IS the completion
   signal - and multi-round tool use is the norm on the hybrid path (4 of 5
   turns, 1 to 3 rounds; record `data/slice2-rounds.md`). Breaking after the
   first tool round would change most hybrid turns, so it is ruled out; the
   only call-saving design that preserves multi-round makes the
   `search_knowledge` tool result carry the chunks (grounding-seam change) and
   needs a scored eval.
   **Gate:** slice 3 is judged on `llm_call_count` on completed turns per
   tenant, with a band by the same documented rule over the four existing runs:
   bytefix 1.90, sababa2 0.00, sababa 0.50 - so a one-call saving is
   detectable. Timing is corroboration only (a one-call saving sits inside the
   2031-2950 ms bands), and a rise in completed turns is a second signal.
   Timeouts truncate recorded call counts (max observed 4), so the structural
   claim rests on completed turns. The measurement must also report
   `input_tokens` (a chunk-carrying tool result is re-sent each later round).
   The eval gate that blocked slice 3 is now unblocked - the provider-seam gaps
   are fixed (`data/eval-blocker-diagnosis.md`); the scored pre-slice-3 baseline
   is recorded (`data/eval-baseline.md`).
   **Outcome (implemented, measured, evaluated - pass on the mechanism).** The
   change landed in `cbad1b0` and was measured at `2ac8247`:
   `search_knowledge`'s tool result now carries the spotlight-wrapped chunks, and
   a tool turn whose terminal prose is grounded (chunks for `knowledge`,
   selections for `recommendation`) with no money tool skips the draft node -
   retries, money routes, refusals and cards are untouched, and the citations
   event narrows to the cited chunks (founder-ratified cited-only, 2026-10-19;
   internal only, see `design-slice-3.md`). Structural result: `agent grounded
   tool answer` fired 8
   times (4 per run, only on sababa's tool turns) and that line exists only
   inside the new branch; the hybrid tenant's single completed tool turn ran
   `llm_call_count` 3 (2 agent rounds + inspection, no draft) where the same
   shape was 4 - 0.50 from one baseline p50 and 1.0 from the other, n=1, so the
   mechanism is the load-bearing evidence, not the sample. The fast tenants did
   not move (p50 delta 0; sababa2 held its 0.00 band exactly, bytefix inside
   1.90). Seven of the 8 grounded turns ran straight to the gates and run 1's
   grounded knowledge turn was rejected and redrafted by the draft node - the
   retry edge still works. On those turns the branch emitted ZERO citations
   events (`cited: 0` on all 8); run 1's lone `citations` event belonged to that
   redraft, not to the new branch. The narrowing is internal only: the controller
   strips citation markers from every approved token run before the flush and
   before persistence (`app/features/chat/controller.py:71-102`, via
   `app/shared/text.py:42`), so the customer surface renders no chip on either
   path - `renderWithCitations` only emits a `CitationChip` for a `[n]` that
   never survives (`frontend/src/app/[slug]/CustomerChat.tsx:117-124`), and
   `CitationChip` has no rendering surface (`design/frontend.md:377`). Cited-only
   is the ratified behaviour, with no fallback to all retrieved chunks.
   Completion rate did not rise and p50s stayed above the revised bands (as
   pre-slice runs in the same window did) - corroboration only. The after-eval
   is case-for-case identical to the baseline on trajectory and injection and
   moved only on generation (faithfulness -0.0311, answer_relevancy +0.0668,
   citation_faithfulness +0.0485); `run_gate`'s own rule therefore FAILS
   generation by 0.001. The eval never exercises the changed path, and it cannot:
   `_tools_for` returns the fast-path tool list before the retrieval tools are
   appended (`agent_node.py:604-605`), and both eval tenants are fast-path (0 of
   116 replayed cases take the branch). The -0.0311 drift is NOT noise: the
   identical-code repeat spread is +0.0019 (`data/eval-noise-repeat.md`), ~17x
   smaller, so it is a between-window level shift - likely provider-side drift,
   unproven with one baseline sample - and the -0.03 tolerance cannot resolve a
   drift of that size. Founder ruling 2026-10-19: accepted as a provider level
   shift and **closed** by ruling, explicitly not reclassified as noise, with the
   tolerance unchanged. Slice verdict: **pass on the mechanism**, with the thin
   sample and both rulings (the accepted FAIL; citations cited-only and internal)
   recorded in `report-slice-3.md`.
4. Parallelize retrieval (`backend/app/retrieval/service.py:43-60`): sparse
   search needs no embedding, so embed and search can run together; a
   `search_ms` drop; watch transaction and connection semantics.
   **Outcome (implemented, measured - pass structurally, no-measurable-effect on
   the clock).** Landed in `040a473` and measured there. The final shape: the
   sparse query starts first and the embedding runs beside it, and dense is
   awaited once the embedding is in hand AND sparse has landed - because a
   connection runs ONE operation at a time (a second in-flight query raises
   asyncpg's `InterfaceError`, which the first cut hit: with the test embedder
   returning without yielding, dense started while sparse was still pending, and
   the existing retrieval tests caught it) and the RLS tenant context lives on
   the caller's connection, so no second connection is available to this
   function. Fused inputs stay `[dense, sparse]`, the filters and the rerank call
   are untouched, and the failure semantics are the sequential ones (the awaited
   embedding's error wins; an in-flight sparse task is cancelled and its outcome
   taken). Bands: the documented rule - completed hybrid turns - has NO sample
   (`sababa` completed one turn in six runs), so the fallback (every hybrid turn
   that ran `retrieve`) gives `search_ms` 2.52 ms, `embed_ms` 68.4 ms and
   `rerank_ms` 247.0 ms. Hybrid `search_ms` p50 fell in both runs (1.9-2.7 ->
   1.25 / 1.15) with every p50 delta inside the band, but `rerank_ms` - which
   this slice cannot touch - also steps over its own band once, so the bands
   cannot certify a causal claim in either direction. The ceiling is physical:
   only the sparse query's own duration can move, measured at median 0.38 ms
   against a 506-1098 ms warm `retrieve`. **No scored eval**: the change is
   output-preserving by construction (pinned by an equivalence test against a
   spelled-out sequential reference, plus a tie fixture that pins the fusion
   argument order - the equivalence test cannot see a swap, since fused scores
   are order-independent) and both eval tenants are fast-path, where
   `get_business_context` returns the corpus before `retrieve` is called
   (`services/retrieval.py:138-149`) - confirmed by the 80 fast-path turns of the
   eight committed runs (2 tenants x 5 turns each, every one null) and by slice
   3's replay (0 of 116 cases used a retrieval tool). The deterministic gate that
   does call `retrieve` passes with recall@5
   1.000 / MRR 0.911 / nDCG@5 0.934, identical to the pre-change logs. Full
   write-up: `docs/agencx/evidence/latency-2026-10/report-slice-4.md` and
   `data/slice4-bands.md`.
5. Prompt caching, replacing the per-request spotlight nonce. The security
   ruling is recorded (supervisor, under the founder's delegation of
   2026-10-19): the nonce is retired for ONE fixed 16-hex delimiter, so the
   prompt prefix is byte-identical across calls and the provider can cache it.
   Enforcement is `escape_delimiters` - now tolerant of case, whitespace,
   invisible and full-width delimiter disguises, and emitting a non-forgeable
   `escaped` marker - plus the standing instruction plus Inspection; the fixed
   token is public by design and the injection gate guards the decision.
   **Gate:** no regression against injection's 0.967 (the founder's stated
   baseline - re-measured first at 0.9667).
   **Outcome (implemented, measured, gate PASS - cache proven, no clock claim).**
   The change landed in `7613091` with the review hardening in `d99ca54` (the
   measured tip), and the turn record gained `cached_input_tokens`. **Injection
   gate: PASS** - 29/30 = 0.967 >= 0.9667, the same single leak
   (`direct-policy-invent-01`), and both delimiter-forgery cases held; row
   `513cec2f`. **Cache reads are proven:** `cached_input_tokens` is non-zero in
   both runs - run 1 (cold) cached on 6 of 15 turns, 29,056 of 140,884 input
   tokens (20.6%); run 2 (warm) on 14 of 15, 109,184 of 169,219 (64.5%); turn 1
   of every tenant is always cold. Per-tenant cached totals: bytefix
   5,376 -> 27,904; sababa2 12,288 -> 60,672; sababa 11,392 -> 20,608.
   **No clock claim:** 10 of 15 turns per run hit the 10 s turn budget and are
   censored out of the percentiles, so the completed samples are thin (bytefix
   1/5 and 2/5, sababa2 1/5 and 2/5, sababa 0/5 both runs). Generation (45
   cases; row `e8ab818f`) faithfulness 0.7628, answer_relevancy 0.8124,
   citation_faithfulness 0.3737, refusal 0.000; the faithfulness rise (+0.0465
   against the slice-3 after row) is OUTSIDE the +0.0019 identical-code spread -
   an upward between-window shift with no mechanism in a delimiter-byte change,
   so it is not a regression and is not attributed to this slice, while
   answer_relevancy (+0.0099) and citation_faithfulness (+0.0045) sit inside
   their same-code spreads. Trajectory (41 cases; row `6219ba04`)
   tool_correctness 0.6098 (25/41), persona 1.000, step_efficiency 0.9677; the
   identical-code repeat (row `302b9a94`) gives 0.6341 (26/41), persona 1.000,
   step_efficiency 0.9797 - so the -0.0244 delta IS the same-code spread, the one
   flipped case being `knowledge-price-match-01` (flaky; failed once, passed on
   repeat), inside `run_gate`'s -0.03. Full write-up:
   `docs/agencx/evidence/latency-2026-10/report-slice-5.md` and
   `data/slice5-cache.md`.
6. Paid-tier A/B across the matrix: latency, cost, and tool-call correctness
   per model.
   **Outcome (implemented, measured - NO WINNER).** The cache-adjusted cost model
   shipped in `2004617`: `evals/latency_report.py` prices cache reads when
   `input_cache_read` is published - `(input - cached)*prompt +
   cached*cache_read + output*completion`, with `cached` clamped to `input` per
   turn - and keeps the all-input-at-prompt formula byte-for-byte when absent;
   four tests pin legacy identity, the reduced figure, absent-price and clamping.
   The OpenRouter matrix ran twice at `2004617` with
   `LATENCY_MODELS=all` and is heavily censored by the 10 s budget: 13/15,
   14/15, 12/15 and 14/15 turns for deepseek run 1, ling run 1, deepseek run 2
   and ling run 2. Cache-adjusted costs (live prices, clamped):
   deepseek $0.003906/$0.002753, ling $0.001692/$0.001563 - 28-60% below the
   cache-blind figures. Ling's trajectory eval cannot run in this window: its
   providers reject structured outputs (`BadRequestError` 400 from Novita, "model
   features structured outputs not support"; the retry surfaced an upstream
   error body with no choices), so both attempts aborted before the aggregate
   insert and no `eval_runs` row or tool-correctness number exists
   (`data/eval-slice6-ling-trajectory.log`,
   `data/eval-slice6-ling-trajectory-retry.log`; the slice-5 pairing stayed
   intact). The production primary Google gemini-3.5-flash-lite was added as a
   config row (`models/gemini-3.5-flash-lite`; no published price, cost `n/a`):
   it completed 10/15 turns in run 1 (including drafted `sababa` turns, 4/5) and
   2/15 in run 2 where Google 429s censored `sababa` entirely. **No winner:**
   completed moves are card turns or n<=4, ling has no correctness score, and
   the Google window swings 10 to 2 - a cross-model window this censored
   supports no latency or correctness ranking. Write-up:
   `docs/agencx/evidence/latency-2026-10/report-slice-6.md`,
   `data/slice6-matrix.md`, `data/slice6-google.md`.
7. Streaming with inspection off the critical path - deferred; needs a
   chunked-validation design, a security ruling, and eval rework, and may be
   unnecessary if 2 through 6 land.

## Corpus

| Tenant | Vertical | Path (expected) | LLM calls (expected) |
|---|---|---|---|
| sababa2 | restaurant | fast | 2 |
| sababa | restaurant | hybrid | 4 |
| bytefix | phone repair | control | 2 |

`sababa` versus `sababa2` is a controlled A/B on the same 96-item menu.
`northgate` is limits-only, not a corpus tenant: its seed path is dead on the
pre-existing ABN/GST onboarding-confirm gap, so it cannot serve a real turn yet
(see `docs/agencx/evidence/latency-2026-10/data/tenant-limits.md`).

## Model matrix

The committed config is `backend/evals/latency_config.json`. At the time of
writing, two OpenRouter candidates are runnable, and both Zen probes are
blocked with recorded reasons and artifacts:

| Route | Model id | Tier | State |
|---|---|---|---|
| OpenRouter | `deepseek/deepseek-v4.1-flash` | candidate | runnable |
| OpenRouter | `inclusionai/ling-3.0-flash` | candidate | runnable |
| Zen | `opencode/ling-3.1-flash-free` | probe | blocked: absent from the live catalogue |
| Zen | `opencode/space-bunny-free` | probe | blocked: the endpoint refuses non-OpenCode clients |

The Zen rows show OpenCode's provider-namespaced id for readability; the Zen
endpoint expects the **bare** id (`space-bunny-free`), which is what the
config's `api_model` carries. See the `data/opencode-*-__bytefix.json` skip
artifacts for the exact catalogue and error.

## Open decisions

- Noise tolerance, revised and derived from four runs. The rule, verbatim:

  > band = max over the comparable run pairings (slice2-run{1,2} vs
  > noise-run{1,2}) of max(|delta p50|, |delta p95|) on `total_ms`, over
  > completed turns.

  The four runs are the two slice-1 baselines (noise-run1/2) plus slice2-run1/2;
  slice 2 counts as an unchanged-mechanism run because its output cap never
  bound. The going-forward bands, with the pairing that drives each:

  | tenant | band (ms) | driven by | completed turns (noise1/noise2/slice2run1/slice2run2) |
  |---|---|---|---|
  | bytefix | 2950.80 | p50 (3977.35 vs 6928.15) | 4/2/3/4 |
  | sababa2 | 2031.33 | p95 (5579.67 vs 7611.00) | 4/3/3/4 |
  | sababa | 2532.65 | p50 (6587.55 vs 9120.20) | 2/1/1/0 |

  A change counts as real only when it exceeds its band.
- Mechanism plausibility comes first: a slice that cannot mechanically affect a
  timing metric - for example an output cap that never binds - is judged inert
  regardless of whether the noise happened to move inside or outside the band.

## Evidence standard

Every number is traceable to the command that produced it. Provider prices are
read live from the provider's models endpoint at run time and stored with the
fetch timestamp, never taken from a config comment.

## Report format

One report per slice or work item, under 300 words, beside its data.

## Merge readiness (slices 1-4)

Checked at the tip of `latency/stack` when the cumulative package landed
(`report-cumulative.md`):

- **Gates green:** `make lint` (ruff check + the import contracts),
  `make typecheck` (mypy strict + `tsc`), `make test` (1418 passed),
  `make format-check` (248 files clean, recorded in `data/format-check.log`).
- **Tree state:** nothing uncommitted but the pre-existing, unrelated deletions
  (26 RF-17 evidence files + untracked `.claude/`); no runtime drift beyond the
  slices themselves. A stray `brag-output/` line was added to `.gitignore` by
  something outside this work during the wrap-up window - it is left untouched and
  is not part of any slice.
- **No reseeds:** `bytefix` is still `e9139d84-0e9f-4282-9af6-e0dc9bf4b56e` and the
  injection probe `464b8823-e113-4a0b-adef-db70db79d44d`; the baseline, after and
  repeat `eval_runs` rows are all intact.
- **Branch:** `latency/stack`, unpushed, no upstream configured.

**Re-checked at the slices 1-6 tip (`5a4578a`).** Gates green:
`make lint-backend` (3 contracts kept), `make typecheck-backend` (246 files),
`make format-check` (248 files) and `make test-backend` (1435 passed), tails in
`data/gates-slice6.log`; the same tree state (only the pre-existing dirty
entries plus the docs this package adds), the same two tenant ids (no reseeds),
and the branch still unpushed. The newest `eval_runs` rows per type are in the
same log; `run_gate` has no failing type (generation 0.7628, trajectory 0.6098
with its identical-code repeat at 0.6341, injection 0.967).

**Rulings recorded (2026-10-19).** The two founder-facing items this section
carried are closed: the slice-3 citations narrowing is ratified as cited-only (no
fallback to all retrieved chunks) and is internal - the controller strips markers
on both paths, so no chip renders either way; and `run_gate`'s generation FAIL
(-0.0311 against a 0.03 tolerance) is accepted as a provider level shift and
closed by ruling, not reclassified as noise, with the tolerance unchanged. This
close-out is docs-only: it changes no code and does not invalidate the gates
recorded above.

**Ruling recorded (2026-10-20, slice 5).** The per-request spotlight nonce is
retired for one fixed 16-hex delimiter so the prompt prefix is cacheable; the
decision was taken by the supervisor under the founder's delegation of
2026-10-19 and is guarded by the injection gate (no regression against 0.9667),
which passed. The fixed token is public by design; the enforcement is
`escape_delimiters` (case/whitespace/invisible/full-width tolerant, with a
non-forgeable `escaped` marker) plus the standing instruction plus Inspection -
none of the three may be weakened without re-running the injection gate. Details
in `docs/agencx/evidence/latency-2026-10/report-slice-5.md`.

**Blockers before merge** (founder-facing):

1. **Slice 7.** Slice 6 (paid-tier A/B across the matrix: latency, cost, and
   tool-call correctness per model) is **closed with no winner**: the cost model
   shipped, the OpenRouter matrix is heavily censored on both runs, ling cannot
   be scored for tool correctness (its providers reject structured outputs), and
   the Google primary swung from 10/15 to 2/15 under 429s. Slice 7 (streaming
   with inspection off the critical path, which needs a chunked-validation
   design, a security ruling and eval rework) is **deferred**: it changes when a
   customer sees model prose and the US-060 inspection buffer is ratified, so
   only a founder scope decision reopens it.
2. **The merge request itself.** One merge to `development`, then `staging`, only
   on the founder's go.

## Instrument

The runner is `backend/evals/latency_run.py`; the record sink is
`backend/app/observability/turn_record.py`; the percentile math is
`backend/app/observability/percentile.py`. The protocol follows
[Agent Conventions](../../design/conventions.md).
