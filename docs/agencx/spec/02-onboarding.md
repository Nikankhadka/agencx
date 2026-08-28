# Phase 1 - Onboarding (O)

The onboarding spine: a single-tool + LLM turn loop and login-in-chat.
These are the first build-phase tickets for the three pillars.

Tickets in this file:

- O-1: Onboarding - one tool + LLM turn loop
- O-2: Login-in-chat - email + 6-digit code
- O-5: Onboarding UI - port the prototype thread
- O-6: Chips, the contact widget, and the ABN beat
- O-7: A link that cannot be read says so, and says why
- O-8: Go-live lands on Home without a blank screen

The knowledge-ingest tickets (O-3, O-4) ship with the chat-grounding build
group and live in `04-chat-grounding.md`.

---

## O-1: Onboarding - one tool + LLM turn loop

### Summary

Re-cut the onboarding flow to the merge-plan shape: one tool to save
profile fields plus an LLM turn loop (extract -> save -> ask missing ->
deflect otherwise). No graph. The Wren copilot already runs a bounded tool
loop with a stateful `extract()` returning `DraftUpdate`; this ticket
collapses it to the single save tool and the loop, keeping the completeness
gate and off-topic deflection.

### Why

The merge flow design: onboarding is a plain, bounded loop - a framework or
a graph would buy nothing (decision 4, "deliberately absent"). One tool
keeps the model surface minimal so edge/free models behave (the measured
lesson: multi-tool loops dropped info on free models; the stateful extract
fixed it).

### User stories

#### US-1 One save tool

**As** the onboarding agent,
**I want** a single `save_profile` tool accepting any subset of profile
fields,
**so that** the loop is one tool call per turn at most.

- [ ] `save_profile` (DraftUpdate fields: name, business_name, business_type,
  headcount, hours, services, contact) merges non-null fields
- [ ] The extract->save->ask-missing turn loop runs within the existing
  bounds (<=4 tool calls/turn, <=40 turns)

#### US-2 The completeness gate still refuses premature finalize

**As** the maintainer,
**I want** go-live refused until the profile is complete,
**so that** a half-onboarded tenant cannot go live.

- [ ] Gate enumerates missing fields; `complete_onboarding` refused while
  incomplete
- [ ] Business type drives which fields are asked (config, I8)

#### US-3 Off-topic deflects, never firmes on the first ask

**As** Sam asking a side question mid-interview,
**I want** a one-line answer with a gentle redirect,
**so that** the interview stays human.

- [ ] The softened off-topic behavior is preserved (one-line answer +
  redirect; no firmness escalation)

#### US-4 Drop-off resumes in place

**As** Sam returning after a day,
**I want** the thread resumed exactly where it left off,
**so that** nothing is re-asked or lost.

- [ ] Resume from persisted history (last 20 turns); return acknowledgement
  deterministic (no model call); captured field names summarized, values
  never re-read back in bulk

### Technical spec

- `backend/app/onboarding/agent.py` + `tools.py`: collapse the tool
  registry to `save_profile` (+ the auth-code tools from O-2, which own
  their own ticket; O-1 integrates them once both exist)
- Keep `TurnDirective`, `TimeLimitedProvider` bounds, SSE streaming

### Tests

- Unit: loop saves merged fields; gate refuses incomplete; off-topic
  deflects
- Integration: full interview to go-live against a fake provider

### Files touched

- `backend/app/onboarding/**`, `backend/tests/**`

### Definition of done

- [ ] One-tool loop works end to end to go-live
- [ ] Completeness gate + deflection preserved
- [ ] Resume behavior green

---

## O-2: Login-in-chat - email + 6-digit code

### Summary

Authenticate the owner inside the conversation: type an email, receive a
6-digit code by email, type it back. The `auth_codes` table (design/database.md
section 3) holds hashed codes with expiry and attempt budget. Supabase
stays the identity store (users.id = auth.users.id); login-in-chat is the
delivery mechanism, replacing the sign-up form on the tenant surface.

