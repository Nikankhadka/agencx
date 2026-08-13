# Phase 2: Onboarding Agent

**Calendar slot:** Week 2

## Goal

The owner opens a chat page, types an email, gets a 6-digit code by email, types it back - all inside the conversation. The same agent interviews them through a plain tool loop, capturing name, business name, business type, headcount, hours, and what they sell. The tenant reaches go-live and lands in the two-tab app. On drop-off and return, the conversation resumes exactly where it left off.

## Features

### Onboarding

**Spec:** The onboarding agent is a plain tool loop (not a graph), ported from Wren's `run_turn` / `TurnDirective` pattern. At most 4 tool calls per turn and 40 turns per session. Business-type config drives questions from the `business_types` row's `profile_template` - no branch on the type anywhere (I8). Identity is email + 6-digit code, issued and verified inside the chat by `send_login_code` / `verify_login_code` tools (decision 6). The loop is bounded, resumes from persisted history (last 20 turns), and the completeness gate refuses premature finalisation.

**What this feature does not own:** the Chat tab UI shell (T-011 owns that), knowledge upload (Phase 3), the Business tab (Phase 3), the public page (Phase 4), the assistant graph (Phase 4).

**Design:** Login-in-chat renders validated email and 6-digit-code fields in-canvas, in the command pill footprint, with no modal or sheet. The inactive send state is the only validation signal - no red error text. The onboarding conversation flows in the Chat tab (S1, design.md). The thread is the progress indicator: no progress bars, no "% complete". After go-live the app has exactly two tabs: Chat and Business. The state-to-shell transition cross-fades in the top-bar hamburger and navigation at 240ms ease-out.

**Stories:**

#### US-1 Login-in-chat (rewritten from ONB-2)

**When:** First app open, no valid session. The shell renders with the chat surface already present - no welcome screen.

**Happy path:**
1. The onboarding agent's first message renders after a brief typing indicator: introduces Agencx, asks what to call them. The message follows natural conversational pacing.
2. The tenant types an email in the command pill. Send activates on valid email format. No form, no separate screen.
3. On submit, the email renders as a right-aligned bubble. The agent sends a 6-digit code to that address.
4. Six digit cells replace the input footprint. Auto-focus on the first cell. Numeric keyboard on mobile.
5. A short line echoes the destination: "Code sent to jordan@example.com", with a "Wrong email?" affordance.
6. Auto-submit on six valid digits. On success the conversation continues to the next beat. No toast, no celebration.

**Alternate paths:**
- Duplicate email: the code sends regardless, so account existence is never leaked. On success the server silently logs into the existing account.
- "Already with Agencx? Log in" affordance sits beneath the field for returning users.

**Failure modes:**
- Wrong code: one line beneath the cells - "That code didn't work. Try again, or resend."
- No email received: "Didn't get it? Resend" inactive for 30 seconds then tappable. No countdown displayed.
- Expired code: "That code expired. Request a new one."
- Invalid email: send stays inactive. No red text.
- Max attempts exceeded: "Too many tries. Request a new code."

**Acceptance criteria:**
- [ ] Email and code fields render in-canvas, never in a modal or sheet
- [ ] Send activates only on a valid email format, with no error text
- [ ] Auto-submit fires on six valid digits
- [ ] Resend is inactive for exactly 30 seconds with no visible countdown
- [ ] Code success produces no toast, no interstitial, no celebration
- [ ] A duplicate email logs into the existing account without leaking that it existed
- [ ] Expired codes and max-attempts are handled clearly
- [ ] The shell renders with the agent's first message already in it, no welcome screen preceding it

#### US-2 Name and solo-or-team (harvested from ONB-1, ONB-3)

**When:** Immediately after login-in-chat succeeds.

**Happy path:**
1. The agent asks for the tenant's name conversationally. Name field renders in-canvas, in the pill footprint. Send activates at 2+ characters.
2. On submit, the reply renders as a right-aligned bubble. The agent uses the first token in reply, stores the full string.
3. The agent re-establishes warmth, then asks whether they work solo or have a team.
4. The tenant answers in their own words: "just me", "me and my partner", "team of three". Parse sets `is_team` on team-indicating language.
5. The acknowledgement differs genuinely between team and solo answers.

**Alternate paths:**
- Multi-token name: use first token in reply, store the full string.
- "just me", "solo", "by myself" never set `is_team`.
- `is_team = true` when team members are not in scope: acknowledged warmly, onboarding continues. No "not available yet" wall.

