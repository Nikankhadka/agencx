# 12 (RF-15): Desktop split-pane Chats, mobile navigation preserved

**Status:** Done - merged in `24e4dc58e3025087cbd03ce8939e8682447f3676` on 2026-10-03.
**Branch:** `feat/rf-15-chats-split-pane`.
**Phase 1 area:** Refinement.

Delivered: at `lg+` (min-width 1024px) Chats is one split view - the owner's
queue list on the left and the conversation thread on the right, with no
navigation between them; a placeholder holds the thread column until a row is
selected. Below `lg` the surface stays list-then-thread, with the console's
bottom tab bar preserved. `/chats/[id]` remains a deep link that renders the
thread in the split pane. The queue is owned by a new route-persistent
`chats/layout.tsx`, so it stays mounted while the route changes underneath it;
`chats/page.tsx` becomes the desktop empty-pane placeholder. One new token,
`--width-queue: 360px`. No API or DB change.

## Agreed behavior

- **RF-15** - Desktop (`lg+`) split pane (list left, thread right, no
  navigation); mobile keeps list-then-thread with the bar preserved, and
  `/chats/[id]` survives as a deep link inside the split pane.

## Ticket detail

- **Visible outcome:** At `lg+` Chats is a split pane (list left, thread right)
  with no navigation between them; mobile keeps list-then-thread with the
  bottom bar preserved. `/chats/[id]` remains a deep link that opens the thread
  in the split pane.
- **Current vs proposed:** Current: list and thread are separate routes reached
  by navigation; no split pane exists. Proposed: add the `lg+` split pane while
  keeping both routes; `/chats/[id]` selects the thread pane. Shipped: a
  route-persistent `chats/layout.tsx` owns the queue list and renders `children`
  in the thread pane; route plus breakpoint CSS (`usePathname()` drives
  `hidden lg:flex` / `flex`) decides the mobile shape; `chats/page.tsx` is the
  desktop placeholder.
- **Design reference:** `agencx-prototype-v6.html` `renderScreen('chats')` plus
  `renderThreadScreen` (list-then-screen in v6; the split pane is the `lg+`
  composition of the same two); `design/frontend.md` section 7 tenant console
  shell and S1. Shipped: `chats/layout.tsx`, `chats/ChatsQueue.tsx`,
  `chats/page.tsx`, `chats/[id]/page.tsx`.
- **Dependencies:** RF-14 (queue filtering precedes split-pane work), delivered
  in `3d8ca72`.
- **API/DB changes:** None.
- **Acceptance scenarios:** At 1024px, selecting a row loads the thread in the
  right pane and keeps the list; `/chats/[id]` deep-links to the same state; at
  360px the list navigates to the full thread with the bar visible; browser
  back returns to the list state.
- **Regression checks:** The existing Chats E2E, focus order, and the mobile bar
  behavior stay green.
- **OPEN:** none.

## Decisions

- **Decision (2026-10-03):** **A route-persistent `chats/layout.tsx` owns the
  queue list.** A segment layout renders at both `/chats` and `/chats/[id]`, so
  the list stays mounted while the route changes underneath it - the whole
  point of the desktop pane. Parallel routes were rejected as more structure
  than the requirement earns.
- **Decision (2026-10-03):** **The desktop boundary is `lg` (min-width
  1024px)**, matching RF-8 and the storefront. Visibility is route plus
  breakpoint CSS keyed on `usePathname()`, never a JS media query.
- **Decision (2026-10-03):** **The queue column is a new `--width-queue` token
  (360px)**, used only through Tailwind's `lg:w-(--width-queue)` custom-property
  shorthand (not a `@theme` mapping, so no `make dev-reset`), following the
  RF-8 `--width-panel` precedent; an Exceptions entry was added to
  `frontend.md` 4.6.
- **Decision (2026-10-03):** **Mobile list-then-thread is CSS visibility keyed
  on the route**, and the console `TabBar` is untouched because it already
  lives in the console layout. The thread keeps its `ScreenTopbar` back
  control; on desktop it deselects to the placeholder.

## Verification

- `make lint` - passed (frontend eslint, `check:tokens: OK`; backend ruff,
  import contracts 3 kept, 0 broken).
- `make typecheck` - passed (frontend tsc clean; mypy 225 files).
- `make test` - passed: backend 1275, frontend 365.
- `make build` - passed.
- `npm run gen:types -- --check` - `api-types.ts is up to date`.
- `make format-check` - passed (226 files already formatted).
- `make seed-tenant1 && make eval-skip-llm` - GATE PASSED (money guardrail,
  leakage 12/12 + 12/12, retrieval recall@3/5 1.000; generation, trajectory, and
  injection skipped with `--skip-llm`).
- `make seed` - demo world restored.
- `make test-e2e` - passed: 224, zero flaky.
- CI on PR [#76](https://github.com/Nikankhadka/agencx/pull/76) - all green:
  backend, frontend, api-types, infra, security, e2e, eval-gate, Vercel.
- Independent reviewer pass (SHIP-WITH-FIXES, no blockers); findings fixed: the
  dangling `(D5)` citation was removed, the delete-spec comment was corrected
  for the route-persistent layout, a desktop back-control deselect assertion
  was added, and the PR title's duplicate `(#76)` suffix was removed.
