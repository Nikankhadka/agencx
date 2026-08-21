# Phase 1 - Hygiene (F)

Dead-code cleanup after the supervisor-with-tools topology (P-3) lands. The
one topology survives; superseded fixed-specialist routing is deleted.

Tickets in this file:

- F-1: Delete dead agent code

---

## F-1: Delete dead agent code

### Summary

Delete the agent code left over from the Wren topology that the Agencx
re-cut renders dead: the fixed five-specialist routing branches that the
supervisor-with-tools shape replaces, orphaned node modules, and unused
prompt/state scaffolding. Deletion over addition; every deleted symbol's
callers must be accounted for.

### Why

Dead code is the cheapest code to maintain - if it does not exist. The
multi-specialist topology (route -> specialist -> price_gate -> inspection
as fixed nodes) is superseded by supervisor-with-tools (D-13); keeping both
paths means every guardrail and inspection change is made twice, and the
second path is unexercised, which is worse than absent.

### User stories

#### US-1 One topology survives

**As** the maintainer,
**I want** exactly one customer-chat topology in the repo,
**so that** there is one path to reason about and test.

- [ ] The supervisor-with-tools flow (P-3) is the only graph shape after
  this ticket; fixed-specialist routing code is gone
- [ ] Specialist logic that becomes tool implementations is MOVED into tool
  handlers (not deleted wholesale - the knowledge/recommend/quote/order
  logic stays, in its new home); only the topology glue dies

#### US-2 No orphaned modules or tests

**As** the maintainer,
**I want** every deleted symbol's imports and tests cleaned in the same
commit,
**so that** nothing imports a deleted module.

- [ ] Import graph clean: no imports of deleted modules
- [ ] Tests that pinned the old topology are updated to the new shape or
  deleted when the shape they pin no longer exists

#### US-3 The safety net stays whole

**As** the platform owner,
**I want** the guardrail, inspection, and escalation behavior identical
after the cleanup,
**so that** deleting code never deletes safety.

- [ ] Money guardrail, inspection, leakage, and escalation suites green
  against the surviving topology (the suites assert behavior, not topology -
  where they asserted topology, they are re-pointed)

### Technical spec

- Order of work: land P-3 (supervisor-with-tools) first; F-1 then removes
  the superseded graph modules and the fixed routing
- `git grep` each deleted symbol before deletion; no orphan imports

### Tests

- Full `make check` + `make eval` green
- Import-linter green

### Files touched

- `backend/app/agents/**` (deletions + moves into tools)

### Definition of done

- [ ] One topology remains
- [ ] Import graph clean
- [ ] Safety suites green
