# Agencx - Spacing, Typography, and Layout Tokens

The single rhythm authority for the UI (D27). `frontend/src/styles/theme.css`
is the implementation; this file is the spec it implements. When this file and
the v6 prototype disagree on spacing, type, radii, or elevation, this file
wins. The prototype's values survive only where they are already tokens - the
Exceptions list below. Anything not on that list is not an exception.

## 1. Space scale

Tailwind numeric utilities are the scale; no spacing tokens are added. The
allowed steps are `0 1 2 3 4 5 6 8 12 16 24`:

| Step | Pixels | Used for |
|---|---|---|
| 0 | 0 | resets |
| 1 | 4 | hairline-adjacent nudges, tight icon gaps |
| 2 | 8 | chips, small stacks |
| 3 | 12 | compact control padding |
| 4 | 16 | default control padding, block gaps |
| 5 | 20 | roomy inline padding |
| 6 | 24 | page gutter, section padding |
| 8 | 32 | large section gaps |
| 12 | 48 | document air |
| 16 | 64 | scroll tails, tall spacers |
| 24 | 96 | hero-scale air only |

Every other numeric step is banned: 0.5, 1.5, 2.5, 3.5, 7, 9, 10, 20, and bare
`px` for spacing. Values found in the wild round as follows: 0.5 to 1, 1.5 to
2, 2.5 to 3, 3.5 to 4, 7 to 8 (6 where the local rhythm wants it), 9 to 8, 10
to 8, 20 to 16, `px-[18px]` / `pt-[18px]` / `gap-[18px]` to the 4-scale
equivalent, `py-[15px]` to `py-4`, `py-[11px]` to `py-3`, `px-[14px]` to
`px-4`, `py-[5px]` / `gap-[5px]` / `gap-[3px]` to `py-1` / `gap-1` / `gap-1`,
`pl-[18px]` to `pl-4`, `pr-[10px]` / `pr-[9px]` to `pr-2`, `m-[9px]` to `m-2`,
`text-[10px]` to `text-badge`.

## 2. Page gutter and page rhythm

The page gutter is 24px (`--gutter`, `px-gutter`) at all breakpoints on all
surfaces. The old "32 desktop / 16 mobile" split was never implemented.

Page rhythm by kind: thread pages keep `pt-thread-top` / `pb-thread-tail`;
document pages use `pt-6 pb-16`; admin pages use `py-8`. Stack gaps are
`gap-2` for rows, `gap-4` for blocks, `gap-6` for sections, `gap-8` from a
header to its content.

## 3. Type

One family everywhere: Plus Jakarta Sans (400 / 500 / 600 / 700, loaded in
`layout.tsx`) for `--font-sans` and `--font-display`; `--font-mono` for
traces, ids, and code at 13/18. Weight discipline: regular for prose, medium
for labels and buttons, semibold for titles; 700 and up is reserved for
hero and marketing display only.

Roles (size/leading, tracking only where the scale departs from zero):

- `text-display` 48/56 (-0.02em), `text-title-1` 32/40 (-0.01em, clamps from
  28), `text-title-2` 22/28, `text-title-3` 18/26, `text-body-lg` 18/28,
  `text-body` 16/24 (default), `text-body-sm` 14/20, `text-footnote` 13/18,
  `text-caption` 12/16 (0.05em).
- Mobile-first additions: `text-greeting` 36/40 (-0.03em, 700),
  `text-display-sm` 24/26 (-0.012em, 700), `text-row-title` 20/20 (-0.008em,
  500), `text-card-hl` 15/22 (500), `text-chip` 13/13 (500), `text-meta`
  12/17 (400), `text-prose` 16/26 (400).
- Onboarding thread, fixed by the prototype: `text-lede` 19/30 (-0.005em,
  400), `text-lede-q` 19/27 (500), `text-bubble` 15/21 (400), `text-proc`
  12/12 italic (400).
- Screen chrome: `text-screen-title` 16/16 (-0.006em, 500), `text-row-label`
  15/15 (500), `text-action` 14/14 (500), `text-tab` 10/10 (500),
  `text-badge` 11/11 (500), `text-field` 18/25 (400).