**Acceptance criteria:**
- [ ] Name field renders in-canvas, send activates at 2+ characters
- [ ] The agent uses first token in reply, stores full string
- [ ] Solo/team is free text, not a segmented control or chip pair
- [ ] "just me" never sets `is_team`
- [ ] Solo and team answers produce genuinely different acknowledgements
- [ ] `is_team = true` produces no capability wall

#### US-3 Business name and what the business does (harvested from ONB-4, ONB-5)

**When:** After solo-or-team is acknowledged.

**Happy path:**
1. The agent asks for the business name, framed to invite the sole-operator answer ("Have you got a business name, or is it just you?")
2. Accept as given. A brand name commits directly. Absence-of-business-name patterns ("just me", "same as my name") are valid - business name stores as equal to the tenant's name.
3. `account_created` holds once business name commits.
4. The agent asks what the business does: "Tell me what you do, or drop a link to your site and I'll learn the rest."
5. URLs pasted into the text input are detected on submit. The "+" opens a sheet with upload file (PDF, PNG/JPG, DOCX).
6. The resource shows as an attachment chip. Processing: the typing indicator carries a status sentence ("Reading your site..."). No percentage, no progress bar.
7. Extraction targets: service type, services in the tenant's own labels, operating hours, contact details. The agent reads back what it found as a chat message: "Here's what I've got: [summary]. Sound right, or anything to fix?"
8. Confirm promotes the fields to confirmed.

**Alternate paths:**
- Verbal path: normal text or dictation. Send activates on any text.
- Corrections: the tenant types a correction. The agent parses, updates, and acknowledges in one line.
- URL unreadable: "Couldn't read that one. Try another link, or describe what you do?"
- Both link and verbal refused: the agent drives the asks one at a time conversationally ("What's the main thing you do for customers?" then services, suburbs, hours).

**Acceptance criteria:**
- [ ] `account_created` holds once business name commits
- [ ] The unbranded sole operator is never asked again or made to feel incomplete
- [ ] A pasted URL needs no special affordance
- [ ] The status sentence appears for slow reads and updates once past 10 seconds
- [ ] No progress bar or percentage renders at any point
- [ ] The read-back is a chat message, not a card
- [ ] Corrections update the field and return it to pending
- [ ] Every failure is one conversational message with no error chrome
- [ ] The guided-question fallback captures the same data over more turns

#### US-4 Handoff and go-live (harvested from ONB-10, ONB-10a)

**When:** Profile is complete - business name, business type, headcount, hours, services captured.

**Happy path:**
1. The agent emits an activation summary: a single conversational message listing all confirmed fields. "You're all set. Here's what I know: [business name], [service type], available [hours], pricing info still to come when you upload your materials."
2. The tenant is now in the two-tab app (Chat + Business). The Chat tab shows the activation summary as the latest message. The Business tab shows the profile captured during onboarding (show-back surface).
3. The top bar gains hamburger, search and avatar by cross-fade (240ms ease-out).
4. The agent tells the tenant how to share their public page link and add knowledge.

**Alternate paths:**
- If some captures were deferred, the summary omits those fields entirely rather than showing "not set".
- A single chip beneath the summary: "See your Business page".

**Acceptance criteria:**
- [ ] No celebration screen, confetti, or welcome overlay
- [ ] No "complete your profile" CTA and no percentage meter
- [ ] No tour of the drawer and no next-steps list
- [ ] Deferred fields are omitted entirely, not shown as "not set"
- [ ] The tenant is in the two-tab app with Chat showing the summary and Business showing the profile
- [ ] The activation summary is a conversational message, not a card
- [ ] The onboarding thread persists as the canonical thread, scrollable forever

#### US-5 Drop-off and return (harvested from ONB-11)

**When:** The tenant leaves mid-interview and returns.

**Happy path:**
1. Post-login abort: the account exists and fields persist. Valid session silently bypasses into the shell exactly where they left it, scrolled to the most recent message.
2. Return acknowledgement, deterministic with no model call: "Welcome back, [first name]. You were telling me about [topic]. Want to keep going?"
3. On return after drop-off, the agent summarises what was already captured (field names, not values), states where it left off, and asks exactly the next question in sequence.

**Alternate paths:**
- Long absence (a day or more): "Welcome back. I'm still here whenever you're ready - nothing's lost. Want to pick up where we were, or start fresh?"
- No engagement after return: no further onboarding prompts. The tenant can resume any time by asking the Copilot.

