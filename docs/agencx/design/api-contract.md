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
  `skip` field and its `__skip__` sentinel are gone.
- The knowledge ask is not a beat - it sits past the last one, holding
  `knowledge_pending` - and it carries the one `Skip for now` chip left,
  always visible, submitting `{selection: {beat: "knowledge", values:
  ["skip"]}}`. It is answered before any beat cursor is consulted, and
  declining it never gates go-live. Typing "skip" still works.
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
- `offering_categories` is tenant-scoped and RLS protected. Offerings carry a
  nullable `category_id` while retaining the category label for compatibility;
  public and retrieval projections use the category label resolved from the
  tenant category.

Unapproved candidates never enter `offerings`, the storefront, or customer
context. Go live publishes only approved candidates; optional unreviewed drafts
remain private and can be opened later from Home or What you offer.

No unrelated API redesign, new relational entities, or full pricing schema is
planned; the broader R-3 schema audit stays separate.
