# Offerings + Media (D24)

Four tickets. `M-1`, `M-2`, `M-3`, and `M-4` are built; live Cloudinary
smoke testing remains credential-dependent. See
`docs/agencx/design/decisions.md` D24 for the design reasoning (catalog/
knowledge split, Cloudinary choice, the rename question `M-1` closed) and
provenance (a Codex CLI session designed this, then hit its usage limit before
writing anything down; this phase file and D24 are the recovered record,
cross-checked against the code). Ticket id prefix `M-` (Media), unused
elsewhere in the ticket set.

Order matters: `M-1` gives Offerings real identity and closes the two
retrieval-safety gaps that become live the moment `offerings` is
owner-written - shipping it without them would ship a working feature next to
a real bug. `M-4` puts what `M-1` made writable in front of a customer, so it
follows `M-1`. `M-2` (media) only needs an offering to exist for its
per-offering visual; it is sequenced after `M-1` for one branch and one
reviewable diff. `M-3`
(import-and-confirm) writes through `M-1`'s service, so it must come last.

**`M-4` amends two of `M-1`'s ticked bullets** rather than rewriting them: the
Business page no longer renders the offerings list at all (the storefront
does, and the owner reaches it through a preview link), and the add/edit/remove
E2E moved with the editor onto `/business/offerings`, asserting the round trip
against the public page instead of the owner's own screen.

---

## M-1: Offerings become a real, owner-writable structured item

### Summary

Give `offerings` its first owner-facing writer: a service + API + a
minimal manual add/edit/remove UI on the Business hub, using the `Offering`
vocabulary D24 locked in. No images in this ticket - that's `M-2`. Bundles the
two correctness fixes that only matter once this table is actually written to
outside seeds, so the ticket ships whole rather than half-safe.

### Why

Today `offerings` is read everywhere that matters (pricing engine,
recommendation, quoting, `agent_node.py`) but has zero owner-facing writers -
only demo seeds insert rows, and the one live endpoint
(`GET /api/pricing/catalog`) is read-only. The Booking page's "Services" list
(`business/offerings.py`) routes around this entirely by deriving `{name,
price}` rows from knowledge-section text at read time, with no id, no image
field, and no way for an owner to edit or remove a row except by rewriting the
underlying document prose. That's the actual gap this ticket closes: an owner
who wants to fix a price or drop a discontinued item today cannot, without
finding the sentence it came from.

### User stories

#### US-1 An owner adds an offering by hand

As a tenant owner, I add a name, an optional description, and an optional
price to my offerings list from the Business hub, without needing to have
uploaded a document first.

- A new offering appears in the Booking page's Services section immediately.
- Price is either blank (no price shown, matching today's "no price provided"
  case) or a value I typed - never inferred, rounded, or computed.
