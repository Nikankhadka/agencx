# 29: Source-first onboarding

**Status:** Active - awaiting review.
**Phase 1 area:** Onboarding, knowledge review, assistant context, site ingestion.

Four slices, delivered across six feature commits plus three fix commits. Ticket
30 (chat catalog for large menus) is a separate ticket on its own branch,
specified in [30-chat-catalog-full-list.md](30-chat-catalog-full-list.md).

## Intent

An owner should not have to answer eight questions before showing the setup
assistant their website. Today the interview runs name, business name, type,
headcount, hours, services and contact, and only then offers a website or a
document. This ticket moves the source ask to second, opens a review that is
priced and editable instead of a wall of rows, and makes a documented menu reach
the assistant as owner-approved wording. The existing optional beats still run
after the review, exactly as they do today.

## Locked decisions

| # | Decision |
|---|---|
| 1 | Flow: name -> website/document -> review -> missing required beats -> existing optional beats -> confirm |
| 2 | Review opens in price-editing mode when prices are missing |
| 3 | Optional beats keep today's behaviour; the source fills ABN only if it finds one |
| 4 | Review shows only the fields the source found, plus one "I'll ask next" note |
| 5 | Crawl keeps the 10-page hybrid; 6 concurrent; 10s deadline; 11,500 characters |
| 6 | One price field: a number becomes fixed cents, words become pricing wording |
| 7 | Missing prices warn, never block go-live |

## Current behaviour this changes (verified)

| Today | Where | Change |
|---|---|---|
| `owner_display_name` is a free-text beat with no skip; "skip" passes `_wordish` and is saved | `onboarding/beats.py:197-214`, `:157-163` | Skip action; skip words resolved deterministically, never saved |
| Website/document ask fires only after every beat, via `_KNOWLEDGE_OFFER`, and gates on `knowledge_pending` checked *after* `next_beat` | `onboarding/agent.py:691-717`, `:750-768` | Source asks second; flag checked before `next_beat`; offer deleted |
| `save_profile` overwrites any non-empty field | `onboarding/tools.py:30-43` | `only_empty` mode for source merges |
| URL turn: crawl -> structure -> offerings -> profile, four serial steps | `features/onboarding/controller.py:153-167`, `features/knowledge/service.py:371-398` | Crawl, then draft and profile together; structure + offerings inside the draft |
| File upload never merges a profile | `features/knowledge/api.py:195-213` | New `POST /api/onboarding/source` does |
| `+` attach exists only on the `knowledge` stage | `onboarding/page.tsx:1141` | Every text input |
| Review save assumes `can_confirm=true` | `onboarding/page.tsx:897` | Re-fetch `/api/onboarding/state` |
| `services` is a required free-text beat and is also filled by the URL extractor | `beats.py:263-286`, `agent.py:974-982` | Services come from approved candidates; `services_source` decides the sync |
| `reconcile_offerings_batch` writes name/description/price_cents only | `features/business/service.py:429-450` | Also `pricing_wording` |

## Acceptance criteria

| # | Scenario | Passes when |
|---|---|---|
| 1 | Name -> paste a no-price site -> review -> fixed price + wording -> save -> missing beats -> optional beats -> confirm | Review opens expanded with the banner; both price shapes save; the required beats ask after; go-live succeeds |
| 2 | Paste a PDF with no prices | Same review and price entry as 1 |
| 3 | Owner answers services, then pastes a site | Owner wording survives; the source fills only empty fields |
| 4 | Barbershop source | 14 distinct services; zero combine prompts; one "Beard trim" row |
| 5 | Assistant answers a fixed price from the catalog and repeats owner wording | Verbatim wording; no invented figure; money gate green |
| 7 | No-source path | The existing interview runs unchanged |
| 8 | Crawl probe | Optimized faster on every URL in the matrix; coverage 100%/95%/90% by size band |

Acceptance 6 (the full-list chat card) belongs to ticket 30.

## Migration

