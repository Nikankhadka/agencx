> **NAVIGATION:** Always binding - this is the one source doc every session obeys in full (root `AGENTS.md` summarizes it).

# WREN - Agent Conventions
 > **Version:** 2.0 | **Applies to:** any AI agent executing work against the Agencx PRD (`docs/agencx/prd.md`) and Architecture Doc (`docs/agencx/architecture.md`).
 > Read this alongside those documents, not instead of them. Where a ticket's acceptance criteria and this document seem to conflict, this document wins on *how* work is done; the PRD/Architecture docs win on *what* is being built.

---

## 1. Writing style

The base standard is the Google developer documentation style guide
(developers.google.com/style), applied at two tiers. Where Google and this
section conflict, this section wins.

**Standing override:** never use the em dash, anywhere - prose, commit
messages, code comments, documentation. Plain dash "-" only. Google permits the
em dash; this repo does not.

### Tier A - reference and procedure

`running.md`, `deploy.md`, everything in `spec/`, every README index, the
`AGENTS.md` command tables, and all agent output. Full Google style:

- Second person, present tense, active voice. The reader is "you"; never "we"
  or "our" for something the reader does.
- Procedures are numbered lists of imperative steps, one action per step. State
  the outcome before the command, not after.
- Headings are sentence case and name a task or a thing. Write "and", never "&".
- Link text names the destination. No "here", no bare URLs, no "see above" or
  "see below" - link to the section instead.
- Code font for commands, paths, filenames, env vars, and identifiers. No `$`
  prompt inside shell blocks.
- Banned: simply, just, easy, obviously, please, note that, sanity check, dummy.
- Serial comma. Numerals for 10 and up; words for zero through nine, except in
  measurements, versions, and table cells.

### Tier B - narrative and record

`prd.md`, `architecture.md`, `design/decisions.md`, `design/frontend.md`,
`design/database.md`, `progress.md`, `LEARNINGS.md`, and this file. The essay
voice in these documents is deliberate and stays. They obey the mechanical
rules only: sentence case headings, "and" not "&", descriptive link text, no
directional cross-references, code font for code, and the banned-word list.

### Agent output: plans and messages

Plans and chat replies follow Tier A, plus:

- Lead with the finding or the answer. No preamble about what you are about to
  do, no restating the request back.
- Every file, symbol, or line referenced is a relative markdown link
  (`[running.md:33](docs/agencx/running.md#L33)`), never a bare backticked path.
- A claim about this codebase carries the path and line that proves it. An
  unverified claim is labelled unverified, or is not made.
- Say what you did not do and why, in the same message as what you did.
- No status theatre: no "Perfect!", no summary of the summary, no closing recap
  of a message the reader has just read.
- A plan file runs in this order: Context (why this change exists), the work
  itself, then Verification (how to prove it end to end).

## 2. Git conventions

- Never add an agent name (Claude, Claude Code, or otherwise) as a co-author on commits.
- Commit messages describe what changed and why, in plain language.

## 3. Auto-generated files

- Never manually modify `CHANGELOG.md` or any file marked as auto-generated. If the project adopts a changelog tool during Week 1 (T-001), that tool owns `CHANGELOG.md` from that point forward - it is not a place for direct hand-edits, ever, by a human or an agent.

## 4. How technical decisions get made

When an implementation choice isn't already pinned down by the Architecture Doc (schema shape, error-handling approach, how thoroughly to test a module, whether to add an abstraction), resolve it by favoring **quality, simplicity, robustness, scalability, and long-term maintainability** over how much time or effort it takes. Development cost is not the deciding factor at the code and system-design level.

**This does not reopen the project's scope boundaries.** The 30-day clock, the MoSCoW cuts in the PRD, and the cut-order list in the Sprint Plan are calendar and portfolio-scope constraints, not corner-cutting decisions - they stay fixed. This rule governs how well the *in-scope* work is built, not how much gets built. If following this rule on a specific ticket would clearly blow the calendar (not just take a bit longer), flag it back rather than silently either cutting scope or blowing the clock.

Per the Architecture Doc's closing note: anything not already decided in these documents that turns out to matter architecturally should be flagged back to the founder, not silently decided mid-build. This rule is the default for the small stuff; it isn't a license to skip that flagging for anything genuinely consequential.

## 5. Bug-fix protocol

Before writing a fix for any bug (during the 30-day build or in the post-launch "next sprint" iteration loop), first reproduce it in an end-to-end setting as close as possible to how a real end user would hit it - through the actual customer chat surface or the tenant admin console, not a unit test or a direct API call, unless the bug is already known to be isolated at that layer. Reproducing it for real is what confirms the fix addresses the actual problem rather than a guessed-at symptom.

### 5.1 Flow-change confirmation