- The list is scoped to my tenant; another tenant's offerings are never
  visible (RLS, unchanged from `offerings`'s existing policy).

#### US-2 An owner edits or removes an offering

As a tenant owner, I correct a price or name, or remove an offering that no
longer applies, and the Booking page reflects it on the next load - no
re-upload, no document edit required.

- Editing does not create a duplicate row.
- Removing an offering removes it from the Booking page and from what the
  agent can recommend, on the next cache lookup (see US-3).

#### US-3 The chat agent never answers from a stale offering

As a customer asking what's on offer, I get an answer built from the current
catalog, not a cached one from before the owner's last edit.

- Editing an `offerings` row bumps `knowledge_version`, so the context-package
  cache invalidates.
- A recommendation answer never states a price that isn't the current
  `price_cents` value for that row - unchanged behavior, `agent_node.py:195`'s
  re-fetch pattern already guarantees this and this ticket does not touch it.

#### US-4 Offering content never leaks into general knowledge answers

As a customer asking a general question ("what are your hours?"), the answer
never accidentally surfaces raw offering text pulled in through the
whole-corpus fast path.

- `whole_corpus()` (`retrieval.py:100`) excludes chunks whose
  `metadata.kind == "catalog_item"` from the fast-path corpus.
- Offering content remains reachable only through the catalog/recommendation
  tool path, which already filters on `metadata_kind="catalog_item"`
  deliberately (unchanged).
- A regression test proves a tenant with both catalog chunks and general
  knowledge chunks does not get catalog text in a fast-path answer to an
  unrelated question.

### Technical spec

- **Naming decision (must be made and recorded, not deferred again):** decide
  whether `catalog_items` keeps its physical name or gets renamed to
  `offerings` in this ticket's migration. D24 left this open on purpose.
  Record the choice and reasoning in this ticket's own section when
  implemented (append to Definition of done below, don't retroactively edit
  D24).
- **Backend writer:** new service functions (`create_offering`,
  `update_offering`, `delete_offering` or the renamed-table equivalents) in a
  module under `backend/app/features/business/` alongside `offerings.py`, or
  replacing its read path outright - `offerings.py`'s current
  knowledge-derivation logic (`_split_line`, `derive`) gets repurposed as the
  candidate-extractor for `M-3`, not deleted.
- **API:** `POST`/`PATCH`/`DELETE` under `/api/business/offerings` (or
  `/api/business/offerings/{id}`), admin-authed via
  `auth.require_tenant_admin`, following the existing cover-endpoint shape in
  `business/api.py:157-208` (validation, 204 on write, `ApiError`-compatible
  error bodies).
- **Write-time re-index:** every write calls `ingest_offerings`
  (`backend/app/ingestion/pipeline.py:96-146`) so the searchable catalog
  projection stays in sync - this is already-working code whose only caller
  today is seed scripts.
- **`knowledge_version.py:32`:** fold `offerings.updated_at` into
  `_VERSION_SQL`'s `greatest(...)` so a direct offering write invalidates the
  cache even on a future code path that doesn't go through
  `ingest_offerings`.
- **`retrieval.py:100` (`whole_corpus()`):** add a `metadata.kind !=
  'catalog_item'` filter (or equivalent) to the fast-path query.
- **Migration:** next number after `0022_drop_auth_codes.sql`, i.e.
  `0023_rename_catalog_items_to_offerings.sql`, which renames the existing
  physical table because its columns already fit `Offering`.
- **Frontend:** a minimal add/edit/remove list on the Business hub
  (`frontend/src/app/(tenant-admin)/(console)/business/`), following the
  Settings > Knowledge page's list-with-inline-actions pattern
  (`settings/knowledge/page.tsx:276-336`) rather than inventing new UI
  vocabulary. The Booking page's existing read-only render
  (`business/booking/page.tsx:156-184`) switches its data source from
  `offerings.py`'s knowledge-derived rows to the real `offerings` rows
  (via `BookingPageResponse.services`, unchanged wire shape - `{name,
  price}` - unless the naming decision above changes it).

### Tests

- Backend: create/update/delete offering (RLS-scoped, cross-tenant isolation
  proven the same way other tenant-scoped writers are); write bumps
  `knowledge_version`; `whole_corpus()` excludes catalog-kind chunks
  (regression test seeded with both kinds present); `ingest_offerings`
  called on write (or its replacement).
- Frontend: add/edit/remove flow on the Business hub; Booking page reflects a
  new/edited/removed offering; existing Booking-page E2E extended (it
  currently only tests the empty cover-photo well, per the Codex session's
  own finding - fold this fix in since the file is already being touched).

### Files touched

- `backend/app/features/business/offerings.py` (repurposed, not deleted)
- `backend/app/features/business/service.py`, `api.py` (writer + endpoints)
- `backend/app/services/knowledge_version.py`
- `backend/app/services/retrieval.py`
- `backend/migrations/0023_*.sql`
- `frontend/src/app/(tenant-admin)/(console)/business/booking/page.tsx`
- new frontend component(s) for the offerings list
- `docs/agencx/design/database.md` (schema section, if the table is renamed)

### Definition of done

- [x] Naming decision made and recorded: `catalog_items` is renamed to
      `offerings`. The existing row shape already fits the generic Offering
      noun, and a physical name aligned with the owner-facing and API vocabulary
      prevents two names for one concept. Migration `0023` preserves its RLS
      policies and grants because they follow the table's OID.
- [x] Owner can add/edit/remove an offering from the Business hub
- [x] Booking page renders from the real writer, not knowledge-derived text
- [x] A catalog edit bumps `knowledge_version`
- [x] Catalog-kind chunks excluded from `whole_corpus()`, proven by a
      regression test
- [x] `make check` green; Booking-page E2E covers add/edit/remove, not just
      the empty state

---

## M-2: Reusable business media via Cloudinary

### Summary

Replace the single-cover, Postgres-bytea `tenant_assets` table with a
Cloudinary-backed model containing one business cover and one optional visual
per offering. Visuals may be uploaded files, image URLs, or video URLs. The
catalogue also carries an optional business-agnostic category.

### Why

`tenant_assets` (`backend/migrations/0021_tenant_assets.sql`) is schema-capped
to exactly one row per tenant: `primary key (tenant_id, kind)`, `kind check
(kind in ('cover'))`. D24 keeps that focused business cover and adds one
optional visual to each offering. Cloudinary supplies the CDN and media
classification for those reusable public assets without turning the owner
page into a separate gallery editor.

### User stories

#### US-1 An owner uploads a business cover

As a tenant owner, I add or replace one cover image from the Business hub.

New uploads are signed server-side and delivered from Cloudinary when the
provider is configured; legacy Postgres covers remain readable during rollout.

#### US-2 An owner attaches a photo to a confirmed offering

As a tenant owner, after confirming an offering (`M-1`), I optionally attach
one image or video by file or URL. A short category is also optional.

- An offering with no photo displays fine - a photo is never required.
- The per-offering visual is stored and served through the same media table as
  the cover, not a separate mechanism.

#### US-3 The customer-facing page serves photos fast, without exposing tenant credentials

As a customer viewing the public Booking page, the cover and offering visuals
load via Cloudinary's CDN, and the page never has to proxy raw bytes through
the backend the way the current private cover endpoint does.

- Public delivery uses Cloudinary's own URL, not an authenticated backend
  proxy (a deliberate change from today's `GET /api/business/cover`, which
  streams bytes behind a bearer token because there was no CDN to hand a
  public URL to).
- Upload itself stays authenticated and server-signed (owner-only), never a
  client-side unsigned upload the public internet could hit.

### Technical spec

- **Schema:** replace `tenant_assets` with a `tenant_media` table (or widen
  `tenant_assets` - decide during implementation): `id uuid primary key,
  tenant_id uuid, offering_id uuid null, role text, type text, provider text,
  url text, public_id text, poster_url text, created_at, updated_at`. Partial
  unique indexes permit one cover per tenant and one offering visual per
  offering. A composite tenant/offering foreign key prevents cross-tenant
  attachments. RLS mirrors `tenant_assets`'s existing policies
  (`tenant_isolation`, `platform_admin_read`, `service_read` for the
  anonymous public page).
- **Migration:** next available number after `M-1`'s (`0024_*.sql` if `M-1`
  used `0023`).
