# 12 (RF-7): Business page composition and contextual owner editing

**Status:** Done - merged in `10c506f7040077900ee06dad487227973396403a` on 2026-10-03.
**Phase 1 area:** Refinement.

Delivered: the public business page is browse-first (cover, identity,
category-grouped offerings, price summaries, links) with clearly labeled chat
access, and the matching signed-in tenant owner reaches the same field editors
from contextual shortcuts on that page. One editor per field kind, two entry
points, explicit Save and Cancel; the owner markup is gated server-side.

## Agreed behavior

Browse-first Business page (cover, identity, category-grouped offerings, price
summaries, links) with clearly labeled chat access, plus contextual owner edit
shortcuts that open the same editors as the Business hub - one editor per field
kind, two entry points, explicit Save and Cancel. Offering card (image, name,
category, price or wording, one line); price summary shows deterministic figures
only, formatted from cents by `src/lib/money.ts`.

## Ticket detail

- **Visible outcome:** The public business page is browse-first (cover,
  identity, category-grouped offerings, price summaries, links) with clearly
  labeled chat access, and the owner reaches the same field editors from
  contextual shortcuts on that page.
- **Current vs proposed:** Current: the browse-first business page and
  storefront ship (M-4, M-7); no contextual owner edit shortcuts exist. The
  storefront price label already routes through `src/lib/money.ts` -
  `frontend/src/app/[slug]/Offerings.tsx:62-64` delegates to `formatCents` -
  so the earlier `priceLabel` arithmetic claim is satisfied and the remaining
  work is the owner-gated shortcuts. Proposed: add contextual shortcuts that
  open the RF-2 editors, keep one editor per field kind and two entry points,
  and gate the owner markup server-side so customers and anonymous visitors
  never receive it.
- **Design reference:** `agencx-prototype-v6.html` `.edit-btn` (the circular
  pencil idiom) and the `.set-field-row` / `.set-edit` settings-row idiom;
  the archived v5 storefront is the accepted structure record. Shipped public
  route: `frontend/src/app/[slug]/Storefront.tsx`, `StorefrontHero.tsx`,
  `Offerings.tsx`. The shortcuts reuse the RF-2 editors, imported from the
  console owner screen at
  `frontend/src/app/(tenant-admin)/(console)/business/details/components/`
  (`ProfileFieldSheet.tsx`, `ContactSheet.tsx`); that is the reused-editor
  path, not `business/page/components/`.
- **Dependencies:** RF-1 and RF-2.
- **API/DB changes:** None. The existing authenticated
  `PATCH /api/business/profile` (RF-2) is the save path, and the price item is
  already satisfied.
- **Decisions (founder-ruled 2026-10-03):**
  - Shortcut fields are **name, hours, description, contact**. There is no
    separate public-address shortcut; the address lives inside the free-text
    `business_contact` value.
  - Owner detection is **server-side**: `resolveViewerSlug` in
    `frontend/src/lib/tenant.ts` reads the Supabase session cookie (pinned
    cookie name `sb-<host>-auth-token`, `SUPABASE_INTERNAL_URL || supabaseUrl`)
    and calls `GET /api/tenants/me`; `frontend/src/app/[slug]/page.tsx:82`
    compares its slug to the page slug with `isStorefrontOwner` and passes
    `canEdit` down to `Storefront`.
  - `description` and `contact` are not published by the storefront
    (`lib/tenant.ts`; `read_public_storefront` at
    `backend/app/features/business/service.py` returns neither), so their
    shortcuts are **owner-only**.
- **Acceptance scenarios:** A contextual shortcut opens the field's editor with
  the current value, Save updates the page and customer answers, and Cancel
  changes nothing; the storefront renders the same price as the owner editor;
  the owner markup appears only for the matching signed-in tenant owner.
- **Regression checks:** The storefront tests, the `money.ts` contract tests,
  and the deterministic-pricing tests stay green. Anonymous and customer HTML
  (any viewer other than the matching owner) contains no owner controls and no
  contact value.
- **OPEN:** Resolved. The founder ruled on the shortcut fields and the
  server-side owner detection on 2026-10-03 (see Decisions above); nothing
  remains open.

## Verification

- `make lint-frontend` - passed (`check:tokens: OK`).
- `make typecheck-frontend` - passed.
- `make test-frontend` - passed: 36 files / 323 tests.
- Targeted E2E - passed: `rf-7` plus `storefront`, `storefront-mobile`, and
  `business-details-rf2`, 32 passed.
- Full `make test-e2e` - passed: 186 passed, zero flaky.
- CI run 37088488040 - all green (backend, frontend, api-types, infra,
  security, e2e, eval-gate, Vercel).
- Independent reviewer pass; findings fixed in `ff88d47` (profile-load gating,
  `resolveViewerSlug` robustness, non-owner-tenant E2E, edit-btn geometry
  Exceptions entry, ticket path corrections); accepted follow-ups: promoting
  the shared editors out of the console route group, `owner.ts` extraction,
  static `ProfileFieldSheet.test.tsx`.
