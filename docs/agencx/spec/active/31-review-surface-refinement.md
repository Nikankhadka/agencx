# 31: Review surface refinement

**Status:** Active - todo.
**Phase 1 area:** Onboarding, knowledge review, offerings, site ingestion.

Refines the review surface delivered by [29-source-first-onboarding.md](29-source-first-onboarding.md)
(status: awaiting review). One component serves three surfaces: onboarding,
Business > Knowledge, and the Home suggestions sheet. The Business surface
passes neither source actions nor suggestions, so every prop added here is
optional and its behaviour must not change.

## Intent

The review sheet works but reads like a form built in a hurry. Its fields are
smaller than the app's own fields, the offering stack is loose, and every card
carries an open category picker whether or not the owner wants one. Removing an
offering or discarding a source takes effect on the first click with no dialog.
Paging, adding and expanding all move content under a keyboard user's focus
without saying where it went. And the one thing the sheet cannot do is fix a
wrong link: a URL source can only be replaced by uploading a file.

This ticket tightens the rhythm to the field recipe the rest of the console
uses, collapses the category picker behind one action per card, routes every
destructive action through the app's one confirm dialog, makes focus follow
what it revealed, lets a URL row be edited in place, and adds the one backend
endpoint a full link replacement needs.

## Design reference

The review sheet's own render functions are the screen: `ReviewDocument`,
`SuggestionDocument`, `OfferingCard`, `ReviewCategoryControl`, `ProfileRow` and
`Pagination` in `frontend/src/components/knowledge/ReviewSheet.tsx`, and
`CategoryPicker` in `frontend/src/components/business/CategoryPicker.tsx`.
Interaction vocabulary comes from the console prototype
(`docs/agencx/design/prototypes/agencx-prototype-v6.html`, the
`#sheet-settings-edit` sheet). Spacing, type and radii come from
`docs/agencx/design/frontend.md` section 4, which wins where the two disagree.

## Locked decisions

| # | Decision |
|---|---|
| 1 | The collapse state is component-local to `ReviewCategoryControl` (one picker per card, one trigger per card). There is no sheet-level category control. |
| 2 | Closed label: `Add category` when `category_ids` is empty, `Categories (N)` when it is not, N = `category_ids.length`. The trigger carries `aria-expanded` and `aria-controls`. |
| 3 | Opening focuses the picker's search field; `Done` collapses and returns focus to the trigger. `CategoryPicker` gains `focusSearch?: boolean` (default false) that puts `autoFocus` on its search input, the same mechanism `ProfileRow` already uses. |
| 4 | The suggested-category line moves inside the expanded region, so a closed card is one row shorter than today. |
| 5 | "The same site reader" is `knowledge_service.scrape_site` (`features/knowledge/service.py:160`), which crawls through `crawl_site` (`ingestion/site.py:1065`). `fetch_page` is never called directly. |
| 6 | The link editor renders under the source row, inside the same bordered container (label and actions stay visible). It never replaces the row. |
| 7 | A row is a URL row when `doc.doc_type === "website"`. URL rows get `Edit link`; file rows keep `Replace`. |
| 8 | `Add a link` and `Add a file` are two labels over one control each: the link opens the inline editor with no target document, the file opens the existing hidden multi-file input (`ReviewSheet.tsx:427`). |
| 9 | Confirm copy is fixed: offering removal `Remove <name>?` / `It will not be saved to your catalog.` / `Remove`; link replacement `Replace this link?` / `The new site will be read, and its details and offerings will replace this source.` / `Replace link`; discard `Discard this source?` (or `Discard these sources?`) / `It is deleted, and its details and offerings are not saved.` (or `They are deleted...`) / `Discard source` (or `Discard sources`). |
| 10 | One dialog for all four removals: the injected `confirmRemove` prop, which is `useConfirm`'s `confirm`. Every call made from inside the sheet passes `layer: "top"`, because the sheet panel is transformed and a fixed overlay inside it clips. |
| 11 | Merge policy: a link *replacement* overwrites the business fields the new site states (`only_empty=False`); `Add a link` is a source, so it keeps `only_empty=True`. A field the new site does not mention keeps its current value in both cases, because `save_profile` never writes an absent value. |
| 12 | Candidates are reconciled on the client through `reconcileOfferings` (`components/knowledge/offerings.ts:80`), exactly as the file-replace path does (`ReviewSheet.tsx:340`), and the next batch save persists the surviving list (`features/onboarding/controller.py:1171`). The endpoint does not reconcile: it cannot see in-session edits, and the server-side `reconcile_replacement` (`onboarding/flow.py:400`) stays the reference the client mirrors. |
| 13 | Replacing with the same URL re-reads in place: `draft_from_url_text` already targets the row with that filename (`service.py:794-799`), so the endpoint deletes the old document only when the resolved document id differs from `replace_document_id`. |
| 14 | `POST /api/onboarding/source/url` takes JSON `{url, replace_document_id?}` and answers `{state: OnboardingStateResponse, document: KnowledgeRecord \| null}`. The sheet needs the document's own candidates; the page needs the state. |
| 15 | The review field recipe is `rounded-field border border-border bg-surface px-4 py-3 text-body text-text min-h-11 outline-none placeholder:text-ink-a40 focus:border-text`. No new token: `text-body` (16/24) and `min-h-11` both exist, and `check:tokens` scans only the `p|m|gap|space` families (`frontend/scripts/check-tokens.mjs:48-49`). |
| 16 | Focus uses one helper, `reveal(refs, id)`: `requestAnimationFrame`, then `node.focus()`, then `node.scrollIntoView({ block: "nearest" })`. It extends the pattern already at `ReviewSheet.tsx:254` with the scroll convention at `PhonePill.tsx:156`. No new focus library, no `setTimeout`. |
| 17 | `Pagination` gains `pageSize` (default `PAGE_SIZE`) and `noun` (default `"offerings"`), so the review's copy and pages are unchanged. |

