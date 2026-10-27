# Agencx API contract

## Errors

JSON errors use RFC 9457 Problem Details with media type
`application/problem+json`:

```json
{
  "type": "about:blank",
  "title": "Validation failed",
  "status": 422,
  "detail": "One or more fields are invalid.",
  "instance": "urn:agencx:request:<request_id>",
  "code": "validation_failed",
  "request_id": "<request_id>",
  "errors": [{"pointer": "/field", "code": "required", "detail": "Field is required."}]
}
```

Malformed JSON is `400 malformed_request`. Semantic validation is `422
validation_failed`. Authentication is `401 unauthenticated` with
`WWW-Authenticate: Bearer`; authorization, missing resources, conflicts, rate
limits, upstream failures, and operational failures use stable local codes and
safe details. Rate limits include `Retry-After`.

Successful responses remain resource-oriented: reads and updates use 200,
creation uses 201, and successful commands or deletions use 204 with no body.
SSE failures after a stream starts use an `error` event containing `code`, safe
`detail`, and `request_id`.

The generated frontend OpenAPI types are refreshed with `npm run gen:types` and
checked without writing with `npm run gen:types -- --check`.

## Knowledge review contract (Phase 13, W-8)

The Phase 13 refinements (`../../archive/phase1-complete/13-walkthrough.md`, amended 2026-09-05)
define the contract used by onboarding and later knowledge review.

- **Draft offering identity, description, provenance, and source references.**
  `PendingOffering` carries a stable opaque `candidate_id`, description, price,
  provenance, and references to the source
  blocks that support the name, description, and price, so edits cannot
  migrate between items and every figure resolves deterministically (W-6,
  W-8).
- **Preserved complex-price context and explicit review issues.** Ranges,
  "from" prices, units, variants, bundles, surcharges, and currency stay
  surfaced with their source wording, with a review flag distinguishing
  absent, ambiguous, and conflicting prices (W-6).
- **Possible-match relationships and owner resolutions.** Proposed duplicate
  pairs and their owner decision (combine with which retained values, or keep
  both) round-trip on the existing save boundary; unresolved suggestions stay
  separate and saving never implies a merge (W-8).
- **Compatible defaults for existing drafts.** Drafts without the new
  metadata keep working and are not migrated eagerly; the new fields read
  through defaults (W-6/W-8 record compatibility).
- **Consistent candidate merge behavior across client and server.** One shared
  precedence policy is applied by both sides; the wire shape documents it
  rather than letting the two disagree (W-6).
- **Original source evidence.** `GET /api/knowledge/records/{document_id}/source`
  is owner-only and returns extracted original source text on demand. A legacy
  record returns its saved reviewed text with `is_fallback: true`.
- **Correction semantics through the existing onboarding message/update
  boundaries.** A turn that corrects previously captured fields is expressed
  through the existing onboarding message/update shapes; no new correction
  endpoint is planned (W-9).

## Resumable owner input and normalized offerings

The onboarding record is the authoritative private checkpoint. Every accepted
message, fixed selection, pending name confirmation, and offering review
decision is written to `tenant_config.config->onboarding` before the response
returns. `revision`, `last_action_key`, and `last_action_fingerprint` make a
retry converge on the same checkpoint instead of advancing twice.

- `POST /api/onboarding/message` accepts exactly one of `text`, `selection`,
  `resume`, or a typed `correction`. No beat exposes a `Skip for now` chip
  (20): the two-ask cap resolves an unanswered optional beat by default, or to
  `skipped` for the owner's name, and a required beat defers then pauses. The
  `skip` field and its `__skip__` sentinel are gone. The name beat carries a
  dashed `Skip` chip, which resolves the same words deterministically.
- The source ask is not a beat: it is the second stage, holding
  `knowledge_pending`, and it carries an always-visible `Skip for now` chip
  submitting `{selection: {beat: "knowledge", values: ["skip"]}}`. It is
  answered before the required beats, declining it never gates go-live, and
  typing "skip" still works.
- Name proposals expose `pending_confirmation`. `Yes` commits the exact
  proposal; `No` is a client-only edit affordance; a replacement is shape
  checked and then receives a constrained plausibility verdict without being
  rewritten.
- Profile `services` is a normalized `string[]`, with a compatibility reader
  for legacy strings. It is required (20), and each entry may carry the
  owner's own rough price text, copied verbatim - it is an overview, never the
  priced catalog, and nothing parses or quotes from it. The storefront and the
  owner's booking page both publish it as a list. `PendingOffering` retains source wording, proposed
  category, description origin, review status, and provenance.
- `GET /api/onboarding/suggestions` returns only pending private candidates.
  `PUT /api/onboarding/suggestions` stores owner review decisions and publishes
  approved candidates immediately for an already-live tenant.
