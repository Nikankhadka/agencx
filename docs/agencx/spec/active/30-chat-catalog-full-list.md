# 30: Chat catalog for large menus

**Status:** Active - todo.
**Phase 1 area:** Customer chat, storefront catalog.

Depends on ticket 29 Slice C, which carries `pricing_wording` in the
`show_catalog` payload and in `recommend_items`. Branch
`feat/30-chat-catalog-full-list` off `development` after 29 merges.

## Intent

A full-list request against a 96-item menu must not render 96 chat rows. Small
catalogs read in full; large ones stay bounded and hand off to the business
page.

## Locked decisions

| # | Decision |
|---|---|
| 1 | Catalog card shows all offerings when the total is 20 or fewer |
| 2 | Above 20: 5 rows per category, `+N more`, and `View all N offerings` linking to `/{slug}#offerings` in a new tab |
| 3 | The storefront catalog gains an `#offerings` anchor |
| 4 | Prompt: a full-list request calls `show_catalog`; the catalog is never repeated in prose; a bounded card points to the business page |
| 5 | `pricing_wording` rides the catalog card payload |
| 6 | 200 offerings never render as 200 chat rows |

## Current behaviour this changes (verified in the planner pass; re-verify at build)

| Today | Where | Change |
|---|---|---|
| `CATALOG_CARD_ROWS_PER_CATEGORY = 5` caps every payload | `frontend/src/components/ui/CatalogCard.tsx:24,49-69` | <= 20 renders all; > 20 keeps the cap |
| No `#offerings` anchor | `frontend/src/app/[slug]/Offerings.tsx:297` | Add `id="offerings"` |
| No page link on the card | `CatalogCard.tsx` | `View all N offerings`, new tab |
| Catalog guidance says nothing about full-list requests | `backend/app/agents/agent_node.py:83,115` | One guidance line |
| `pricing_wording` is rendered when present | `CatalogCard.tsx:12,56` | Wire it through the payload (ticket 29 Slice C) |

## Acceptance criteria

| # | Scenario | Passes when |
|---|---|---|
| 1 | Full-list chat request, 14 offerings | All 14 render, no `+N more`, no link |
| 2 | Full-list chat request, 96 offerings | Bounded rows, `+N more` per category, one `View all 96 offerings` link to `/{slug}#offerings` opening in a new tab |
| 3 | The link lands | `/{slug}#offerings` scrolls to the storefront catalog region |
| 4 | A 200-offering payload | The card renders no more than 5 rows per category |
| 5 | Wording-only offering | The card renders the owner's wording verbatim where a price would sit |

## Technical contract

- `CatalogCard` takes `slug: string` as a prop, threaded from `CustomerChat`
  through `StructuredResponse`. It stays out of the payload so a restored card
  (`lib/chat-restore.ts`) still resolves.
- `total` is the payload's offering count.
  - `total <= 20` -> render every offering in its category order, no `+N more`,
    no link.
  - `total > 20` -> keep `CATALOG_CARD_ROWS_PER_CATEGORY = 5`, the existing
    `+N more` line, and add one `View all {total} offerings` link:
    `href={/${slug}#offerings}`, `target="_blank"`, `rel="noreferrer"`.
- `Offerings.tsx` catalog region gains `id="offerings"` beside its existing
  `data-testid`. A word anchor - `check:tokens` flags hex-shaped anchors.
- Guidance in `agent_node.py`: for a full-list request, call `show_catalog`; do
  not repeat the catalog in prose; when the card is bounded, point to the
  business page.
- No backend route, no migration, no payload shape change beyond ticket 29's
  `pricing_wording`.

## Test seams

- `frontend/src/components/ui/CatalogCard.test.tsx` - 14 renders 14 rows with no
  link; 96 renders bounded rows plus a link whose `href` ends in `#offerings` and
  carries `target="_blank"`; 200 renders at most 5 rows per category; a
  wording-only offering renders the wording and no formatted amount.
- `frontend/src/app/[slug]/Offerings.test.tsx` - the `#offerings` anchor exists.
- `frontend/e2e/chat-catalog-large.spec.ts` (new) - a mocked `POST /api/chat`
  turn emitting a 96-offering `catalog` event shows the bounded card; the link
  opens `/{slug}#offerings`.
- `backend/tests/test_recommendation_agent.py` - the `show_catalog` payload
  carries `pricing_wording` (asserted again here if ticket 29 did not pin it).

**Verify**

```
docker compose run --rm --no-deps frontend npx vitest run src/components/ui/CatalogCard.test.tsx
docker compose run --rm --no-deps frontend npx vitest run "src/app/[slug]"
make test-e2e
```

## Out of scope

- Virtualised or paginated chat lists.
- Per-category deep links.
- Rendering a 200-row catalog in chat.

## Definition of done

- Two commits if the frontend and the prompt land separately; otherwise one.
- The five acceptance scenarios demonstrated, with the catalog card unit tests
  and the new E2E green.
- `docs/agencx/design/frontend.md` updated for the card's 20-offering boundary
  and the page link.
- ADR added to `docs/agencx/design/decisions.md` for the catalog page link and
  the 20-offering boundary, numbered after ticket 29's.
- `docs/agencx/progress.md` row for 30, and `docs/agencx/spec/README.md` active
  row.

## Blockers

- Ticket 29 Slice C must land first for `pricing_wording` in the payload.