## Current behaviour this changes (verified)

| Today | Where (file:line) | Change |
|---|---|---|
| Review fields are the 18/25 sheet-field size at `px-3 py-2` | `components/knowledge/ReviewSheet.tsx:458`, `:471`; `CategoryPicker.tsx:134` | 16/25 `text-body`, `px-4 py-3`, `min-h-11` (44px floor) |
| The profile row's input is the tightest control on the sheet | `ReviewSheet.tsx:458` | Same recipe as the offering rows |
| Card stack gap is 12px; the offerings section opens at 20px; later sections at 32px | `ReviewSheet.tsx:387`, `:382`, `:167`, `:398`, `:406` | `gap-2`, `mt-4`, later sections `mt-6` |
| The price input is 112px wide | `ReviewSheet.tsx:471` | `w-24` (96px) |
| `CategoryPicker` renders open on every card, with no trigger and no Done; its search input is never focused on open | `ReviewSheet.tsx:489`; `CategoryPicker.tsx:96-135` | Collapsed trigger, Done, focus on open |
| The suggested-category line sits above the picker and adds height to every card | `ReviewSheet.tsx:488` | Inside the expanded region |
| Removing an offering drops the row immediately on both surfaces | `ReviewSheet.tsx:243` (review), `:168` (suggestions) | Confirmed through `confirmRemove`, `layer: "top"` |
| Removing a *source* already confirms through the injected `confirmRemove` | `ReviewSheet.tsx:345-357` | Unchanged; the same dialog now also guards the footer discard |
| The footer discard acts immediately and is labelled `Discard` | `ReviewSheet.tsx:450`; `onboarding/page.tsx:1287` | Confirmed; labelled `Discard source` / `Discard sources` |
| Cancel of any dialog returns focus to its opener already, because `Modal` captures and restores it | `components/ui/Modal.tsx:42-55` | No new mechanism; the cancel paths inherit it |
| Paging moves no focus | `ReviewSheet.tsx:388`, `:505` | First row of the new page focused and scrolled into view |
| `Add offering` focuses the new row but does not scroll to it | `ReviewSheet.tsx:254` | Also scrolls |
| `Review all` expands and pages to the top with no focus move | `ReviewSheet.tsx:390` | Focuses the first row |
| Source rows offer `Replace` (a file picker) and `Remove` only; a URL source cannot be edited | `ReviewSheet.tsx:413-422` | URL rows get `Edit link` plus an inline editor; file rows keep `Replace` |
| One hidden multi-file input sits behind `Add another source` | `ReviewSheet.tsx:426-428` | Two actions: `Add a link`, `Add a file` |
| Suggestions render every candidate in one unpaginated stack; their cards carry no refs | `ReviewSheet.tsx:164-170`, `:168` | Pages of 5 desktop / 3 mobile, with refs for focus |
| Pagination copy hardcodes `PAGE_SIZE` and the word "offerings" | `ReviewSheet.tsx:505-506` | `pageSize` and `noun` props, defaults unchanged |
| A suggestion save already sends every local candidate, not a page | `ReviewSheet.tsx:160-162` | Keep it that way; acceptance 12 is a regression guard, not new work |
| The first source merge fills empty profile fields only | `onboarding/agent.py:1113`; `onboarding/tools.py:69` | A replacement overwrites; add-a-link stays fill-empty |
| A URL already ingested re-reads in place rather than duplicating | `features/knowledge/service.py:794-799` | The replace path reuses it and skips the delete |
| There is no onboarding URL endpoint, only the streaming turn and the file upload | `features/onboarding/api.py:247`; `controller.py:823` | New `POST /api/onboarding/source/url` |