**Acceptance criteria:**
- [ ] No "resume onboarding" banner exists anywhere - the thread is the resume mechanism
- [ ] The return acknowledgement is deterministic, with no model call
- [ ] The topic reference is never a step number or percentage
- [ ] After page refresh, full conversation history renders from the server (last 20 turns)
- [ ] Scroll position lands on the most recent message after refresh
- [ ] Input state matches the in-progress capture beat after refresh
- [ ] Agent identifies where it left off and summarises captured field names (not values)
- [ ] If visual history is incomplete, the agent reassures in simple terms without technical explanations
- [ ] Drop-off never regresses state

#### US-6 Refusal and resistance (harvested from ONB-12)

**When:** The tenant refuses or resists providing information during onboarding.

**Happy path:**
1. The agent accepts the refusal, names the consequence honestly if there is one, offers the smallest path forward, and does not re-ask in the same session.
2. Hard refusal ("I don't want to do this", "this isn't for me", "stop"): accepted without persuasion. "All good - no obligation. Your account stays here if you change your mind."
3. Deferred items surface at their natural downstream moment, never on a schedule.

**Acceptance criteria:**
- [ ] No refused item is re-asked in the same session
- [ ] No "are you sure?" double-confirmation on hard refusal
- [ ] The reason for a skip is never tracked or used against the tenant
- [ ] Hard refusal never deletes or modifies the account
- [ ] No re-engagement push fires for a tenant who hard-refused

## Tickets

| Ticket | Name | What it delivers | Files/modules | Depends on |
|---|---|---|---|---|
| T-011 | Tenant chat shell | Chat tab UI with message list, composer (command pill: text + "+" + send), streaming support, SSE client; renders S1 Chat surface (design.md S1) | `frontend/src/app/chat/`, `frontend/src/components/ChatBubble.tsx`, `frontend/src/components/StreamingText.tsx`, `frontend/src/hooks/useSSE.ts` | T-010 |
| T-012 | LLM provider with tool calling | `ModelPort` seam (`backend/app/llm/provider.py`): `chat_with_tools` function, structured `extract` for evals; env-driven provider selection; free-tier model config | `backend/app/llm/provider.py`, `backend/app/llm/config.py` | T-010 |
| T-013 | Onboarding tool loop | `run_turn` / `TurnDirective` pattern (ported from Wren): login-in-chat tools (`send_login_code`, `verify_login_code`), profile capture tools (`save_business_profile`, `complete_onboarding`), off-topic redirect budget, bounded loop (4 tool calls/turn, 40 turns/session), resume from last 20 turns | `backend/app/onboarding/agent.py`, `backend/app/onboarding/tools.py`, `backend/app/services/completeness_gate.py` | T-012 |
| T-014 | Business_types config driving questions | Onboarding agent reads the `business_types` row's `profile_template` to determine what is asked, in what order, and what counts as complete. No branch on type (I8). | `backend/app/onboarding/agent.py` (config integration) | T-013, T-007 |
| T-015 | Resume after drop-off | Session restoration: re-render full conversation history from server (last 20 turns), scroll to most recent message, resume at exact capture beat in progress. Return acknowledgement (deterministic, no model call). | `backend/app/onboarding/agent.py` (resume path), `backend/app/routes/chat.py`, `frontend/src/hooks/useChatHistory.ts` | T-013 |
| T-016 | Completeness gate + go live | `complete_onboarding` refused while profile incomplete; gate enumerates missing fields; post-handoff activation summary as conversational message; state-to-shell transition (two-tab app, navigation cross-fade) | `backend/app/services/completeness_gate.py`, `frontend/src/app/layout.tsx` (two-tab shell) | T-015 |

## Gate

- [ ] A new tenant can open the chat page, type an email, receive a 6-digit code, type it back, and begin the interview - all inside the conversation, no sign-up form
- [ ] The onboarding agent completes a full interview (name, business name, business type, hours, services) and the tenant reaches go-live in the two-tab app
- [ ] Drop-off mid-interview and return: the conversation resumes at the exact capture beat
- [ ] The activation summary lists all confirmed fields as a single conversational message
- [ ] Off-topic redirect budget works: redirects twice, then turns firm
- [ ] Payment/price/tax fields are NOT captured (these are Stage 2)
- [ ] Business type drives questions from config, never from code branches (I8 verified)
- [ ] Phone OTP path does not exist in the codebase (decision 6: email + 6-digit code only)

## Done when

- [ ] Six tickets complete
- [ ] Full end-to-end onboarding walkthrough works: login-in-chat -> interview -> go-live
- [ ] Drop-off and return works
- [ ] Activation summary renders as a chat message
- [ ] Two-tab app shell renders with Chat and Business tabs
- [ ] No phone-OTP code path exists
- [ ] No price, tax, or payment mode capture exists in the flow
- [ ] Fits or observed slip
