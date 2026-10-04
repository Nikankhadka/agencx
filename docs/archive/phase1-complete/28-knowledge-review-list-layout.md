# 28: Knowledge review list layout

**Status:** Done - merged in `3823740` on 2026-10-05.
**Phase 1 area:** Knowledge review (onboarding and Business > Details > Knowledge).

Numbering note: 23 through 28 are the 2026-10 storefront and console
refinement batch; this is the last ticket in it.

## Design reference

`ReviewDocument`, `OfferingCard`, and `KnowledgeDocument` render functions in
`frontend/src/components/knowledge/ReviewSheet.tsx`; the review sheet prototype
block `#sheet-settings-edit` in
`design/prototypes/agencx-prototype-v6.html`; the `lg` desktop boundary
(`DESKTOP_QUERY`, `frontend/src/lib/useMediaQuery.ts`).

## Summary

The knowledge review sheet leads with Offerings in both modes (onboarding and
Business > Details > Knowledge). The collapsed list shows at most three
offerings below `lg` and five at `lg+`; "Review all N offerings" and "Add
offering" sit below the visible cards, not above them. "Review all" still
expands in place with the existing five-per-page pager, and "Add offering"
still expands and focuses the new row. The suggestions-only sheet is
untouched.

## Why

Offerings and their rough prices are the reason the review exists; business
information is context the owner can read afterward. Outside onboarding the
sheet currently leads with the document's own content, so the owner meets
their hours and location before the thing they came to check. Long catalogs
also push the controls out of the reading path: the actions sit above five
read-only cards, so the owner scrolls past a wall of rows to find them.
Capping the collapsed list and moving the actions to its foot keeps the
review short and puts the controls where the reading ends.

## Current vs proposed behavior

| | Current | Proposed |
|---|---|---|
| Section order | Onboarding: Offerings then Business information; Business > Knowledge: reversed | Offerings first in both modes |
| Collapsed list | Up to five offerings (`PAGE_SIZE`) at every width | Up to three below `lg`, up to five at `lg+` |
| Actions | "Review all N" and "Add offering" above the cards | Below the visible cards |
| Small catalog | Five or fewer offerings render all rows, editable | At or below the cap all rows render editable and "Review all" hides; above it the owner expands |
| Expanded list | Five-per-page pager inside the sheet | Unchanged |
| Add offering | Expands, inserts after the last owner row, focuses it | Unchanged |
| Suggestions-only sheet | Compact editing list with its own footer | Unchanged |

## Locked decisions

1. Offerings render before Business information in both modes. This
   supersedes RF-6's business-mode ordering (the archived RF-6 record stays
   as history).
2. The collapsed cap is three below `lg` and five at `lg+`. `PAGE_SIZE`
   stays five for the expanded pager; SSR renders the mobile cap and the
   client corrects after hydration (`useMediaQuery` is SSR-safe, default
   mobile).
3. Collapsed cards stay read-only, exactly as today; "Review all" is what
   makes them editable.
4. When the catalog fits inside the cap (two offerings on a phone, four on a
   desktop), all rows render editable and "Review all" is hidden.
5. "Review all N offerings" and "Add offering" render in one row below the
   cards and any pagination. "Add offering" keeps forcing expansion and
   focusing the new row.
6. `SuggestionDocument` (the `suggestionsOnly` flow) does not change.

## User stories

### US-1 Offerings are the first thing reviewed

**As** Sam reviewing an upload,
**I want** the offerings and their prices first,
**so that** I check the commercial facts before skimming the rest.

- [ ] In both onboarding and Business > Knowledge mode, the Offerings section
      precedes Business information in DOM and visual order
- [ ] The five-per-page pager and the count line are unchanged when expanded

### US-2 The collapsed list stays short and its actions sit at its foot

**As** Sam with a long menu,
**I want** three offerings on my phone and five on my desktop with the
controls right below them,
**so that** the review does not open as a wall of rows.