None. The highest applied migration is
`backend/migrations/0038_conversations_resolved_at.sql`; `0039` stays unused.
Offering candidates are not a table - they live in
`tenant_config.config->'onboarding'.offering_candidates`
(`features/onboarding/service.py:23,34-40`), so `PendingOffering.pricing_wording`,
`services_source`, and the source markers are all additive jsonb. The one DB
column this ticket needs already exists: `offerings.pricing_wording`
(`migrations/0036_offering_pricing_wording.sql:8`).

## Slice A - Flow inversion

**Goal:** name -> source -> review -> beats -> confirm, with the no-source path
unchanged.

**Files**

- `backend/app/onboarding/beats.py` - `SKIP_WORDS`, source-stage `InputSpec` (reuse `KNOWLEDGE_INPUT`), `services` stays `optional=False`.
- `backend/app/onboarding/agent.py` - `progress()`, `_completion_reply`, `decline_knowledge`, `prepare_url_turn`, new `prepare_source_profile`, `OnboardingRecord.services_source`, `_URL_EXTRACT_PROMPT`.
- `backend/app/onboarding/tools.py` - `save_profile(..., only_empty: bool = False)`.
- `backend/app/features/onboarding/controller.py` - `_stream_url_turn`, `_run_url_message`, new `run_source_upload`, skip branch in `run_selection`, services sync in `save_onboarding_knowledge_batch`.
- `backend/app/features/onboarding/api.py` - `POST /api/onboarding/source`.
- `backend/app/features/knowledge/service.py` - `_draft_sections_and_extraction` (parallel structure + offerings), new `draft_from_upload_with_profile`.
- `frontend/src/app/(tenant-admin)/(console)/onboarding/page.tsx` - `onFiles` on every stage, skip chip, post-save state re-fetch, `PROCESSING_COPY` entries.
- `frontend/src/lib/onboarding.ts` - stage typing only.

**Technical contract**

- `OnboardingRecord` gains `services_source: Literal["", "owner", "document"] = ""`,
  read and written in `from_jsonb`/`to_jsonb` beside `knowledge_pending`
  (`agent.py:326-462`).
- `progress(record)`: after `paused_beat` and `pending_name`, return
  `("knowledge", beats.KNOWLEDGE_INPUT, False)` when `record.knowledge_pending`
  and no source has been supplied, *before* `next_beat`. Move, do not duplicate,
  the existing branch at `agent.py:766-767`.
- New records start with `knowledge_pending=True` and the beat cursor on
  `owner_display_name`. Delete `_KNOWLEDGE_OFFER` and the flag-setting half of
  `_completion_reply` (`agent.py:691-717`); `decline_knowledge` becomes the
  source-stage skip and keeps its name.
- `beats.SKIP_WORDS = {"skip", "skip for now", "no thanks", "none", "later"}`.
  In `run_message` and `run_message_stream`, when the current beat is
  `owner_display_name` and the trimmed, casefolded text is in `SKIP_WORDS`,
  append the key to `record.skipped`, advance with `selection_reply`, and make
  no model call. "skip" is never written to `draft`.
- `run_selection` accepts `{beat: "owner_display_name", values: ["skip"]}` on the
  same deterministic path (extend the `beat_key == "knowledge"` branch at
  `controller.py:403-413`). No new request field, so no generated-types change.
- `save_profile(draft, args, *, only_empty=False)`: with `only_empty=True`, a
  field is written only when the draft value is empty. Owner-typed values always
  win. `abn` keeps the existing 11-digit normalisation (`tools.py:34-40`).
- URL source (`_stream_url_turn`, `controller.py:655-710`): yield
  `progress: reading_site`, `crawl = await scrape_site(url)`, yield
  `progress: finding_services`, then
  `asyncio.gather(knowledge_service.draft_from_url_text(...), prepare_source_profile(...))`
  under one `asyncio.timeout`. Merge the profile with `only_empty=True`, merge
  candidates through the existing `_merge_document_candidates`
  (`controller.py:253-265`), set `services_source="document"` when the profile
  gained `services`, then yield `progress: review` before `state`.