- **Backend:** signed-upload endpoints (Cloudinary's server-signed upload
  pattern, not client-side unsigned uploads) following the existing cover
  endpoint shape in `business/api.py:157-208`; env vars for
  `CLOUDINARY_CLOUD_NAME`/`CLOUDINARY_API_KEY`/`CLOUDINARY_API_SECRET`
  documented in `.env.example` and `docs/agencx/deploy.md`.
- **`shared/storage.py`:** do not force Cloudinary through the existing
  `Storage` ABC (`put`/`get`/`delete_prefix`, byte-in/byte-out) - that
  abstraction fits opaque private document blobs, not URL/transform-centric
  public media. A separate, smaller interface for media (upload -> returns a
  servable URL + public id; delete by public id) is more honest about the
  different contract.
- **Frontend:** the owner editor keeps name required and puts category, price,
  description, and media under `Add details`. Public storefront sections are
  category-aware and render provider URLs; videos never autoplay.
- **Migration of existing data:** `python -m scripts.migrate_tenant_covers`
  uploads existing `tenant_assets` covers to Cloudinary and verifies
  source/destination counts before legacy rows are retired.

### Tests

- Backend: signed upload/import/delete, replacement rollback, provider
  classification, per-offering attach/detach, and RLS isolation.
- Frontend: cover and offering media controls, category sections, detail sheet,
  contextual chat prefill, and public Share/Copy link behavior.
