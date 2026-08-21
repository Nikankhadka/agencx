# Archive - the pre-Agencx documentation

Everything documented before the Agencx restructure (2026-08-20), moved here so the new
canonical set under `docs/agencx/` has no duplicates. Nothing here is edited or
maintained. It is reference material for history, evidence, and provenance.

## What is where

| Path | What it was | Where the info lives now |
|---|---|---|
| `PROGRESS.md` | Wren ticket tracker (T-001..T-044, phases 0-5) | `docs/agencx/progress.md` carries every ticket forward with BUILT status + commit evidence |
| `DEMO.md` | Wren demo walkthrough (tenants, credentials, troubleshooting) | Operationally still true while the demo world exists; the rebrand (B-1) and login-in-chat (O-2) will supersede it |
| `source/` | Frozen Wren planning: `product-requirements.md`, `architecture.md` | `docs/agencx/prd.md` + `docs/agencx/architecture.md` (rewritten) |
| `agencx-planning/` | The pre-merge Agencx plan: PRD, architecture, design (incl. HTML prototypes), phases 0-5, stage-2 backlog | Rewritten from scratch into the new set; ticket-level detail is re-cut in `docs/agencx/spec/` |
| `wren-design/` | Wren implementation truth: `database.md`, `frontend.md` | `docs/agencx/design/database.md` + `design/frontend.md` (rewritten) |
| `plan/agencx-merge.md` | The merge plan that scoped this restructure | Its locked decisions and flow design are the spine of the new set |
| `artifacts/` | Wren build evidence: eval report, security write-up, generalization proof (+ stray `Untitled` dictation file) | Referenced from `docs/agencx/progress.md`; the evidence still stands |

## Retired content notes

- The HTML prototypes (`agencx-planning/design/prototypes/*.html`) were structural
  references only. They were promoted to `docs/agencx/design/prototypes/` and
  reworked (crimson identity, monogram mark, Sababa copy, D18 bottom tab bar) on
  2026-08-21; the pre-rework cleaning copy, teal accent, and Hivee emblem here are
  retained for provenance only.
- `Untitled` is a stray dictation file of the restructure request itself; kept for
  provenance, it is not documentation.