## Acceptance criteria

| # | Scenario | Passes when |
|---|---|---|
| 1 | Any review field is measured | Computed font-size 16px, height at least 44px, radius and padding match the shared field recipe, on the offering rows, the price row and every profile row |
| 2 | Spacing is measured | Card-to-card gap is 8px, the offerings section starts 16px below the intro, later sections 24px |
| 3 | A card with no category is closed | One `Add category` button, no picker in the DOM, card height unchanged by the suggested-category line |
| 4 | A card with two categories is closed | One `Categories (2)` button, `aria-expanded="false"` |
| 5 | The trigger is clicked | The picker renders, its search field has focus and is in view, the suggested-category line is inside the expanded area |
| 6 | `Done` is clicked | The picker leaves the DOM and focus returns to the trigger |
| 7 | An offering's `Remove` is clicked | The dialog reads `Remove <name>?` / `It will not be saved to your catalog.` and paints above the sheet; confirm removes the row, cancel keeps it |
| 8 | The same removal is reached from the Home suggestions sheet | Same dialog, same copy, same above-sheet layer |
| 9 | The footer discard is clicked | The dialog names what is deleted; confirm deletes every reviewed source, cancel keeps them all and leaves the review open |
| 10 | `Next` is clicked on page 1 | The page changes and the first offering name on page 2 has focus and is scrolled into view; `Previous` behaves the same |
| 11 | The only row on the last page is removed | Focus lands on the previous row; removing a middle row focuses the next one; removing the last row of all focuses `Add offering` |
| 12 | `Add offering` / `Review all` / category open / link editor open | Focus lands on the revealed field and that field is in view |
| 13 | Every cancel path is exercised | Focus returns to the control that opened it: category `Done` to the trigger, link `Cancel` to `Edit link` or `Add a link`, dialog cancel to the opener |
| 14 | A URL row's `Edit link` is clicked, `Cancel` is clicked | The editor closes; the document count, the source label, the review and the interview stage are all unchanged, and no request was made |
| 15 | The link editor is saved with the same URL | The site is read again into the same document id; no new row, no delete |
| 16 | The link editor is saved with a different URL | The new site is crawled, the old document is gone, the new one is listed, and the old document's offerings that the owner never edited are gone from the review |
| 17 | The replacement states a field the review already holds | The new value wins in the review and in both profile jsonb copies after the next save |
| 18 | The replacement does not state a field | The current value survives, and is not cleared |
| 19 | `Add a link` is used | A second URL document joins the review, the profile fills empty fields only, and owner answers survive |
| 20 | The suggestions sheet holds nine candidates | Five rows on desktop, three on mobile, with `Showing 1-5 of 9 suggestions`; paging focuses and scrolls to the first suggestion |
| 21 | All nine are saved from page 1 | The request body carries nine candidates |
| 22 | The Business > Knowledge review sheet is opened | No source actions, no suggestions, no category regression; paging, focus and the discard confirm behave as they do on onboarding |

## Migration

None. The highest applied migration is
`backend/migrations/0038_conversations_resolved_at.sql`; `0039` stays unused.
The new endpoint writes only existing tables (`documents`, which already
carries `doc_type = 'website'` from
`0015_website_doc_type.sql`, and `tenant_config.config->'onboarding'`).
`frontend/src/lib/api-types.ts` is regenerated, not hand-edited.

## Slice A - Field recipe, spacing, profile rows

**Goal:** the review reads as one form, and every field matches the shared recipe.

**Files**

- `frontend/src/components/knowledge/ReviewSheet.tsx` - `ProfileRow`,
  `OfferingCard`, `KnowledgeDocument` inputs, section and card spacing.