- E2E: owner media save -> public catalogue render round trip.

### Files touched

- `backend/migrations/0024_*.sql` (or next available number)
- `backend/app/features/business/service.py`, `api.py` (media endpoints)
- new backend module for Cloudinary signed uploads (not `shared/storage.py`)
- `frontend/src/app/(tenant-admin)/(console)/business/` (cover and offering
  media controls)
- `.env.example`, `docs/agencx/deploy.md` (Cloudinary credentials)
- `docs/agencx/architecture.md` (Cloudinary as a listed external dependency)

### Definition of done

- [x] Cloudinary credentials documented as server-only environment variables
- [x] Owner can replace a Cloudinary-backed cover
- [x] Owner can attach/remove one visual on a confirmed offering
- [x] Public Booking page uses the Cloudinary URL when a managed asset exists;
      live delivery smoke testing requires rotated credentials
- [ ] Existing cover photo (if any) migrated, not silently dropped
- [x] Focused media/migration tests and frontend checks pass; live smoke requires rotated credentials

---

## M-3: Import-and-confirm - knowledge ingestion proposes offerings

### Summary

Extend the existing knowledge structure/review flow so that a document (PDF
upload or scraped URL) containing menu/price lines automatically proposes
candidate offerings for the owner to confirm, writing through `M-1`'s service
rather than leaving them as unstructured prose forever.

### Why

The founder's ask, directly: an owner who uploads one PDF with hours, policy,
*and* a menu should not have to separately re-type the menu into a catalog
screen, but the model must never become the source of truth on its own. D24's
resolved pattern is exactly this - reuse the existing Settings > Knowledge
review step (`ReviewSheet.tsx`) rather than inventing a second onboarding
flow, and only owner-confirmed items become real rows.

### User stories

#### US-1 A structured document with offering-shaped sections proposes candidates

As a tenant owner, after I upload or paste a document that gets structured
into sections, if any section is headed `"What we offer"` or `"Prices"`, I see
a compact list of detected candidate offerings alongside the normal
knowledge-section review - not a second questionnaire.

- Detection reuses `offering_candidates.py`'s existing line-splitting/price-slice logic
  (`_split_line`, `extract_monetary_figures`) verbatim - no new extraction
  model, no new money-handling code path.
- If nothing offering-shaped is detected, review proceeds exactly as today
  with no interruption.

#### US-2 Confirmation is one step, not a re-review of every line

As a tenant owner, I see something like "I found 12 items that look like
offerings" with items pre-selected when confidence is high (a price was
found), and I can deselect, edit a name/price, or confirm the set in one
action.

- Confirming writes through `M-1`'s offering writer - never a direct insert
  that bypasses it.
- Skipping is always available; skipping never blocks saving the rest of the
  document as ordinary knowledge.

#### US-3 Re-uploading never silently overwrites an owner's own edit

As a tenant owner, if I re-upload an updated menu after I've already edited an
offering by hand, I see the new document's version as a proposed change, not
an automatic overwrite.

- A previously-confirmed offering whose price differs from a freshly-detected
  candidate is shown as a diff, requiring a second confirm - the owner's live
  catalog value stays authoritative until they explicitly accept the change.
- An item present in the old document but missing from the new one is never
  auto-deleted.

### Technical spec

