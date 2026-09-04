# Phase 1 refinement (R)

This active file contains only the refinement work that remains open. Completed
R-1 and R-2 records are preserved in
`docs/archive/phase1-complete/12-refinement-r1-r2.md`.

## R-3: Schema and type safety

**Status:** backlog, not yet scoped.

Pydantic models across the API layer are not uniformly configured with an
explicit unknown-field policy. The generated-types path currently covers error
responses, but success responses consumed by the frontend have not yet been
audited end to end.

### Acceptance signal

- [ ] Every request and response model has an explicit, deliberate
  unknown-field policy.
- [ ] Generated TypeScript types are the only declared shapes for success
  responses consumed by the frontend.
- [ ] No hand-duplicated interface remains beside a generated type.

## R-4: Reliability and provider

The Google provider's multi-tool history fix is complete. Provider-owned
assistant metadata is preserved and replayed verbatim, including
`thought_signature` values required by Google.

### Remaining work

- [ ] Judge calibration is completed using founder hand-labeling rather than
  agent-generated labels.
- [ ] Production-smoke evidence beyond the B-4 deployment smoke test is
  collected and recorded.

## R-5: Operations and security

The URL-ingest SSRF hardening is complete. HTTP(S)-only validation, public DNS
resolution, peer verification, redirect-hop validation, media-type checks, and
body-size limits are covered by backend tests.

### Remaining work

- [ ] Backups, RPO/RTO, and a restore drill have a documented status and proof
  command.
- [ ] Error tracking has a documented status and operational verification.
- [ ] The Playwright suite runs in CI, not only locally.
- [ ] Dependency scanning has a documented status and scan report.

### Acceptance signal

Each item above is marked built, planned, or deliberately deferred, with an
owner, urgency trigger, and validation command where applicable.