- `prepare_source_profile(record, text, provider)` replaces the extract half of
  `prepare_url_turn` (`agent.py:1010-1043`): one `extract()` against
  `_URL_EXTRACT_PROMPT`, now listing `business_name, business_type, hours, abn`.
  `services` leaves that prompt - services come from candidates.
- `POST /api/onboarding/source` (multipart `file`) returns
  `OnboardingStateResponse`. Validate with `_reject_upload`
  (`features/knowledge/api.py:95-117`), extract text, then run structure,
  offerings and profile extraction in parallel, merge, checkpoint, return
  `controller.response_from_record(...)`.
- `save_onboarding_knowledge_batch` (`controller.py:750-881`): when
  `services_source != "owner"` and approved candidates exist, set
  `onboarding.draft["services"]` to the approved names in submission order
  (cap 12) and set `services_source="document"`. Owner-typed services are never
  overwritten.
- Fix point for the plan's "never assume can_confirm": replace
  `setCanConfirm(true)` at `page.tsx:897` with `apiFetch("/api/onboarding/state")`
  and `applyStateFields`, keeping `workspace`/`drafts` cleared only on success.

**Test seams**

- `backend/tests/test_onboarding_agent.py` - `progress()` returns the source
  stage before the business-name beat; a fresh record starts on the name beat;
  skip words never land in `draft.owner_display_name`; `decline_knowledge`
  still clears the flag; no `_KNOWLEDGE_OFFER` text in the activation summary.
- `backend/tests/test_onboarding_api.py` - `{beat:"owner_display_name",
  values:["skip"]}` advances without a selection 409; `POST /api/onboarding/source`
  returns state with the merged profile and candidates.
- `backend/tests/test_onboarding_knowledge_batch.py` - services sync writes
  approved names when `services_source != "owner"` and leaves owner services
  alone; `only_empty` leaves an owner-typed field untouched.
- `frontend/e2e/onboarding-source-first.spec.ts` (new) - name -> source ->
  review -> beats -> confirm, with the source mocked at `/api/onboarding/source`
  and the beats answered for real.
- `frontend/e2e/onboarding.spec.ts`, `onboarding-url.spec.ts`,
  `onboarding-go-live.spec.ts` - updated for the new first two stages; the
  no-source path asserted as unchanged (acceptance 7).

**Verify**

```
docker compose run --rm backend pytest tests/test_onboarding_agent.py tests/test_onboarding_api.py tests/test_onboarding_knowledge_batch.py -q
docker compose run --rm --no-deps frontend npx vitest run src/lib
```

## Slice B - Review sheet

**Goal:** a priced, editable review that leads with what the business offers.

**Files**

- `frontend/src/components/knowledge/ReviewSheet.tsx`
- `frontend/src/components/knowledge/types.ts`
- `frontend/src/components/knowledge/offerings.ts`
- `frontend/src/app/(tenant-admin)/(console)/onboarding/page.tsx` (props and save payload)
- `backend/app/features/onboarding/api.py` + `controller.py` (profile patch on the batch)
- `backend/app/features/knowledge/offering_extraction.py` (match predicate)

**Technical contract**

- `WorkingOffering` gains `priceWording: string`; `priceText` stays. One input.
  Serialisation in `toPendingOffering` (`ReviewSheet.tsx:419-443`): a value that
  `parsePriceCents` accepts becomes `price_cents` and clears the wording; any
  other non-empty value becomes `pricing_wording` with `price_cents: null`. Both
  set is not representable from the UI.
- Expanded default: `const pricesMissing = offerings.some((o) => o.price_cents == null && !o.priceWording)`;
  the offerings list renders expanded on first paint when true. Banner copy,
  verbatim: `No prices found here. Add a price, or write it your way, like "from $30".`