- `frontend/src/components/business/CategoryPicker.tsx` - search input class.
- `docs/agencx/design/frontend.md` - section 4.4 names the review field recipe
  (`px-4 py-3 text-body min-h-11`) beside the sheet-field recipe, and 4.6 notes
  the `text-body` size on form controls as a founder ruling.

**Technical contract**

- One exported constant in `ReviewSheet.tsx`, `FIELD`, holding the recipe from
  locked decision 15, used by every text and number input in the file. The
  `KnowledgeDocument` heading input keeps `text-row-label` (it is a heading, not
  a field) and takes only the padding and height.
- Card stack `gap-3` becomes `gap-2` at `:387` and `:167`. The offerings
  section `mt-5` at `:382` becomes `mt-4`; `:398` and `:406` become `mt-6`;
  `:437` becomes `mt-6`.
- Price input `w-28` becomes `w-24` at `:471`. Name input keeps `flex-1`.
- No new token and no `@theme` change, so no `make dev-reset` is needed.

**Test seams**

- `frontend/src/components/knowledge/ReviewSheet.test.tsx` - the rendered
  markup carries `text-body` and `min-h-11` and does not carry `text-field` on
  any review input; the price input carries `w-24`.
- `frontend/e2e/knowledge-review.spec.ts` - one computed-style assertion on the
  first offering name input and one on a profile input: font-size 16px, height
  at least 44px, border-radius from `--radius-field`.

**Verify**

```
make lint-frontend
make typecheck-frontend
docker compose run --rm --no-deps frontend npx vitest run src/components/knowledge
```

## Slice B - Collapsed categories and focus movement

**Goal:** a card is quiet until the owner opens categories, and focus always
lands on what just appeared.

**Files**

- `frontend/src/components/knowledge/ReviewSheet.tsx`
- `frontend/src/components/business/CategoryPicker.tsx`
- `frontend/src/components/knowledge/ReviewSheet.test.tsx`,
  `frontend/src/components/business/CategoryPicker.test.tsx`

**Technical contract**

- `CategoryPicker` gains `focusSearch?: boolean` (default `false`) and an
  internal `searchRef`; the search input gets `autoFocus={focusSearch}`. Nothing
  else changes, so `business/components/OfferingsList.tsx:680` keeps today's
  behaviour.
- `ReviewCategoryControl` gains `open`, `triggerRef`, `pickerRef`:
  the closed state is one button (`data-testid="review-category-trigger"`,
  `aria-expanded`, `aria-controls`, label per locked decision 2); the open state
  renders the suggestion line, then `CategoryPicker focusSearch`, wrapped in a
  `div ref={pickerRef}`, then `Done` (`data-testid="review-category-done"`).
  Opening runs `reveal`-style scroll on `pickerRef`; `Done` calls
  `setOpen(false)` then `triggerRef.current?.focus()`.
- `reveal(refs, id)` is a module-level helper in `ReviewSheet.tsx` per locked
  decision 16. `addOffering` (`:254`) and the duplicate jump (`:276`) switch to
  it.
- `ReviewDocument` gains `gotoPage(next)`: clamp to `0..pages-1`, `setPage`,
  then `reveal(cardRefs, offeringPage(offerings, clamped)[0].candidate_id)`.
  `Pagination` at `:388` takes `onPage={gotoPage}`.
- `Review all` (`:390`) sets expanded, pages to 0, then reveals
  `offerings[0]`. `Add offering` reveals the new row through the same helper.
- `removeOffering` becomes `async`, computes the removed index, keeps the
  survivor id (`offerings[index + 1] ?? offerings[index - 1]`), and after the
  filter sets the page with the existing `pageForOffering` (`:508`) and reveals
  the survivor. With no survivor it focuses a new `addOfferingRef`. Confirm
  wiring is Slice C; this slice keeps the direct removal.
- `SuggestionDocument` gets its own `cardRefs` map, passed as
  `inputRef={(node) => { if (node) cardRefs.current.set(offering.candidate_id, node); }}`,
  so Slice D can focus a suggestion.

**Test seams**

- `ReviewSheet.test.tsx` - a closed card renders `Add category` and no
  `Search or create a category` field; a selected card renders
  `Categories (2)`; the suggestion line is absent while closed; `Pagination`
  calls its handler with the neighbouring page and the default copy is
  unchanged.
- `CategoryPicker.test.tsx` - `focusSearch` marks the search field
  `autofocus`; the default render does not.
