# 12 (RF-5): Cover and offering-image workflows

**Status:** Done - merged in `eda75ec` on 2026-10-02.
**Phase 1 area:** Refinement.

Delivered: one media workflow covers the cover photo and offering media with
the same states (empty, uploading, preview, saved) and an explicit Remove
affordance on both; a failed cover upload restores the previous photo without
leaving a partial state.

## Agreed behavior

Upload, preview, replace, and remove run through one shared media component
across the cover band and the offering editor. Both surfaces share the same
state vocabulary (empty, uploading, preview, saved) and a visible, explicit
Remove control; removal is never implied. A failed upload recovers to the last
saved state.

## Shipped

- New shared presentational component
  `frontend/src/app/(tenant-admin)/(console)/business/components/MediaField.tsx`.
  It owns the hidden file input, the image/video preview, the shared state
  vocabulary, and the explicit Remove affordance. A cover variant (the 200px
  `.bk-photo-wrap` band, camera icon, "Tap to add a cover photo", "Edit photo"
  pill) and an offering variant (the compact slot chip) share those internals.
- `frontend/src/app/(tenant-admin)/(console)/business/page/components/CoverPhoto.tsx`
  renders MediaField and adds explicit removal: a danger-tone `ConfirmDialog`
  then `DELETE /api/business/cover`, landing back on the empty well. It shows a
  local object-URL preview while the PUT is in flight, restores the previous
  server image on failure, and revokes the pending URL once the refetched
  canonical image lands (an uploading ref stops an older refetch from revoking a
  newer pick).
- `frontend/src/app/(tenant-admin)/(console)/business/components/OfferingMediaField.tsx`
  renders MediaField for the slot while keeping the deferred save, the URL
  field, the pending-file chip with Edit/Cancel, the pending-removal copy, and
  every existing test id. Its explicit remove still routes through the parent
  `OfferingsList` confirm and removal flow.
- Tests: `MediaField.test.tsx` (state rendering, remove affordance, disabled
  behavior), `CoverPhoto.test.tsx` (rendered states and the decode fallback),
  and `frontend/e2e/business-hub.spec.ts` cover upload/replace/remove,
  failed-upload recovery, offering URL replace/remove, and a route-mocked
  offering image upload.
- No backend or schema change. The existing cover and offering media endpoints
  are reused; the cover DELETE already existed and is idempotent.

## Ticket detail

- **Visible outcome:** One cover/offering-image workflow covers upload, preview,
  replacement, and removal, with the same states everywhere (empty, uploading,
  preview, done, remove); removal is explicit.
- **Current vs proposed:** Current: the cover photo ships (E-6, Cloudinary) and
  offering media has an upload/preview field; a single unified workflow across
  cover and offering images, and explicit removal states, are partial.
  Proposed: unify the two on one media component and add an explicit remove
  state.
- **Design reference:** `agencx-prototype-v6.html` `renderScreen('booking')`
  `.bk-photo-wrap` with the "Edit photo" control; `design/frontend.md` section
  6 `FileDropzone` (images are refused for knowledge, not for brand assets).
  Shipped: `business/page/components/CoverPhoto.tsx`,
  `business/components/OfferingMediaField.tsx`, and the Cloudinary adapter
  behind the media endpoints.
- **Dependencies:** RF-1.
- **API/DB changes:** Reuse the existing upload and delete endpoints; add an
  explicit removal call for the cover if one is missing; no schema change.
- **Acceptance scenarios:** Upload a cover, replace it, and remove it back to
  the empty state; upload, replace, and remove an offering image; a failed
  upload recovers without leaving a partial state.
- **Regression checks:** The E-6 cover tests, the Cloudinary rollback, and the
  legacy `tenant_assets` reads stay green.
- **OPEN:** none.

## Verification

- `make lint` - passed (frontend eslint plus the token guard; backend `ruff
  check` plus import-linter, 3 contracts kept, 0 broken).
- `make typecheck` - passed (frontend `tsc --noEmit`; backend mypy, "no issues
  found in 223 source files").
- `make test` - 1247 backend passed and 304 frontend passed (run as
  `make test-backend` and `make test-frontend`).
- `make build` - passed.
- Targeted E2E `frontend/e2e/business-hub.spec.ts` through the e2e container -
  14 passed.
- The cover E2E sends a real 1x1 JPEG fixture rather than a fake byte string:
  `downscale()` falls back to the raw bytes when `createImageBitmap` fails, and
  a configured Cloudinary rejects non-image payloads, so fake bytes would only
  pass with Cloudinary unconfigured. The full e2e suite was not run as a whole.