- Business details block: business name, business type, hours, contact, and ABN
  only when `draft.abn` is non-empty. Compact rows with an Edit affordance
  (`OwnerFieldRow` idiom, `StorefrontHero.tsx:58-95`). Saved with the review
  through a new optional `profile: dict[str, str]` on
  `OnboardingKnowledgeBatchRequest`, applied in
  `save_onboarding_knowledge_batch` with `save_profile(only_empty=False)` before
  the checkpoint.
- Missing required fields: not rendered as empty rows. `OnboardingStateResponse`
  and `_state_event` gain `missing_required: list[str]` (labels from
  `beats.check_completeness`, required beats only, in beat order). One note
  reads `I'll ask next: {", ".join(missing_required)}.`
- "More about what I read": `KnowledgeDocument` sections collapse behind a
  disclosure closed by default (`ReviewSheet.tsx:398`). Assert on a field
  inside it, never `toBeHidden` - `Sheet` never unmounts (memory gotcha).
- Source line: keep the existing Sources block (`ReviewSheet.tsx:358`) but render
  one compact row per document - `sourceLabel` (`types.ts:91-98`), Replace,
  Remove, then one `Add another source`. Drop the separate `sourcesMode` chrome.
- Possible-match predicate (`offering_extraction.py:594-619`): flag only
  (a) typo - head words more than 4 characters with edit distance <= 2, or
  (b) brand prefix - one normalized name is a prefix of the other and the
  leading leftover token starts at least 3 candidate names. Containment alone is
  no longer a flag. Same-block variants that differ only by case, punctuation or
  diacritics merge in `_reconcile` (`:575-591`) through a folded key. Copy:
  `possible duplicates to check`.

**Test seams**

- `frontend/src/components/knowledge/ReviewSheet.test.tsx` - price mode opens
  expanded with the banner when a price is missing; a numeric entry serialises to
  `price_cents` and a worded entry to `pricing_wording` and never both; the
  business block renders ABN only when present; the missing note lists required
  beats and no empty row appears.
- `frontend/src/components/knowledge/offerings.test.ts` - merge and reconcile
  keep the wording, and a wording candidate never wakes a cents comparison.
- `backend/tests/test_offering_extraction.py` - the barbershop fixture yields 14
  candidates with zero `possible_matches`; a typo pair still flags; the folded
  key merges "Acai Bowl"/"Acai Bowl" with an accent in one segment.
- `backend/tests/test_onboarding_knowledge_batch.py` - the `profile` patch
  persists name/type/hours/contact through both config copies.
- `frontend/e2e/knowledge-review.spec.ts`, `knowledge-review-mobile.spec.ts` -
  the priced-first sheet, expanded default, and the collapsed source text.

**Verify**

```
docker compose run --rm --no-deps frontend npx vitest run src/components/knowledge
docker compose run --rm backend pytest tests/test_offering_extraction.py tests/test_onboarding_knowledge_batch.py -q
```

## Slice C - Data and assistant wiring

**Goal:** one price story everywhere the assistant reads.

**Files**

- `backend/app/onboarding/flow.py` - `PendingOffering`, `merge_offerings`
- `backend/app/features/business/service.py` - `reconcile_offerings_batch`
- `backend/app/features/onboarding/controller.py` - conflict detection
- `backend/app/services/context_package.py` - `ActiveOffering`, `format_offerings`
- `backend/app/ingestion/chunker.py`, `backend/app/ingestion/pipeline.py`
- `backend/app/agents/agent_node.py` - `_recommend_items_impl`, `show_catalog`

**Technical contract**

- `PendingOffering.pricing_wording: str = Field(default="", max_length=120)`
  plus a `model_validator` rejecting a value set alongside `price_cents` - RF-4's
  mutual exclusion (`features/business/api.py:289-292`), now at the draft layer
  too. 120 is the shipped cap (`test_business_api.py:1387-1418`).