- `frontend/e2e/knowledge-review.spec.ts` - `Review all` then `Next`: the
  first name on page 2 is focused and inside the viewport; `Add offering`
  focuses and reveals the new row; a closed card shows `Add category`, opening
  focuses the search field, `Done` returns focus to the trigger.
- `frontend/e2e/knowledge-review-mobile.spec.ts` - the collapsed list keeps
  three cards and the same trigger copy at 360px.

**Verify**

```
make lint-frontend
make typecheck-frontend
docker compose run --rm --no-deps frontend npx vitest run src/components/knowledge src/components/business
docker compose --profile e2e run --rm -e E2E_LLM=1 e2e sh -c "$E2E_NET_SH" -- npm run test:e2e -- e2e/knowledge-review.spec.ts
```
(`E2E_NET_SH` and the stack requirement are defined under Verification.)

## Slice C - Removal and discard confirmations

**Goal:** nothing is destroyed on a single click, and the confirm sits above
the sheet.

**Files**

- `frontend/src/components/knowledge/ReviewSheet.tsx`
- `frontend/src/components/knowledge/OfferingSuggestions.tsx`
- `frontend/src/app/(tenant-admin)/(console)/business/details/knowledge/page.tsx`
  (pass the existing `confirm` through)
- `frontend/src/components/knowledge/ReviewSheet.test.tsx`
- `frontend/e2e/knowledge-review.spec.ts`, `knowledge-review-mobile.spec.ts`,
  `business-page-actions.spec.ts`, `onboarding-resume.spec.ts`,
  `onboarding-go-live.spec.ts`, `onboarding-url.spec.ts`,
  `settings-knowledge.spec.ts`

**Technical contract**

- `OfferingCard`'s `onRemove` stays a synchronous callback; the guard lives in
  the two owners, so one dialog covers both surfaces.
- `ReviewDocument.removeOffering` becomes `async`: `await confirmRemove?.({...})`
  with the copy from locked decision 9, `tone: "danger"`, `layer: "top"`; return
  on false; otherwise run the Slice B removal and focus logic.
- `SuggestionDocument` takes `confirmRemove` and confirms the same way before
  filtering. `ReviewSheet` passes it to both branches.
- `OfferingSuggestions` calls `useConfirm()`, renders `{dialog}` beside
  `<ReviewSheet>` (never inside a panel, per `ConfirmDialog.tsx:104-106`), and
  passes `confirmRemove={confirm}`.
- Footer discard becomes `handleDiscard()`: confirm with the locked copy
  (pluralised from `workspace.documents.length`) when `confirmRemove` is
  provided, then `onDiscard()`. The label becomes `Discard source` /
  `Discard sources` on the onboarding surface; the non-onboarding labels stay
  `Discard draft` and `Remove source`.
- `business/details/knowledge/page.tsx` passes `confirmRemove={confirm}` to its
  `ReviewSheet` (`:538-553`), so its footer discard asks too. This is the one
  shipped behaviour outside onboarding that changes; see Flags.
- Spec updates this forces: `onboarding-go-live.spec.ts:208`, `:258`,
  `onboarding-url.spec.ts:139`, `settings-knowledge.spec.ts:294`, `:305` each
  add one `confirm-accept` click.

**Test seams**

- `ReviewSheet.test.tsx` - rendering `ReviewDocument` and `SuggestionDocument`
  with a confirming `confirmRemove` shows no removal until the promise
  resolves true; resolving false leaves the row; the footer label follows the
  document count; `ConfirmOptions` carries `layer: "top"`.
- `frontend/e2e/knowledge-review.spec.ts` - remove an offering: dialog copy,
  confirm removes, cancel keeps; discard asks and cancel leaves the review open.
- `frontend/e2e/business-page-actions.spec.ts` and `onboarding-resume.spec.ts` -
  the suggestions sheet asks before removing a suggestion.

**Verify**

```
make lint-frontend
make typecheck-frontend
docker compose run --rm --no-deps frontend npx vitest run src/components/knowledge
docker compose --profile e2e run --rm -e E2E_LLM=1 e2e sh -c "$E2E_NET_SH" -- npm run test:e2e -- e2e/knowledge-review.spec.ts
```

## Slice D - Suggestions pagination at 5 and 3

**Goal:** the suggestions sheet stops being an endless list without narrowing
what it saves.

**Files**