- One uppercase label role: `text-label` 11/11 (0.045em) with `font-medium`.
  Status pills stay `text-caption font-semibold uppercase`; trace labels are
  `text-caption font-mono font-medium uppercase`.
- Retired: `text-eyebrow` (folded into `text-label`; its two sentence-case
  platform-tile uses became `text-meta`), `text-sheet-title` and
  `text-timestamp` (unused; the timestamp stop was a fractional 11.5px, which
  the scale does not admit). `text-display` stays reserved.

Overrides are banned: no `leading-relaxed`, no `tracking-wide`, no
`tracking-[...]`, no redundant `tracking-[var(--text-*-tracking)]` (the
utility already applies it). The only exception is `leading-none` on the two
decorative glyph spans (the platform-tile arrow, the sheet close glyph), where
a glyph is not text.

The warning pair is `#8A5A00` on `#FDF4E3` (founder-set tint): dark ochre
warning text on the warm wash. It clears AA and is pinned by the theme
contract test.

## 4. Layout recipes

- `Container`: `mx-auto w-full px-gutter` plus `max-w-thread` (640, default)
  or `max-w-5xl` (1024, `wide`). Thread, detail, and document pages use
  `thread`; the storefront, admin, and Wren-era pages use `wide`.
  `ScreenTopbar` is full-bleed with `px-gutter`, so content in a Container
  aligns under it.
- `Card`: `rounded-card border border-hairline bg-surface` with padding `none`
  (table and shell uses), `compact p-4` (default; in-column chat cards), or
  `roomy p-6` (standalone stat and form cards). Elevation is added by the
  caller as `shadow-card`; cards inside sheets stay flat.
- List row: `flex w-full items-center gap-4 border-b border-hairline py-4`
  inside a Container; compact table rows use `px-4 py-3`.
- Controls: the sheet-field recipe is `rounded-field border border-border
  px-4 py-3 text-field`. Pills use `py-4` (field) or `py-3` (command) with
  `pl-4` / `pr-2`.
- Safe-area bottom padding lives only on the element touching the viewport
  bottom: composers use `pb-[max(1rem,env(safe-area-inset-bottom))]`, the
  TabBar uses `pb-[env(safe-area-inset-bottom)]`, sheets and the thread top
  carry their own `env()` expressions.

## 5. Exceptions

These prototype values stay because they are already tokens, not because the
prototype says so: `--space-thread-*` (14/16/18/44/20),
`--size-topbar/tabbar/tab/tab-inset*`, `--size-icon-btn*`, `--size-send*`,
`--size-code-cell-*`, `--width-thread`, all radii and shadows, and every
`env()` / `max()` safe-area expression. Fixed geometry the scale cannot name
also stays: bubble `max-w-[85%]`, sidebar `w-56`, `max-w-xs` form widths,
WaitingPanel `max-h-[...]`, the typing-row height, the sheet handle, caret and
dot sizes.

## 6. Enforcement

`frontend/scripts/check-tokens.mjs` (`npm run check:tokens`, in
`lint-frontend` and CI) fails the build on: a spacing utility with a numeric
step outside the allowed set (variants and negatives included); an arbitrary
`[value]` spacing value containing `px` or `rem`, unless it starts with
`max(`, `min(`, `clamp(`, or `env(` or contains `var(`; an arbitrary
`text-[value]` with `px` or `rem`. Deliberately not flagged: `text-5xl`,
`border-2`, `max-w-5xl`, `leading-none`, `size-[7px]`, `max-w-[520px]`,
`max-h-[...]`, `min-h-[...]`, and every named token utility (`px-gutter`,
`pt-thread-top`, `border-chip`). The guard is value-level with no file
allowlist - strict beats clever.

## 7. Change rule

A genuinely needed off-scale value gets a founder ruling plus a token or an
Exceptions entry here - never an inline class. Intentional shifts this pass
introduced, so nobody "fixes" them back: bubble text 14/20 to 15/21; card
padding 18/24/12 to 16/24; chats and Wren-era pages centered at 1024/640 on
desktop; admin gutter 32 to 24; sheet radius 28 to 24; tab gap 3 to 4; scroll
tails 80 to 64.
