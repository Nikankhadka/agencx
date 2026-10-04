# 25: Media replace hardening

**Status:** Active - in progress on `fix/25-media-replace-hardening`.
**Phase 1 area:** Backend, business media.

Numbering note: 23 through 28 are the 2026-10 storefront and console
refinement batch; this is the third ticket in it.

## Design reference

Not UI. `_replace_media`, `write_cover`, `delete_media`, and
`set_offering_media` in `backend/app/features/business/service.py`; the
Cloudinary adapter in `backend/app/features/business/media.py`;
`docs/agencx/design/database.md` for `tenant_media` and `tenant_assets`.

## Summary

The media replace and delete paths stop creating orphans and dangling
references. A DB write that fails after a successful Cloudinary upload
destroys the new asset. A Cloudinary cover write clears any stale local-dev
`tenant_assets` row. Deletion removes the DB row first and treats a failed
cloud destroy as a logged, non-fatal orphan. There is no historical sweep.

## Why

The founder asked what happens when a cover photo is replaced: today the row
updates in place and the previous Cloudinary object is hard-deleted, with no
versioning. Two failure edges remain. A DB failure after the upload leaves the
new object orphaned with nothing pointing at it. A local-dev fallback row can
linger once Cloudinary is configured and shadow the real cover, because
readers still consult `tenant_assets`. And a failed cloud destroy during
delete currently 502s while leaving the row pointing at an object that is
gone. The fix closes those paths; it does not build a sweeper.

## Current vs proposed behavior

| | Current | Proposed |
|---|---|---|
| DB write fails after upload | New asset orphaned | New asset destroyed; the old row and asset are untouched |
| Cloudinary cover write with a local fallback row | Fallback row lingers, shadowed | Fallback row deleted in the same flow |
| Cloud delete fails during delete | 502; the row keeps pointing at a missing object | Row deleted first; cloud failure logged, response 204 |
| Old-asset destroy fails during replace | Row reverted, new asset destroyed, 502 | Unchanged |

## Locked decisions

1. Failure-path fixes only. No sweep for orphans left by past failures.
2. Delete ordering is row-first, cloud-second. A failed cloud delete logs a
   warning and is never surfaced to the owner as an error.
3. The existing replace rollback (old-asset destroy fails: revert the row,
   destroy the new asset, raise) is unchanged.
4. API behavior change: media deletion no longer returns 502 on a cloud
   failure. The 502 branches remain and now only catch the unconfigured-cloud
   guard.

## User stories

### US-1 Replacing a photo cannot accumulate storage

**As** the maintainer,
**I want** a failed row write to take its uploaded object with it,
**so that** storage holds only objects some row points at.

- [ ] A DB failure after a successful upload destroys the new asset
- [ ] The previous row and its asset are untouched on that failure
- [ ] A Cloudinary cover write removes any stale `tenant_assets` cover row

### US-2 Deleting media never leaves a broken reference

**As** a customer,
**I want** a deleted photo to actually be gone from the page,
**so that** no broken image or video remains.

- [ ] The `tenant_media` row is deleted before the cloud object is destroyed
- [ ] A cloud destroy failure logs a warning and still returns success
- [ ] Both the offering-media and cover delete endpoints return 204 in that
      case

## Technical spec

- `_replace_media`: wrap the DB write block in try/except; on any exception,
  destroy `media` when it is Cloudinary-backed, swallow a destroy failure,
  and re-raise. `previous` initializes to `None` before the block.
- `write_cover`: after the Cloudinary `_replace_media`, delete the
  `tenant_assets` row for `(tenant_id, 'cover')`.
- `delete_media`: fetch and delete the row inside one `tenant_context`
  transaction; then destroy the cloud object with `MediaUploadError` caught
  and logged (`logger.warning`), returning `True` either way.
- Add a module logger to `service.py`.

## Tests

`backend/tests/test_business_api.py`:
1. `_replace_media` with a broken `tenant_context` destroys the new
   Cloudinary `public_id` and re-raises.
2. A local fallback cover PUT followed by a configured Cloudinary PUT leaves
   `tenant_assets` at zero and one `tenant_media` cover row.
3. With a fake whose `delete` raises, `DELETE .../media` and
   `DELETE /api/business/cover` both return 204 and the rows are gone.

## Files touched

- `backend/app/features/business/service.py`
- `backend/tests/test_business_api.py`

## Definition of done

- [ ] The three failure paths are closed with tests
- [ ] Existing media tests still pass
- [ ] `make lint-backend`, `make typecheck-backend`, `make test-backend` pass

## References

- RF-5 cover and offering-image workflows (archived) - the replace flow
- `docs/agencx/design/database.md` - `tenant_media` / `tenant_assets`
