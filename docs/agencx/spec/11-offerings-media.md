# Offerings + Media (D24)

Three forward tickets. None have started - see `docs/agencx/design/decisions.md`
D24 for the design reasoning (catalog/knowledge split, Cloudinary choice, the
still-open `catalog_items` rename question) and provenance (a Codex CLI
session designed this, then hit its usage limit before writing anything down;
this phase file and D24 are the recovered record, cross-checked against the
code). Ticket id prefix `M-` (Media), unused elsewhere in the ticket set.

Order matters: `M-1` gives Offerings real identity and closes the two
retrieval-safety gaps that become live the moment `catalog_items` is
owner-written - shipping it without them would ship a working feature next to
a real bug. `M-2` (media) only needs an offering to exist for its per-offering
photo half; its gallery half has no dependency on `M-1` but is sequenced after
it for one branch, one reviewable diff. `M-3` (import-and-confirm) writes
through `M-1`'s service, so it must come last.

---

## M-1: Offerings become a real, owner-writable structured item

### Summary

Give `catalog_items` its first owner-facing writer: a service + API + a
minimal manual add/edit/remove UI on the Business hub, using the `Offering`
vocabulary D24 locked in. No images in this ticket - that's `M-2`. Bundles the
two correctness fixes that only matter once this table is actually written to
outside seeds, so the ticket ships whole rather than half-safe.

### Why