- `merge_offerings` (`flow.py:283-366`): add `pricing_wording` to the
  `preferred` precedence chain, union sources, and add
  `wording_options: list[str]` when two non-empty wordings differ. `price_options`
  stays cents-only. `needs_review` rises when either conflicts.
- `save_onboarding_knowledge_batch` conflict check (`controller.py:788-799`)
  counts a wording conflict as a conflict, message
  `{name}: multiple prices found - resolve before publishing`.
- `reconcile_offerings_batch` (`business/service.py:429-450`): write
  `pricing_wording` on both the update and the insert. `create_offerings_batch`
  already does (`:376-383`).
- `ActiveOffering.pricing_wording: str | None`; the query at
  `context_package.py:180` selects it; `format_offerings` prints the wording
  verbatim in the price position when `price_cents` is null. Keep the wording
  inside `owner_material` (`:158-160`) - that is what keeps a wording figure on
  the allowed side of the money guard (C-1) without the model inventing one.
- `chunk_catalog_item(item_id, name, description, price_cents, pricing_wording)`
  (`chunker.py:146-149`) and the `ingest_offerings` select (`pipeline.py:178`).
- `_recommend_items_impl` (`agent_node.py:368-384`) selects and returns
  `pricing_wording`; the `show_catalog` payload (`:946-966`) adds
  `"pricing_wording": offering.pricing_wording`. The card's cap and page link are
  ticket 30.

**Test seams**

- `backend/tests/test_offering_extraction.py` - wording supersedes and conflicts
  through `merge_offerings`; both-set is rejected.
- `backend/tests/test_business_api.py` - publish writes the wording and keeps
  RF-4's mutual exclusion at the API layer.
- `backend/tests/test_context_package.py` - `format_offerings` prints the
  wording, `owner_material` carries it, and a 96-item tenant stays within the
  inline budget.
- `backend/tests/test_recommendation_agent.py` - `recommend_items` returns
  wording; `show_catalog` payload carries it for every offering.
- `backend/tests/test_validation_gate.py` - a reply quoting owner wording passes;
  an invented figure still fails.

**Verify**

```
docker compose run --rm backend pytest tests/test_offering_extraction.py tests/test_context_package.py tests/test_recommendation_agent.py tests/test_business_api.py tests/test_validation_gate.py -q
```

## Slice D - Crawl and processing speed

**Goal:** find the offerings page first, read it faster, and say where the time
went.

**Files**

- `backend/app/ingestion/site.py`
- `backend/app/features/knowledge/service.py` (`_draft_sections_and_extraction`)
- `backend/app/features/onboarding/controller.py` (timing log)
- `backend/scripts/crawl_probe.py` (new)
- `backend/tests/test_site_discovery.py`, `test_site_crawl.py`, `test_url_ingestion.py`

**Technical contract**

- Constants (`site.py:48-56`): `DEFAULT_CONCURRENCY = 6`,
  `DEFAULT_TIMEOUT_S = 10.0`. `DEFAULT_MAX_PAGES = 10` and
  `DEFAULT_MAX_CHARS = 11_500` unchanged. Per-page caps unchanged
  (4,000 / 6,000).
- `_SOURCE_RANK` (`:162`) becomes `{"home": 0, "nav": 1, "body": 2, "sitemap": 3}`
  and `discover_pages` considers in that order (`:528-534`).
- `page_priority` (`:257-266`) tiers: 1 offerings
  (`services, service, treatments, menu, menus, pricing, prices, price, rates,
  what, repairs`), 2 about (`about, story, team, who, mission`), 3 contact
  (`contact, location, locations, hours, opening, find, visit, directions`), then
  the existing faq/policies/booking tiers, then 99.
- `extract_links` (`:290-315`) returns `(url, label)`; `page_priority(url, label)`
  tests the path tokens unioned with the anchor text tokens, casefolded.
- Sitemaps are fetched only when nav and body contain no offerings-tier page.
  Today `_sitemap_urls` is awaited unconditionally at `:494`.
