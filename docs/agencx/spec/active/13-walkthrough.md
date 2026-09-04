# Phase 13: walkthrough fixes (W)

A founder walkthrough of the deployed build surfaced defects across three
surfaces: the owner's home escalation queue, the onboarding interview, and
customer chat grounding. Some of what the walkthrough asked for already
shipped on this branch and needs refinement, not rebuilding:

| Commit | What it already delivers |
|---|---|
| `8496f25` | Rounded escalation card, count pill on top, per-customer rows with name, age, and an assistant-written summary, oldest first, direct `/chats/:id` link, amber count badge on the Chats tab |
| `497bbf3` | Onboarding knowledge review sheet, document offering candidates |
| `0ebd1fc` | Confirmed offerings injected into the customer system prompt |

So the escalation ask is largely built; W-1 covers what remains. The
onboarding and retrieval defects (W-2 through W-6) are unaddressed.

Ticket id prefix `W-` (Walkthrough), unused elsewhere in the ticket set. Six
tickets, in build order. W-5 precedes W-6 so the reported chat bug closes
before the document-extraction feature builds on top of it.

---

## W-1: The escalation queue fits the screen and does not go stale

### Summary

Replace the fixed three-row cap on the home screen's waiting-customer panel
with a screen-fitted scroll cap, keep the Chats tab badge and the panel in
sync with the server without a manual refresh, and correct a token
discrepancy between the panel's own comment and the token it uses.

### Why

