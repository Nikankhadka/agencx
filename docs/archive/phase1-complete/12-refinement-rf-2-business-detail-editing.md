# 12 (RF-2): Business-detail editing and immediate consistency

**Status:** Done - merged in `baa0ade` on 2026-10-02.
**Phase 1 area:** Refinement.

Delivered: post-launch editing of business name, hours, description, and
business contact from the Business hub, with the edits reaching the Business
page and customer answers.

## Agreed behavior

Core business-detail editing after launch (name, hours, description, business
contact), in the shipped ABN-editor sheet idiom; the public address is a
separate field and stays stable when the name changes. Saved edits appear
immediately on the Business page and in customer answers.

Shipped: `/business/details` editors for business name, hours, description and
business contact in the ABN-sheet idiom via one reusable `ProfileFieldSheet`;
`BusinessProfile`/`ProfileUpdate` widened (API `name` -> `business_name`,
`business_contact` -> `contact`); `PROFILE_FIELDS` widened; both jsonb copies
kept in sync; `tenants.business_name` and an existing `brand.display_name`
synced, slug never touched; `description` added to the context package's
`_PROFILE_LABELS`. Customer freshness relies on `knowledge_version` already
including `tenant_config.updated_at`, which `write_profile` bumps (confirmed at
`backend/app/services/knowledge_version.py:41` and
`backend/app/features/business/service.py:1038`). The public address editor was
deliberately not built (the ticket's OPEN line); contact stays private on
`/{slug}`.

## Ticket detail

- **Visible outcome:** The owner edits business name, hours, description, and
  business contact after go-live from the Business hub, in the shipped sheet
  idiom; saved edits appear on the Business page and in customer answers. The
  public address is a separate field and stays stable when the name changes.
- **Current vs proposed:** Current: `/business/details` reads back ABN/GST,
  services, and assistant voice; none of business name, hours, description, or
  business contact has an editor, and `PATCH /api/business/profile` refuses
  extra keys (`backend/app/features/business/api.py` `ProfileUpdate`). Proposed:
  add an editor per field kind over the same save path, extend the profile
  model and update handler to accept the new fields, and revalidate that
  customer answers read the updated profile.
- **Design reference:** `agencx-prototype-v6.html` `renderScreen('settings')`
  `.set-field-row` rows and `openSettingsEdit(idx)` sheet; `design/frontend.md`
  section 4.4 sheet-field recipe. Shipped:
  `frontend/src/app/(tenant-admin)/(console)/business/details/page.tsx`,
  `AbnSheet.tsx`, and `backend/app/features/business/api.py` `BusinessProfile` /
  `ProfileUpdate`.
- **Dependencies:** RF-1. The field editors follow the same idiom RF-7 uses.
- **API/DB changes:** Extend `BusinessProfile` and `ProfileUpdate` with `name`,
  `hours`, `description`, and `business_contact`; store on `tenant_config` or
  the existing profile storage; no new table.
- **Acceptance scenarios:** Edit name, hours, description, and contact in turn;
  each appears immediately on the Business page and in the customer chat's
  answers; changing the name does not change the public address or link.
- **Regression checks:** Tenant isolation and onboarding-confirmed values stay
  intact; the existing ABN, services, and voice editors still save;
  `make test-backend`, `make test-frontend`, and `make test-e2e`.
- **OPEN:** whether the public address gains a post-launch editor in this pass,
  or stays a go-live-only choice from M-4 US-3. Resolved as: not built in this
  pass; the public address stays a go-live-only choice.

## Verification

- `pytest tests/test_business_api.py tests/test_context_package.py` - 64 passed.
- `npx vitest run` - 278 passed.
- `make lint` - passed.
- `make typecheck` - passed.
- `make test` - 1238 backend + 278 frontend passed.
- `make build` - passed.
- `make test-e2e` - 168 passed.
- New `frontend/e2e/business-details-rf2.spec.ts`.
