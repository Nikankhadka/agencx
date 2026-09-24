# 21: Category management and multi-category offerings

**Status:** Active - todo. Not scheduled. Written 2026-09-24 from the
founder's category audit; no code changed.
**Phase 1 area:** Offerings, storefront, and catalog.

Numbering note: 17 is reserved for the M-7 storefront redesign, 18 was
absorbed into [12-refinement.md](12-refinement.md), 19 is intent and
identity, and 20 is required services, so 21 is the next free ticket.

## Summary

An offering carries one category, and the owner types that category as free
text. Two consequences follow:

- One concept enters the catalog under many spellings, and near-duplicate
  categories accumulate.
- One offering cannot sit on two shelves. Coffee filed under
  "breakfast / drinks" and Coke filed under "drinks" produce two unrelated
  categories, and the storefront shows two fragmented sections.

The industry separates what an item is from how customers browse it: one
canonical placement per item plus many-to-many browse membership, or a
primary category plus collections or tags. Every platform researched lands on
the same shape, summarized in [Industry standard](#industry-standard-research-2026-09-24).

Two phases are proposed. Phase A adds vocabulary control to the existing
input with no schema change. Phase B adds a membership join table so one
offering can appear in several categories with one primary. Nothing is
locked: the founder schedules this ticket, picks the phases, and answers the
open questions.

## Why

The founder found the failure while auditing the catalog:

- Adding Coffee with the category "breakfast / drinks" creates a category
  keyed `breakfast drinks`. Adding Coke with "drinks" creates a second
  category keyed `drinks`. The two rows never meet.
- The customer sees two sections, one named after a slash-separated phrase
  and one named Drinks, and Coffee sits on the wrong one.
- The owner cannot fix it by renaming: rename rewrites one label, and delete
  clears its offerings to Uncategorized. There is no merge.

The same structure blocks correct behavior without a typo: a business that
wants Coffee under both Breakfast and Drinks has no way to express it. The
model suggestion path
([service.py:35](../../../../backend/app/features/business/service.py#L35))
returns one label, so it cannot express it either.

The repo's own research anticipated the fix.
[The category discussion](../../research/owner-input-and-conversational-agent-architecture.md#L372)
warrants a tenant-scoped category table with a stable foreign key, "plus a
join table if membership becomes many-to-many". Membership is now the open
need.

## Current behavior

### Data model

[offering_categories](../../../../backend/migrations/0031_offering_categories.sql#L5)
holds one row per distinct label per tenant, unique on
`(tenant_id, normalized_key)`
([migration 0031:13](../../../../backend/migrations/0031_offering_categories.sql#L13)).
Each offering carries one label, `offerings.category` (legacy) and
`offerings.category_id`
([migration 0031:19](../../../../backend/migrations/0031_offering_categories.sql#L19)).
The backfill maps each offering to one category row through its legacy label
([migration 0031:28](../../../../backend/migrations/0031_offering_categories.sql#L28)).

### Write path

`_ensure_category`
([service.py:58](../../../../backend/app/features/business/service.py#L58))
creates a category row from any non-empty label the caller supplies. The key
comes from
[normalize_name](../../../../backend/app/features/business/offering_candidates.py#L21):
Unicode NFKC, casefold, punctuation to space, whitespace collapsed. That
catches "Drinks" against "drinks" and "Drinks!"; it does not know that
"breakfast / drinks" names two concepts, so the slash and both words key into
one label.

Rename rewrites the row and the label copies on its offerings
([service.py:100](../../../../backend/app/features/business/service.py#L100)).
Delete clears the offerings to null, which reads as Uncategorized
([service.py:124](../../../../backend/app/features/business/service.py#L124)).
Neither operation merges.

### Model suggestions

The extraction path calls
[suggest a category](../../../../backend/app/features/business/service.py#L256)
only in production, and it returns one short label while preferring existing
categories. One string in, one string out: no two memberships.

### Owner console

The category field is a free-text input under "Add details"
([OfferingsList.tsx:453](../../../../frontend/src/app/(tenant-admin)/(console)/business/components/OfferingsList.tsx#L453)).
The list groups by the resolved label, sorted A-Z with Uncategorized last
([OfferingsList.tsx:35](../../../../frontend/src/app/(tenant-admin)/(console)/business/components/OfferingsList.tsx#L35)).
Rename and Delete render only for a group a category row owns. There is no
combobox, no suggestion list, and no warning when a typed label nearly
matches an existing one.

### Storefront

[sectionsOf](../../../../frontend/src/app/[slug]/Offerings.tsx#L14) derives
sections from the distinct category values on the offerings. One category or
fewer collapses to a single "What we offer" section; null falls into "More"
when several categories exist. More than one category renders the browse nav,
mobile chips, and desktop sidebar
([Offerings.tsx:129](../../../../frontend/src/app/[slug]/Offerings.tsx#L129)).
Every section filters the same flat list, so an offering appears in one
section only.

### Chat and agent context

The catalog card groups by the one label, with "Offerings" as the fallback
([CatalogCard.tsx:17](../../../../frontend/src/components/ui/CatalogCard.tsx#L17)).
The agent reads one coalesced category per offering in its context
([context_package.py:148](../../../../backend/app/services/context_package.py#L148))
and renders it as `name (category: X)`
([context_package.py:226](../../../../backend/app/services/context_package.py#L226)).

## Industry standard (research, 2026-09-24)

| Platform | What the item is (one) | How customers browse it (many) |
|---|---|---|
| Square | Identity stays single; the old single `category_id` field is deprecated in favor of a list | `CatalogItem.categories[]`: one item in several categories, each with a position; categories can nest through `parent_category` ([categorize items](https://developer.squareup.com/docs/catalog-api/categorize-catalog-items), [CatalogItem](https://developer.squareup.com/reference/square/objects/CatalogItem)) |
| Shopify | One product category from the Standard Taxonomy, which drives tax and attributes | Collections carry the browse grouping; manual picks and conditions combine in the 2026-07 [composable collections model](https://shopify.dev/docs/apps/build/product-merchandising/products-and-collections/use-new-collections-model) ([product category help](https://help.shopify.com/en/manual/products/details/product-category)) |
| WooCommerce | One primary category per product, used for breadcrumbs and canonical URLs | Flat [tags](https://woocommerce.com/document/managing-product-taxonomies/) for cross-cutting traits; guidance keeps 5-15 categories with 5-8 products each, 2-3 levels deep at most |
| Uber Eats | The item is canonical once | Menu > Category > Item; a category is a menu section, and an item joins it per menu ([menu integration](https://developer.uber.com/docs/eats/guides/menu-integration)) |
| DoorDash | The POS menu is the source of truth | Categories and items sort by `sort_id`; deactivating a category applies everywhere it is attached ([menu setup](https://developer.doordash.com/en-US/docs/marketplace/faq/menu_setup_content/)) |
| Catalog hygiene | Controlled vocabulary at submission, never free text | Normalization for messy imports ([SANTA](https://ar5iv.labs.arxiv.org/html/2106.09493)) and taxonomy mapping ([Topsort](https://docs.topsort.com/en/knowledge-base/ad-platform/catalog-management/catalog-one)); the [controlled-vocabulary pattern](https://auditbuffet.com/patterns/ab-001025) names this exact failure mode |

The consensus separates classification from browse. An item gets one
canonical placement plus membership in any number of browse groups, and free
text with separators such as "a / b" is the failure mode every source writes
against. At Agencx scale, the Square shape is the smallest fit: tenant-owned
category rows plus a membership list with one primary.

## Current vs proposed behavior (conventions 5.1)

| | Current | Proposed phase A | Proposed phase B |
|---|---|---|---|
| Category input | free text, creates on save | combobox over existing categories, explicit create for a new one | as phase A |
| Separators | accepted silently, keyed as one label | questioned: reject or offer a split | as phase A |
| Memberships | one per offering | one per offering | many per offering, one primary |
| Storefront sections | an offering reaches one section | unchanged | an offering reaches each joined category, once per shelf |
| Agent context | one coalesced category | unchanged | every membership, primary first |
| Rename and delete | rename rewrites, delete clears | unchanged | unchanged, merge becomes possible later |

### Phase A: controlled vocabulary input

- The category field becomes a combobox fed by
  `GET /api/business/offering-categories`, with free typing allowed and an
  explicit "Create category X" step before a new row is written.
- A label containing `/`, `,`, `;`, or `&` inside one entry is questioned.
  The owner either picks an existing category or confirms a split into two.
- Inline guidance states the target shape: a handful of categories, each
  holding several offerings; merge thin shelves instead of growing the list.

No schema change. The write path, rename, and delete keep working.

### Phase B: multi-category membership

- New join table, for example
  `offering_category_memberships(tenant_id, offering_id, category_id,
  position, is_primary)`, backfilled from `offerings.category_id`.
- `offerings.category` and `offerings.category_id` stay as the compatibility
  read during the migration window, the pattern D28 used for the legacy label
  ([decisions.md:826](../../design/decisions.md#L826)).
- Storefront `sectionsOf` dedupes by offering id, so Coffee renders under
  Breakfast and Drinks once each; the browse nav gains a section per
  membership; the primary drives the owner preview line and the canonical
  label elsewhere.
- Agent context lists every membership with the primary first.
- RLS follows migration 0031: tenant isolation policy, platform-admin read,
  service read.

Constraints that bind either phase:

- Categories stay tenant-owned rows. No vertical taxonomy enters the code
  (architecture I8), and no category carries a monetary value (the
  deterministic-pricing hard rule).
- The owner console stays show-back, so the preview cannot disagree with the
  storefront.

## Open questions (founder decisions pending)

1. Phase A alone, or A and B together?
2. Separators: reject the save, offer a two-category split, or warn only?
3. Primary category: chosen by the owner, or the first membership wins?
4. Do model-suggested categories write memberships, or prime the owner's
   choice only?
5. Category guardrails: adopt the WooCommerce-style guidance (5-15
   categories, several offerings each), or leave the count to the owner?
6. Storefront with multi-membership: show the offering on every shelf it
   joins, the industry norm, or pin it to the primary only?

## Acceptance criteria (draft; final once the founder picks phases)

Phase A:

- [ ] The category field lists existing categories while typing.
- [ ] Creating a new category requires an explicit confirmation step.
- [ ] A separator inside one label is caught before save.
- [ ] Backend and frontend tests cover the three cases above.
- [ ] `make check` green.

Phase B:

- [ ] A migration adds the join table, backfills from `category_id`, and
      keeps the legacy columns readable.
- [ ] The offerings API returns the membership list with one primary.
- [ ] The storefront renders an offering under each category once.
- [ ] The agent context lists every membership.
- [ ] RLS and isolation tests cover the new table.
- [ ] `make check` green.

## References

Internal:

- [Category versus offering](../../research/owner-input-and-conversational-agent-architecture.md#L227)
  and [the category-table warrant](../../research/owner-input-and-conversational-agent-architecture.md#L372)
  in the offering normalization research.
- [D28](../../design/decisions.md#L826) - the decision that introduced
  stable category IDs with a compatibility label.
- [migration 0031](../../../../backend/migrations/0031_offering_categories.sql)
  and [business/service.py](../../../../backend/app/features/business/service.py).
- [OfferingsList.tsx](../../../../frontend/src/app/(tenant-admin)/(console)/business/components/OfferingsList.tsx),
  [Offerings.tsx](../../../../frontend/src/app/[slug]/Offerings.tsx),
  [CatalogCard.tsx](../../../../frontend/src/components/ui/CatalogCard.tsx).
- [context_package.py](../../../../backend/app/services/context_package.py).

External: the platform documentation linked in the industry table above.

When a direction is locked, record it as ADR D31, the next free decision
number ([decisions.md:889](../../design/decisions.md#L889)), and update
[design/database.md](../../design/database.md) section 5 and
[design/api-contract.md](../../design/api-contract.md) with the schema and
payload changes.

## Definition of done

Draft, to be finalized with the phase choice:

- The chosen phases are built as scoped, with no unrequested extras.
- Categories remain tenant-owned; no vertical taxonomy enters the code.
- No category carries money; the pricing engine and the money guardrail are
  untouched.
- Tests cover the changed surfaces, `make check` is green, and the storefront
  e2e spec follows any section change.
- The ADR, [design/database.md](../../design/database.md),
  [design/api-contract.md](../../design/api-contract.md), and
  [progress.md](../../progress.md) reflect what shipped.
