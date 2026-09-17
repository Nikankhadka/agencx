# Walkthrough round 2 evidence (2026-09-05)

**Status:** Done - merged.
**Phase 1 area:** Walkthrough fixes.

A second founder walkthrough of the running onboarding and document-review
flow, supported by repository scans and planning, refined the phase. This
file records the walkthrough's observations, the founder's clarified
preferences, the implementation evidence at the time, and the boundary
between reported symptoms, confirmed code behavior, suspected causes, and
outstanding browser verification. The tickets live in
[13-walkthrough.md](../completed/13-walkthrough.md) and reference this file
rather than restating it. The original PDF behind the 40-row review output
is unavailable, so the pasted review output is preserved here as reported
but cannot establish which prices, descriptions, or offerings correctly
reflect the source - an explicit verification boundary, not a gap in this
record.

## The founder's clarified preferences

The agreed product decisions preserved in the refined tickets:

- Keep the existing business-information, hours, location, policies, and
  other-information sections; improve their readability and editing without
  discarding factual detail.
- Show five offerings initially. "Review all" opens the editor with five
  offerings per page.
- Suggest possible duplicates and let the owner combine them or keep both.
- Preserve complex pricing context and flag ambiguity instead of inventing a
  flat price.
- Let uploads process responsively while the owner remains on the page.
- Correct clear spelling mistakes in ordinary descriptions and offerings using
  the existing model call; preserve personal names and brand names unless
  explicitly corrected.
- Quotation functionality and a full pricing-rule editor remain future work.

## Reported observations (from the pasted review output and walkthrough)

The pasted review output proves what the owner reported seeing. The concrete
defects and phrasing flags in it:

- Offering names rendered as sentence fragments or prose joins
  (`"Bowl is,"`, `"the,"`, `"Plate and Pita Pocket both run"`), none of which
  is a sellable item.
- A possible duplicate pair reported for review (`"coffe"` alongside
  `"coffee drinks"`), where the owner's preferred outcome - keep both, or
  merge only on explicit choice - is not yet reflected in how the sheet
  behaves.
- Displayed amounts in the output. Because the original PDF is unavailable,
  which amount (if any) is correct is not established; the amounts are
  recorded as reported and flagged for re-extraction from source when the
  PDF regression fixture becomes available.

The full 40-row pasted output is greater than the examples above; only the
observations the notes name are transcribed here because the paste itself is
not preserved verbatim. Where a later step reproduces the source, the
regression fixture replaces this table as the authority.

| # | Reported (pasted review) | Ticket | Classification |
|---|---|---|---|
| 1 | Offering name fragments: "Bowl is", "the" | W-6 | Symptom |
| 2 | Prose-joined offering names: "Plate and Pita Pocket both run" | W-6 | Symptom |
| 3 | Possible duplicate pair: "coffe" / "coffee drinks" | W-6, W-8 | Symptom |
| 4 | Displayed amounts (source-correctness not established) | W-6 | Symptom |
| 5 | Whole catalogue or raw sections in the review sheet | W-8 | Symptom |
| 6 | Complex price context (ranges, "from", units) flattened or dropped | W-6 | Symptom |
| 7 | Descriptions missing or invented | W-6 | Symptom |
| 8 | Review sheet hard to scan when many candidates | W-8 | Symptom |
| 9 | Same text twice within a single reply (duplicated names) | W-9 | Symptom |

## Confirmed code behavior, suspected causes, and outstanding verification

A repository scan separated what is real in the code from what remains a
runtime hypothesis. This is read-only evidence; none of it is a shipped fix.

