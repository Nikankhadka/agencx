# 23: Sparse storefront layout

**Status:** Done - merged in `b64736a` on 2026-10-05.
**Phase 1 area:** Storefront UI.

Numbering note: 23 through 28 are the 2026-10 storefront and console
refinement batch; this is the first ticket in it.

## Design reference

`AssistantInvite` and the no-offerings branch of `Storefront`
(`frontend/src/app/[slug]/Storefront.tsx`); the M-7 v4 frames 5a/5b
(archived); `ServicesOverview`
(`frontend/src/components/ui/ServicesOverview.tsx`) is the width and
height peer the invitation has to match.

## Summary

On a storefront with no published offerings, the assistant invitation card
aligns to the same `mx-auto w-full max-w-5xl` column as the hero and the
services overview, and sizes to its content. The wrapping flex column no
longer stretches to fill the remaining viewport height; the leftover space
stays empty above the footer, which `mt-auto` still anchors to the bottom.

## Why

The invitation currently takes all remaining viewport height and, on
desktop, renders full-bleed while every other block sits in a centered
1024px column. On a large screen the result is a pink band that dominates
the page for one sentence and a button, and it reads as a different layout
system from the rest of the storefront. The owner's standard is that the
block follows the page's column and its own content height.

## Current vs proposed behavior

| | Current | Proposed |
|---|---|---|
| Invitation width | Full-bleed with gutter padding | Same `max-w-5xl` column as hero and services |
| Invitation height | Stretches to fill the remaining viewport (`flex flex-1 items-center`) | Sizes to its content with `py-8` spacing |
| Remaining space | Filled by the pink card | Empty above the footer |
| Mobile | Full-width card | Unchanged (the column is full width below the cap) |
| Render condition | Only when the catalog is empty | Unchanged |

## Locked decisions

1. The invitation joins the page's single `max-w-5xl` column; no new width
   token is introduced.
2. It sizes to content; leftover space stays empty rather than being
   distributed into the card.
3. The M-7 note that the invitation "uses the remaining page" is superseded
   here. The sakura wash still lives only behind the card, never the hero.
4. Nothing about the offerings branch changes.

## User stories

### US-1 The sparse desktop page reads as one layout

**As** a customer (or the owner previewing) on a desktop,
**I want** the assistant invitation to line up with the hero and the
overview,
**so that** the page looks composed rather than dominated by one block.

- [ ] At 1280px the invitation card is inside the same `max-w-5xl` column
      as the hero and the services overview
- [ ] The invitation is shorter than the viewport and the space above the
      footer stays empty
- [ ] The catalog-empty state still never renders "nothing published" copy

### US-2 The phone page is unchanged

**As** a customer on a phone,
**I want** the invitation to stay a full-width card under the overview,
**so that** nothing about the mobile reading changes.

- [ ] At 390px the card spans the gutter-inset width with the same padding
      and content

## Technical spec

- `Storefront.tsx`: drop `flex-1` from the no-offerings wrapper
  (`flex flex-1 flex-col` becomes `flex flex-col`).
- `AssistantInvite`: the wrapper becomes
  `mx-auto w-full max-w-5xl px-gutter py-8` (was
  `flex flex-1 items-center px-gutter py-8`).
- Update the `AssistantInvite` comment and the M-7 memory note to record the
  supersession.
- No API, DB, or token change.

## Tests

- `Storefront.test.tsx`: assert the invitation wrapper carries
  `mx-auto w-full max-w-5xl px-gutter py-8` and that no
  `flex flex-1 items-center` invitation wrapper remains.
- No deterministic e2e reaches an empty-catalog public storefront (all four
  seeded tenants carry catalogs and the page payload is server-rendered), so
  the founder visual check at 390 and 1280 is the acceptance step.

## Files touched

- `frontend/src/app/[slug]/Storefront.tsx`
- `frontend/src/app/[slug]/Storefront.test.tsx`
- `.agents/memory.md` (one-line M-7 note)

## Definition of done

- [x] Invitation aligns to the page column and sizes to content
- [x] Mobile unchanged; footer stays bottom-anchored
- [x] Unit tests, lint, and typecheck pass
- [x] Visual check at 390 and 1280 confirms one consistent layout

## References

- M-7 finalized storefront (archived) - full-page invitation intent
  superseded here
- `docs/agencx/design/frontend.md` (columns and container idioms)

## Verification

- `make lint-frontend`, `make typecheck-frontend`, `make test-frontend`: 366
  passed (43 files)
- Visual check at 390 and 1280 against a temporarily emptied bytefix catalog
  (offerings restored afterwards): the invitation sits in the same `max-w-5xl`
  column as the hero and the services overview, sizes to content, and the
  footer stays bottom-anchored