[WaitingPanel.tsx:34](../../../../frontend/src/app/(tenant-admin)/(console)/home/components/WaitingPanel.tsx#L34)
hard-codes `COLLAPSED_ROWS = 3` regardless of viewport, so a desktop window
with room for eight rows still shows three behind a "Show all" tap.
Separately, [QueryProvider.tsx:22-25](../../../../frontend/src/components/QueryProvider.tsx#L22-L25)
sets `staleTime: 30_000` with no `refetchInterval`, so the panel and the
Chats tab badge (both driven by `/api/conversations`, per
[layout.tsx:85-91](../../../../frontend/src/app/(tenant-admin)/(console)/layout.tsx#L85-L91))
keep showing a resolved escalation as waiting until the owner navigates away
and back. The panel's own comment at
[WaitingPanel.tsx:20](../../../../frontend/src/app/(tenant-admin)/(console)/home/components/WaitingPanel.tsx#L20)
claims the count pill uses "the prototype's actual amber, `--amber-400`", but
[theme.css:270](../../../../frontend/src/styles/theme.css#L270) points
`--color-highlight` at `--amber-300`.

### User stories

#### US-1 An owner on a small screen sees a manageable list

As a tenant owner on a phone, I see roughly the number of waiting customers
that fit below the greeting without the home screen feeling congested, and I
can scroll or expand to see the rest.

- The collapsed list height is unchanged from today's three-row feel on a
  phone-width viewport.
- Expanding still reveals every waiting customer, oldest first, matching
  today's ordering.

#### US-2 An owner on a desktop sees more at once

As a tenant owner on a wide screen, I see more waiting customers before I
need to scroll, because the screen has the room.

- At the `lg` breakpoint (1024px), the collapsed panel shows roughly five
  rows before scrolling, not three.
- No layout shift or content jump when the window crosses the breakpoint.

#### US-3 The count reflects reality without a manual refresh

As a tenant owner, once I resolve a customer's escalation, the panel and the
Chats tab badge stop showing them within a few seconds, without me needing to
reload the page.

- The `/api/conversations` query underlying both surfaces refetches on an
  interval while the console is open, matching the cadence the conversation
  thread page already polls at
  ([chats/[id]/page.tsx:28](../../../../frontend/src/app/(tenant-admin)/(console)/chats/[id]/page.tsx#L28),
  4 seconds).

### Design reference

The prototype (`agencx-prototype-v6.html`) has no per-customer escalation
card and no count pill; its only notification affordance is a bare dot,
`#ndot` (line 32), with no number. `8496f25` already established the row
idiom by porting the chats screen's `.chat-row` (line 138: name, time,
truncated preview). This ticket does not introduce new visual vocabulary; it
changes how much of that existing list is visible before scrolling, and how
current the data behind it is.

### Technical spec

- In `WaitingPanel.tsx`, remove the `rows.slice(0, COLLAPSED_ROWS)` split.
  Render every row inside one `overflow-y-auto` container whose collapsed
  `max-height` is sized for roughly three rows by default and roughly five
  at `lg:` (the console's one mobile/desktop switch, per
  [layout.tsx:109](../../../../frontend/src/app/(tenant-admin)/(console)/layout.tsx#L109)
  and [TabBar.tsx:57](../../../../frontend/src/components/ui/TabBar.tsx#L57)).
  The existing expanded caps (`max-h-[288px] lg:max-h-[432px]`, one row taller
  each) are the reference for computing a per-row height; the collapsed cap
  is the same formula at the lower row count.
  Do not add `matchMedia`, a resize listener, or client-only state to measure
  the viewport - the repo has no such hook today, and a CSS breakpoint is the
  established pattern.
- Keep the toggle. Its visibility condition becomes "does the list overflow
  its collapsed cap", which for a short list is equivalent to today's
  `rows.length > COLLAPSED_ROWS` check; for a list that fits within the
  collapsed cap but was previously hidden behind the row-count cap (four rows
  on desktop, say), the toggle no longer appears, because there is nothing to
  reveal.
- Add `refetchInterval: 4000` to the `useApiQuery<ConversationSummary[]>("/api/conversations")` call.
  Both call sites share the query key, so one option change covers
  [home/page.tsx:49](../../../../frontend/src/app/(tenant-admin)/(console)/home/page.tsx#L49)
  and [layout.tsx:85](../../../../frontend/src/app/(tenant-admin)/(console)/layout.tsx#L85).
  Confirm `useApiQuery` (wherever it wraps `useQuery`) passes an
  options-object override through; if it does not yet, add the pass-through
  rather than hard-coding the interval inside the hook.
- Resolve the token discrepancy: either repoint `--color-highlight` at
  `--amber-400` in [theme.css:270](../../../../frontend/src/styles/theme.css#L270),
  or correct the WaitingPanel comment to name `--amber-300`. Pick whichever
  matches the prototype's literal `--c-amber:#F5A623` (prototype line 13);
  `--amber-400` is `#F5A623` and `--amber-300` is not, so the fix is to
  repoint the token, not the comment.

### Tests

- Frontend: a viewport-width test (or a `lg:` class assertion) confirming the
  collapsed container's class differs between the default and `lg:` cases.
- Frontend: existing `WaitingPanel` tests updated for the new collapse
  mechanism (no more slicing to exactly three items).
- Frontend: `home-brief.spec.ts` (E2E) still passes the direct-open assertion
  unchanged.
- Manual: resolve an escalation in one tab, confirm the badge in a second
  open tab clears within one polling interval.

### Definition of done

- [ ] Collapsed row count is CSS-breakpoint-driven, not a fixed JS constant.
- [ ] `/api/conversations` refetches on an interval; badge and panel self-heal
      without a manual reload.
- [ ] `--color-highlight` and its documenting comment agree on one amber
      value, matching the prototype's `--c-amber`.
- [ ] `make check` green.

---

## W-2: The interview never re-asks a question it already has an answer to

### Summary

Stop the onboarding assistant from re-asking a filled slot. Make the
question the owner sees a server-owned, verbatim string instead of an
LLM paraphrase; keep the extractor free to capture any field from any
answer (so an off-beat reply like an offer list given while hours are being
asked still gets filed correctly and acknowledged); add a repeat guard for a
slot that genuinely will not fill; and reword the hours question so it
answers both hours and days in one turn.

### Why

The founder's transcript shows the business-name question asked three times
after `business_name` had already been captured, and the assistant
apologizing without correcting course:

> Hi! I'm your Agencx setup assistant... What's your name?
> ... Nice to meet you, Nikan! What does your business go by?
> sababa
> ... What kind of business is it?
> ...
> Got it, 7 to 8. What would you like customers to know you offer?
> pita coffee wraps and more
> Great, "pita coffee wraps and more" sounds delicious! ... **What's the name
> of your business?**
> i already told u
> Got it - pita, coffee, wraps, and more. Thanks for sharing! ... **What's
> the name of your business?**

Root cause: [beats.py:182-187](../../../../backend/app/onboarding/beats.py#L182-L187)
(`next_beat`) picks the next unanswered slot deterministically and
correctly, but [agent.py:420-432](../../../../backend/app/onboarding/agent.py#L420-L432)
hands that choice to a second LLM call as advisory prose (a directive string
built by `as_prompt()` at [agent.py:50-57](../../../../backend/app/onboarding/agent.py#L50-L57),
`"Ask for: {ask_for}"`) which composes the visible question freely, with only
a three-message history window
([agent.py:428](../../../../backend/app/onboarding/agent.py#L428)) and a
system prompt that lists every field by name
([agent.py:60-67](../../../../backend/app/onboarding/agent.py#L60-L67)).
Nothing checks that the emitted text actually asks for `ask_for`. This design
has been in place since the first onboarding commit (`e919435`) and has never
been changed; the one place that already emits the beat's question verbatim
is the chip-selection path
([agent.py:241-244](../../../../backend/app/onboarding/agent.py#L241-L244)),
which free text does not go through.

Two supporting defects feed the same symptom:

- **Conditional persistence can rewind the pointer.**
  [agent.py:402](../../../../backend/app/onboarding/agent.py#L402) only
  persists a turn when `acknowledged` is non-empty or the turn was not flagged
  off-topic. `offering_names` is not counted toward `acknowledged`
  ([agent.py:397-398](../../../../backend/app/onboarding/agent.py#L397-L398)),
  so a turn that yields only offering names and is flagged off-topic is
  computed, shown to the owner, and never saved. Because `next_beat` rescans
  `BEAT_ORDER` from index 0 every call with no forward cursor, the next turn
  reloads the older database row and can land back on an earlier beat.
- **The extractor cannot route an offer answer into `services`.** The
  extraction prompt ([agent.py:77-84](../../../../backend/app/onboarding/agent.py#L77-L84))
  tells the model to list named offerings under `offering_names`, separate
  from `profile.services`, and never instructs it to also fill `services`
  when the reply is answering the offer question. An answer can leave
  `services` empty while still being a complete answer to that beat, which
  research also confirmed can produce a single merged offering
  (`"pita coffee wraps and more"`) instead of three, because splitting is
  delegated entirely to the model with no example covering an unpunctuated,
  conjunction-joined list.

### User stories

#### US-1 A filled slot is never asked for again

As a business owner, once I have told the assistant my business name, it
never asks for it again for the rest of the interview, no matter what I say
in between.

- Given `business_name` is set in the draft, the beat the assistant asks for
  next is never `business_name`, verified against the emitted reply text, not
  only against internal state.
- The visible question text matches the target beat's `ask` string exactly
  (server-emitted), for every beat.

#### US-2 An off-beat answer is captured, not discarded, and the flow continues on-topic

As a business owner, if I answer a different question than the one asked
(for example, naming what I offer while being asked about hours), the
assistant notes what I gave it, applies it to the right field, and still asks
me the question that is actually pending.

- Given the current beat is `hours` and the owner's reply names offerings,
  `services` (or `offering_names`) is filled from that reply.
- The next visible question is still the `hours` beat's `ask` (unless the
  reply also happens to answer `hours`), phrased as an acknowledgment of the
  off-beat information followed by the pending question, for example: "Great,
  you offer pita, coffee, and wraps - I have noted those. What are your
  opening hours, and which days are you open?"

#### US-3 An unpunctuated list of offerings becomes separate candidates

As a business owner, if I say "we offer pita coffee and wraps" with no
commas, the interview treats that as three offering candidates, not one.

- The extraction prompt gains an explicit example of a conjunction-joined,
  comma-less list yielding multiple `offering_names` entries.
- The review sheet (existing safety net from `497bbf3`) still lets the owner
  split, rename, or merge candidates before publish.

#### US-4 A slot that will not fill degrades gracefully instead of looping

As a business owner, if I cannot or do not want to answer a question after
two tries, the assistant stops repeating the identical sentence and offers a
way forward.

- A per-beat consecutive-ask counter is tracked in the onboarding record.
- The second consecutive ask of the same beat rephrases the acknowledgment
  and adds a concrete example.
- The third consecutive ask offers to move on and revisit the field later
  from Settings, and treats a "skip"-shaped reply as satisfying the beat with
  an explicit empty/placeholder value where the beat's semantics allow it.

#### US-5 The opening-hours question also asks about days

As a business owner, answering the hours question tells the assistant both
when I am open in a day and which days of the week I am active, in one turn.

- [beats.py:127](../../../../backend/app/onboarding/beats.py#L127)'s `ask`
  changes from "When are you open?" to a question that names both hours and
  days, for example: "What are your opening hours, and which days of the
  week are you open?"
- The extraction schema and prompt are updated so a reply covering only one
  half (hours or days) still fills what it answers and the repeat guard (US-4)
  handles the other half if it remains missing.

### Design reference

No visual change. The onboarding thread's structure, spacing, and composer
widgets are unchanged (`agencx-prototype-v6.html`, ONBOARDING section); this
ticket is entirely about which text the assistant emits and when.

### Technical spec

- **Beat-aware, still-open extraction.** Add the current beat's key and `ask`
  text to `_extraction_input` ([agent.py:262-270](../../../../backend/app/onboarding/agent.py#L262-L270))
  as context, not a filter: "The question asked this turn was: {ask}." Instruct
  the model to fill that field when the reply answers it, and separately to
  fill whatever other field(s) the reply actually answers when it answers
  something else instead. The extractor keeps its full nine-field schema; the
  beat hint only helps it disambiguate an ambiguous reply, it never narrows
  what can be captured.
- **Server-owned question text.** Change the reply-composition prompt at
  [agent.py:420-432](../../../../backend/app/onboarding/agent.py#L420-L432)
  so the model is asked to write only a short acknowledgment sentence of what
  was captured this turn (or of any off-beat information captured this turn), and
  explicitly told not to ask a question. The server appends `nxt.ask`
  verbatim after the model's acknowledgment:
  `reply = f"{ack} {nxt.ask}".strip()`. This is the same shape as the
  existing chip path ([agent.py:241-244](../../../../backend/app/onboarding/agent.py#L241-L244)),
  applied to free text. Update `_COPILOT`
  ([agent.py:60-67](../../../../backend/app/onboarding/agent.py#L60-L67)) so
  it no longer implies the model chooses or phrases the question.
- **Fill `services` from `offering_names` deterministically.** In the merge
  step ([agent.py:393](../../../../backend/app/onboarding/agent.py#L393) /
  `_merge_owner_offerings`), when `update.offering_names` is non-empty and
  `draft.get("services")` is empty, set `draft["services"]` to the
  comma-joined names. No extra model call; this is a plain server-side join.
- **Extraction prompt examples for unpunctuated lists.** Add one example pair
  to the prompt at [agent.py:77-84](../../../../backend/app/onboarding/agent.py#L77-L84)
  showing an input like "we offer pita coffee and wraps" mapped to
  `offering_names: ["pita", "coffee", "wraps"]`.
- **Repeat guard.** Add an `ask_count: dict[str, int]` (or a single
  `{beat, count}` pair, since only the current beat needs tracking) to the
  onboarding record's jsonb shape, bumped in `prepare_turn` when `next_beat`
  returns the same key as the previous turn's, reset to zero when it changes.
  At count 2, the reply-composition directive includes an instruction to
  rephrase and give a concrete example. At count 3, the directive offers to
  move on; a reply recognized as declining (already-handled "skip" vocabulary
  from the knowledge-offer path, [agent.py:218-223](../../../../backend/app/onboarding/agent.py#L218-L223),
  is the precedent) sets the field to an explicit placeholder that satisfies
  `beat.complete` (for text-shaped beats, the literal string the owner used,
  or a sentinel the Business tab already knows to render as "not set").
  `OnboardingRecord.from_jsonb`'s version gate
  ([agent.py:105-132](../../../../backend/app/onboarding/agent.py#L105-L132))
  needs its `version` literal bumped so old records reset cleanly rather than
  crashing on the new field's absence - this is the existing migration
  pattern, not a new one.
- **Persist every turn.** Remove the conditional at
  [agent.py:402](../../../../backend/app/onboarding/agent.py#L402); always
  call `service.save_record` after a turn (streaming and non-streaming paths
  both, per [controller.py:331-333](../../../../backend/app/features/onboarding/controller.py#L331-L333)
  and [controller.py:227-233](../../../../backend/app/features/onboarding/controller.py#L227-L233)).
  This guarantees the emitted `state` event and the stored record never
  disagree, closing the rewind path described above.
- **Hours beat rewording.** Update `beats.py:127`'s `ask` per US-5, and widen
  the beat's extraction guidance to expect a compound answer.

### Convention to add

The founder asked, in the walkthrough, for a standing rule that a working
conversational flow is not changed without a flagged confirmation. Add a new
subsection to [conventions.md](../../design/conventions.md), placed after
section 5 (bug-fix protocol), which it extends:

> ### 5.1 Flow-change confirmation
>
> A change to a working user-facing flow - the onboarding interview script or
> beat order, the chat routing between fast and hybrid paths, the publish/
> confirm sequence, or any other multi-turn behavior a user has already
> exercised successfully - is flagged to the founder before it is made, with
> the current behavior and the proposed behavior both stated. This applies
> even when the change is a refactor that is not intended to alter behavior:
> intent and actual behavior have diverged before in this codebase (the
> onboarding beat-versus-paraphrase seam this phase's W-2 closes is the
> concrete example), and the flag is what catches that divergence before a
> user does.

### Tests

Backend, in `backend/tests/test_onboarding_agent.py` or the equivalent
`agent.py` test module:

- A filled slot is never re-asked: seed a record with `business_name` set,
  run a turn whose reply is off-topic or answers a later beat, assert the
  emitted reply's `ask` portion equals the next unfilled beat's exact `ask`
  string and does not contain the business-name question text.
- An off-beat answer captures its own field and the pending beat is still
  asked: seed the current beat as `hours`, send a reply naming offerings,
  assert `services` or `offering_names` is populated and the emitted question
  is still the `hours` beat's `ask`.
- An unpunctuated, conjunction-joined answer yields more than one
  `PendingOffering` (via the new prompt example - this test may need a fixed
  provider response in the harness's `RecordingProvider` style, matching the
  pattern in `test_context_package.py`).
- A turn persists even when the extractor returns an empty `DraftUpdate`
  (regression test for the conditional-persistence fix).
- The repeat guard: three consecutive turns that fail to fill the same beat
  produce three distinct reply shapes (initial ask, rephrase-with-example,
  offer-to-skip), and a "skip"-shaped fourth reply advances past the beat.

### Definition of done

- [ ] The onboarding reply's question text is server-appended, not
      model-composed, for every beat (chip and free-text paths agree).
- [ ] A filled slot cannot be re-asked, proven by a regression test.
- [ ] An off-beat answer is captured without derailing the pending question.
- [ ] An unpunctuated offer list yields multiple candidates.
- [ ] A three-times-unanswered beat offers to move on instead of repeating.
- [ ] The hours beat asks for both hours and days.
- [ ] Every turn persists regardless of extraction outcome.
- [ ] [conventions.md](../../design/conventions.md) carries the new
      flow-change confirmation subsection.
- [ ] `make check` green.

---

## W-3: The onboarding thread reads as work in progress

### Summary

Remove the redundant "Answering…" status line (the thinking dots above it
already show this), stop the composer pill from changing height between
beats, and give a processing file upload the same dots-based motion the rest
of the thread uses instead of a static stamp.

### Why

- [page.tsx:595-607](../../../../frontend/src/app/(tenant-admin)/(console)/onboarding/page.tsx#L595-L607)
  renders `"Answering…"` in a status line below the composer while
  `TypingLine` ([Thread.tsx:129-135](../../../../frontend/src/components/ui/Thread.tsx#L129-L135))
  already renders pulsing dots above it in the thread itself for the same
  pending turn. The two say the same thing in two places.
- The composer widget swaps shape per beat - chip row, masked ABN pill, phone
  pill, or plain text pill
  ([BeatComposer.tsx:129-179](../../../../frontend/src/app/(tenant-admin)/(console)/onboarding/components/BeatComposer.tsx#L129-L179)) -
  and the plain textarea separately auto-grows with typed content
  ([CommandPill.tsx:28](../../../../frontend/src/components/ui/CommandPill.tsx#L28),
  [CommandPill.tsx:56-63](../../../../frontend/src/components/ui/CommandPill.tsx#L56-L63)).
  The combination reads as the composer randomly resizing between turns.
- An attached file gets one static text stamp,
  `"${file.name} · adding…"` ([page.tsx:378-383](../../../../frontend/src/app/(tenant-admin)/(console)/onboarding/page.tsx#L378-L383)),
  with no animation while the document is scraped, structured, and drafted -
  a multi-second operation the founder specifically flagged as needing a
  visible "still working" signal. `PROCESSING_COPY`
  ([page.tsx:86-88](../../../../frontend/src/app/(tenant-admin)/(console)/onboarding/page.tsx#L86-L88))
  already has a `reading_site` entry for the URL path; the upload path has no
  equivalent even though the backend emits `progress: processing` for it
  ([controller.py:335](../../../../backend/app/features/onboarding/controller.py#L335)).

### User stories

#### US-1 The assistant's "thinking" state is shown once

As a business owner, I see one clear signal that the assistant is composing
its reply, not a duplicated one.

- The thinking-dots row in the thread is the only pending-turn indicator.
- The status line below the composer is repurposed as the error slot only
  (see W-4) and shows nothing while a turn is in flight.

#### US-2 The composer holds a steady size between questions

As a business owner, the input area does not visibly grow or shrink when the
assistant asks its next question; it only grows as I type a longer answer,
and shrinks back when I clear it.

- Switching from one beat's widget to another's does not change the
  composer's baseline height.
- Typing still grows the textarea up to its existing 96px cap; clearing the
  text still shrinks it back.

#### US-3 A processing upload shows visible progress

As a business owner, after I attach a file, I see an animated indicator (not
a static line) while the document is being read and structured, so I know
work is happening in the background.

- The upload stamp shows a dots-based or equivalent animated state between
  "adding" and "added" (or the failure text), reusing the existing
  `ThinkingDots`/`ProcessingLine` vocabulary rather than a new spinner.
- A `processing` copy entry exists in `PROCESSING_COPY` alongside
  `reading_site`, used for whichever backend `progress` event corresponds to
  document structuring.

### Design reference

`ThinkingDots` ([ThinkingDots.tsx:21-33](../../../../frontend/src/components/ui/ThinkingDots.tsx#L21-L33))
and `ProcessingLine` ([Thread.tsx:144-150](../../../../frontend/src/components/ui/Thread.tsx#L144-L150))
are the two existing motion primitives this ticket reuses; no new component
or dependency. The composer's visual shell (pill, chip row, radii, shadow)
is unchanged - only its height stability.

### Technical spec

- Delete the `"Answering…"` branch from the status line at
  [page.tsx:595-607](../../../../frontend/src/app/(tenant-admin)/(console)/onboarding/page.tsx#L595-L607),
  leaving `{error ?? ""}`. Keep the element mounted (it stays the `role="status"`
  live region and gains the danger styling in W-4).
- Give the `BeatComposer` root or its widget wrapper a fixed minimum height
  matching the tallest common single-line state (the plain `CommandPill` at
  rest, `min-h-6` inside its padded shell), so a swap between chip/masked/
  phone/plain widgets does not change the composer's outer height on a normal
  one-line case. `CommandPill`'s own auto-grow (`useLayoutEffect`,
  [CommandPill.tsx:56-63](../../../../frontend/src/components/ui/CommandPill.tsx#L56-L63))
  is unchanged; this only stabilizes the shell around it.
- Replace the static `"${file.name} · adding…"` stamp's rendering
  with the existing animated line component while `busy` is true for that
  stamp, falling back to the static "added"/failure text once resolved. Add
  a `processing` (or equivalent) key to `PROCESSING_COPY` and have the
  backend's structuring stage emit a `progress` event of that name if it does
  not already (check `controller.py`'s upload path for an existing progress
  emission before adding a new one - the SSE-based URL path already has this
  shape at [controller.py:371](../../../../backend/app/features/onboarding/controller.py#L371);
  the file-upload path may need the same event added, since today's upload
  endpoint response is a single non-streamed POST per
  [page.tsx:401-406](../../../../frontend/src/app/(tenant-admin)/(console)/onboarding/page.tsx#L401-L406) -
  if it is not streamed, the client-side animation for the stamp is
  sufficient on its own and no new backend event is required).

### Tests

- Frontend: a snapshot or class assertion that the status line renders empty
  (not "Answering…") while `busy` is true.
- Frontend: a test that the composer wrapper's height class is stable across
  a beat change (e.g. render with `input.kind` toggled between `"text"` and
  a chip-bearing spec, assert the outer container's height-affecting classes
  are unchanged).
- Frontend: the upload stamp renders the animated state while its message is
  the "adding" placeholder.

### Definition of done

- [ ] No duplicate "Answering…" text; thinking dots are the sole pending
      indicator.
- [ ] Composer height is stable across beat changes; still grows with typed
      content.
- [ ] Upload stamp animates while processing.
- [ ] `make check` green.

---

## W-4: Going live shows the address and says what went wrong

### Summary

Fix the one-line bug that leaves the public-address field blank after a
knowledge-review round trip, move slug-confirmation failures into the
field's own danger state plus a toast instead of the shared grey status
line, and validate the slug shape client-side so an owner never sees the
generic 422 message.

### Why

- `applyStateFields` ([page.tsx:135-143](../../../../frontend/src/app/(tenant-admin)/(console)/onboarding/page.tsx#L135-L143))
  is the only place that prefills `publicSlug` from the server's
  `suggested_slug`, and it only runs from the initial load and the turn
  handlers. `saveKnowledge`
  ([page.tsx:437-448](../../../../frontend/src/app/(tenant-admin)/(console)/onboarding/page.tsx#L437-L448))
  and `discardKnowledge`
  ([page.tsx:456-465](../../../../frontend/src/app/(tenant-admin)/(console)/onboarding/page.tsx#L456-L465))
  call `setCanConfirm(!remaining)` directly, bypassing it entirely. Since
  `497bbf3` forces `can_confirm=False` while any knowledge draft exists
  ([controller.py](../../../../backend/app/features/onboarding/controller.py)),
  every owner who uploads a document and then reviews it reaches the publish
  step through this exact bypass - which is the path the founder actually
  used. The field renders empty and has to be typed by hand.
- A confirm failure lands in the shared status line
  ([page.tsx:472-503](../../../../frontend/src/app/(tenant-admin)/(console)/onboarding/page.tsx#L472-L503)),
  styled `text-meta text-text-secondary` inside a hard `h-4` (one line,
  clipped) - grey, not danger-colored, and low-visibility. `Input` already
  supports an `error` prop that renders `border-danger` and
  `text-footnote text-danger` ([Input.tsx:34-46](../../../../frontend/src/components/ui/Input.tsx#L34-L46)),
  unused here.
- A malformed or reserved slug (wrong shape, too short, too long, on the
  reserved list) is rejected by a pydantic field validator
  ([slug.py:60-64](../../../../backend/app/features/tenants/slug.py#L60-L64)),
  which FastAPI surfaces as a generic 422 `"One or more fields are invalid."`
  ([errors.py:77](../../../../backend/app/shared/errors.py#L77)); the actual
  reason sits in an `errors[]` array the frontend never reads
  ([api.ts:44-62](../../../../frontend/src/lib/api.ts#L44-L62)). Only the 409
  "taken" case currently shows a real message.

### User stories

#### US-1 The suggested address is always pre-filled

As a business owner, when I reach the "confirm and go live" step, whether I
uploaded a document and reviewed it first or not, the address field already
shows a suggested slug based on my business name.

- The prefill happens through the same code path regardless of which
  handler flips `canConfirm` to true.
- Typing over the prefilled value is unaffected (existing behavior).

#### US-2 A slug problem is visible where the field is, not in a grey caption

As a business owner, if my chosen address will not work, the field itself
shows the problem in red, and a toast tells me immediately.

- A 409 ("already taken") or a client-caught shape violation sets the
  `Input`'s `error` prop, producing the red border and red message.
- The same failure fires a toast via the app's existing `Toaster`
  ([Toaster.tsx](../../../../frontend/src/components/Toaster.tsx)).

#### US-3 A malformed slug is caught before it reaches the server

As a business owner, typing an address that is too short, too long, or in an
invalid shape shows me why before I press confirm, not a generic error after.

- Client-side validation mirrors `SLUG_PATTERN`, `SLUG_MIN_LENGTH`, and
  `SLUG_MAX_LENGTH` from [slug.py](../../../../backend/app/features/tenants/slug.py)
  (or a shared constant if one is generated for the frontend - check
  `api-types.ts` for an existing generated constant before hand-duplicating
  the regex).
- The confirm button is disabled, or confirm short-circuits with the same
  red-field-plus-toast treatment as US-2, when the client-side check fails.

### Design reference

No new screen. The slug `Input` and `Button` are the existing onboarding
go-live components ([page.tsx:561-581](../../../../frontend/src/app/(tenant-admin)/(console)/onboarding/page.tsx#L561-L581));
this ticket wires up states they already support (`Input`'s `error` prop,
the app-wide `Toaster`) rather than building new ones.

### Technical spec

- Route the slug prefill through one function on every path. Either call
  `applyStateFields`-equivalent logic from `saveKnowledge` and
  `discardKnowledge` too, or lift the prefill line
  (`setPublicSlug((current) => current || fields.suggested_slug || "business")`)
  into a small helper both call whenever `can_confirm` transitions to true,
  regardless of which handler caused the transition.
- Add an `error` local state for the slug field (or reuse the existing
  `error` state if scoping allows without colliding with the general
  onboarding error), pass it to `Input`'s `error` prop, and call
  `toast.error(...)` alongside it in `handleConfirm`'s catch block
  ([page.tsx:472-503](../../../../frontend/src/app/(tenant-admin)/(console)/onboarding/page.tsx#L472-L503)).
- Add a client-side check before the `POST /api/onboarding/confirm` call
  using the same pattern (regex, min/max length) as
  [slug.py:16](../../../../backend/app/features/tenants/slug.py#L16) and
  [slug.py:62](../../../../backend/app/features/tenants/slug.py#L62). Do not
  duplicate the reserved-word list client-side (low value, server already
  catches it with a specific message); only shape and length are worth
  catching before submit.
- Leave the 409 path's error text untouched -
  `"That page address is already taken. Choose another."`
  ([controller.py:495](../../../../backend/app/features/onboarding/controller.py#L495))
  is already a usable sentence and now also drives the field's danger state
  and a toast.

### Tests

- Frontend: after completing a knowledge-review round trip (upload, save,
  no more drafts), assert `publicSlug` is pre-filled, not empty.
- Frontend: a 409 confirm failure sets the `Input` error prop and fires a
  toast (mock `toast.error`, assert called).
- Frontend: a client-side shape violation (too short, invalid character)
  blocks submission and shows the same error treatment without a network
  call.
- E2E: extend the existing onboarding go-live E2E to cover the
  upload-then-confirm path, asserting the address field is non-empty at that
  point.

### Definition of done

- [ ] The slug field is always pre-filled when the confirm step is reached,
      regardless of path.
- [ ] A confirm failure shows red field state and a toast.
- [ ] A malformed slug is caught client-side before submit.
- [ ] `make check` green.

---

## W-5: One answer draws on the catalog and the knowledge base together

### Summary

Fix the customer chat grounding gap introduced by `0ebd1fc`: a question like
"what services do you offer?" must be answered from the confirmed offerings
catalog and the uploaded knowledge base in the same reply, not the catalog
alone with the knowledge base surfacing only on a second, more insistent
question.

### Why

`0ebd1fc` added the confirmed-offerings block to the customer system prompt
correctly, but two mechanisms still stop a single reply from combining it
with uploaded knowledge:

- **The prompt instructs the model to lead with the catalog and stop there.**
  [agent_node.py:325-333](../../../../backend/app/agents/agent_node.py#L325-L333)
  says the catalog is "authoritative for what the business currently offers"
  and to "enumerate the complete catalog before offering to share more
  detail." [agent_node.py:78-80](../../../../backend/app/agents/agent_node.py#L78-L80)
  reinforces this by telling the model not to reach for a tool for exactly
  this question. On the fast path, the PDF's chunks are in the very same
  prompt as the offerings block, yet the model does what it is told and
  answers from the catalog first, matching the founder's observed two-step
  behavior exactly.
- **On the hybrid path, the two sources can never reach one generation.**
  `search_knowledge` returns only a chunk count to the model
  ([agent_node.py:507](../../../../backend/app/agents/agent_node.py#L507));
  the retrieved chunks are drafted separately by
  `_build_knowledge_prompt` ([draft_node.py:67-89](../../../../backend/app/agents/draft_node.py#L67-L89)),
  which reads `retrieved_chunks` only, never
  `ContextPackage.offerings`, and is instructed to answer "using ONLY the
  numbered context below." `get_business_context`
  ([retrieval.py:151-159](../../../../backend/app/services/retrieval.py#L151-L159))
  also excludes catalog-kind chunks from that retrieval, per the fix M-1
  made for a different reason (keeping catalog text out of the fast-path
  whole-corpus block).
- `_FAST_PATH_GUIDANCE` ([agent_node.py:102-103](../../../../backend/app/agents/agent_node.py#L102-L103))
  additionally overclaims that the corpus block "is everything the business
  has published" - it is not, since `whole_corpus` strips catalog chunks by
  design; the offerings block is the (currently insufficient) compensation
  for that gap.

### User stories

#### US-1 A general "what do you offer" question gets one complete answer

As a customer, when I ask what a business offers, I get one answer that
includes both the owner-confirmed catalog items and relevant detail from any
uploaded menu, price list, or FAQ document, without needing to ask a
follow-up for "all" of it.

- On the fast path (small corpus, whole document in one prompt), the reply
  synthesizes both blocks instead of listing the catalog and stopping.
- On the hybrid path (corpus over the fast-path token budget), a
  `search_knowledge` call's resulting `draft_node` answer also includes the
  confirmed catalog, not knowledge-chunk text alone.

#### US-2 The catalog stays authoritative for names, availability, and price

As a customer, if the catalog and an uploaded document ever disagree on a
price or whether something is still offered, the catalog wins, because it is
the row the owner actively maintains.

- The rewritten prompt instruction keeps "authoritative for prices and
  availability" for the catalog; it only removes the "before offering to
  share more detail" sequencing that causes the two-step answer.
- The deterministic-pricing invariant
  ([conventions.md section 8](../../design/conventions.md)) is unaffected:
  no new path lets a model author a price. `owner_material()` remains the
  provenance source for the money gate
  ([agent_node.py:730](../../../../backend/app/agents/agent_node.py#L730)).

### Design reference

No UI change; this is a backend prompt-assembly and grounding fix.

### Technical spec

- Rewrite the offerings-block instruction at
  [agent_node.py:325-333](../../../../backend/app/agents/agent_node.py#L325-L333):
  keep "authoritative for names, availability, and prices"; keep "use
  reviewed knowledge for additional descriptions and supporting details";
  remove "enumerate the complete catalog before offering to share more
  detail" and replace it with an instruction to answer from both sources
  together in one reply when both are relevant.
- Soften [agent_node.py:78-80](../../../../backend/app/agents/agent_node.py#L78-L80)
  so it still discourages an unnecessary tool call but no longer implies the
  catalog alone is a complete answer to "what do you offer."
- Correct `_FAST_PATH_GUIDANCE`'s claim
  ([agent_node.py:102-103](../../../../backend/app/agents/agent_node.py#L102-L103))
  that the corpus block is everything published - state instead that it is
  everything published except the confirmed catalog, which is provided
  separately above.
- Pass `package.offerings_text()` into `_build_knowledge_prompt`
  ([draft_node.py:67-89](../../../../backend/app/agents/draft_node.py#L67-L89))
  as a second grounded block alongside the numbered chunks, and change its
  "using ONLY the numbered context below" instruction to also admit the
  offerings block, naming both explicitly (for example: "using ONLY the
  confirmed offerings and numbered context below"). `draft_node` will need
  access to the `ContextPackage` (or only its `offerings` list) at the call
  site in the graph - trace how `retrieved_chunks` currently reaches it and
  thread `package.offerings` the same way rather than re-fetching from the
  database.
- Do not extend [fuse.py](../../../../backend/app/retrieval/fuse.py) to rank
  catalog rows against knowledge chunks, and do not add a third retrieval
  source. The catalog is small and already loaded whole by
  `build_package` ([context_package.py:128-141](../../../../backend/app/services/context_package.py#L128-L141));
  it belongs in the prompt directly, the same way it already does on the
  fast path, not through the scored-retrieval pipeline.

### Tests

- Backend: extend or add to `test_context_package.py` a test that the
  **hybrid** knowledge-route prompt (the input to `_build_knowledge_prompt`
  or its resulting draft call) carries the offerings block - today nothing
  asserts this, and it is currently false.
- Backend: a test that a fast-path answer to "what do you offer" -
  using a `RecordingProvider` fixture whose canned reply references both an
  offering name and a knowledge-chunk-only detail - is accepted by
  whatever downstream check exists for provenance (inspection/price gate),
  confirming the combined answer does not trip the money-gate or
  provenance checks.
- Backend: `test_fast_path_prompt_lists_the_complete_confirmed_catalog`
  ([test_context_package.py:391](../../../../backend/tests/test_context_package.py#L391))
  stays green; extend its assertion or add a sibling asserting the
  instruction text no longer contains "before offering to share more
  detail".
- E2E or manual: reproduce the founder's exact scenario end to end -
  onboard a tenant with three chip-typed offerings and upload a document
  with additional menu detail, then ask the storefront chat "what services
  do you offer?" once, and confirm the single reply lists items from both
  sources. Per the bug-fix protocol
  ([conventions.md section 5](../../design/conventions.md)), reproduce this
  through the actual customer chat surface before considering the fix
  verified, not only via a unit test.

### Definition of done

- [ ] A single customer-facing reply to "what do you offer" includes both
      catalog and knowledge-derived content, on both the fast and hybrid
      paths.
- [ ] The catalog remains authoritative for price and availability.
- [ ] `_FAST_PATH_GUIDANCE`'s claim about corpus completeness is accurate.
- [ ] The scenario is reproduced and confirmed fixed through the actual
      customer chat surface, per the bug-fix protocol.
- [ ] `make check` green.

---

## W-6: The uploaded business document becomes priced offerings

### Summary

Extend document ingestion so an owner who uploads one document describing
the whole business - facts, policies, hours, and what they sell with prices
- gets each sellable item extracted into a reviewable candidate with a name,
a description, and a price, landing in the `offerings` table at confirm the
same way chip-typed offerings do today. The model never authors a price; it
identifies the item and the line of source text that names its price, and
the server extracts the figure deterministically from that line.

Sequenced after W-5 so the retrieval fix (one answer draws from both
sources) is already in place before this ticket makes the catalog larger and
more complete.

### Why

Today, document-derived offering candidates come only from two hard-coded
section headings ("What we offer", "Prices") and are split at the first
monetary figure in each line
([offering_candidates.py:76-159](../../../../backend/app/features/business/offering_candidates.py#L76-L159)).
`description` is never populated from a document - `PendingOffering.description`
defaults to empty and is only ever filled by hand in the review sheet. A
business document that describes its menu in prose, under a business-specific
heading, or with an item's description on a separate line from its price
produces no offering candidates at all, or candidates with no description.
The founder's ask is specifically to treat the whole document as the source
of offerings-with-detail, not only two narrow sections.

### User stories

#### US-1 A menu item described anywhere in the document becomes a candidate

As a business owner, if my uploaded document describes an item I sell - its
name, what it is, and its price - anywhere in the document, not only under a
literal "Prices" heading, it shows up as an offering candidate for me to
review.

- The heading match widens beyond the current two literal headings (`"What
  we offer"`, `"Prices"`) to the full set `structure_document` already
  produces (`about`, `offerings`, `prices`, `hours`, `location_contact`,
  `policies`, `other` - [structuring.py:49-81](../../../../backend/app/features/knowledge/structuring.py#L49-L81)),
  reading `offerings` and `prices` as the primary sources and treating `about`
  as a fallback when structuring degrades.
- The deterministic `derive()` fallback path
  ([offering_candidates.py:125-159](../../../../backend/app/features/business/offering_candidates.py#L125-L159))
  still applies when structuring falls back to `AS_WRITTEN`
  ([structuring.py:98](../../../../backend/app/features/knowledge/structuring.py#L98)).

#### US-2 A candidate carries its description, not only its name and price

As a business owner, an offering candidate extracted from my document shows
the description that was written about it in the document, so I am not
starting from a blank description field in review.

- A new extraction pass returns `{name, description, source_line}` per
  candidate.
- `source_line` is validated as a substring of the source document text
  before use; a candidate whose `source_line` does not match is dropped
  rather than trusted.

#### US-3 The price is never model-authored

As the platform, a price shown to a customer is always a number the server
computed from the document's own text, never a figure the language model
wrote.

- `price_cents` is extracted from each candidate's `source_line` using the
  existing `extract_monetary_figures`
  ([knowledge/service.py:223-234](../../../../backend/app/features/knowledge/service.py#L223-L234)),
  the same function the current `derive()` path already relies on.
- The extraction schema for `{name, description, source_line}` has no numeric
  price field at all, so there is no field for a model to fill with an
  invented number. This is the concrete implementation of the
  deterministic-pricing invariant
  ([conventions.md section 8](../../design/conventions.md)) for this new
  path.

#### US-4 The owner reviews name, description, and price together before publish

As a business owner, the knowledge review sheet shows each extracted
candidate's name, description, and price together, and I can edit or discard
any of them before confirming.

- `ReviewSheet.tsx` renders the `description` field for document-sourced
  candidates (today it is present in the type but empty for document
  candidates).
- Saving a review still calls the same
  `PUT /api/onboarding/knowledge/{document_id}` shape from `497bbf3`; no new
  endpoint.

### Design reference

The onboarding thread and its knowledge-review sheet are unchanged in
structure - `ReviewSheet.tsx` already has a description field in its data
model; this ticket makes document-derived candidates populate it, and adds
no new screen. Images remain explicitly out of scope, per the founder's own
framing: onboarding stays text/price/description only, and an owner adds
images afterward from the Business tab, which `M-2` already supports.

### Technical spec

- **Stage one, unchanged.** `structure_document`
  ([structuring.py:139-174](../../../../backend/app/features/knowledge/structuring.py#L139-L174))
  already reorganizes the raw document into the fixed headings under the
  `figures_preserved` money guard
  ([structuring.py:120-128](../../../../backend/app/features/knowledge/structuring.py#L120-L128)),
  which discards the model's structured output entirely (falling back to
  `AS_WRITTEN`) if it invents a figure. Keep this stage and this guard
  exactly as they are - they are the existing enforcement of the
  deterministic-pricing invariant at the structuring layer, and this ticket
  adds a second enforcement point rather than relaxing this one.
- **New stage two: item extraction without price.** Add an extraction pass
  (new Pydantic schema, e.g. `ExtractedOffering { name: str, description: str,
  source_line: str }`, a list of these) that runs over the `offerings` and
  `prices` structured sections (and `about` as a fallback). Prompt
  instruction: identify each distinct sellable item, its description as
  written, and the exact line of source text where its price appears -
  never write a number.
- **Deterministic price extraction and provenance check.** For each
  `ExtractedOffering`, look up `source_line` in the original section text
  (exact substring match); reject the candidate if it is not found (the
  model paraphrased instead of quoting, which also means it is not safe to
  trust for price extraction). For an accepted candidate, run
  `extract_monetary_figures` on `source_line` to get `price_cents` the same
  way `derive()` does today.
- **Fold into `PendingOffering`.** Produce `PendingOffering(name, description,
  price_cents, sources=["document"])` from the accepted candidates, merging
  by `normalize_name` the same way `_merge_owner_offerings`
  ([agent.py:162-185](../../../../backend/app/onboarding/agent.py#L162-L185))
  already merges owner-typed names, so a document candidate and an
  owner-typed chip candidate with the same normalized name combine into one
  reviewable row rather than duplicating.
- **Widen the heading set consumed by `derive()` / `_source_lines()`**
  ([offering_candidates.py:34](../../../../backend/app/features/business/offering_candidates.py#L34),
  [offering_candidates.py:76-84](../../../../backend/app/features/business/offering_candidates.py#L76-L84))
  as the fallback path for documents that degrade to `AS_WRITTEN` - this
  keeps today's behavior as the safety net rather than replacing it outright.
- **Review sheet.** Update `ReviewSheet.tsx` to render `description` for
  every candidate regardless of source, and confirm the existing save/discard
  handlers (`saveKnowledge`, `discardKnowledge` in `page.tsx`, unchanged by
  this ticket) pass the description through to
  `PUT /api/onboarding/knowledge/{document_id}` - check whether
  `OnboardingKnowledgeRequest`'s `offerings` field already round-trips
  `description` (it should, since `PendingOffering` already has the field);
  if not, that is the one wire-shape gap to close.
- **Retrieval consumer.** No change needed beyond W-5: once these
  document-sourced rows are confirmed into `offerings` at publish
  (`reconcile_offerings_batch`, [business/service.py:187-244](../../../../backend/app/features/business/service.py#L187-L244)),
  they are projected into the vector store by the existing
  `ingest_offerings` pipeline and answered from by the same catalog block
  W-5 already wired into both the fast and hybrid prompts. This ticket's job
  is only getting a complete, priced, described catalog into that table; W-5
  is what makes the chat answer from it correctly.

### Tests

- Backend: a fixture document with an item's description on one line and its
  price on another (not both in the same source line as today's `derive()`
  assumes) yields a candidate with both fields populated.
- Backend: a candidate whose model-returned `source_line` does not appear
  verbatim in the source document is dropped, not trusted.
- Backend: no test path allows a `price_cents` value that does not trace back
  to `extract_monetary_figures` output on real document text - this is the
  regression test for the deterministic-pricing invariant on this new path,
  analogous to the existing figure-provenance tests in `test_agent_graph.py`.
- Backend: a document-sourced candidate and a chip-typed candidate with the
  same normalized name merge into one `PendingOffering` rather than
  duplicating.
- Frontend: `ReviewSheet` renders a non-empty description for a
  document-sourced candidate.

### Definition of done

- [ ] Offerings described anywhere in a whole-business document (not only
      under two fixed headings) are extracted as reviewable candidates.
- [ ] Each candidate carries a description sourced from the document.
- [ ] Every price is extracted deterministically from quoted source text; no
      extraction schema has a model-fillable numeric price field.
- [ ] The review sheet shows name, description, and price together for
      document-sourced candidates.
- [ ] The confirm-time write path and the retrieval path from W-5 need no
      further change to serve these rows.
- [ ] `make check` green.