| Area | Status | Evidence |
|---|---|---|
| Reply context includes the current owner message twice | Confirmed code | [agent.py:688-713](../../../../backend/app/onboarding/agent.py#L688-L713): `record.history.append({...admin_message})` (line 691) runs before `reply_msgs` is built, whose `record.history[-3:]` loop (lines 711-712) includes that just-appended message, then `admin_message` is appended again (line 713). Its relationship to the reported duplicated names is a **suspected cause** pending browser reproduction |
| Review-return paths skip slug prefill | Confirmed code | `saveKnowledge`/`discardKnowledge` set confirm state without running `applyStateFields`' slug prefill (see [page.tsx:458-499](../../../../frontend/src/app/(tenant-admin)/(console)/onboarding/page.tsx#L458-L499) and [page.tsx:141-157](../../../../frontend/src/app/(tenant-admin)/(console)/onboarding/page.tsx#L141-L157)). Requires browser reproduction against the go-live screen to call the runtime cause established |
| Upload stamp is client-side only, non-streamed | Confirmed code | [page.tsx:398-417](../../../../frontend/src/app/(tenant-admin)/(console)/onboarding/page.tsx#L398-L417) - a static `"adding…"` stamp over a single non-streamed `POST /api/knowledge/drafts/upload`; no progress events, so any progress shown is client-side animation, never fabricated percentages |
| Review sheet renders every candidate in one scroll | Confirmed code | [ReviewSheet.tsx:134-212](../../../../frontend/src/components/knowledge/ReviewSheet.tsx#L134-L212) - a single `offerings.map`, no pagination; duplicates are a hard save block (`hasDuplicateNames`, [ReviewSheet.tsx:257-264](../../../../frontend/src/components/knowledge/ReviewSheet.tsx#L257-L264)), not combine/keep-both choices; price conflicts surface as a "choose one" option row |
| Candidate price/description/provenance fields | Confirmed code | [flow.py:56-76](../../../../backend/app/onboarding/flow.py#L56-L76) - `PendingOffering` carries `name, description, price_cents, sources`; no identity, provenance, source-reference, complex-price-context, review-issue, or possible-match fields yet (proposed in W-6/W-8 contract extensions) |
| Merge rule for overlapping candidate | Confirmed code | [flow.py:78-99](../../../../backend/app/onboarding/flow.py#L78-L99) - document values win an overlap; [agent.py:228-246](../../../../backend/app/onboarding/agent.py#L228-L246) re-merges by `normalize_name` |
| Extraction is heading-limited / prose-splitting | Confirmed code | `offering_candidates.py` derives candidates deterministically from `"What we offer"`/`"Prices"`; no whole-source, section-spanning item extraction or reference-resolution price pass yet (scope of W-6) |
| SSE vs ordinary request split | Confirmed code | typed answers stream over SSE; chip, resume, and upload use ordinary requests (see [page.tsx:398-425](../../../../frontend/src/app/(tenant-admin)/(console)/onboarding/page.tsx#L398-L425) for the non-streamed upload). A `fetch` entry in DevTools is not evidence of polling |
| "Answering…" duplicate pending indicator | Outstanding browser verification | The status line's "Answering…" and the thread's thinking dots are candidate duplicates (W-3); reproduce in the browser before runtime claim |

Outstanding browser verification is required before any of the above is
declared the established runtime cause. Bug fixes begin with an E2E
reproduction through the owner-facing surface; none of the W-3 through W-9
specs claim a runtime fix from these scans.

## Requirement ownership

One owning ticket per requirement, with dependency links instead of duplicated
acceptance criteria:

| Concern | Owning ticket |
|---|---|
| SSE versus polling; pending indicators; repeated input placeholder | [W-3](../completed/13-walkthrough.md#w-3-keep-the-onboarding-thread-clear-and-responsive) |
| Slug prefill, review-return paths, and actionable go-live errors | [W-4](../completed/13-walkthrough.md#w-4-complete-go-live-address-handling) |
| Customer answers combining confirmed offerings and knowledge | [W-5](../completed/13-walkthrough.md#w-5-answer-from-confirmed-offerings-and-knowledge-together) |
| Offering names, descriptions, source-backed prices, duplicate proposals | [W-6](../completed/13-walkthrough.md#w-6-extract-accurate-offerings-from-the-complete-source) |
| Five-item preview, pagination, editing, duplicate decisions | [W-8](../completed/13-walkthrough.md#w-8-review-a-large-import-without-losing-information) |
| Readable, editable knowledge sections | [W-8](../completed/13-walkthrough.md#w-8-review-a-large-import-without-losing-information) |
| Repeated names, conservative wording cleanup, conversational corrections, the customer-assistant contract and voice | [W-9](../completed/13-walkthrough.md#w-9-definitive-onboarding-and-customer-assistant-contract) |
