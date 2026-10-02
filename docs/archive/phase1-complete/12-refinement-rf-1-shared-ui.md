# 12 (RF-1): Shared typography, surfaces, controls, navigation, and focus

**Status:** Done - merged in `ac11c6f` on 2026-10-02 (squash of `bfcbe0a`,
`cf1ea84`, `1be142a`; docs closeout was `105c575`).
**Phase 1 area:** Refinement.

Delivered: one shared row grammar, visible keyboard focus, focus restoration
after an overlay closes, and inner-container scroll restoration across the
console. This ticket preceded the RF-2 through RF-16 visual ports.

## Agreed behavior

Every console screen shares one type rhythm, surface, control, and navigation
language; list rows read as one grammar (identity or icon slot, primary line,
meta line, trailing action); keyboard focus is always visible, focus returns
after a sheet closes, and a list restores its scroll position when the owner
returns. Routes and flow order do not change. Home is unchanged in behavior
(greeting plus the brief); refinement restyles it through shared tokens only.
U-1 through U-4 are landed pre-work.

Shipped: shared `ListRow` row grammar with an identity/icon leading slot plus
title/meta/trailing, with `RowLink` re-pointed at it; focus restoration via
`useRestoreFocusTarget` (old overlays captured `document.activeElement` before
child `autoFocus`, so focus fell to body); inner-container scroll restoration
via `useScrollRestoration` (Next 16 does not restore inner-container scroll
without `cacheComponents`); a single-line truncated Chats preview; and a compact
amber exclamation badge (`priority_high`) replacing the "Action needed" text
pill so the name is not squeezed at 360px.

## Ticket detail

- **Visible outcome:** Every console screen shares one type rhythm, surface,
  control, and navigation language; list rows read as one grammar (identity or
  icon slot, primary line, meta line, trailing action); keyboard focus is
  always visible, focus returns after a sheet closes, and a list restores its
  scroll position when the owner returns. Routes and flow order do not change.
  U-1 through U-4 are landed pre-work.
- **Current vs proposed:** Current: U-1 through U-4 shipped shared navigation,
  buttons, the confirm dialog, and toasts; row grammar is not unified -
  `components/ui/RowLink.tsx` carries icon, label, detail, and chevron only,
  with no identity or trailing slot, and Chats, Home, records, and admin lists
  each build their own row; no scroll preservation exists under `frontend/src`;
  no E2E asserts a `:focus-visible` ring. Proposed: extend or add a row
  primitive with identity and trailing slots, migrate the list screens, add
  focus restoration and scroll preservation, and pin focus visibility with a
  Playwright check.
- **Design reference:** `agencx-prototype-v6.html` `#tabbar`, `#screen-layer`,
  `.dst-topbar`, and the `.bh-row` grammar inside `renderScreen('business')`;
  `design/frontend.md` sections 4 and 7. Shipped:
  `frontend/src/components/ui/RowLink.tsx`, `TabBar.tsx`, `ScreenTopbar.tsx`,
  `Container.tsx`, and the `:focus-visible` rule in
  `frontend/src/app/globals.css`.
- **Dependencies:** None. This ticket precedes the visual ports RF-2 through
  RF-16.
- **API/DB changes:** None.
- **Acceptance scenarios:** A keyboard-only owner tabs through Home, Chats, and
  Business and always sees a focus ring; opening and closing a sheet returns
  focus to the control that opened it; scrolling a long list, opening a row,
  and returning restores the scroll position; the migrated rows render the same
  slots at 360px and 1024px.
- **Regression checks:** `make lint-frontend`, `make typecheck-frontend`,
  `make test-frontend`, and `make test-e2e`; the existing U-1 through U-4 checks
  stay green.

## Verification

- `make lint-frontend` - passed.
- `make typecheck-frontend` - passed.
- `make test-frontend` - 278 passed.
- `make test-e2e` - 163 passed, then 165 once the new specs landed.
- New `frontend/e2e/rf1-shared-ui.spec.ts` asserts slot order at 360/1024, the
  `:focus-visible` outline, focus return after Sheet and Modal, one-line meta,
  and scroll restoration.

## Known follow-up

- `/chats/[id]` was untouched by RF-1.
- Offerings "Add" openers are conditionally unmounted, so focus cannot return
  to that exact node (flagged, not fixed).
