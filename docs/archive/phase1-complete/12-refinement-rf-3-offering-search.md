# 12 (RF-3): Offering search and category grouping

**Status:** Done - merged in `486156c` on 2026-10-02.
**Phase 1 area:** Refinement.

Delivered: search over the owner offerings editor and the storefront catalog,
with the shipped category grouping left intact.

## Agreed behavior

Searchable, category-grouped offerings; equal prices never merge distinct
offerings. The owner editor and the storefront filter the loaded catalog by a
case-insensitive substring match over name, description, and category names.

Shipped: an optional `search` query parameter on `GET /api/business/offerings`
and the storefront catalog read, matching name, description, and category names
(including `offering_category_memberships`) with a literal
`position(lower(needle) in lower(...))` predicate. Because it is a literal
substring, `%` and `_` match nothing. The read stays tenant-scoped via
`o.tenant_id = $1`. Both frontend surfaces share one predicate in
`src/lib/offering-search.ts` (`offeringMatches`/`filterOfferings`) so they
agree. Category grouping, already shipped in `CatalogCard.tsx` and migration
`0034`, is untouched. The ticket's `OPEN` line resolved to matching name,
description, and category.

## Ticket detail

- **Visible outcome:** The owner searches offerings and sees them grouped by
  category; two distinct offerings that happen to share a price never merge
  into one row.
- **Current vs proposed:** Current: category grouping ships in `CatalogCard.tsx`
  and migration `0034`; the owner offerings editor and the storefront render
  groups, but no offering search exists. Proposed: add search to the owner
  offerings editor and the storefront catalog, and assert that equal-priced
  distinct offerings stay distinct.
- **Design reference:** Shipped storefront
  `frontend/src/app/[slug]/Offerings.tsx` (`sectionsOf`) and
  `frontend/src/components/ui/CatalogCard.tsx`; owner editor
  `frontend/src/app/(tenant-admin)/(console)/business/components/OfferingsList.tsx`;
  category model in `backend/migrations/0034_offering_category_memberships.sql`.
  v6 has no offerings screen; use its `.chat-row` list grammar with
  `openChatsSearch()` / `filterChats()` for the search bar.
- **Dependencies:** RF-1.
- **API/DB changes:** Add a `search` query parameter to
  `GET /api/business/offerings` and the storefront catalog read; no schema
  change (category memberships already exist).
- **Acceptance scenarios:** Typing a partial offering name filters the list; a
  price-shared pair shows as two rows; clearing the search restores every
  group; a category with one member still renders.
- **Regression checks:** The grouping tests in `CatalogCard.test.tsx` and
  `Offerings.test.tsx` stay green; storefront grouping at 6 and 7 or more
  offerings.
- **Resolved:** search matches name, description, and category
  (case-insensitive substring), the same full-row match the prototype's
  `filterChats()` uses.

## Verification

- `pytest tests/test_business_api.py` - 50 passed (3 new search tests).
- `npx vitest run` - 285 passed, including the new
  `offering-search.test.ts` and the equal-price-pair and one-member-category
  grouping tests.
- `make lint` - passed.
- `make typecheck` - passed.
- `make test` - 1241 backend + 285 frontend passed.
- `make build` - passed.
- Targeted E2E (`offering-search`, `storefront`, `storefront-mobile`,
  `business-hub`) - 32 passed.
- Full `make test-e2e` - 169 passed, 1 failed.

## Known unrelated failure

`chats-takeover` timed out because its freshly created conversation arrived
`escalated` (terminal) rather than `open`. Proven not caused by RF-3 by stashing
the RF-3 backend files and re-running, which produced the same failure. Treated
as an environment/provider flake and recorded as a separate open item, not an
RF-3 defect.

## Note

The new storefront search input needed `min-h-11` to satisfy the 44px mobile
tap-target check.
