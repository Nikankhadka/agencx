# RF-17 four-business walkthrough evidence - 2026-10-03

The assembled-experience verification for RF-17 Slice 2: one deterministic
Playwright walkthrough of the four seeded businesses on identical workflow code
with configuration-only differences.

## Environment and date

| Item | Value |
|---|---|
| Environment | Local Docker Compose stack (`make dev` then `make seed`) |
| Date | 2026-10-03 |
| Base URL | `http://localhost:3000` (customer pages `/{slug}`, console `/chats` and `/business`); backend `http://localhost:8000` |
| Branch | `feat/rf-17-four-business-walkthrough` |
| Evidence commit | `4373b3e142c51344f99754eb6e22255dc5644bfe` (spec and screenshots) |
| Base commit | `ee337c5` (RF-17 Slice 1, the fourth config-only tenant) |
| Browser | Chromium, desktop 1440x900 and mobile 390x844 (viewport-only captures) |

Every screen here reads the seeded demo world: `sababa` (cafe), `bytefix`
(retail/repair), `lumident` (dental), and `wellspring` (general clinic). The
walkthrough stubs the customer-chat stream with each business's own catalog, so
the live model is never on the path and the run is deterministic.

## Reproduce

1. Start the stack and seed the demo world: `make dev` then `make seed`.
2. Capture the screenshots:
   `cd frontend && RF17_CAPTURE=1 RF17_SHOTS_DIR=<repo>/docs/agencx/evidence/rf-17-2026-10-03 npx playwright test e2e/rf-17-four-business-walkthrough.spec.ts --project=chromium`
3. Run the regression suite, where the spec runs with capture off:
   `make test-e2e`.

With `RF17_CAPTURE` unset the spec asserts and captures nothing, so CI never
rewrites tracked files.

## Ledger

All five tests live in the Playwright describe `RF-17 four-business
walkthrough`. The "Named E2E check" column quotes each test's exact title - the
string passed to `test(...)`, which is what `make test-e2e` prints.

### bytefix (retail/repair)

| # | Screenshot | Named E2E check | Result |
|---|---|---|---|
| 01 | `01-bytefix-storefront-desktop.png` | `RF-17 bytefix (retail/repair) - config-driven storefront, chat, queue, and business hub` | Pass |
| 02 | `02-bytefix-storefront-mobile.png` | same test | Pass |
| 03 | `03-bytefix-chat-start-desktop.png` | same test | Pass - own greeting and "How much is a screen replacement?" starters |
| 04 | `04-bytefix-chat-reply-desktop.png` | same test | Pass - own catalog card, `$249.00` |
| 05 | `05-bytefix-queue-desktop.png` | same test | Pass - `alex.rivera` / `jordan.patel`, no other tenant's refs |
| 06 | `06-bytefix-business-hub-desktop.png` | same test | Pass - console shows "Bytefix Repairs" |

### lumident (dental)

| # | Screenshot | Named E2E check | Result |
|---|---|---|---|
| 01 | `01-lumident-storefront-desktop.png` | `RF-17 lumident (dental) - config-driven storefront, chat, queue, and business hub` | Pass |
| 02 | `02-lumident-storefront-mobile.png` | same test | Pass |
| 03 | `03-lumident-chat-start-desktop.png` | same test | Pass - own greeting and cleaning/filling starters |
| 04 | `04-lumident-chat-reply-desktop.png` | same test | Pass - own catalog card, `$1,100.00` |
| 05 | `05-lumident-queue-desktop.png` | same test | Pass - `patient.a` / `patient.b`, no other tenant's refs |
| 06 | `06-lumident-business-hub-desktop.png` | same test | Pass - console shows "Lumident Dental" |

### sababa (cafe)

| # | Screenshot | Named E2E check | Result |
|---|---|---|---|
| 01 | `01-sababa-storefront-desktop.png` | `RF-17 sababa (cafe) - config-driven storefront, chat, queue, and business hub` | Pass |
| 02 | `02-sababa-storefront-mobile.png` | same test | Pass |
| 03 | `03-sababa-chat-start-desktop.png` | same test | Pass - own greeting and menu starters |
| 04 | `04-sababa-chat-reply-desktop.png` | same test | Pass - own catalog card, `$37.00` |
| 05 | `05-sababa-queue-desktop.png` | same test | Pass - `diner.a` / `diner.b`, no other tenant's refs |
| 06 | `06-sababa-business-hub-desktop.png` | same test | Pass - console shows "Sabbaba" |

### wellspring (general clinic)

| # | Screenshot | Named E2E check | Result |
|---|---|---|---|
| 01 | `01-wellspring-storefront-desktop.png` | `RF-17 wellspring (general clinic) - config-driven storefront, chat, queue, and business hub` | Pass |
| 02 | `02-wellspring-storefront-mobile.png` | same test | Pass |
| 03 | `03-wellspring-chat-start-desktop.png` | same test | Pass - own greeting and consultation/results starters |
| 04 | `04-wellspring-chat-reply-desktop.png` | same test | Pass - own catalog card, `$85.00` |
| 05 | `05-wellspring-queue-desktop.png` | same test | Pass - `patient.c` / `patient.d`, no other tenant's refs |
| 06 | `06-wellspring-business-hub-desktop.png` | same test | Pass - console shows "Wellspring Medical Centre" |

## Cross-tenant isolation

Test:
`RF-17 cross-tenant isolation - each public page carries only its own business`

For each business's anonymous public page, the spec asserts:

- Its own unique offering is present: bytefix `iPhone 11 (Refurbished, 64GB)`,
  lumident `Dental Crown`, sababa `Super Plate`, wellspring `Skin Check`.
- Every other business's unique offering is absent.
- None of the four owner emails appears.
- No owner-only storefront markup appears (`owner-edit-name`,
  `owner-edit-fields`).

Result: pass. The data-layer half is pinned by the backend leakage eval and
tests; this is the surface proof of what a customer actually receives.

## Regression results

| Command | Result |
|---|---|
| `make test-e2e` | 239 passed, 0 failed, 0 flaky (5.3m); the 5 RF-17 tests pass inside it |
| `make seed-tenant1 && make eval-skip-llm` | GATE PASSED - money guardrail 21/21, leakage 12/12 each direction, retrieval recall@5 1.000 |
| `npm run gen:types -- --check` (host) | `api-types.ts is up to date` |
| `make lint` | frontend ESLint + `check:tokens` OK; backend `ruff` + `lint-imports` 3 contracts kept |
| `make typecheck` | frontend `tsc --noEmit` clean; backend `mypy` clean (226 files) |
| `make format-check` | 227 files already formatted |
| `make build` | production build succeeds |
| `git status --short` | only the intended spec, ledger, and screenshots |

## Decisions

- None of the four businesses required a code change to walk through; the
  differences are entirely `tenant_config` and seeded catalog, which is the
  invariant RF-17 exists to prove.

## Follow-ups (not fixed, out of scope)

- The documented `docker compose run --rm --no-deps frontend npm run gen:types
  -- --check` fails in the frontend container because that image has no `uv`
  binary and the script shells out to `uv run python` against a sibling
  `backend/` path that is not mounted. The check passes from the host, where
  `uv` and the backend tree exist. This is a pre-existing command-table
  inaccuracy, unrelated to RF-17.
- In the 1440px split-pane Chats view the filter tab strip ("Human handled")
  clips and scrolls horizontally because the list pane is narrow. This is the
  existing `overflow-x-auto` behavior at that width, not introduced here, and
  it does not block the walkthrough.