- `frontend/src/components/knowledge/ReviewSheet.tsx` (`SuggestionDocument`,
  `Pagination`)
- `frontend/src/components/knowledge/ReviewSheet.test.tsx`

**Technical contract**

- `Pagination({ page, pages, count, onPage, pageSize = PAGE_SIZE, noun = "offerings" })`;
  the summary line uses `pageSize` and `noun` and nothing else changes.
- `SuggestionDocument` uses `useMediaQuery(DESKTOP_QUERY)`, `pageSize =
  desktop ? PAGE_SIZE : COLLAPSED_MOBILE`, `pages`, `page`, `visible`, and a
  `gotoPage` that reveals the first visible suggestion through `reveal`.
  `Pagination` renders when `pages > 1`.
- `save()` keeps mapping the whole `offerings` array, never `visible`.
- The page resets to 0 when the last row on the last page is removed.

**Test seams**

- `ReviewSheet.test.tsx` - nine suggestions render five rows on the desktop
  branch and three on the mobile branch (mock `@/lib/useMediaQuery`, spreading
  the real module per the memory gotcha); the summary copy reads
  `Showing 1-5 of 9 suggestions`; `onSaveSuggestions` receives nine candidates
  while page 1 shows five.
- `frontend/e2e/business-page-actions.spec.ts` - the sheet pages at 1024px with
  five rows; `frontend/e2e/onboarding-resume.spec.ts` covers save-after-paging.

**Verify**

```
make lint-frontend
make typecheck-frontend
docker compose run --rm --no-deps frontend npx vitest run src/components/knowledge
docker compose --profile e2e run --rm -e E2E_LLM=1 e2e sh -c "$E2E_NET_SH" -- npm run test:e2e -- e2e/business-page-actions.spec.ts
```

## Slice E - The URL source endpoint

**Goal:** one owner-authenticated call reads a site the way onboarding reads
one, and can replace an existing source in place.

**Files**

- `backend/app/features/onboarding/api.py` - request and response models, the
  route.
- `backend/app/features/onboarding/controller.py` - `run_source_url`.
- `backend/app/onboarding/agent.py` - `prepare_source_profile(..., only_empty: bool = True)`.
- `backend/tests/test_onboarding_api.py` - a new section.
- `frontend/src/lib/api-types.ts` - regenerated (host).
- `docs/agencx/design/api-contract.md` - the new section.

**Technical contract**

```python
class OnboardingSourceUrlRequest(BaseModel):
    url: str = Field(min_length=1, max_length=2048)
    replace_document_id: UUID | None = None

class OnboardingSourceUrlResponse(BaseModel):
    state: OnboardingStateResponse
    document: KnowledgeRecord | None
```

- `@router.post("/source/url", response_model=OnboardingSourceUrlResponse)`,
  owner-only through `auth.require_owner`, JSON body. `url` passes through the
  knowledge module's `_absolute_url` (`features/knowledge/api.py:78`); importing
  that private helper is the precedent already set at `onboarding/api.py:25`.
- `run_source_url(*, tenant_id, url, replace_document_id, provider)` returns
  `{"state": ..., "document": ...}` and runs:
  1. Load the record and 409 when `onboarding.completed`, mirroring
     `run_source_upload` (`controller.py:969-975`).
  2. `crawl = await knowledge_service.scrape_site(url=url)`. A `ValueError`
     becomes a 422 whose detail is the existing `_url_failure_code(exc)` line
     (`:93`); nothing is written and the old source is untouched.
  3. `document_id = uuid4()`; the draft and the profile read run together under
     one `asyncio.timeout(_SOURCE_TURN_TIMEOUT_S)` with
     `asyncio.gather(..., return_exceptions=True)`, exactly as
     `_stream_url_turn` (`:842-868`) does:
     `draft_from_url_text(...)` and
     `prepare_source_profile(record=..., text=crawl.text, provider=bounded,
     only_empty=replace_document_id is None)`.
  4. If the draft result is a `BaseException`, do not delete anything and
     return `document=None` with the unchanged state.
  5. Delete the old source only when `replace_document_id` is set, the returned
     document's id differs from it, and the returned record's `status` is
     `"draft"`: `knowledge_service.delete_record(...)` (`service.py:1192`).
  6. `_merge_document_candidates(onboarding, document["offering_candidates"])`,
     `onboarding.knowledge_pending = False`, append the URL and the
     `url_readback(onboarding.draft)` line to `history`, `_checkpoint`, return.
