# 12 (RF-6): Document-review workspace clarification

**Status:** Done - merged in `684a2bf` on 2026-10-02.
**Phase 1 area:** Refinement.

Delivered: the document-review workspace is clearer to read and edit without
changing what saves or publishes. Business draft rows name their state, the
review sheet drops a repeated source line and labels its footer secondary
action by context, its two sections render in true DOM order, and removing a
saved source reuses the row-level removal confirmation.

## Agreed behavior

Document review is clarified only - copy, ordering, and state labels - with
publication semantics unchanged and no new review behavior. Every existing
review path still saves the same content, nothing answers a customer before
Save, and the changed copy reads correctly at mobile and desktop widths.

## Shipped

- Business > Knowledge draft rows name their state through the shared
  `statusLine(record)` ("Not saved yet") above the read-back prompt, matching
  saved rows. The change is in
  `frontend/src/app/(tenant-admin)/(console)/business/details/knowledge/page.tsx`.
- The review sheet drops the repeated `From <labels>.` prefix on the business
  offerings count in
  `frontend/src/components/knowledge/ReviewSheet.tsx`.
- The sheet footer's secondary action is labeled by context: onboarding
  "Discard", business draft "Discard draft", business saved "Remove source".
  The design-pinned strings, handlers, endpoints, and testids are untouched.
- The two sections render in DOM order that matches their visual order -
  business mode leads with Business information then Offerings; onboarding
  leads with Offerings then Business information - replacing the CSS `order`
  swap.
- Removing a saved source reuses the row-level removal confirmation:
  `Remove <label>?`, `Its reviewed facts stop answering customers.`, the
  `Remove` confirm label, the `Removed` toast, and `layer: "top"`. Exactly one
  DELETE runs on confirm and none on Escape or cancel. Drafts still drop
  without a dialog, and the onboarding path is untouched.
- Tests: `ReviewSheet.test.tsx` pins the context-specific footer labels and the
  DOM order; `frontend/e2e/settings-knowledge.spec.ts` covers the draft footer
  label and the saved-source removal dialog.
- No API or DB change.

## Ticket detail

- **Visible outcome:** The document-review workspace is clearer to read and
  edit; publication semantics do not change and no new review behavior is
  added.
- **Current vs proposed:** Current: the review sheet ships (O-3, W-8) with
  read-first documents, capped offering cards, duplicate decisions, and inline
  editing. Proposed: clarification only - copy, ordering, and state labels -
  with no change to what saves or publishes.
- **Design reference:** Shipped
  `frontend/src/app/(tenant-admin)/(console)/business/details/knowledge/components/ReviewSheet.tsx`
  and `knowledge/page.tsx`; `design/frontend.md` S2 states table and the W-8
  paragraph.
- **Dependencies:** RF-1.
- **API/DB changes:** None.
- **Acceptance scenarios:** Every existing review path still saves the same
  content; nothing answers a customer before Save; the changed copy reads
  correctly at mobile and desktop widths.
- **Regression checks:** `make test-e2e` knowledge-review and
  knowledge-review-mobile specs stay green.
- **OPEN:** none.

`design/frontend.md` S2's summary row still reads "Save / Discard"; the shipped
business-mode secondary labels are the context-specific "Discard draft" /
"Remove source" pair above.

## Verification

- `make lint-frontend` - passed (eslint plus the token guard).
- `make typecheck-frontend` - passed.
- `make test-frontend` - 307 passed across 31 files.
- `make build` - passed.
- Targeted E2E through the e2e container with `E2E_LLM=1`:
  `frontend/e2e/knowledge-review.spec.ts` 8,
  `frontend/e2e/settings-knowledge.spec.ts` 5, and
  `frontend/e2e/knowledge-review-mobile.spec.ts` 4 = 17 passed, 0 failed.
  Screenshots at 360px and 1024px were inspected.
- The full e2e suite was not run as a whole (same as RF-5).
