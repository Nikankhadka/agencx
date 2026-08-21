# Phase 1 - Foundation (A)

The doc restructure that stands up the canonical Agencx set and re-points every
entry point at it. Both tickets are **done**.

Tickets in this file:

- A-1: Docs restructure + archive
- A-2: Pointer updates

---

## A-1: Docs restructure + archive

### Summary

Move the pre-Agencx documentation into `docs/archive/` (git mv, history
preserved) and stand up the canonical Agencx set under `docs/agencx/`:
`prd.md`, `architecture.md`, `progress.md`, `design/` (database, frontend,
decisions), and this `spec/` ticket set. No duplicate documentation remains.

### Why

The doc tree had three competing authorities (frozen Wren planning, Wren
design truth, the Agencx plan set) plus a merge plan on top. The build needs
one canonical set; everything before it is archive material. The user's
directive: rewrite from scratch, one archive folder, no duplicates.

### User stories

#### US-1 Archive everything pre-Agencx

**As** the build agent,
**I want** every pre-Agencx doc moved into `docs/archive/` with git history,
**so that** nothing is lost and nothing outside the archive can be mistaken
for current truth.

- [ ] `docs/PROGRESS.md`, `docs/DEMO.md`, `docs/source/`, `docs/agencx/`,
  `docs/design/`, `docs/artifacts/`, and the merge plan move under
  `docs/archive/` (as `PROGRESS.md`, `DEMO.md`, `source/`,
  `agencx-planning/`, `wren-design/`, `artifacts/`, `plan/`)
- [ ] Moves are `git mv` (rename detection, history preserved)
- [ ] `docs/archive/README.md` indexes every folder: what it was, where the
  info lives now, what is retired

#### US-2 Canonical set exists

**As** the build agent,
**I want** the new set (`docs/agencx/`) to hold the PRD, architecture,
progress, design docs, and this spec,
**so that** every question has exactly one doc to read.

- [ ] `docs/agencx/README.md` is the set's index with the read-this table
- [ ] `prd.md`, `architecture.md`, `progress.md` exist and are complete
- [ ] `design/decisions.md`, `design/database.md`, `design/frontend.md` exist
- [ ] `spec/` exists with the index and every ticket file

#### US-3 No duplicates

**As** the maintainer,
**I want** each fact to have one home in the new set,
**so that** the docs never drift.

- [ ] Grep-check: no section is a verbatim copy of an archived doc (the
  archive stays reference, the new set stands alone)
- [ ] Standing facts (invariants, copy rules, guardrail contract) appear once

### Technical spec

- `git mv` moves, one commit together with the new set
- Archive `README.md` carries the mapping table

### Tests

- Verification script: grep for old paths (`docs/source`, `docs/design/`,
  `docs/PROGRESS.md`, `docs/plan/`) outside `docs/archive/` - zero hits
  (except in pointer-update scope, which is A-2)
- No em dashes in any new file

### Files touched

- `docs/archive/**` (moved + README)
- `docs/agencx/**` (new set)

### Definition of done

- [ ] All archive moves committed with history
- [ ] Archive index written
- [ ] Canonical set complete
- [ ] Old-path grep clean outside the archive

---

## A-2: Pointer updates

### Summary

Re-point every entry point to the canonical Agencx set: root `README.md`,
`AGENTS.md`, `.agents/memory.md`, and the `docs/conventions.md` header. No
link left pointing at an archived path.

### Why

A restructure that leaves stale pointers undoes itself: the next agent reads
the old map and works against the archive. Entry points are load-bearing.

### User stories

#### US-1 README points at the new set

**As** a contributor,
**I want** the README docs table to reference `docs/agencx/progress.md`,
`docs/agencx/prd.md`, `docs/agencx/design/`, and `docs/archive/`,
**so that** the entry point leads to the canonical docs.

- [ ] The "How the docs work" table is re-pointed
- [ ] Artifact links re-pointed into `docs/archive/artifacts/`
- [ ] The product paragraph says Agencx (surface rename; the repo intro
  keeps the honest "built on the Wren build" note)

#### US-2 AGENTS.md structure + doc-loading rules updated

**As** an agent starting a session,
**I want** AGENTS.md to name the new set as canonical and the archive as
reference-only,
**so that** I never load frozen docs into context.

- [ ] The "Do not load" note now names `docs/archive/` (all of it) instead
  of just `docs/source/`
- [ ] Structure section lists `docs/agencx/` and `docs/archive/`
- [ ] Progress pointer changes to `docs/agencx/progress.md`

#### US-3 Memory + conventions updated

**As** the maintainer,
**I want** the "Documentation consolidated" memory entry and the conventions
header to reflect the new set,
**so that** no stale pointer survives.

- [ ] `.agents/memory.md`: the consolidated-docs entry is replaced with the
  Agencx restructure entry (dated), old paths updated
- [ ] `docs/conventions.md` header: applies-to points at
  `docs/agencx/prd.md` + `docs/agencx/architecture.md` (the archive source
  docs are retired)

### Technical spec

- Pure docs edits; no code changes

### Tests

- Grep for `docs/source`, `docs/design/`, `docs/PROGRESS`, `docs/plan/`,
  `docs/artifacts/` in `README.md`, `AGENTS.md`, `docs/conventions.md`,
  `.agents/*.md` - remaining hits must be deliberate archive references or
  updated

### Files touched

- `README.md`, `AGENTS.md`, `docs/conventions.md`, `.agents/memory.md`

### Definition of done

- [ ] Every entry point navigates to the canonical set
- [ ] No stale pointer to a pre-restructure path remains outside
  `docs/archive/`
