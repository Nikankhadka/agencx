# Archive - the pre-Agencx documentation

Historical and point-in-time documentation is moved here so the current set
under `docs/agencx/` has no duplicate active records. Nothing here is edited or
maintained. It is reference material for history, evidence, and provenance.

## What is where

| Path | What it was | Where the info lives now |
|---|---|---|
| `PROGRESS.md` | Wren ticket tracker (T-001..T-044, phases 0-5) | `docs/agencx/progress.md` carries every ticket forward with BUILT status + commit evidence |
| `DEMO.md` | Wren demo walkthrough (tenants, credentials, troubleshooting) | Superseded by `docs/agencx/running.md` |
| `source/` | Frozen Wren planning: `product-requirements.md`, `architecture.md` | `docs/agencx/prd.md` + `docs/agencx/architecture.md` (rewritten) |
| `agencx-planning/` | The pre-merge Agencx plan: PRD, architecture, design (incl. HTML prototypes), phases 0-5, stage-2 backlog | Rewritten from scratch into the new set; ticket-level detail is re-cut in `docs/agencx/spec/` |
| `wren-design/` | Wren implementation truth: `database.md`, `frontend.md` | `docs/agencx/design/database.md` + `design/frontend.md` (rewritten) |
| `plan/agencx-merge.md` | The merge plan that scoped this restructure | Its locked decisions and flow design are the spine of the new set |
| `artifacts/` | Wren build evidence: eval report, security write-up, generalization proof | Referenced from `docs/agencx/progress.md`; the evidence still stands |
| `industry-standard-gap.md` | Point-in-time Agencx industry-standard assessment | The current gap summary is in `docs/agencx/architecture.md`; open items in `docs/agencx/spec/active/12-refinement.md` R-5 |
| `phase1-complete/` | Delivered Phase 1 ticket records ([index](phase1-complete/README.md)): foundation through auth OTP, R-1/R-2, walkthrough evidence, and M-7 storefront | Active work is in `docs/agencx/spec/active/`; status in `docs/agencx/progress.md` |
| `prototypes/agencx-storefront-customer-v3.html` | Superseded storefront prototype | Interaction vocabulary only |
| `prototypes/agencx-storefront-customer-v4.html` | Approved original M-7 storefront rebuild | Implemented in `frontend/src/app/[slug]/` and finalized by v5 |
| `prototypes/agencx-storefront-customer-v5.html` | Final M-7 sparse-catalog amendment | Implemented in `frontend/src/app/[slug]/`; archived after founder acceptance on 2026-09-24 |

## Retired content notes

- The HTML prototypes (`agencx-planning/design/prototypes/*.html`) were structural
  references only. They were promoted to `docs/agencx/design/prototypes/` and
  reworked (crimson identity, monogram mark, Sababa copy, D18 bottom tab bar) on
  2026-08-21; the pre-rework cleaning copy, teal accent, and Hivee emblem here are
  retained for provenance only.
- Every file under `source/`, `wren-design/`, `agencx-planning/`, plus
  `PROGRESS.md`, `DEMO.md`, and `industry-standard-gap.md`, carries a
  SUPERSEDED banner naming its live replacement. The stray `Untitled`
  dictation file was deleted 2026-09-18.