### Why

The PRD spine step 1 and decision 6: no sign-up form, no paid SMS. The
first conversation IS the product; a separate identity flow breaks the
spine. Email codes are free and universally understood.

### User stories

#### US-1 Login inside the chat

**As** Sam opening the app the first time,
**I want** the chat to ask for my email and then a code,
**so that** I never see a sign-up form.

- [ ] Email renders in the command pill; send activates only on valid email
  format (no red error text)
- [ ] A 6-digit code is emailed; six digit cells replace the input footprint
  (auto-focus first cell, numeric keyboard on mobile)
- [ ] Auto-submit on six valid digits; success continues the conversation
  with no toast/celebration

#### US-2 The code lifecycle is safe

**As** the maintainer,
**I want** codes hashed, expiring, attempt-bounded, and single-use,
**so that** the auth path is not brute-forceable or replayable.

- [ ] `code_hash` = sha-256 of the code; the raw code is never stored or
  logged
- [ ] `expires_at` short TTL; `attempts` budget invalidates on exceed;
  `verified_at` set once
- [ ] Duplicate email: the code sends regardless (no account-existence
  leak); on success the server logs into the existing account

#### US-3 Failure modes are calm one-liners

**As** Sam mistyping the code,
**I want** one line beneath the cells, no error chrome,
**so that** the chat stays conversational.

- [ ] "That code didn't work. Try again, or resend."
- [ ] "Didn't get it? Resend" inactive for 60 seconds, then tappable, no
  countdown displayed
- [ ] "That code expired. Request a new one." / "Too many tries. Request a
  new code."
- [ ] "Wrong email?" affordance next to the destination echo

#### US-4 The session is a real Supabase session

**As** the maintainer,
**I want** a verified code to yield the same JWT/session the rest of the
app expects,
**so that** every existing authed route works unchanged.

- [ ] Verification mints/exchanges for the Supabase session; existing auth
  middleware untouched
- [ ] Email sending is a provider-seam (console/SMTP/resend) - an env
  config, not a hardcoded vendor; local dev uses a captured/logged code
  path for the demo

### Technical spec

- Migration `0017_auth_codes.sql` (auth_codes table + RLS per
  design/database.md)
- `send_login_code` / `verify_login_code` tools on the onboarding agent
- UI: login-in-chat states per design/frontend.md S1

### Tests

- Unit: hash/expiry/attempts/verify lifecycle; duplicate-email non-leak
- API: verified code -> session; authed routes work
- E2E: full login-in-chat against the local demo world

### Files touched

- `backend/migrations/0017_auth_codes.sql`, `backend/app/onboarding/tools.py`
- `backend/app/services/auth_codes.py` (new), email seam
- `frontend/src/**` (login-in-chat UI states), `frontend/e2e/**`

### Definition of done

- [ ] Login-in-chat works end to end in the chat surface
- [ ] Code lifecycle secure (hash/expiry/attempts/single-use)
- [ ] Verified code yields the Supabase session
- [ ] All failure modes calm one-liners

---

## O-5: Onboarding UI - port the prototype thread

### Summary

Rebuild the onboarding conversation surface as a port of the prototype's
ONBOARDING screen, across both routes it spans (`/login`, `/onboarding`). The
thread becomes the entire screen: no title, no navigation, and no progress
surface. Every prototype value lands as a `theme.css` token, so the look is
re-pointable from one file. Includes B-3's US-1 (the lighter crimson ramp),
pulled forward because colour is half of what this ticket is for, and proper
server-side email validation for the conversational login step.

### Why