- `prepare_source_profile` gains `only_empty: bool = True` and passes it to
  `save_profile` (`agent.py:1113`). Default keeps `_stream_url_turn` and
  `run_source_upload` byte-identical.
- `OnboardingStateResponse` is unchanged, so no other frontend type moves.

**Test seams**

- `backend/tests/test_onboarding_api.py`, using the existing
  `UrlFakeProvider`/`_patch_fetch`/`_signup_tenant_admin` seams (`:1301`,
  `:1355`, `:244`) and `superuser_conn` for the row assertions:
  - add-link: no `replace_document_id` keeps the owner's `business_name`, fills
    an empty `hours`, creates one `website` draft, returns that document.
  - wrong-URL replacement: the old row is gone from `documents`, the new row is
    a `website` draft, and the response document is the new one.
  - field overwrite: a field the new site states replaces the owner's value in
    `draft`; a field it does not state keeps its value (two assertions).
  - same-URL re-read: `replace_document_id` equals the row that holds that URL,
    so the response document id equals it, `documents` still holds one row, and
    no delete happened (assert via the still-present row, not a mock).
  - scrape failure: a `ValueError` from `scrape_site` is 422, one document
    remains, `draft` is unchanged.
  - confirmed onboarding: 409.
  - auth: no bearer token is 401.
  - `_reject_upload`-class rejections do not apply (JSON route); an empty `url`
    is 422 from `Field(min_length=1)`.

**Verify**

```
docker compose run --rm backend pytest tests/test_onboarding_api.py -q
docker compose run --rm backend ruff check . && docker compose run --rm backend mypy
cd frontend && npm run gen:types && npm run gen:types -- --check
```

## Slice F - Link editing on the review sheet

**Goal:** a wrong link is fixed in place, and the sheet calls the new endpoint
through the same page-owned callbacks the file actions use.

**Files**

- `frontend/src/components/knowledge/ReviewSheet.tsx`
- `frontend/src/app/(tenant-admin)/(console)/onboarding/page.tsx`
- `frontend/e2e/knowledge-review.spec.ts`,
  `frontend/e2e/knowledge-review-mocks.ts`
- `frontend/src/components/knowledge/ReviewSheet.test.tsx`

**Technical contract**

- New props, both optional:
  `onReplaceLink?: (documentId: string, url: string) => Promise<{ record: KnowledgeRecord; draft: Record<string, unknown> } | null>`
  and `onAddLink?: (url: string) => Promise<KnowledgeRecord[]>`.
- `ReviewDocument` state: `linkEditor: { documentId: string | null } | null`,
  `linkValue`, `linkInputRef`, `linkOpenerRef`.
  - `Edit link` (`data-testid="review-edit-link"`, `aria-label="Edit link for
    <label>"`) seeds `linkValue` with `doc.filename` and stores
    `event.currentTarget` as the opener.
  - `Add a link` (`data-testid="review-add-link"`) opens the editor with
    `documentId: null` and an empty value.
  - `Add a file` keeps the hidden multi-file input and takes the testid
    `review-add-file` (`review-add-source` has no other consumer).
  - The editor is an input (`data-testid="review-link-input"`) plus `Save`
    (`aria-label="Save link"`) and `Cancel` (`aria-label="Cancel link"`), inside
    the row container for a replace and below the list for an add.
- Save path: for a replace, confirm first with the locked copy
  (`layer: "top"`), then `await onReplaceLink(id, trimmed)`. On a record,
  delete `sectionsByDocument` and `sources` entries for the old id, set the new
  one, run
  `reconcileOfferings(previous, record.offering_candidates ?? [], id, editedIdsRef.current)`,
  and merge the returned `draft`'s `PROFILE_ROWS` keys into `profileValues`.
  For an add, `await onAddLink(trimmed)` and hand the records to the same
  `adoptRecords(records)` helper `handleAddFiles` uses (`:305-315`).
  Failure sets nothing but `busy` and the page's existing `reviewError` path.
- Cancel path: `setLinkEditor(null)` and `linkOpenerRef.current?.focus()`.
  Nothing else runs: no request, no document change, no stage change, no
  `onDiscard`.
- Page: `replaceLink(documentId, url)` and `addLink(url)` post to
  `/api/onboarding/source/url`, then `applyStateFields(state)`, then rebuild
  `workspace` (replace or append, keeping `workspace.id`) and `setCanConfirm(false)`
  as `addSources` already does (`:800`). They return the record and draft, or
  `null`/`[]` with `setReviewError(err.detail)` on an `ApiError`.