- **Detection point:** after `structure_document()` runs (existing O-3 flow,
  `knowledge/service.py`), before or alongside the section review step -
  scan structured sections for `OFFERING_HEADINGS` (`offering_candidates.py:27`) and run
  the existing `_split_line` extraction to produce candidates.
- **Review UI:** extend `ReviewSheet.tsx` (`settings/knowledge/components/`)
  with a candidates block, following its existing `SectionField` pattern
  (auto-growing text areas, per-item edit) rather than a new sheet type.
  Confidence = "has a price" vs. "name only, price unclear" (matching the
  Codex-conversation example: `✓ item - $price` vs `! item - Price unclear`).
- **Write path:** confirmed candidates call `M-1`'s
  `create_offering`/`update_offering` service functions directly - this
  ticket adds no new persistence path of its own.
- **Diffing on re-upload:** compare newly-detected candidates against existing
  `offerings` rows by name (case-folded, matching `offerings.py`'s
  existing dedupe key); a match with a different price surfaces as a proposed
  change, not an automatic write.
- **Money rule, explicitly unrelaxed:** the extraction model (if any LLM
  involvement exists in section classification) never touches the price
  value itself - only `extract_monetary_figures`'s deterministic slice does,
  exactly as it does for the read-time derivation today.

### Tests

- Backend: a document with a `"What we offer"` section produces the expected
  candidates; confirmation writes real `offerings` rows; re-upload with a
  changed price produces a diff, not a silent write; a document with no
  offering-shaped section produces zero candidates and doesn't interrupt
  normal review.
- Frontend: candidates render in the review sheet; confirm/edit/skip actions;
  diff presentation on re-upload.
- Regression: the money guardrail test matrix (`C-4`) gains cases proving a
  candidate's price is always a verbatim slice, never a re-formatted or
  computed value.

### Files touched

- `backend/app/features/business/offering_candidates.py` (candidate-extraction reused)
- `backend/app/features/knowledge/service.py` (detection hook post-structure)
- `frontend/src/app/(tenant-admin)/(console)/settings/knowledge/components/ReviewSheet.tsx`
- `frontend/src/app/(tenant-admin)/(console)/settings/knowledge/lib/types.ts`

### Definition of done

- [x] Structured document with offering-shaped sections proposes candidates in
      the existing review flow
- [x] Confirmation writes through `M-1`'s service, never a bypass insert
- [x] Re-upload diffs against existing offerings instead of overwriting
- [x] Money guardrail remains enforced; candidate prices are deterministic
- [x] `make check` green

---

## M-4: The public storefront, and the address the owner chooses

**Status: built.** Depends on `M-1`.

### Summary

Turn `/{slug}` from a bare chat window into a compact, business-agnostic
catalogue: the offerings `M-1` made writable, with the owner's prices,
optional media, categories, and the assistant one tap away rather than
occupying the whole page. Let the owner choose that address at go-live instead
of inheriting the provisional one. Re-cut the Business hub around the three
jobs this leaves.

### Why

`M-1` gave an owner somewhere to put what they sell, and nowhere for a
customer to see it. `/{slug}` rendered a chat and nothing else, so a customer
arriving from a shared link had to know what to ask before the page told them
anything - the business's own offerings, prices, and story were reachable only
by interrogating an assistant about them.

The address was the second half of the same problem. A self-onboarded tenant
got a provisional slug (`biz-` plus a fragment of its id) and no way to change
it, so the link the owner shares was never the one they would have chosen.

### User stories

#### US-1 A customer sees the business before they ask it anything

As someone who followed a shared link, I land on a page that tells me who the
business is, what it offers, and what it costs - and I can start a
conversation when I want one, not before.

- Offerings render with the owner's own price when they published one, and
  with no price at all when they did not. Nothing rounds, marks up, or invents
  a figure; the page formats integer cents and does no other arithmetic.
- The assistant opens in the existing sheet from the single top-of-page
  "Ask a question" action. The storefront has no second composer or redundant
  chat action.