A change to a working user-facing flow - the onboarding interview script or beat order, the chat routing between fast and hybrid paths, the publish/confirm sequence, or any other multi-turn behavior a user has already exercised successfully - is flagged to the founder before it is made, with the current behavior and the proposed behavior both stated. This applies even when the change is a refactor that is not intended to alter behavior: intent and actual behavior have diverged before in this codebase (the onboarding beat-versus-paraphrase seam W-2 closes is the concrete example), and the flag is what catches that divergence before a user does.

## 6. End-to-end testing and UI standard

Whenever end-to-end testing the product (the customer chat surface, the tenant admin console, the platform-owner surface, the escalation flow, the dashboards), be exacting about the UI. If something looks visibly off - misaligned, inconsistent spacing, a broken state, a confusing empty state - fix it along the way even if it isn't related to the current ticket. This applies most directly to E10/E11/E12 (the three surfaces) and the Week 4 polish pass.

Building a screen is a separate discipline from testing one: **UI is ported from the prototype, never designed from ticket text.** Every Phase 1 screen already exists in `docs/agencx/design/prototypes/` (`agencx-prototype-v6.html` is current; `agencx-storefront-customer-v3.html` is the superseded storefront, good for interaction vocabulary only), and each UI ticket names its exact screen or render function in a "Design reference" section. Read that screen before writing the component and match its structure, states, spacing, and interaction vocabulary. Take behaviour, never strings (prototype copy is demo copy), and never hex values - visual values land as `theme.css` tokens, which CI enforces.

## 7. Engineering hygiene

Treat lint errors, failing tests, and flaky tests as blocking wherever they're encountered, regardless of whether the current ticket caused them. Fix them as part of the work rather than working around or ignoring them. This applies to the CI regression gate and everywhere else in the codebase.

---

## 8. The deterministic-pricing invariant (hard rule, never relaxed)

No language model - in any agent, on either side of the system - ever produces, computes, or emits a monetary amount. Agents select pricing rules, catalog items, and quantities; the deterministic pricing engine computes every total in integer cents. This holds at three layers, all of which must stay true:

- **Agent layer**: the Quoting Agent's output schema carries a *selection* (rule codes, item ids, quantities) and free-text descriptions, never a number field the model fills in.
- **Validation layer**: the reasoning-inspection/supervisor layer blocks any quote whose displayed amounts don't reconcile to the pricing engine's output, and blocks any response containing a figure that doesn't trace to it.
- **API layer**: no endpoint accepts a client- or model-supplied total; monetary amounts are server-computed only, and a request carrying one is rejected.

If any ticket's implementation would let a model-authored number reach a customer or a stored quote, that implementation is wrong regardless of what the ticket text says - stop and flag it. This invariant outranks convenience, speed, and any individual ticket's phrasing.

## 9. The domain-agnostic invariant (hard rule, never relaxed)

Wren is one codebase serving any business vertical - a dentist, a butcher, a phone repair shop, an online store - through per-tenant configuration and uploaded knowledge alone. This holds at three layers:

- **Agent layer**: no agent, prompt template, tool, or routing rule ever branches on a vertical name or business type (no `if vertical == "dentist"` or equivalent, anywhere). Behavior differences come from `tenant_config`, `offerings`, `pricing_rules`, and uploaded knowledge, never from code.
- **Data layer**: schema fields describe generic concepts (services, items, rules, thresholds), never vertical-specific ones. If a field name only makes sense for one vertical, it's modeled wrong - push it into a config/knowledge value instead.
- **Test layer**: the generalization proof (onboarding a second, structurally different tenant by config alone, per the Sprint Plan) is not a demo trick - it is the test that this invariant actually holds. If Tenant 2 requires a code change, that change is a bug in this invariant, not a normal feature request.

A single vertical-branch in agent or tool logic invalidates the platform's central claim. Treat it with the same severity as a cross-tenant leakage failure - stop and flag it, don't work around it.

## 10. Where this shows up in the existing docs

- The PRD's (`docs/agencx/prd.md`) keep/pivot/stop signals should be read as including: no known lint errors, and no failing or flaky tests, in CI at the time v1 is called shipped, and zero model-authored monetary figures (per section 8 above).
- Engineering hygiene (section 7 above) is maintained continuously, not swept up at the end of a phase.
- Any ticket touching a customer- or tenant-facing surface should be read as including: fix visibly broken UI encountered along the way, per section 6 above.
- Any ticket touching agent, tool, retrieval, or pricing logic should be read as including: no vertical-specific branching, per section 9 above.

## 11. Document maintenance

- Keep open tickets in `docs/agencx/spec/active/`.
- When every ticket in a phase is complete, move its file to
  `docs/agencx/spec/completed/` with `git mv`.
- When a ticket ships, update `docs/agencx/progress.md` with its status and
  evidence.
- When a decision, assessment, or prototype is superseded, preserve it under
  `docs/archive/` and update the archive index.
- Do not delete historical content merely to shorten an active document.

*End of Agent Conventions v2.0.*