- `knowledge-review-mocks.ts` gains `stubSourceUrl(page, store, options)` that
  fulfils `/api/onboarding/source/url` with the Slice E shape and records the
  posted body, so the E2E never crawls.

**Test seams**

- `ReviewSheet.test.tsx` - `Edit link` opens the editor with the current URL and
  `Cancel` calls neither callback; `Save` on a replace calls the confirm and
  then `onReplaceLink`; a cancelled confirm calls nothing; a successful replace
  drops the old document's candidates the owner never edited and keeps an edited
  one as `orphaned`; `Add a link` calls `onAddLink` with no target.
- `frontend/e2e/knowledge-review.spec.ts` - edit, cancel: the sheet stays open,
  the source label and count are unchanged, and `stubSourceUrl` recorded no
  call; edit, save with the same URL: one source, same id; edit, save with a
  different URL: confirm copy, the old label is gone, the new label appears, and
  the deleted id is recorded by `stubRecords().deletedIds()`.
- `frontend/e2e/knowledge-review.spec.ts` - `Add a link` adds a second source
  and focuses the revealed field.

**Verify**

```
make lint-frontend
make typecheck-frontend
docker compose run --rm --no-deps frontend npx vitest run src/components/knowledge
docker compose --profile e2e run --rm -e E2E_LLM=1 e2e sh -c "$E2E_NET_SH" -- npm run test:e2e -- e2e/knowledge-review.spec.ts
```

## Verification

The stack must be up before any spec-scoped run (`make dev && make seed`). The
network shim is the Makefile's own `E2E_NET` body:

```
E2E_NET_SH='socat TCP-LISTEN:3000,fork,reuseaddr,bind=127.0.0.1 TCP:frontend:3000 & socat TCP-LISTEN:8000,fork,reuseaddr,bind=127.0.0.1 TCP:backend:8000 & socat TCP-LISTEN:54321,fork,reuseaddr,bind=127.0.0.1 TCP:auth-proxy:80 & socat TCP-LISTEN:8025,fork,reuseaddr,bind=127.0.0.1 TCP:mailpit:8025 & exec "$@"'
```

Full-suite gate at the branch tip: `make lint`, `make typecheck`, `make test`,
`make test-e2e`, plus `cd frontend && npm run gen:types -- --check` (host).

## Definition of done

- Slices A to F land in order, each with its verify command green and the
  output pasted into this file.
- Acceptance scenarios 1 to 22 demonstrated: unit tests for the field recipe,
  the closed and open category states, both confirmations, pagination copy and
  page size, and the link editor's three paths; E2E for every focus move, both
  confirmations, `Edit link` cancel and save, `Add a link`, and the 5/3
  suggestions split; backend tests for the endpoint's seven cases.
- `docs/agencx/design/api-contract.md` documents
  `POST /api/onboarding/source/url` and its replace semantics.
- `docs/agencx/design/frontend.md` 4.4 carries the review field recipe and 4.6
  the `text-body` control exception.
- `docs/agencx/progress.md` row for 31 and the `docs/agencx/spec/README.md`
  active row.
- `.agents/memory.md` gains only the non-obvious facts: the client-side
  candidate reconcile for a link replacement, and the confirm-from-inside-a-sheet
  `layer: "top"` requirement for offering removal.
- No new migration; `make migrate` still reports `0038` as the head.

## Flags for the founder

| Flag | Default taken |
|---|---|
| The discard confirm reaches the Business > Knowledge sheet too, because the footer is shared and `confirmRemove` is now passed there; that surface's own record list already confirms, its sheet footer did not | Confirmed everywhere, with the label unchanged off onboarding; two specs gain one click. Say the word and it stays onboarding-only |
| `px-4 py-3 text-body` renders 48px tall, so `min-h-11` (44px) is a floor that never binds. A 44px field exactly would need `py-2` | Keep `py-3` (the system recipe's padding) and the 44px floor |
| `text-body` on form controls departs from the 18/25 `text-field` role that `frontend.md` 4.4 names for sheet fields; `text-field` itself stays for the contact and profile sheets | Treated as a founder ruling for the review surface only, recorded in 4.6 |
| A replacement never clears a field the new site omits, per the request | Kept as stated; clearing is a separate ask |

## Blockers

None.
