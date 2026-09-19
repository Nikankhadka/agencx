# 20: Required services and a skip-free interview

**Status:** Merged 2026-09-19. Founder-decided 2026-09-18.
**Phase 1 area:** Onboarding interview.

Numbering note: 17 is reserved for the M-7 storefront redesign, 18 was absorbed
into [12-refinement.md](12-refinement.md), and 19 is intent and identity, so 20
is the next free ticket.

## Summary

Make `services` (a basic overview of what the business offers, priced in the
owner's own rough words if they want) a required onboarding field, remove the
"Skip for now" chip from every beat, give the knowledge ask a chip of its own,
and give Home a neutral greeting fallback when the owner's name was never
captured.

- Required set becomes: `business_name`, `business_type`, `hours`, `contact`,
  `services`.
- Optional beats keep their defaults: `headcount` -> "just me", `abn` ->
  `"none"` (No), `gst` -> "no", `customer_voice_preset` -> first preset.
  `owner_display_name` stays optional with no default - unanswered after two
  asks it falls to `skipped` (blank), exactly as it does today.
- No beat renders a "Skip for now" chip. `__skip__` and `SkipPayload` are
  deleted: no caller remains.
- The knowledge stage keeps an always-visible "Skip for now" chip, submitting
  `{selection: {beat: "knowledge", values: ["skip"]}}`. Knowledge never gates
  go-live, so declining it is one tap rather than a word the owner has to
  guess. Typing "skip" still works.
- The services beat asks "What do you offer, and roughly what does it cost?"
- Home greets the owner's name, then the business name, then `"admin"`.
- The storefront renders a "What we offer" block from `services` when the
  catalog is empty.

## Why

Founder decision 2026-09-18: a business without a stated service has no
business, so the service overview is as compulsory as the business name.
Skipping UI is unnecessary where a truthful default already exists (team,
ABN, GST, voice), and where the field states a real business fact (name,
type, hours, contact, services) the existing defer/pause path keeps go-live
honest instead of storing fiction. The owner's name is not a business fact:
any staff member may operate the app, so it stays optional and the greeting
falls back rather than blocking.

History this reverses: W-2 introduced the chip with the two-ask cap, W-7
removed it as robotic, and PR #42 (`7635dde`) reintroduced it for resumable
explicit skips. This ticket removes the chip for good - the cap and defaults
now cover every optional beat except the owner's name, which drops to a blank
on the same cap.

## Locked decisions (founder, 2026-09-18)

1. `services` is required. Unanswered twice: defer a pass, return, then pause
   with go-live blocked. The same path required beats already use.
2. `owner_display_name` stays optional. Blank is allowed; Home uses a neutral
   greeting fallback.
3. The "Skip for now" chip is not rendered anywhere.
4. Defaults stay as they are: `just me`, `none` (No), `no`, first voice preset.
5. Knowledge stays skippable and keeps the one Skip chip left in the product.
6. `contact` stays required with no default for now.
7. Home's fallback is the owner's name, then the business name, then "admin".
8. `services` may carry the owner's own rough price text. It is copied, never
   parsed - see the split below.

## Current vs proposed behavior (conventions 5.1)

| | Current | Proposed |
|---|---|---|
| `services` beat | optional; "Skip for now"; skipped after two asks; go-live possible with no offerings typed (`12-refinement.md:93-94`) | required; defer then pause; go-live blocked until it has content |
| Skip chip | rendered on every optional beat (`beats.py:377-378`); tap persists `skipped` (`controller.py:424-434`) | not rendered anywhere |
| Required set | `business_name`, `business_type`, `hours`, `contact` | plus `services` |
| Unanswered optional beat | default if it has one, else `skipped` (`agent.py:766-774`) | unchanged |
| Owner name blank | Home greets "there" (`home/page.tsx:67`) | Home greets the chosen fallback |
| Knowledge | optional, "say skip", never gates, no chip | unchanged, plus an always-visible Skip chip |
| Services ask | "What do you offer?" | "What do you offer, and roughly what does it cost?" |
| Empty catalog on the storefront | nothing but the assistant's invitation | a "What we offer" block reading back `services` |

## Accepted consequence

A menu or price-list upload can no longer satisfy an unanswered `services`
beat: the knowledge ask only opens after every beat completes
(`agent.py:738-739`), so it cannot rescue a paused interview. A URL pasted
mid-interview still can, because `prepare_url_turn` extracts profile fields
into the draft (`agent.py:1004-1005`). Founder accepted this on 2026-09-18 as
part of making services compulsory; the old promise in `12-refinement.md`
("go-live without confirmed offerings") must be rewritten with it.

## The services/offerings split (binding)

`services` is `tenant_config.config.profile.services`: a normalized list of
owner-authored strings, a plain overview that may carry rough price ranges in
the owner's own words ("coffee, $4-$10"), copied verbatim. Offerings are the
offerings table, with exact integer-cent prices. The two may overlap.

- Services text never auto-creates offering rows.
- Offerings never auto-rewrite the overview.
- Every computed or quoted amount still comes from the pricing engine. The
  overview states nothing the owner did not state, and the product quotes
  nothing from it. This is the deterministic-pricing hard rule, unchanged.

The storefront gives the "What we offer" heading to offerings whenever the
catalog has anything in it, so the two blocks never render together and never
disagree.

## What shipped

Backend:

- `backend/app/features/business/service.py` - the storefront read model
  publishes `services` through `read_services`, not `profile_field`. M-7
  landed with the latter, which rendered the list's Python repr onto the
  customer's page; this ticket's first commit is that fix.
- `backend/app/features/business/public_api.py`, `api.py` - `services` is
  `list[str]` on both the storefront and the owner's booking page.
- `backend/app/onboarding/beats.py` - `services` is required, carries the new
  ask and example, and `input_spec` appends no Skip chip. `KNOWLEDGE_INPUT`
  carries the one chip left.
- `backend/app/onboarding/agent.py` - the extractor keeps a price in the same
  services entry it was typed with; `decline_knowledge` closes the knowledge
  ask from the chip with no model call.
- `backend/app/features/onboarding/controller.py` - `run_selection` answers a
  `knowledge` selection before any beat cursor is consulted, since the
  knowledge ask sits past the last beat. The `__skip__` branch is gone.
- `backend/app/features/onboarding/api.py` - `SkipPayload` and the `skip`
  field are deleted.

Frontend:

- `frontend/src/components/ui/ServicesOverview.tsx` - new, shared by the
  public storefront and the owner's preview of it so the preview cannot lie.
- `frontend/src/app/[slug]/Storefront.tsx`, `StorefrontHero.tsx` - the
  overview renders in the catalog-empty branch; the hero subtitle joins the
  list.
- `frontend/src/app/(tenant-admin)/(console)/business/page/page.tsx` - the
  preview falls back to the overview with nothing priced.
- `frontend/src/app/(tenant-admin)/(console)/home/page.tsx` - owner name,
  then business name, then "admin".
- `frontend/src/app/(tenant-admin)/(console)/business/details/components/ServicesSheet.tsx`
  - the placeholder shows a price in the line.
- `frontend/e2e/onboarding-resume.spec.ts` - rewritten around the knowledge
  chip; `frontend/e2e/storefront.spec.ts` - the repr regression and the
  catalog-empty overview.

Docs: `12-refinement.md`, `design/api-contract.md`, `design/decisions.md`
(new ADR), `design/frontend.md`, `progress.md`.

## Definition of done

- `services` is required; go-live is blocked until it has content, through
  the same defer/pause/retry path as other required beats.
- No beat renders "Skip for now"; unresolvable optional beats resolve by
  default or drop to `skipped` (owner name only).
- The knowledge ask carries an always-visible Skip chip and still never gates
  go-live.
- Home greets the owner's name, the business name, or "admin".
- The storefront and its preview read back the owner's overview when the
  catalog is empty, verbatim, quoting nothing.
- Docs and ADR updated; `make check` green; e2e updated.

## Questions the building session closed

1. Fallback copy: owner name, then business name, then "admin".
2. `__skip__` is deleted, route and payload and tests. No caller remained.
3. `contact` keeps the pause. No auth lookup for a default email this ticket.
4. `headcount` and `customer_voice_preset` stay optional with defaults.