- [ ] At 390px the collapsed sheet shows at most three offering cards
- [ ] At 1280px the collapsed sheet shows at most five offering cards
- [ ] "Review all N offerings" and "Add offering" render below the last
      visible card; with the catalog inside the cap, "Add offering" renders
      alone
- [ ] Rows inside the cap are editable without pressing "Review all"

### US-3 Expanding still navigates the whole catalog

**As** Sam with more offerings than the cap,
**I want** "Review all" to expand the same in-place pager,
**so that** nothing about approving the catalog changes.

- [ ] Pressing "Review all N offerings" reveals the five-per-page pager,
      editable rows, and the "Page X of Y" copy
- [ ] "Add offering" expands, inserts the new row after the last owner row,
      and focuses it

## Technical spec

- `ReviewSheet.tsx` (`ReviewDocument`):
  - Import `useMediaQuery` and `DESKTOP_QUERY`; add
    `const COLLAPSED_MOBILE = 3`; `const collapsedLimit = desktop ? PAGE_SIZE : COLLAPSED_MOBILE`.
  - `expanded` starts `false`; `allFit = offerings.length <= collapsedLimit`;
    collapsed cards are editable when `expanded || allFit`; visible rows are
    `expanded ? offeringPage(offerings, currentPage) : offerings.slice(0, collapsedLimit)`.
  - Render the action row (`{showReviewAll ? reviewButton : <span />}` plus
    "Add offering") after the cards and pagination; rename the label to
    `Review all {offerings.length} offerings`.
  - Render `{offeringsSection}{businessInformationSection}` unconditionally;
    set the offerings wrapper to `mt-5` and the business wrapper to `mt-8`;
    update the RF-6 comment to record the reversal.
- No API, DB, or token change.

## Tests

- `ReviewSheet.test.tsx`: collapsed seven-offering case asserts three cards
  ("Offering 1" through "Offering 3", no "Offering 4"), the new label, and
  that both actions come after the last card in the markup; the four-offering
  case now asserts "Review all 4 offerings"; a two-offering case asserts no
  "Review all" and "Add offering" below the cards; the section-order test
  asserts Offerings before Business information in both modes.
- `frontend/e2e/knowledge-review.spec.ts` (desktop project): rename
  "Review all 12" to "Review all 12 offerings"; assert at 1280 the collapsed
  list shows five and the actions sit below the cards.
- `frontend/e2e/knowledge-review-mobile.spec.ts` (mobile project): rename the
  selectors and assert the collapsed list shows three before expanding; the
  existing expand, pagination, and alignment assertions still hold.
- `onboarding-url.spec.ts` "Add offering" assertion is unchanged.

## Files touched

- `frontend/src/components/knowledge/ReviewSheet.tsx`
- `frontend/src/components/knowledge/ReviewSheet.test.tsx`
- `frontend/e2e/knowledge-review.spec.ts`
- `frontend/e2e/knowledge-review-mobile.spec.ts`

## Definition of done

- [ ] Offerings first in both modes
- [ ] Collapsed cap three below `lg`, five at `lg+`; inside-the-cap catalogs
      stay fully editable
- [ ] Actions below the cards; Review all expands in place; Add offering
      focuses the new row
- [ ] Unit and targeted e2e suites pass
- [ ] `make lint-frontend`, `make typecheck-frontend`, `make test-frontend`
      pass

## References

- RF-6 document-review workspace clarification (archived) - ordering decision
  superseded here
- `docs/agencx/design/frontend.md` (responsive and list idioms)
- `frontend/src/lib/useMediaQuery.ts` (`DESKTOP_QUERY`)

## Verification

- `make lint-frontend`, `make typecheck-frontend`, `make test-frontend`: 366
  passed (43 files)
- Targeted e2e `knowledge-review.spec.ts`, `knowledge-review-mobile.spec.ts`,
  `onboarding-url.spec.ts`: 13 passed
