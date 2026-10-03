# 12 (RF-9): Offering and price-summary card alignment

**Status:** Done - merged in `86de712cd672597b3c6d8822e46da2de3a07ed2d` on 2026-10-03.
**Phase 1 area:** Refinement.

Delivered: the offering (`CatalogCard`), price-summary (`PriceSummaryCard`),
and quote (`QuoteCard`) cards in the customer thread share one width and one
chrome, so they left-align in one column as a single visual family.

## Agreed behavior

Offering and price-summary cards align on one width and chrome. The offering
card and the price-summary card share one width and chrome so they read as one
family.

## Ticket detail

- **Visible outcome:** The offering card and the price-summary card share one
  width and chrome so they read as one family.
- **Current vs proposed:** Current: grouping logic is already correct in
  `CatalogCard.tsx`; the only mismatch was width and chrome -
  `PriceSummaryCard.tsx` and `QuoteCard.tsx` used `max-w-[420px]`, while
  `CatalogCard.tsx` used `max-w-[520px]`. Proposed: pick one width and one
  chrome and apply it to all three cards.
- **Design reference:** Shipped `frontend/src/components/ui/CatalogCard.tsx`,
  `PriceSummaryCard.tsx`, and `QuoteCard.tsx`; `design/frontend.md` section 6
  `QuoteCard`.
- **Dependencies:** RF-1, RF-4, and RF-7.
- **API/DB changes:** None.
- **Decisions:** the canonical chat-card width is 520px (2026-10-03).
  `design/frontend.md` section 4.7 already accepts `max-w-[520px]`,
  `CatalogCard` already used it, and `w-full` means the cap never overflows a
  narrower viewport, so `PriceSummaryCard` and `QuoteCard` moved from 420px to
  520px. The quote card's header (`h3 text-body font-semibold text-text`) now
  matches the other two, and it gained `aria-label="Quote"` for parity; the
  status badge is unchanged.
- **Acceptance scenarios:** The offering, price-summary, and quote cards
  left-align in one column at the same width and share padding, radius, and
  header treatment.
- **Regression checks:** `CatalogCard.test.tsx` and `PriceSummaryCard.test.tsx`
  stay green; a visual check at 360px and 1024px.
- **OPEN:** Resolved. No open product questions remained; the canonical width
  was ruled 520px (see Decisions above).

## Verification

- `make lint-frontend` - passed (`check:tokens: OK`).
- `make typecheck-frontend` - passed.
- `make test-frontend` - passed: 39 files / 337 tests.
- Targeted E2E - passed: `rf-9-card-alignment` plus `storefront`,
  `rf-8-desktop-chat-panel`, and `typing-indicator`, 33 passed.
- Full `make test-e2e` - passed: 197 passed, zero flaky.
- CI on PR #70 - all green (backend, frontend, api-types, infra, security,
  e2e, eval-gate, Vercel).
- Independent reviewer pass: SHIP; findings fixed - the 520px ruling was
  recorded on the ticket before merge and the E2E rejects a zero-width card.
