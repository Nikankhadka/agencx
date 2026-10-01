# Founder walkthrough evidence - 2026-10-01

Screenshots first captured on the live preview deploy (`https://agencx-kpr6m783q-nikankhadkas-projects.vercel.app`,
commit `dba1f05` on `development`) for three tickets that were built but awaiting founder
walkthrough sign-off: `docs/archive/phase1-complete/19-intent-and-identity.md`,
`docs/archive/phase1-complete/20-required-services.md`, and `docs/agencx/spec/active/12-refinement.md`
(the onboarding-normalization slice plus Part 3 U-1..U-4).

**Re-walk:** after the three bugs below were fixed, the same spec was rerun against the
preview deploy `https://agencx-njtuy81ys-nikankhadkas-projects.vercel.app` (commit `4cc2683`
on `development`) with new assertions for each fixed item: one handoff message after
"Jordan", "Jordan" on the owner's chat row, no `['` in the services read-back, an exact
"Saved" toast, and "Butter croissant" live on the storefront with the services overview gone.
Both tests passed (3.0m). Every screenshot in this directory is from the re-walk; the result
column below records it.

Captured with the throwaway Playwright spec `frontend/e2e/walkthrough-2026-10.spec.ts`
(excluded from the regression suite in `playwright.config.ts`'s `testIgnore`, same as
`w7-screenshots.spec.ts` and `w9-repro.spec.ts`). Desktop = 1440x900, mobile = 390x844
(iPhone 13 viewport, viewport-only screenshots - `page.screenshot()`, not `fullPage`, since
this app keeps the chat Sheet always mounted off-screen and a full-page capture paints its
closed state into the stitched image).

**Safety note:** the preview shares the production Supabase database. Nothing below was
cleaned up by this run - the tenants, conversation, and document rows all still exist. No
migrations, deletes, or write SQL ran; all DB reads below were plain `SELECT`s. No secret,
OTP, or token was ever logged, printed, or captured in a screenshot.

## Ledger

### Ticket 19 - intent and identity

| # | Screenshot | Checklist item | Result |
|---|---|---|---|
| 01 | `01-t19-storefront-opening-desktop.png` | bytefix storefront, anonymous customer | Pass |
| 01b | `01b-t19-chat-opened-desktop.png` | Chat sheet opens | Pass |
| 02 | `02-t19-pricing-reply-desktop.png` | Pricing question answered in chat | Pass |
| 03 | `03-t19-handoff-contact-ask-desktop.png` | Human request triggers handoff + single contact ask | Pass |
| 04 | `04-t19-name-only-accepted-desktop.png` | Name-only answer accepted | Pass on the re-walk - "Thanks, Jordan" and only the missing email is asked for; the handoff text appears once (asserted). First walk: Flaky, Bug 1. |
| 05 | `05-t19-continues-after-handoff-desktop.png` | Chat never blocks after handoff | Pass - a follow-up question gets a normal, relevant reply |
| 06 | `06-t19-thread-mobile.png` | Same thread, mobile viewport | Pass |
| 07 | `07-t19-owner-chats-list-desktop.png` | Owner console shows the new conversation | Pass |
| 08 | `08-t19-owner-thread-name-desktop.png` | Owner thread view | Pass on the re-walk - the thread header reads "Jordan" and the chat row carries it (asserted). First walk: name absent, Bug 1. |

| 09a | `09a-t19-support-name-email-desktop.png` | Re-walk addition: a bad repair (support), a person request, then "Sam, <email>" in one reply | Pass - the handoff text appears once and the email appears once, in the customer's own bubble (both asserted); the chat continues after |
| 09b | `09b-t19-owner-thread-email-desktop.png` | Owner thread shows the stored email | Pass - `thread-email` reads the address (asserted) and the header reads "Sam" |

"Never blocks, never re-asks" - both hold on the re-walk.

Read-only DB check after the re-walk: the support reply's `messages.metadata.intent` is
`support`, the pricing reply's is `information` (a classifier miss: the ticket defines
pricing as `offer`), and both conversations have the right
`customer_ref` (Sam's conversation also has a `customer_email`). Both `escalations.intent`
values are null, which the ticket allows (locked decision 5). The explicit-request guard
runs before any classifier, and on the tool path the model left `create_escalation`'s
optional `intent` out with no offer or information tool to fall back on. Person requests
therefore rarely record an intent; this is noted for the founder, not treated as a defect.

### Ticket 20 - required services

| # | Screenshot | Checklist item | Result |
|---|---|---|---|
| 10 | `10-t20-opening-owner-name-ask-desktop.png` | New `wt-` business onboarding opens | Pass |
| 13 | `13-t20-headcount-chips-desktop.png` | Headcount beat (chips) | Pass |
| 14 | `14-t20-services-ask-no-skip-chip-desktop.png` | Services beat is required, free text, price-inclusive, **no Skip chip** | Pass - asserted in-test (`onboarding-chip-skip` count is 0) |
| 15 | `15-t20-services-answered-desktop.png` | Services answer accepted | Pass (content-wise); this shot and #16 landed on the same rendered state - see note below |
| 16 | `16-t20-voice-chips-desktop.png` | Beat advances to voice preset | Pass on the re-walk - the read-back reads "Got what you offer: Drip coffee, $4 to $6; Pastries, $3 to $6." (no `['` asserted). First walk: Bug 2. |
| 17 | `17-t20-knowledge-ask-single-skip-chip-desktop.png` | Knowledge ask carries the one always-visible Skip chip in the whole interview | Pass |
| 18 | `18-t20-readiness-confirm-wt-slug-desktop.png` | Readiness/confirm screen, proposed slug starts with `wt-` | Pass |
| 20 | `20-t20-home-greeting-desktop.png` | Owner console home after confirm | Pass |
| 21 | `21-t20-home-greeting-mobile.png` | Mobile tab bar nav idiom (U-1) | Pass |
| 22 | `22-t20-business-preview-services-overview-desktop.png` | Owner's own storefront preview reads the `services` answer back verbatim when nothing is priced | Pass - contains "Drip coffee" |
| 23 | `23-t20-public-storefront-services-overview-desktop.png` | Public storefront, same component/text | Pass - contains "Drip coffee" |
| 24 | `24-t20-public-storefront-services-overview-mobile.png` | Same, mobile | Pass |

Note on 15/16: both files are byte-identical (confirmed via `md5`). The services-answered
shot landed on the already-advanced voice-chips state rather than the intermediate moment;
a test-script capture-sequencing redundancy, not a product defect - the voice-chips shot
(16) is genuine and still proves the beat, and it independently reproduces Bug 2.

### Ticket 12 - onboarding normalization + Part 3 U-1..U-4

| # | Screenshot | Checklist item | Result |
|---|---|---|---|
| 11 | `11-t12-owner-name-proposal-confirm-desktop.png` | Owner name is a proposal, confirmed, not assumed | Pass |
| 12 | `12-t12-business-name-proposal-confirm-desktop.png` | Business name, same proposal/confirm seam | Pass |
| 19 | `19-u3-signout-confirm-dialog-desktop.png` | U-3: shared confirm dialog (sign-out), cancelled to keep the session | Pass |
| 25 | `25-t12-knowledge-upload-toast-desktop.png` | Knowledge upload auto-opens the review sheet with its toast | Pass |
| 26 | `26-t12-review-sheet-candidates-private-desktop.png` | Offering candidates stay private/pending until reviewed - review sheet shows "2 retained offerings", no warning banner | Pass on "private until reviewed"; see Bug 3 below for what the backend was doing at this moment, invisibly |
| 27 | `27-t12-storefront-still-no-offerings-desktop.png` | Storefront still shows nothing priced while the review sheet is open/unsaved | Pass |
| 28 | `28-t12-review-sheet-save-toast-desktop.png` | Save the review | Pass on the re-walk - the exact "Saved" toast shows and `menu.txt` reads "Answering from this, 2 offerings came from this". First walk: Bug 3. |
| 29 | `29-t12-storefront-offerings-now-public-desktop.png` | Storefront after save | Pass on the re-walk - "Drip coffee $5.00" and "Butter croissant $4.00" under "What we offer", and the services overview is gone (both asserted); the file now differs from #23/#27 by `md5`. First walk: Fail, Bug 3. |

U-2 (button feel/press states) and U-4 (toasts) are visible throughout the shots above
(the same `TEXT_PRESS` press styling and toast component appear consistently) but a static
screenshot cannot itself prove a press/motion feel - noted as an honest gap rather than a
separate capture, since a moving interaction isn't screenshot-provable.

## Bugs found (all three fixed and re-walked)

| Bug | Fix commit | Re-walk items |
|---|---|---|
| 1 - duplicate handoff on a name reply | `4cc2683` | 04, 07, 08 |
| 2 - list repr in the onboarding read-back | `2c6e129` | 16 |
| 3 - a price-list-only record could not be saved | `7d8425b` | 28, 29 |

Open observation from the re-walk, out of scope here and reported as its own task: the
console sidebar of a self-onboarded tenant shows its slug ("wt-walkthro...", shots 20 and
28) rather than the business name. `(console)/layout.tsx` reads `brand.display_name` then
`tenant.name` (the signup name), skipping the go-live business name that the backend's
`display_name()` already prefers. Seeded tenants like bytefix are unaffected.

**Bug 1 - name-only handoff answer is sometimes re-asked instead of acknowledged (ticket 19).**
In 3 of 4 test runs this session, after the customer answered the contact ask with just
"Jordan", the assistant's next message was the exact same text as its own preceding
question, verbatim, instead of an acknowledgment - `conversations.customer_ref` stayed
empty. In the 1 run where it worked, `customer_ref` was correctly set to "Jordan" and the
owner console listed the conversation by that name. The conversation never gets stuck
afterward (screenshot 05 shows a normal follow-up reply), so "never blocks" holds, but
"never re-asks" does not.

Root cause (supervisor, from the preview runtime logs for request
`31549d3a71224a28aea687a5e3bbb943`, 23:02:13 UTC): on the "Jordan" turn the model called
`create_escalation` again instead of `set_customer_contact`. The escalation insert is a
no-op on an already-open escalation, but the agent node still ended the turn on the
escalation route, so the server emitted the full handoff message and contact ask a second
time. The model's tool choice varies run to run; the server treating a duplicate handoff as
a fresh one is the deterministic half.

**Bug 2 - raw Python list syntax leaks into onboarding copy (ticket 20/12).**
Screenshot `16-t20-voice-chips-desktop.png`: the assistant's services confirmation line
reads `Got what you offer: ['Drip coffee, $4 to $6', 'Pastries, $3 to $6']. How should your
assistant sound to customers?` - literal Python list/repr syntax (square brackets,
single-quoted strings) instead of natural language. Single clear, reproducible instance.

Root cause (supervisor): `services` is stored as a list since ticket 20, and every onboarding
read-back site in `backend/app/onboarding/agent.py` (the turn acknowledgement, corrections,
the URL read-back) formats a draft value with `str(...)`, which renders a list as its Python
repr.

**Bug 3 - offerings never persist after a knowledge-review save, no failure surfaced in the review flow (ticket 12).**
Root-caused to source and the database, not just observed: after uploading `menu.txt`
during the `/business/details/knowledge` review (not onboarding's own knowledge step), the
review sheet showed 2 correctly-extracted, healthy-looking offerings ("Drip coffee $5.00",
"Butter croissant $4.00") with no warning of any kind (screenshot 26). Unknown to that
screen, the backend's ingest pipeline had already (or concurrently) marked the underlying
`documents` row `status = 'failed'`, `error = "We could not make this document searchable.
Please retry."`, about 10 seconds after upload - confirmed via a read-only query against
the live `documents` table. `backend/app/features/knowledge/service.py`'s `save_record()`
returns early when the document's status is `'failed'` (lines ~791-798), before the
offering-creation code ever runs, and `backend/app/features/knowledge/controller.py` turns
that into an HTTP 422. Confirmed via a read-only query against `offerings`: 0 rows for this
tenant, despite the review sheet's "2 retained offerings." The only place this failure is
surfaced to the owner is a red status line + Retry button on the separate knowledge list
page (`business/details/knowledge/page.tsx`, `data-testid="knowledge-retry"`) - not inside
the review sheet the owner just used, and not on the save action itself. Screenshot 28 (the
frame captured right after the in-test "Saved" text assertion passed) still shows the sheet
open with the save button mid-spinner and only the older "Draft ready to review" toast
visible - so whether a genuine fresh "Saved" toast ever appeared before this failure is
inconclusive from this evidence; what is conclusive is that the storefront (screenshots
23/27/29, byte-identical by `md5`) never showed the reviewed offerings at any point.

Root cause (supervisor, from the preview runtime logs for request
`f779c73c50db4b849a822d61ef202ff7`, 23:01:49 UTC): not quota and not transient. The failure
happened on the save itself (`PUT /api/knowledge/records/{id}` returned 422).
`menu.txt` is all offerings, so the reviewed record had no prose sections; `save_record`
re-renders the sections to text and runs `process_document`, which raised
`_NoExtractableContent` on the empty text (logged under the misleading `stage=embed`) and
marked the document failed before the offerings were written. Any document that is purely
a price list cannot be saved. Deterministic and reproducible.

## Data created on the production Supabase database (not cleaned up by this run)

### `wt-` tenants (7 total, all via `owner` self-onboarding through `/login` -> `/onboarding`)

| Tenant id | Slug | Login email | Created (UTC) | Outcome |
|---|---|---|---|---|
| `c2eb75c6-5bf8-4ba7-a90a-bc1eff36a773` | `wt-walkthrough-smoketest-17908-dznx` | `wt-walkthrough+smoketest-1790805947170@agencx.test` | 22:06:13 | Early mechanics smoke-test of the login/OTP helper, before the full spec existed |
| `967c6b5b-8f24-407a-9f42-6c432828fcc8` | `wt-walkthrough-cafe` | `wt-walkthrough+1790806864894@agencx.test` | 22:21:11 | Published, first full run |
| `5385ef79-2900-4b4f-be7c-9e5908d45c7f` | `wt-walkthrough-1790807862751-px33` | `wt-walkthrough+1790807862751@agencx.test` | 22:37:47 | Abandoned mid-onboarding (slug-collision bug in the test script, since fixed) |
| `2938767f-1aa9-4b0f-bdf2-491aa8c0d58b` | `wt-walkthrough-cafe-1790808088501` | `wt-walkthrough+1790808088501@agencx.test` | 22:41:46 | Published, full run |
| `056074ee-6b49-4724-a712-dadd302d0635` | `wt-walkthrough-1790808251344-4ui6` | `wt-walkthrough+1790808251344@agencx.test` | 22:44:27 | Abandoned mid-onboarding (services-beat re-ask stall, see Bug candidate noted above as likely LLM flakiness; 15-minute test timeout) |
| `73ef58a0-0049-44e4-8ff3-426cb042d88e` | `wt-walkthrough-cafe-1790809192954` | `wt-walkthrough+1790809192954@agencx.test` | 23:00:10 | Published, final run of the first walk |
| (see slug) | `wt-walkthrough-cafe-1790849200481` | `wt-walkthrough+1790849200481@agencx.test` | re-walk | **Published, re-walk** - the tenant behind the current screenshots 10-29 |

### `bytefix` conversations created (6 total, plus 5 pre-existing seed conversations untouched)

| Conversation id | `customer_ref` | Created (UTC) | Messages | Notes |
|---|---|---|---|---|
| `ea90edc0-94bd-4e33-a474-75ae22396c8e` | (empty) | 22:19:14 | 8 | Early full run of ticket 19's flow before script fixes |
| `714282d5-f3a7-4eb0-8fa3-2dd2a1b81a18` | `Jordan` | 22:20:42 | 8 | Name capture worked correctly this run |
| `2dab372b-6f69-4c98-b57f-1929d3f3b6d0` | (empty) | 22:37:23 | 8 | Bug 1 reproduced |
| `3110e051-a2e4-4d9d-882f-6a5cf5bb1bc6` | (empty) | 23:02:06 | 8 | Final run of the first walk; Bug 1 reproduced |
| `b04686f8-ab9c-40ee-9691-4cee8f54c6d6` | `Jordan` | re-walk | 8 | **Re-walk** - the conversation behind the current screenshots 01-08 |
| `b1b600ea-6fa2-468b-8a4b-b3b0a6bf4705` | `Sam` (+ email `wt-customer+1790849540211@agencx.test`) | re-walk | 8 | **Re-walk** - the conversation behind screenshots 09a-09b |

## Files

- `frontend/e2e/walkthrough-2026-10.spec.ts` (new, throwaway, excluded from `testIgnore`)
- `frontend/playwright.config.ts` (`testIgnore` extended to exclude the above, matching the
  `w7`/`w9` precedent)
- `frontend/e2e/copy-rules.spec.ts` (extended with a `"copy rules - shared components"` case
  exercising the shared confirm dialog and a toast; runs against the local stack, not
  preview - 9/9 passing)
- This directory's screenshots and this `README.md`

## copy-rules.spec.ts result

9/9 passing locally (`npx playwright test e2e/copy-rules.spec.ts --project=chromium`),
including the new shared-components case.

## LLM quota / 429s

No explicit quota or 429 error was observed or logged in any test output this session. Bug
1 (re-ask) and the one-off services-beat stall are plausibly LLM-side in origin but this was
not confirmed either way.