`conventions.md` section 6 and `spec/README.md` carry the standing rule that UI
is **ported from `design/prototypes/agencx-prototype-v6.html`, never designed
from ticket text**. The shipped onboarding screen predates that rule and was
designed from prose, so it diverged structurally: a console sidebar wrapping the
thread, an `<h1>Onboarding</h1>`, assistant turns in grey bubbles, and a
show-back aside carrying an "N/7 captured" counter - which also breaks the
load-bearing rule in `design/frontend.md` section 9 ("no progress bars, no
'% complete' anywhere; the thread is the progress indicator").

### User stories

#### US-1 The thread is the screen

**As** Sam opening the product for the first time,
**I want** the conversation to be the whole screen,
**so that** the first conversation IS the product, as the PRD spine says.

- [ ] No `<h1>`, no subtitle, no welcome screen
- [ ] `/onboarding` renders chrome-free: no sidebar, no hamburger header (the
  prototype shows no navigation until the business is live)
- [ ] No show-back aside, no mobile Business sheet, no captured counter - the
  profile is shown back on the Business tab (S2, E-1)

#### US-2 The thread looks like the prototype

**As** the founder,
**I want** the screen to match the prototype it was designed as,
**so that** the shipped product is the product that was designed.

- [ ] Assistant turns are bare prose (`.a-prose`), never a bubble
- [ ] Owner turns are a filled accent bubble, 20px radius, tip bottom-right
  (`.u-bubble`) - distinct from the operator thread's `ChatBubble`
- [ ] The opening message is the larger lede with the beat question beneath it
  (`#first-msg` / `#first-msg-q`)
- [ ] The crimson veil (`#s1-grad`) covers the bottom 56% and fades for good
  once the owner has answered once
- [ ] Typing dots are accent-coloured and precede static messages too

#### US-3 Values are tokens, not literals

**As** the maintainer,
**I want** every prototype value to be a `theme.css` token,
**so that** the whole look is re-pointable from one file and CI can prove it.

- [ ] The prototype's one-hue alpha ladder lands as tokens derived from
  `--primary-40-rgb` / `--neutral-10-rgb` channel triples
- [ ] Lede, lede-question and bubble type sizes are tokens
- [ ] Thread geometry, send-circle and code-cell sizes are tokens
- [ ] `npm run check:tokens` green (no literal outside `theme.css`)

#### US-4 Mobile first, responsive to the browser

**As** Sam on a phone, and later at a desk,
**I want** the same screen to work at both sizes,
**so that** one codebase serves both without a separate build.

- [ ] Prototype geometry (390px) is the mobile-first base
- [ ] Above `--width-thread` the column centres rather than stretching
- [ ] Safe-area insets honoured top and bottom

#### US-5 A conversational email answer is validated on the server

**As** Sam typing an email into a chat composer,
**I want** a bad address answered with one calm line,
**so that** I can fix it in place instead of hitting a validation dump.

- [ ] The client gate is *liveness only* (text contains something
  address-shaped), so "it's sam@shop.com" is sendable
- [ ] `app/services/email_address.py` extracts an address from prose, normalizes
  it, and validates syntax; the API is the authority
- [ ] A bad address returns 400 with one conversational line, rendered verbatim;
  the typed text is kept so it can be corrected
- [ ] Issue and verify normalize identically, so they cannot disagree on the key
- [ ] The refusal never echoes the address and never leaks account existence

### Design reference

**`docs/agencx/design/prototypes/agencx-prototype-v6.html`**, the ONBOARDING
section. Port `initName()`, `agentMsg()`, `userMsg()`, `setInput()`,
`buildCmdPill()` and `initOtp()`, plus the `#thread`, `#first-msg`,
`#first-msg-q`, `.a-prose`, `.u-bubble`, `.typing` / `.td`, `.sys-pill`,
`#s1-grad`, `#input-area`, `.chips-row`, `.cmd-pill`, `.plain-pill`, `.sc` and
`.otp-cell` rules. Copy is demo copy for the Sababa reference tenant - take
structure and behaviour, never strings; values become tokens, never hex.

Five deviations are deliberate and documented in code:

1. No camera/mic glyphs in the empty composer - Stage 1 has neither feature, and
   a control that does nothing is a worse defect than an absent one
2. No visible resend countdown - the GoTrue resend cadence is 60s inactive, no countdown
3. No `verif` tint on the code cells - O-2's spec is that success silently continues
4. No "Already with Agencx? Log in" link - O-2 made login and signup one path
5. Chips keep a 44px touch target (prototype ~29px) - `frontend.md` section 10

O-9 adds a sixth, in the Settings sheet rather than the thread: GST is a chip
pair, not the prototype's toggle.

The prototype's 46ms-per-word reveal is not ported: real SSE `token` events
already pace the text, and a client-side word queue would fight the stream.

### Technical spec

- `frontend/src/styles/theme.css`: B-3 US-1 ramp; `--neutral-10` to the
  prototype's ink; `-rgb` channel triples; the alpha ladder; lede/bubble type;
  thread geometry; `--duration-rise-fast`, `--duration-veil`
- `frontend/src/app/globals.css`: `@theme inline` mappings, `rise` and
  `caret-blink` keyframes, `--animate-*` names, and the `.command-pill`
  focus-within rule
- `frontend/src/components/ui/Thread.tsx` (new): `Thread`, `LedeMessage`,
  `AgentLine`, `OwnerBubble`, `TypingLine`, `ThreadPill`, `ThreadVeil`
- `backend/app/services/email_address.py` (new) + `app/features/auth/api.py`

### Tests

- `make check`, `make format-check`, `npm run check:tokens`
- `backend/tests/test_email_address.py` (syntax rules), `test_auth_codes.py`
  (conversational refusal, prose extraction, issue/verify key agreement)
- `make test-e2e`: onboarding, auth-login, landing, dashboards, including a
  no-console-nav assertion on `/onboarding`
- Visual: side by side against the prototype at 390px, then at 1440px

### Files touched

- `frontend/src/styles/**`, `frontend/src/app/globals.css`
- `frontend/src/components/ui/**`, `frontend/src/app/(tenant-admin)/**`
- `backend/app/services/email_address.py`, `backend/app/features/auth/api.py`
- `frontend/e2e/**`, `backend/tests/**`

### Definition of done

- [ ] Both routes render the prototype thread; no nav, no title, no progress surface
- [ ] Every value a token; `check:tokens` green
- [ ] Conversational email validation server-side, with tests
- [ ] Lint, typecheck, format, unit and e2e green


---

## O-6: Chips, the contact widget, and the ABN beat

**Amendment** - recorded after the work shipped (founder walkthrough,
2026-08-23). Shape per `README.md`.

### Summary

Put the prototype's suggestion chips back on the beats that have them, add the
country-code phone pill and the welded ABN pill as composer widgets a chip can
open, and add `abn` / `gst` as beats.

### Why

O-1 cut chips to keep extraction reliable on free models ("seven text beats, no
chips"). Walking the shipped flow against the prototype showed that trade was
not necessary: chips can be presentation rather than protocol. And an ABN is
what a business puts on an invoice - the prototype asks for it, and the shipped
interview did not.

### User stories

#### US-1 A chip is a shortcut, never a gate

**As** Sam answering "is it just you, or do you have a team?",
**I want** to tap "Just me",
**so that** I do not type an answer the assistant already guessed.

- [x] Tapping a chip sends its **label as ordinary text** on the existing
  streaming route; `save_profile` extraction is still the only way into the draft
- [x] Every beat keeps `kind: "text"` - the pill is always there, placeholder
  "or type…", and typing past the chips always works
- [x] The `selection` payload stays refused (409); no new protocol
- [x] `.chips-row` sits **above** the pill in the same widget, as the prototype has it

#### US-2 A chip can open a different input

**As** Sam asked for the best way to reach me,
**I want** tapping "Phone number" to give me a real phone field,
**so that** I get a numeric keypad and a country code, not a text box.

- [x] `ChipSpec.widget` declares the swap, so the client never hardcodes a beat
- [x] The phone pill ports `initPhone()`: AU/NZ/US/UK/SG, per-country formatting
  and validation, popover opening upward, error line only after a rejected send
- [x] The ABN pill is the prototype's `.abn-pill`: welded label, `XX XXX XXX XXX`,
  armed at exactly 11 digits
- [x] The chips row stays up after a swap and the active chip toggles back, so a
  beat is never a trap
- [x] The login address is offered as a one-tap chip on the contact beat, via
  `InputSpec.suggest_owner_email` - the server declares it, the client supplies
  the value it already holds

#### US-3 ABN and GST, without branching on a vertical

- [x] `abn` and `gst` are beats; the profile is jsonb, so no migration
- [x] `gst` skips itself when the owner said they have no ABN, via its own
  `complete` predicate - conditional on a previous *answer*, never on the
  business type (I8)
- [x] `"none"` is the stated answer of an owner without one, distinct from
  "not asked yet"

### Design reference

`agencx-prototype-v6.html`: `buildCmdPill(placeholder, onSubmit, chips)` and the
`.chips-row` / `.c-reply` / `.c-suggest` rules; `initPhone()` + `COUNTRIES`;
`handlePricing()` / `handleAbn()` and the `.abn-pill` rules.

### Definition of done

- [x] `make check`, `check:tokens`, e2e green
- [x] Verified against the running stack: a real login code, a real interview
  through every beat with the live model, and the no-ABN branch skipping GST

---

## O-7: A link that cannot be read says so, and says why

**Amendment** - recorded after the work shipped (founder walkthrough,
2026-08-23). Shape per `README.md`.

### Summary

Send browser-like request headers on the ingest fetch, log the reason a scrape
failed instead of swallowing it, and match a scheme-less link.

### Why

A pasted Uber Eats link came back as "I couldn't read that page" with nothing
behind it. Three defects were under that one sentence: the fetch announced
itself as `python-httpx` and was refused by bot protection; both URL paths
caught `except ValueError:` binding no variable, so a 403, an empty page and a
dead host were indistinguishable in the logs; and `_URL_RE` matched only
`https?://`, so what the address bar shows was never fetched at all.

### User stories

- [x] The fetch sends a real user agent, accept and accept-language
- [x] The reason is logged with the URL; the fetch names the HTTP status
- [x] A `www.` host, or a bare host with a path and an alphabetic TLD, is
  matched and given `https://` - while "$16.50 a plate", "16.50/plate" and
  "3.5/5 stars" stay prose
- [x] The failure line names the situation instead of implying a typo

Deliberately **not** done: a headless browser. Marketplace pages fingerprint
beyond headers - Uber Eats still answers 403, verified against the live
stack - and the honest product behaviour is to say so.

---

## O-8: Go-live lands on Home without a blank screen

**Amendment** - recorded after the work shipped (founder walkthrough,
2026-08-23). Shape per `README.md`.

### Summary

Keep the conversation on screen through go-live, prefetch `/home`, and stop the
confirm button re-arming during the transition.

### Why

Confirming replaced the whole thread with one line, held a fixed 1400ms on that
near-empty screen, then navigated to `/home`, which fetched its brief from three
endpoints cold. The pause had nothing to look at, so it read as a stall.

### User stories

- [x] The activation line is appended to the conversation, not substituted for it
- [x] `/home` is prefetched as soon as confirming becomes possible
- [x] The hold drops to 700ms - enough to read, with no blank frame to sit through
- [x] The button stays held until the route changes (a second click 409s and
  paints an error over the live line), and the timer is cleaned up on unmount

Measured on the running stack: confirm to `/home` in 827ms.

Not covered by a test: there is no component-test harness in this repo, and the
only route to this code is an LLM-driven e2e interview. Verified by hand.

---

## O-9: An ABN the owner can read, and correct

**Amendment** - recorded after the work shipped (founder walkthrough,
2026-08-23). Shape per `README.md`.

### Summary

Show the ABN and GST answer back on a Settings row, and let the owner fix them
in the prototype's "ABN & Tax" edit sheet.

### Why

O-6 taught the interview to ask for an ABN and a GST registration. Both land in
the profile and are rendered by nothing: of the nine captured fields only three
reach a screen (`name` on Home, `business_name` on the Booking page, and
`services` + `hours` fused into its tagline). So the product asks a small
business for its tax number and then never shows it - which is worse than not
asking, because a wrong answer can never be corrected. The extract prompt tells
the model to store the digits, so it is held as `51824753556`; that only
matters once something displays it, which is the point of this ticket.

### User stories

**US-1 - I can see what you have** (owner)

- [x] Settings holds an "ABN & Tax" row under Knowledge
- [x] Its line is the prototype's summary (`setSummary('abn')`):
  `51 824 753 556 · GST registered` / `· Not GST registered`
- [x] An owner who said they have no ABN reads "No ABN", not the `none`
  sentinel, and is not told the answer to a GST question they never heard
- [x] Nothing captured reads "Not set"
- [x] The stored digits render grouped - the formatting is the screen's job,
  never what is written down

**US-2 - I can fix it** (owner)

- [x] The row opens the prototype's edit sheet (`openSettingsEdit('abn')`): a
  masked ABN field and the GST answer
- [x] The mask is the interview's, because it is now literally the same
  function - `formatMask()` left `BeatComposer` and became `lib/abn.ts`
- [x] GST is asked only of a business that has an ABN, the same condition the
  interview's conditional beat carries
- [x] Clearing the field is the stated "I do not have one", not "never asked"
- [x] An ABN that is not eleven digits is refused in the owner's words ("An ABN
  is 11 digits."), with the sheet still open and the typed value intact
- [x] The correction survives a reload

**US-3 - the two copies stay together** (engineering)

- [x] `PATCH /api/business/profile` writes `config->profile` (what confirm
  writes, and what the E-5 spec names) and `config->onboarding.draft` (what the
  Booking page reads) in one statement
- [x] A field outside the editable slice is refused, not ignored
- [x] `GET /api/business/profile` reads the profile, falling back per field to
  the draft

### Deliberately not done

The rest of the profile - business name, hours, what you offer, how customers
reach you - stays frozen after go-live. `config->profile` is only ever written
at confirm, and that is the real gap here; the ABN slice was chosen over
building the settings tree the PRD forbids. It is written down rather than
implied: an owner who moves premises still cannot say so, and that wants its
own ticket with its own screen.

`ShowBack.tsx` is deleted in this ticket. It had been orphaned since O-5 dropped
its import, its field list predates these beats, and the profile show-back it
was written for is not what is being built here.

### Deviation from the prototype

GST is a `Chip` pair (Yes / Not yet), not the prototype's `se_toggleField`
switch. It is the same question the interview asks, asked with the control the
interview asks it with, and it keeps a switch primitive out of the system for
one boolean. Recorded with O-5's list above.

### Files touched

- `backend/app/features/business/api.py`, `service.py`, `tests/test_business_api.py`
- `frontend/src/lib/abn.ts` (new) + `abn.test.ts` (new)
- `frontend/src/app/(tenant-admin)/(console)/settings/page.tsx` +
  `components/AbnSheet.tsx` (new)
- `frontend/src/components/ui/RowLink.tsx` (a row can open a sheet)
- `frontend/src/app/(tenant-admin)/(console)/onboarding/components/BeatComposer.tsx`
  (uses the promoted formatter), `ShowBack.tsx` (deleted)
- `frontend/e2e/settings-abn.spec.ts` (new)

### Definition of done

- [x] The row reads back what was captured, formatted
- [x] The sheet corrects it, and the correction survives a reload
- [x] Both jsonb copies move together
- [x] `make check` green, the new e2e green