- `discover_pages(..., legacy_discovery: bool = False)` keeps the pre-ticket
  constants, order, priority table and eager sitemap for the probe only, with a
  `ponytail:` comment naming the ceiling and the removal path (delete once the
  evidence table is filed).
- `_draft_sections_and_extraction` (`service.py:371-398`) runs
  `structure_document` and `_extraction` under `asyncio.gather` inside the
  existing `_DRAFT_TIMEOUT_SECONDS`, keeping the `_StageFailure` stage labels.
- Source turn emits one log line, `logger.info("onboarding source timing",
  extra={"tenant": ..., "crawl_ms": ..., "draft_ms": ..., "structure_ms": ...,
  "offerings_ms": ..., "profile_ms": ..., "total_ms": ...})`, from
  `_stream_url_turn`. Sub-stage values come from the gathered tasks' own
  measurement, not from re-timing.
- Progress stages: `reading_site` before the fetch, `finding_services` before
  `gather`, `review` before `state`. `PROCESSING_COPY` in `page.tsx:105-107`
  gains the two new keys.

**`backend/scripts/crawl_probe.py`**

`python -m scripts.crawl_probe --url <u> --label <name> --json <path>` runs
`crawl_site` twice on the same URL - `legacy_discovery=True` with
`concurrency=3, timeout_s=30` and the new defaults - and prints one row:
pages, chars, wall ms, `timed_out`, `skipped`, and an offering-name overlap count
against the legacy text. Run from the backend container.

**Validation matrix** (evidence table under
`docs/agencx/evidence/onboarding-source-2026-10/`)

| Band | URLs | Bar |
|---|---|---|
| Small | `frontend/public/fixtures/example-business.html`, a 3-page fixture | core fields found; >= 95% of current crawl coverage; optimized faster |
| Mid | stylesbyjaimy, Sydney Dental Care, Phone Clinic | same, p50 ~5s on the primary model |
| Big | Sabbaba 96-item menu, The Grounds, a multi-location clinic | >= 90% coverage; p50 6-7s; no junk pages |

No guarantee is claimed on the fallback model, large PDFs, or slow sites.

**Test seams**

- `backend/tests/test_site_discovery.py` - offerings-tier pages outrank about;
  sitemaps are not fetched when the nav carries an offerings page; a nav anchor
  label alone can promote a page; the pasted subpath stays priority 0.
- `backend/tests/test_site_crawl.py` - never more than 6 page reads in flight;
  the 10s deadline cancels and reports `timed_out`; the total never exceeds
  11,500 characters.
- `backend/tests/test_url_ingestion.py` - structure and offerings start
  concurrently (a fake provider asserts overlap, so it fails on a serial
  implementation).
- `frontend/e2e/onboarding-url.spec.ts` - the three progress stamps appear in
  order and `Reading your site` clears.

**Verify**

```
docker compose run --rm backend pytest tests/test_site_discovery.py tests/test_site_crawl.py tests/test_url_ingestion.py -q
docker compose run --rm backend python -m scripts.crawl_probe --url http://frontend:3000/fixtures/example-business.html --label fixture
```

## Collisions with shipped behaviour

| Collision | Resolution |
|---|---|
| `services` is a required beat (`beats.py:278`) and the URL prompt fills it (`agent.py:977`) | Keep it required and fill it from approved candidate names with `services_source`; drop `services` from the source prompt |
| `knowledge_pending`/`KNOWLEDGE_INPUT`/`decline_knowledge` are pinned by tests (`test_onboarding_agent.py:32,876-881`) | Keep all three names; change when the flag is set and where `progress()` checks it. Founder-confirmed default: reuse the flag, do not rename it |
| RF-4 enforces `price_cents` XOR `pricing_wording` at the API (`business/api.py:289-292`) | Enforce the same at `PendingOffering` so a draft cannot reach publish both-set; the API stays the second gate |
| `pricing_wording` is already on the frontend catalog type and rendered (`CatalogCard.tsx:12,56`) | Only the payload changes; no card rendering work in this ticket |
| Ticket 28 already put offerings first in the review (`3823740`) | Slice B extends that ordering; it does not redo it |
| `reconcile_offerings_batch` ignores wording (`service.py:429-450`) | Add the column to both statements - the one-line gap that would otherwise null every wording at go-live |
| `progress()` cannot read `documents` | `review` is an SSE progress event, never a state stage |
| D46 fixed 3 concurrent / 30s (`site.py:50-51`) | 6 / 10s with the probe as the evidence; the timeout skip list is where big-site coverage will show up |