Today `catalog_items` is read everywhere that matters (pricing engine,
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
  visible (RLS, unchanged from `catalog_items`'s existing policy).

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

- Editing a `catalog_items` row bumps `knowledge_version` (currently it does
  not - `catalog_items.updated_at` is absent from `_VERSION_SQL` in
  `knowledge_version.py:32`), so the context-package cache invalidates.
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
- **Write-time re-index:** every write calls `ingest_catalog_items`
  (`backend/app/ingestion/pipeline.py:96-146`) so the searchable catalog
  projection stays in sync - this is already-working code whose only caller
  today is seed scripts.
- **`knowledge_version.py:32`:** fold `catalog_items.updated_at` into
  `_VERSION_SQL`'s `greatest(...)` so a direct catalog write invalidates the
  cache even on a future code path that doesn't go through
  `ingest_catalog_items`.
- **`retrieval.py:100` (`whole_corpus()`):** add a `metadata.kind !=
  'catalog_item'` filter (or equivalent) to the fast-path query.
- **Migration:** next number after `0022_drop_auth_codes.sql`, i.e.
  `0023_...sql`. Either widens `catalog_items` (unlikely to need schema
  changes - the columns already fit `Offering`) or renames it, per the naming
  decision above.
- **Frontend:** a minimal add/edit/remove list on the Business hub
  (`frontend/src/app/(tenant-admin)/(console)/business/`), following the
  Settings > Knowledge page's list-with-inline-actions pattern
  (`settings/knowledge/page.tsx:276-336`) rather than inventing new UI
  vocabulary. The Booking page's existing read-only render
  (`business/booking/page.tsx:156-184`) switches its data source from
  `offerings.py`'s knowledge-derived rows to the real `catalog_items` rows
  (via `BookingPageResponse.services`, unchanged wire shape - `{name,
  price}` - unless the naming decision above changes it).

### Tests

- Backend: create/update/delete offering (RLS-scoped, cross-tenant isolation
  proven the same way other tenant-scoped writers are); write bumps
  `knowledge_version`; `whole_corpus()` excludes catalog-kind chunks
  (regression test seeded with both kinds present); `ingest_catalog_items`
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

- [ ] Naming decision made and recorded (table renamed, or kept with reasoning
      noted here)
- [ ] Owner can add/edit/remove an offering from the Business hub
- [ ] Booking page renders from the real writer, not knowledge-derived text
- [ ] A catalog edit bumps `knowledge_version`
- [ ] Catalog-kind chunks excluded from `whole_corpus()`, proven by a
      regression test
- [ ] `make check` green; Booking-page E2E covers add/edit/remove, not just
      the empty state

---

## M-2: Reusable business media via Cloudinary

### Summary

Replace the single-cover, Postgres-bytea `tenant_assets` table with a
Cloudinary-backed model supporting a capped 5-image business gallery and
optional per-offering photos, reusing the client-side downscale pattern that
already exists for the cover photo.

**Blocked:** the founder confirmed Cloudinary credentials are not set up yet.
This ticket is not implementable until they exist - it stays written forward
until then.

### Why

`tenant_assets` (`backend/migrations/0021_tenant_assets.sql`) is schema-capped
to exactly one row per tenant: `primary key (tenant_id, kind)`, `kind check
(kind in ('cover'))`. Its own migration comment already names the upgrade
path: "Object storage is the upgrade path if this ever holds galleries rather
than one cover." The founder was explicit about wanting that gallery - "a
simple business owner... wants to display like five different images. It can
be a cover image. It can be a popular menu item" - and D24 chose Cloudinary
over Supabase Storage for the CDN/transform layer a real photo gallery needs
that a plain object-storage bucket does not provide on its own.

### User stories

#### US-1 An owner uploads up to 5 gallery photos

As a tenant owner, I add photos to a business gallery - a cover-equivalent
plus up to four more - from the Business hub.

- The 6th upload attempt is refused with a clear reason, not silently dropped
  or silently replacing an existing photo.
- Each photo is downscaled client-side before upload (reusing
  `CoverPhoto.tsx`'s `downscale()`, extracted into a shared helper - max 1600px
  edge, JPEG q0.82).
- Photos display in the order the owner set them (a `position` field), and the
  owner can reorder or remove one.

#### US-2 An owner attaches a photo to a confirmed offering

As a tenant owner, after confirming an offering (`M-1`), I optionally attach
one photo to it.

- An offering with no photo displays fine - a photo is never required.
- The per-offering photo is stored and served the same way as a gallery photo
  (same table, different `kind`/`offering_id`), not a separate mechanism.

#### US-3 The customer-facing page serves photos fast, without exposing tenant credentials

As a customer viewing the public Booking page, gallery and offering photos
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
  tenant_id uuid, kind text check (kind in ('cover', 'gallery', 'offering')),
  offering_id uuid null references catalog_items(id) on delete cascade,
  cloudinary_public_id text, position integer, created_at, updated_at`. A
  partial unique index or application-level check caps gallery rows at 5 per
  tenant (`kind = 'gallery'` count, including the cover-equivalent slot -
  decide during implementation whether `cover` is `gallery` position 0 or a
  separate `kind`). RLS mirrors `tenant_assets`'s existing policies
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
- **Frontend:** extract `CoverPhoto.tsx`'s `downscale()` (lines 22-48) into a
  shared helper (e.g. `frontend/src/lib/image.ts`); a gallery uploader
  component (multi-slot, drag-to-reorder or simple up/down controls, 5-image
  cap enforced client-side and server-side); a per-offering "Add photo"
  control on the `M-1` offerings UI. Public Booking page renders gallery/
  offering images via plain `<img src>` to the Cloudinary URL (no more
  `apiFetchStream`/object-URL dance the private cover proxy needed).
- **Migration of existing data:** the one existing cover-photo row (if any
  exists on a live tenant) needs a one-time migration into the new model -
  `FLAG: data migration`, founder sign-off, matching how D24 flagged this.

### Tests

- Backend: upload/delete/reorder gallery photos; 5-image cap enforced
  server-side (not just client-side); per-offering photo attach/detach; RLS
  isolation.
- Frontend: gallery upload/reorder/remove flow; per-offering photo attach
  flow; cap-reached error state; extracted `downscale()` helper covered by
  its existing test (if any) plus the new call site.
- E2E: a full gallery upload -> public Booking page render round trip.

### Files touched

- `backend/migrations/0024_*.sql` (or next available number)
- `backend/app/features/business/service.py`, `api.py` (media endpoints)
- new backend module for Cloudinary signed uploads (not `shared/storage.py`)
- `frontend/src/lib/image.ts` (new, extracted from `CoverPhoto.tsx`)
- `frontend/src/app/(tenant-admin)/(console)/business/` (gallery UI, offering
  photo control)
- `.env.example`, `docs/agencx/deploy.md` (Cloudinary credentials)
- `docs/agencx/architecture.md` (Cloudinary as a listed external dependency)

### Definition of done

- [ ] Cloudinary credentials provisioned and documented
- [ ] Owner can upload/reorder/remove up to 5 gallery photos
- [ ] Owner can attach/remove a photo on a confirmed offering
- [ ] Public Booking page serves photos via Cloudinary CDN, not a backend
      proxy
- [ ] Existing cover photo (if any) migrated, not silently dropped
- [ ] `make check` green; E2E gallery round trip passes

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

- Detection reuses `offerings.py`'s existing line-splitting/price-slice logic
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
  scan structured sections for `OFFERING_HEADINGS` (`offerings.py:27`) and run
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
  `catalog_items` rows by name (case-folded, matching `offerings.py`'s
  existing dedupe key); a match with a different price surfaces as a proposed
  change, not an automatic write.
- **Money rule, explicitly unrelaxed:** the extraction model (if any LLM
  involvement exists in section classification) never touches the price
  value itself - only `extract_monetary_figures`'s deterministic slice does,
  exactly as it does for the read-time derivation today.

### Tests

- Backend: a document with a `"What we offer"` section produces the expected
  candidates; confirmation writes real `catalog_items` rows; re-upload with a
  changed price produces a diff, not a silent write; a document with no
  offering-shaped section produces zero candidates and doesn't interrupt
  normal review.
- Frontend: candidates render in the review sheet; confirm/edit/skip actions;
  diff presentation on re-upload.
- Regression: the money guardrail test matrix (`C-4`) gains cases proving a
  candidate's price is always a verbatim slice, never a re-formatted or
  computed value.

### Files touched

- `backend/app/features/business/offerings.py` (candidate-extraction reused)
- `backend/app/features/knowledge/service.py` (detection hook post-structure)
- `frontend/src/app/(tenant-admin)/(console)/settings/knowledge/components/ReviewSheet.tsx`
- `frontend/src/app/(tenant-admin)/(console)/settings/knowledge/lib/types.ts`

### Definition of done

- [ ] Structured document with offering-shaped sections proposes candidates in
      the existing review flow
- [ ] Confirmation writes through `M-1`'s service, never a bypass insert
- [ ] Re-upload diffs against existing offerings instead of overwriting
- [ ] Money guardrail test matrix extended and green
- [ ] `make check` green
