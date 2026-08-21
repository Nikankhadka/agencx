# Phase 1 - Onboarding (O)

The onboarding spine: a single-tool + LLM turn loop and login-in-chat.
These are the first build-phase tickets for the three pillars.

Tickets in this file:

- O-1: Onboarding - one tool + LLM turn loop
- O-2: Login-in-chat - email + 6-digit code

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
- [ ] "Didn't get it? Resend" inactive for 30 seconds, then tappable, no
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