- A tenant that is suspended still shows its calm unavailable state; one that
  is neither active nor suspended (`provisioning`) falls back to the bare chat
  rather than an empty page.

#### US-2 The page stays low-interaction for the owner

As an owner, I can focus on the catalogue and business rather than maintaining
an extra page-builder section.

- Legacy About data remains in `tenant_config.brand->storefront` for
  reversibility, but the owner editor and public storefront do not expose or
  render it.

#### US-3 An owner chooses their public address at go-live

As an owner finishing onboarding, the confirm step offers an address derived
from my business name, which I can edit before going live.

- The suggestion always passes the slug rule. A business name that would
  derive a reserved slug ("Settings") gets `-page` appended rather than
  failing the validator with nothing to fall back on.
- An address another tenant already holds is refused with a message that says
  so, not a 500.
- After go-live the address is fixed - changing it would break every link
  already shared.

#### US-4 The Business hub is three places, not two plus an editor

As an owner, Business holds one row per job: the page customers see, what I
offer, and my business details.

- `/settings` and `/business/booking` are gone as paths, not aliased: one
  route per screen, so the two cannot drift apart.

### Technical spec

- **Public read:** `features/business/public_api.py` -
  `GET /api/public/tenant/{slug}/storefront` and `.../cover`, resolving the
  slug through the existing `resolve_active_tenant` and reading under the
  `customer` role. `offerings`' existing `tenant_isolation` policy already
  covers this: `tenant_context` sets `app.tenant_id` whatever the role.
- **Presentation:** the public response contains the resolved business identity,
  cover URL, categorized offerings, and existing platform links. No About field
  is returned.
- **Slug at confirm:** `POST /api/onboarding/confirm` takes an optional
  `slug`; `suggested_slug()` derives the default and is guaranteed to pass
  `validate_slug`. A unique violation becomes a 409, not a 500, and both the
  old and new slug are dropped from the resolver cache.
- **Routes:** `business/booking/` -> `business/page/`, `settings/` ->
  `business/details/`, `M-1`'s `OfferingsList` mounted at
  `business/offerings/`. `/settings` leaves `proxy.ts` with the route, and
  stays in `RESERVED_SLUGS` (that list is a floor, not a mirror).

### Tests

- Backend: the storefront exposes only owner-published content, with
  `price_cents` passed through; a priceless offering reaches the page with no
  price; retiring an offering drops it from both the owner's list and the
  storefront while the row survives; a suggested slug always passes
  `validate_slug` across reserved, punctuation-only and ordinary names.
- E2E: `storefront.spec.ts` (absence of About, opening the chat
  sheet, an unknown slug still 404s) and the offerings round trip in
  `business-hub.spec.ts`, which now asserts the price on the public page.
- **Not covered by E2E:** choosing the slug at go-live. Reaching confirm means
  walking the seven-beat interview against a live model, which is slow and
  flaky; the derivation, the reserved-name fallback and the 409 are covered by
  backend tests instead.

### Files touched

- `backend/app/features/business/public_api.py` (new), `service.py`, `api.py`,
  `controller.py`
- `backend/app/features/onboarding/{api,controller,service}.py`,
  `backend/app/features/tenants/slug.py`
- `backend/migrations/0024_offering_position.sql`
- `frontend/src/app/[slug]/{page.tsx,Storefront.tsx}`, `src/lib/tenant.ts`
- `frontend/src/app/(tenant-admin)/(console)/business/**`, `layout.tsx`,
  `src/proxy.ts`

### Definition of done

- [x] `/{slug}` renders categorized offerings with the owner's prices, optional
      media, and links, with the assistant a tap away
- [x] An offering with no price shows none
- [x] About is preserved for reversibility but absent from owner and public UI
- [x] The owner chooses their public address at go-live; a taken one is a 409
      and a reserved-derived one cannot 500
- [x] One route per screen - the aliases are gone
- [x] `make check` green; E2E covers the storefront round trip
