# 12 (RF-8): Desktop customer chat panels and mobile sheets

**Status:** Done - merged in `b01787ea8c9f5997ae6c10f55a5e7e3d6cda0010` on 2026-10-03.
**Phase 1 area:** Refinement.

Delivered: the customer chat renders as a docked, non-modal right side panel at
`lg+` that leaves the business page visible, scrollable, and interactive, and
as the full-height modal bottom sheet below `lg`. One `CustomerChat` instance
survives both presentations and breakpoint changes, with no second chat tree
and no remount on resize.

## Agreed behavior

Customer chat is a desktop side panel (`lg+`) and a full-height mobile sheet;
the Business page stays reachable while chat is open. At `lg+` the chat is a
docked, non-modal right side panel (`role="complementary"`, no scrim, no
`aria-modal`, page visible and interactive, content inset so the panel never
covers it); below `lg` it stays the full-height modal bottom sheet with focus
trap, `aria-modal`, scrim, Escape and scrim close. Exactly one `CustomerChat`
instance is preserved across both presentations and across breakpoint changes -
one panel host switches presentation; no second chat tree and no remount on
resize.

## Ticket detail

- **Visible outcome:** On `lg+` the customer chat is a side panel that leaves
  the business page reachable; below `lg` it is a full-height sheet.
- **Current vs proposed:** Current: chat renders as a mobile `Sheet` only; no
  `lg+` desktop side panel exists. Proposed: add the `lg+` side panel while
  keeping the mobile sheet, with the business page visible beside it.
- **Design reference:** Shipped `frontend/src/app/[slug]/CustomerChat.tsx`,
  `Storefront.tsx` (sheet host), and `components/ui/Sheet.tsx`;
  `design/frontend.md` S3. v6 is mobile-only.
- **Dependencies:** RF-7.
- **API/DB changes:** None.
- **Decisions:** Desktop composition accepted for RF-8: at `lg+` the chat is a
  docked, non-modal right side panel (`role="complementary"`, no scrim, no
  `aria-modal`, page visible and interactive, content inset so the panel never
  covers it); below `lg` it stays the full-height modal bottom sheet with focus
  trap, `aria-modal`, scrim, Escape and scrim close. Exactly one
  `CustomerChat` instance is preserved across both presentations and across
  breakpoint changes - one panel host switches presentation; no second chat
  tree and no remount on resize.
- **Acceptance scenarios:** At 1024px the chat opens beside the page and the
  page stays scrollable and interactive; at 360px the sheet is full height with
  the composer reachable; closing the panel restores the page state.
- **Regression checks:** The storefront E2E at both widths; focus trap and
  `aria-modal` behavior for the sheet.
- **OPEN:** Resolved. No open product questions remained; the desktop
  composition (docked non-modal `lg+` panel versus modal mobile sheet, one
  preserved `CustomerChat` instance) was accepted for RF-8 (see Decisions
  above).

## Verification

- `make lint-frontend` - passed (`check:tokens: OK`).
- `make typecheck-frontend` - passed.
- `make test-frontend` - passed: 38 files / 332 tests.
- Targeted E2E - passed: `rf-8` plus `storefront`, `storefront-mobile`,
  `business-details-rf2`, `rf-7-business-page-shortcuts`, `typing-indicator`,
  and `business-hub`, 62 passed.
- CI on PR #69 - all green (backend, frontend, api-types, infra, security,
  e2e, eval-gate, Vercel).
- Full local `make test-e2e` - 194 passed with 1 pre-existing order-dependent
  flake in `tab-shell-mobile.spec.ts` (a different test each run, passes 6/6 in
  isolation; documented repo flake, unrelated to RF-8); this is not a clean
  full-suite run.
- Independent reviewer pass; findings fixed in `f25f581` (desktop role
  regressions in `typing-indicator`/`business-hub`, pinned `complementary` in
  `storefront`, breakpoint-survival E2E, focus-not-trapped E2E,
  comment/cross-reference/shadow/constant nits). Accepted follow-ups: shared
  overlay focus-trap hook, double safe-area padding, Escape-only-when-focused,
  `MediaQueryList.addEventListener` legacy guard.