- `offering_categories` is tenant-scoped and RLS protected. An offering accepts
  `category_ids: UUID[]` plus `primary_category_id: UUID | null`; duplicate IDs,
  a primary outside the list, and malformed combinations are rejected. On a
  PATCH, omitted category fields preserve membership and an explicit empty list
  clears it. When a non-empty list omits the primary, its first item becomes
  primary.
- Offering, booking-page, storefront, and catalog responses return
  `categories: [{id, name, position, is_primary}]`, primary first. The singular
  `category` and `category_id` fields remain during the compatibility window and
  mirror the primary membership.
- `GET /api/business/offering-categories` returns category objects with an
  active `offering_count`. `POST /api/business/offering-categories` creates an
  explicit owner-confirmed category; PATCH renames and DELETE removes it.
  Normalized create or rename collisions return 409. Missing and cross-tenant
  IDs return 404.
- Deleting a primary category promotes the remaining lowest-position
  membership. Deleting the final membership leaves the offering Uncategorized.
  A model's `proposed_category` is private review metadata only: persistence
  requires an owner-confirmed category selection or explicit creation.

Unapproved candidates never enter `offerings`, the storefront, or customer
context. Go live publishes only approved candidates; optional unreviewed drafts
remain private and can be opened later from Home or What you offer.

## Source-first onboarding and pricing wording (29)

- `POST /api/onboarding/source` is owner-only and multipart: one `file`. It
  validates through the knowledge screen's own upload edge (extension
  allowlist, 4MB cap, empty-file rejection), parses the file once, runs the
  document draft, offering extraction and the profile read together, merges
  the profile into empty fields only, checkpoints the record, and returns
  `OnboardingStateResponse`. A confirmed onboarding is `409`; a failed profile
  read does not fail the upload, so the document and its candidates still
  return.
- `OnboardingKnowledgeBatchRequest` gains an optional `profile:
  dict[str, str]`. Its keys are the `ProfileDraft` fields; an unknown key is
  `422 validation_failed` rather than a silent drop. The patch is written to
  both profile jsonb copies in the same checkpoint as the documents and
  offerings.
- `OnboardingStateResponse.missing_required: string[]` and the streamed `state`
  event carry the required beat labels the source did not answer, in beat
  order. Optional beats are excluded, because they resolve themselves later.
  The review sheet renders one "I'll ask next" note from this list and never
  empty rows.
- `PendingOffering` gains `pricing_wording` (string, 120-character cap) and
  `wording_options: string[]`. `pricing_wording` is mutually exclusive with
  `price_cents` at the draft layer as well as at the API; two differing source
  wordings set `wording_options` and `needs_review`, and the review save answers
  the same conflict message as a cents conflict. Cents stay integers in
  `price_options`; words stay words in `wording_options`.
- The `show_catalog` catalog payload carries `pricing_wording` on every
  offering beside `price_cents`, along with the existing category fields, so
  the card can show the owner's wording when there is no fixed amount.

## Link editing on the review sheet (31)

- `POST /api/onboarding/source/url` is owner-only JSON:
  `{url, replace_document_id?}` answers `{state: OnboardingStateResponse,
  document: KnowledgeRecord | null}`. The sheet needs the document's own
  candidates; the page needs the state, so one call answers both.
- The crawl goes through the site reader onboarding already uses
  (`knowledge_service.scrape_site`), never a single-page fetch. A `ValueError`
  from the reader is `422` with the stable failure category as its detail
  (`upstream_http`, `timeout`, `no_content`, `blocked_address`, and the rest of
  `_url_failure_code`); nothing is written and the old source is untouched. A
  relative or scheme-less URL is `422` from the knowledge module's
  `_absolute_url`. A confirmed onboarding is `409`.
- The document draft and the profile read run together under one deadline,
  exactly as the streamed URL turn does. A draft failure returns `document:
  null` with the unchanged state and deletes nothing. That deadline firing
  after the crawl is `504` with detail `timeout`; it writes nothing either.
- Replace semantics: `replace_document_id` switches the profile merge to
  `only_empty=False`, so the new site overwrites the fields it states. A field
  the new site omits keeps its current value in both cases, because
  `save_profile` never writes an absent value. Without `replace_document_id`
  the link is an added source and fills empty fields only.
- The replaced document is deleted only when the resolved document id differs
  from `replace_document_id` and the new row is a `draft`. The same address is
  the same source, so a re-read of it updates that row in place and no delete
  happens.
- The endpoint does not reconcile offerings. The client reconciles with
  `reconcileOfferings`, mirroring `reconcile_replacement`, so an owner-edited
  candidate survives a replacement as `orphaned` and the next batch save
  persists the surviving list.

No unrelated API redesign, new relational entities, or full pricing schema is
planned; the broader R-3 schema audit stays separate.