## Open - builder decides

| Question | Safe default |
|---|---|
| Cap on synced `services` | 12, storefront order |
| Replace or append on the services sync | Replace |
| `_URL_EXTRACT_CHARS` (`agent.py:972`) = 4,000 against an 11,500 crawl | Keep 4,000 unless acceptance 1/3 fails on a big site, then 8,000 |
| Whether `legacy_discovery` is one flag or several | One keyword-only flag, probe-only, `ponytail:` comment |
| `wording_options` vs reusing `price_options` | New `list[str]`; cents stay integers |
| Profile patch type on the batch endpoint | `dict[str, str]`, unknown keys rejected by `ProfileDraft` |
| Where the skip action lives in the UI | A dashed chip from `InputSpec`, same as the existing knowledge skip |

## Verification

Run at the branch tip on 2026-10-27.

| Surface | Command | Result |
|---|---|---|
| Backend tests | `docker compose run --rm backend pytest -q` | 1,624 passed |
| Backend lint | `docker compose run --rm backend ruff check .` | clean |
| Backend format | `docker compose run --rm backend ruff format --check .` | 259 files already formatted |
| Backend types | `docker compose run --rm backend mypy` | no issues in 256 source files |
| Frontend lint | `make lint-frontend` | eslint clean; `check:tokens` OK |
| Frontend types | `make typecheck-frontend` | `tsc --noEmit` clean |
| Frontend tests | `make test-frontend` | 43 files, 396 tests passed |
| Frontend build | `make build` | green; the first invocation hit the known `next/font/google` fetch failure and the retry compiled clean |
| Generated types | `cd frontend && npm run gen:types -- --check` | `api-types.ts is up to date` (runs on the host; the container has no `uv`) |
| End to end | `make test-e2e` | 255 passed, 0 failed (6.1m) |

The two `tab-shell-mobile` navigation tests have timed out on earlier runs of
this branch; this run passed them, so the pair stays recorded as the known flake
and not as a regression.

Crawl probe, three runs per URL, medians (full raw runs in the
[evidence table](../../evidence/onboarding-source-2026-10/README.md)):

| Label | Pages (legacy / new) | Chars (legacy / new) | Legacy ms | New ms | Overlap |
|---|---|---|---|---|---|
| fixture | 5 / 5 | 3,664 / 3,664 | 461 | 145 | 6/6 |
| python.org | 6 / 6 | 11,468 / 11,468 | 967 | 1,350 | 0/0 |
| The Grounds | 6 / 4 | 11,443 / 11,440 | 6,281 | 1,882 | 0/0 |
| nandos.com.au | 9 / 9 | 11,484 / 7,657 | 1,575 | 1,676 | 2/3 |

The migration runner (`make migrate`) was already at
`0038_conversations_resolved_at.sql`; this ticket adds no migration.

## Definition of done

- The slice commits (six feature commits plus three fixes), each with its
  slice's verify command green and the output pasted into this file's
  Verification section.
- Acceptance scenarios 1-5, 7 and 8 demonstrated: backend tests for stage order,
  fill-empty merge, services sync, review profile save, pricing wording,
  merge/conflict, duplicate rules, crawl discovery and parallel calls; frontend
  tests for review price mode, business details, missing note, price
  serialisation; E2E for name -> source -> review -> beats -> confirm and the URL
  and PDF no-price paths.
