# 26: Business page actions

**Status:** Active - in progress on `feat/26-business-page-actions`.
**Phase 1 area:** Tenant console, Business page.

Numbering note: 23 through 28 are the 2026-10 storefront and console
refinement batch; this is the fourth ticket in it.

## Design reference

The Business page render
(`frontend/src/app/(tenant-admin)/(console)/business/page/page.tsx`),
`ServicesOverview` (`frontend/src/components/ui/ServicesOverview.tsx`),
`ServicesSheet`
(`frontend/src/app/(tenant-admin)/(console)/business/details/components/ServicesSheet.tsx`),
and `OfferingSuggestions`
(`frontend/src/components/knowledge/OfferingSuggestions.tsx`); prototype
`renderScreen('booking')` in `design/prototypes/agencx-prototype-v6.html`.

## Summary

The Business page gains two owner actions. While the offerings catalog is
empty, the gray What-we-offer overview gets an Edit affordance that opens the
existing services sheet; saving PATCHes the profile and refetches the page.
Whenever pending offering candidates exist, the page shows the same review
card Home uses. The public storefront gains nothing: `ServicesOverview`
renders owner markup only when it is given an `onEdit` handler, and only this
console page passes one.

## Why

The preview is where the owner sees the page as a customer will. Discovering
here that the services block is wrong and having to leave for Business
details is a dead end the owner hits exactly when they notice the problem.
Separately, pending offering candidates are reviewable from Home and from
What you offer but not from the page those offerings will appear on.

## Current vs proposed behavior

| | Current | Proposed |
|---|---|---|
| Services overview (empty catalog) | Read-only gray block, no actions | Header gains Edit, opening "Edit services" |
| Saving services from here | Only from Business > Details | PATCH `/api/business/profile`, then refetch `/api/business/page` |
| Pending candidates | Home card and What you offer section only | Also a card on the Business page whenever the count is above zero |
| Public storefront | No owner markup | Unchanged - `onEdit` is optional and only the console passes it |
| Catalog non-empty | Offerings summary with its Manage link | Unchanged |

## Locked decisions

1. The services overview stays the read-back of the owner's own words: no
   parsing, no quoting, and no conversion into offerings. Ticket 20's
   services/offerings split holds.
2. Edit only. No confirm or acknowledge state is introduced for the overview.
3. The candidate entry reuses the existing `OfferingSuggestions` card and its
   existing endpoints. It shows whenever pending candidates exist,
   independent of catalog state, and renders nothing at zero.
4. Owner actions are console-only. The public storefront and the owner-gated
   storefront preview gain none.

## User stories

### US-1 Fix the services overview where it is noticed

**As** Sam previewing my business page with no priced catalog,
**I want** an Edit action on the What-we-offer block,
**so that** I can correct my own words without leaving the preview.

- [ ] With the catalog empty, the gray block header shows Edit
- [ ] Edit opens the existing "Edit services" sheet with the saved list
- [ ] Save PATCHes the profile, closes the sheet, and the page refetches so
      the new text renders in place
- [ ] A failed save surfaces the calm error inside the sheet and keeps the
      editor open
- [ ] A customer's storefront DOM contains no Edit action

### US-2 Review pending candidates from the page they will appear on

**As** Sam with extracted offerings waiting,
**I want** the review card on the Business page,
**so that** Home is not the only entry point.

- [ ] With pending candidates, the same card Home shows appears on the page
      ("N offerings waiting for review")
- [ ] Review opens "Suggestions to review" with the existing private-drafts
      copy
- [ ] With no pending candidates the card renders nothing
- [ ] The card shows whether or not the catalog has offerings

## Technical spec

- `ServicesOverview`: add optional `onEdit?: () => void`. When present, the
  header row (`flex items-center justify-between gap-3`) renders an Edit text
  action (`data-testid="services-overview-edit"`, the `text-chip` accent
  idiom). When absent, the rendered markup is unchanged.
- `business/page/page.tsx`: add profile/edit/busy/error state and `useConfirm`
  exactly as Business details does; fetch `/api/business/profile` on mount
  beside `/api/business/page`; pass `onEdit` only once the profile has loaded;
  render `ServicesSheet` with the same save path (`PATCH
  /api/business/profile`, then `load()`), and `{confirmDialog}` at page level.
- Mount `<OfferingSuggestions variant="card" />` above the What-we-offer
  block. It self-fetches and renders null at zero.
- No API or DB change. Endpoints reused: GET/PATCH `/api/business/profile`,
  GET `/api/business/page`, GET/PUT `/api/onboarding/suggestions`.

## Tests

- New `ServicesOverview.test.tsx`: without `onEdit` no
  `services-overview-edit` renders; with it the action renders; empty
  services still returns null.
- New `frontend/e2e/business-page-actions.spec.ts` at 1280 with mocked
  endpoints:
  1. Empty catalog and services: Edit opens the sheet, changing the line and
     saving PATCHes the profile, the page GET is requested again, and the new
     text shows.
  2. Pending candidates with a non-empty catalog: the card shows and Review
     opens the suggestions sheet with the private-drafts line.
- Regression re-run: `business-hub`, `storefront`, `rf-7-business-page-shortcuts`,
  `business-details-rf2`.

## Files touched

- `frontend/src/components/ui/ServicesOverview.tsx`
- `frontend/src/components/ui/ServicesOverview.test.tsx` (new)
- `frontend/src/app/(tenant-admin)/(console)/business/page/page.tsx`
- `frontend/e2e/business-page-actions.spec.ts` (new)

## Definition of done

- [ ] Services Edit opens the reused sheet, saves, and refetches the page
- [ ] The candidate card shows whenever pending candidates exist
- [ ] Customer storefront markup is byte-identical without `onEdit`
- [ ] Unit, lint, typecheck, and the targeted e2e specs pass

## References

- Ticket 20 required services and the services/offerings split (archived)
- RF-2 business-detail editing (archived) - the profile save path reused here
- `frontend/src/components/knowledge/OfferingSuggestions.tsx` - the existing
  review entry and endpoints
