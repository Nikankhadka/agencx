# 12 (RF-4): Explicit pricing wording across editing, publication, and customer display

**Status:** Done - merged in `d6e3552` on 2026-10-02.
**Phase 1 area:** Refinement.

Delivered: an offering can carry either a fixed price (numeric, calculable) or
owner-confirmed pricing wording (display text such as "from $12 a head");
wording is display-only and never becomes a calculable amount on either
surface.

## Agreed behavior

Fixed price (numeric, calculable) versus pricing wording (owner-confirmed
display text such as "from $12 a head"); wording is display-only and never
treated as a calculable amount on either surface.

## Shipped

- Migration `0036_offering_pricing_wording.sql` adds nullable
  `offerings.pricing_wording text`. It is additive: the existing `FORCE ROW
  LEVEL SECURITY` and the `tenant_isolation` policy are unchanged.
- `pricing_wording` is exposed on create, update, and read, on the owner API
  and the public storefront catalog read (`OfferingCreate`, `OfferingUpdate`,
  `OfferingResponse`, `PublicOffering`, and `BookingPageOffering`).
- Price and pricing wording are mutually exclusive. Create rejects a request
  that sets both; update setting one clears the other; a patch that sets both
  at once is refused with a readable validation error. If legacy or direct data
  ever carries both, `price_cents` is authoritative and the wording is ignored,
  so wording is never calculable anywhere.
- Wording is trimmed, blank normalizes to none, and a 120-character cap
  (`PRICING_WORDING_MAX`) is enforced with a readable error.
- `priceLabel` in `frontend/src/app/[slug]/Offerings.tsx` now delegates to
  `formatCents` in `src/lib/money.ts`, removing the inline arithmetic.
- Wording renders as plain display text on the storefront row and detail sheet
  and in `CatalogCard`; priced offerings still format from cents through
  `money.ts`.

## Hard-rule proof

`pricing_wording` appears nowhere under `backend/app/pricing/`. The engine's
item read selects `price_cents` and nothing else, so wording is structurally
absent from the calculable path.
`test_rf4_pricing_wording_is_never_calculable` in
`backend/tests/test_pricing_engine.py` shows a wording-only offering has no
direct price (the engine raises) and a wording-plus-price offering still
computes from cents (1200 x 2 = 2400) with `wording` absent from the serialized
line items.

## Ticket detail

- **Visible outcome:** An offering carries either a fixed price (numeric,
  calculable) or owner-confirmed pricing wording (such as "from $12 a head");
  wording is display-only and never becomes a calculable amount on either
  surface.
- **Current vs proposed:** Current: offerings carry `price_cents` only
  (`backend/app/features/business/api.py` `OfferingCreate` / `OfferingUpdate`);
  no display-only pricing wording exists anywhere. Proposed: add a
  `pricing_wording` field through the offering API, the owner editor, the
  storefront card, the detail sheet, and `CatalogCard`; the
  deterministic-pricing invariant still holds because wording never enters the
  pricing engine.
- **Design reference:** Shipped `frontend/src/app/[slug]/Offerings.tsx`
  `OfferingRow` and `Storefront.tsx` detail sheet; owner editor
  `business/components/OfferingsList.tsx`; `frontend/src/lib/money.ts`. v6
  quote lines (`openQuotePreview`) show the money-rendering idiom only.
- **Dependencies:** RF-3.
- **API/DB changes:** Add a nullable `pricing_wording text` column to
  `offerings` (migration with the implementation ticket) and expose it on
  create, update, and read.
- **Acceptance scenarios:** Save wording on an offering with no fixed price and
  see it on the storefront card and detail; the assistant never derives a total
  from wording; a priced offering still formats from cents through `money.ts`;
  wording longer than the cap is refused with a readable message.
- **Regression checks:** The deterministic-pricing tests stay green; the price
  gate rejects any model-authored amount; the storefront tests for priced and
  unpriced offerings.
- **Resolved:** price and pricing wording are mutually exclusive. The API
  rejects a request that sets both (or a non-empty price alongside wording)
  with a readable validation error, and the owner editor is an explicit mode
  choice (Fixed price / Pricing wording). If legacy or direct data ever carries
  both, `price_cents` is authoritative and the wording is ignored - wording is
  never calculable anywhere.

## Verification

- `pytest tests/test_business_api.py tests/test_pricing_engine.py tests/test_migrations.py` - 92 passed.
- `npx vitest run` - 288 passed.
- `make lint` - passed.
- `make typecheck` - passed.
- `make test` - 1247 backend + 288 frontend passed.
- `make build` - passed.
- RF-4 E2E `pricing-wording` - 2 passed.

## Known unrelated failure

The full-suite E2E runs hit pre-existing order flakes (`mobile-voice-sheet`,
`tab-shell-mobile`) that passed in isolation. Recorded as the documented flake
class, not RF-4 defects.