- Crawl evidence table with the nine URLs, plus per-stage timing logs showing the
  real `total_ms`.
- `docs/agencx/design/api-contract.md` updated for the source endpoint, the
  profile patch, `missing_required`, and `pricing_wording` in the catalog payload.
- `docs/agencx/design/frontend.md` updated for the review sheet's priced-first
  mode.
- ADRs added to `docs/agencx/design/decisions.md`: source-first onboarding;
  pricing wording in assistant context. Numbered from D47.
- `docs/agencx/progress.md` row for 29, and `docs/agencx/spec/README.md` active
  row.
- `.agents/memory.md` gains the non-obvious ones only: the wording-in-
  `owner_material` money-guard dependency, `progress()`'s inability to read
  documents, and the reconcile wording gap.

## Delivered

| Slice | Commit | What landed |
|---|---|---|
| A1 | `65ef878` | Flow inverted to name -> source -> review -> beats -> confirm: the source stage is second, skip words resolve deterministically and never reach the draft, `save_profile(only_empty=True)` lets an owner answer win, and `services_source` decides the services sync. |
| A2 | `b8d8b19` | The source turn runs structure, offerings and the profile read together under one timeout; `POST /api/onboarding/source` is the upload twin; `_URL_EXTRACT_PROMPT` no longer extracts `services`; the turn logs one `onboarding source timing` line. |
| A3 | `3e9dd7c` | The onboarding screen treats the source as a stage: "+" on every composer, a stage-aware upload target, the review opens only on a pending draft, and a review save re-reads `/api/onboarding/state` instead of assuming `can_confirm`. |
| B | `ef70289` | The review sheet leads with priced services, opens in edit mode with the missing-price banner, takes one price field in two shapes, shows the found business details, one "I'll ask next" note, collapsed source text and compact source rows; the batch carries the optional `profile` map. |
| C | `7556f67` | `pricing_wording` rides the candidate, the merge and the conflict check, the publish/reconcile path, catalog chunks, `recommend_items` and `show_catalog`; it stays inside `owner_material` so the money guard can reconcile a quoted wording. |
| D | `ab335b3`, `a29cc31`, `68885f6` | Offerings-first discovery with the anchor label, the sitemap only when nav/body sell nothing, six concurrent reads under 10s, budget-satisfied early exit, a thin-result sitemap fallback, and the fallback's depth-first ranking with a two-page cap per first path segment. |

Slice A shipped as three commits plus one fix commit:
`492d167` closed four source-fill ownership edges. The profile-read failure is
swallowed at one seam (`prepare_source_profile` returns `None`, because
`LimitTimeout` is not a `TimeoutError`), and the turn gathers with
`return_exceptions=True` so one failure cannot leak its sibling. The source
stage reuses `knowledge_pending` and the `knowledge` wire key rather than
renaming either. The `active/` ticket's acceptance row for the full-list card
belongs to ticket 30 and is not shipped here.

## Known limitations

- `www.nandos.com.au` recovers 7,657 of the legacy 11,484 characters (66.7%,
  2/3 offering names), not the 90% bar. The depth-first fallback stops
  `/menu-item/*` from filling the budget, but the site's shallow pages are
  mostly chrome and the rich legacy pages are deeper or untiered; a second
  mechanism would be needed and is deliberately not added.
- The 5s p50 target was not measured end to end. The probe measures crawl wall
  time only; the draft, structure, offerings and profile calls are not in those
  numbers.
- No guarantee is claimed on the fallback model, large PDFs or slow sites.
- Five of the nine validation-matrix URLs (stylesbyjaimy, Sydney Dental Care,
  Phone Clinic, the Sabbaba 96-item menu, a multi-location clinic) have no row:
  stylesbyjaimy and Sabbaba did not resolve from the container, and the other
  three were not identified by a verifiable URL.

## Blockers

None.
