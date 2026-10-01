# 12 (Part 3): Shipped UX consistency record (U-1 through U-4)

**Status:** Delivered.
**Phase 1 area:** Refinement.

Delivered: code in `development` (commit `ff90e4a`), and the founder
mobile/desktop walkthrough on the preview passed on 2026-10-01
(`docs/agencx/evidence/walkthrough-2026-10/README.md`, items 11, 12, 19 and
25-29). The 7 specs named below ran green on 2026-10-01 (45 tests). Landed
pre-work for RF-1: the mobile tab bar's accent active state and the
desktop sidebars' grey pill were visibly different products. All navs now
wear the mobile accent idiom, every button answers hover and press,
destructive actions ask through one in-app dialog, and mutations report
through toasts. Deltas recorded in `design/frontend.md` (nav idiom,
`ConfirmDialog`, `Toast` rows).

## U-1: one nav idiom

Shared `navTone()` helper in `components/ui/TabBar.tsx`; tenant sidebar,
platform sidebar/drawer, and storefront category navs all use it. Active is
accent text on a 9% accent wash with the filled glyph; inactive hover is the
same wash. Inactive text is the only per-surface choice, and it is a
contrast choice (`text-text-secondary` on the light sidebars, `text-ink-a40`
on the mobile bar).

- [x] `tab-shell` computed-style test: active Home is
  `rgba(255, 56, 92, 0.09)` / `rgb(180, 0, 78)`; hovered Chats is
  `rgba(255, 56, 92, 0.07)` (`e2e/tab-shell.spec.ts:104-110`).
- [x] `tab-shell-mobile` computed-style test: active tab is the accent
  wash (`e2e/tab-shell-mobile.spec.ts:85-86`).

## U-2: button feel

One unlayered global rule in `globals.css` restores `cursor: pointer` on
buttons (Tailwind v4 preflight leaves `default`); per-role hover/active
idioms everywhere else, semantic tokens only.

- [x] `make lint` (includes `check:tokens`) and `make typecheck` pass
  (`make check` green on 2026-10-01).
- [x] Keyboard pass: visible focus ring on every button, pointer cursor
  everywhere enabled (keyboard probe on 2026-10-01; the only miss was the
  Next dev overlay, which is not product UI).

## U-3: confirmations

`components/ui/ConfirmDialog.tsx` (`ConfirmDialog` + `useConfirm`), built on
`Modal` with a `layer` prop for confirms opened over a sheet. Destructive
removes (offering, media, link, knowledge row, review source, non-draft
discard), hand-back, and all three sign-outs ask through it. Take-over,
draft discard, and copy link never ask. `window.confirm` is gone (`grep` is
empty).

- [x] `business-hub` Escape test: cancel closes the confirm, no DELETE
  fires (`e2e/business-hub.spec.ts:264-295`).
- [x] `auth-login` sign-out, `chats-takeover` hand-back,
  `settings-knowledge` remove all pass through `confirm-accept`
  (`auth-login.spec.ts:93`, `chats-takeover.spec.ts:72`,
  `settings-knowledge.spec.ts:88`).

## U-4: toasts

`react-hot-toast` (already mounted top-center) for every mutation: offering
added/saved/removed, link saved/removed, cover updated, knowledge
saved/draft-ready/replaced/removed/discarded, tenant suspended/reactivated.
Inline errors remain only for initial loads; field validation stays inline.

- [x] `business-hub`, `settings-knowledge` assert toast text, not roles
  (`business-hub.spec.ts:109/140/149/209/244/427/448`,
  `settings-knowledge.spec.ts:75/95/290`).
- [x] `copy-rules` passes on the new confirm and toast copy
  (`e2e/copy-rules.spec.ts:88-119`).
