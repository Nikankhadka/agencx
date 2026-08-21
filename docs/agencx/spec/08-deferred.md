# Phase 2 / Deferred (B-2, D-1, D-3, D-4)

Tickets deferred out of Phase 1: the domain/CORS move (external DNS/Vercel
founder step) and the full per-tenant tool-gating machinery + toggle UI + tests
(Phase 2, with a merge-plan open question on scope). D-1's registry is the
machinery D-2 depends on, but D-2 itself stays in Phase 1.

Tickets in this file:

- B-2: Domain + CORS to agencx.app (deferred - external DNS/Vercel)
- D-1: Tools built from the tenant enabled set (Phase 2)
- D-3: Business-tab tool toggle UI (Phase 2)
- D-4: Tool gating tests (Phase 2)

---

## B-2: Domain + CORS to agencx.app

### Summary

Point the public surface at `agencx.app` (wildcard `{slug}.agencx.app`,
tenant console `app.agencx.app`, platform `admin.agencx.app`, apex
`agencx.app`) and update CORS/allowed-hosts configuration accordingly. Slug
resolution itself is unchanged - only the host patterns around it move.

### Why

The product promise is a link at `{slug}.agencx.app`. The Wren build serves
`{slug}.wren.app`; the rebrand must move the surface without touching tenant
data or the resolver (the resolver is tenant-scoped, not host-scoped).

### User stories

#### US-1 Host middleware accepts the Agencx hosts

**As** the founder,
**I want** the Next.js host middleware (`proxy.ts`) and FastAPI CORS to
accept `agencx.app` patterns,
**so that** the three surfaces serve on the product's real domain.

- [ ] `proxy.ts` routes `app.agencx.app` -> tenant-admin segment,
  `admin.agencx.app` -> platform segment, `{slug}.agencx.app` -> customer
  segment, apex -> marketing
- [ ] FastAPI `CORS_ALLOW_ORIGINS` (or equivalent config) covers the three
  host patterns plus local dev hosts
- [ ] Local dev keeps working on `*.localhost:3000` / `localhost:8000`

#### US-2 The old domain still resolves (gracefully)

**As** the founder,
**I want** `wren.app` traffic to keep working during the transition,
**so that** nothing 404s on rename day.

- [ ] Both host families resolve; the old hosts are not removed in this
  ticket (removal is a later founder call)

#### US-3 Nothing else changes

**As** the maintainer,
**I want** the resolver, slugs, and tenant data untouched,
**so that** the domain move is pure configuration.

- [ ] `resolve_tenant_slug` untouched; no migration in this ticket
- [ ] Seeded slugs resolve identically on the new hosts

### Technical spec

- Host patterns are config (env/vercel.json + `proxy.ts`), not code branches
- DNS/Vercel domain wiring is the founder's external step; the ticket
  delivers the config so the flip is one DNS entry

### Tests

- E2E: host-resolution checks for all four host shapes (marketing, app,
  admin, slug) on local hosts
- Backend CORS test: allowed-origin matrix

### Files touched

- `frontend/proxy.ts` (or middleware), `frontend/vercel.json`
- `backend/app/main.py` (CORS config), env examples

### Definition of done

- [ ] All three surfaces + marketing serve on agencx.app host patterns
- [ ] CORS matrix green
- [ ] Local dev unaffected

---

## D-1: Tools built from the tenant enabled set

### Summary

Build the assistant's tool registry from `tenant_config.enabled_tools`
instead of a fixed list. The lean default is answering + escalate; the
advanced tools (recommend, quote, order/ticket lookup) exist only when the
tenant's enabled set includes them.

### Why

The merge decision: "Advanced tools = per-tenant toggle, default lean." The
small-business flow is one grounded answer path, not a menu of sales
machinery; the machinery stays available for tenants who want it. Tool gating
is also what keeps the pricing engine dormant for lean tenants (PRD section
8).

### User stories

#### US-1 The registry is data-driven

**As** the maintainer,
**I want** the tool list for a turn to come from the tenant's enabled set,
**so that** adding/removing a capability is a data change, never a code
change.

- [ ] `enabled_tools` names map 1:1 to tool implementations (registry with
  names, schemas, handlers)
- [ ] Unknown/legacy tool names in a row are ignored gracefully (log, skip)

#### US-2 The lean default is answering + escalate

**As** Sam on the Starter plan,
**I want** my assistant to answer from my material and hand off to me,
**so that** nothing quotes or recommends without my say-so.

- [ ] Default `enabled_tools` = `["answer_from_knowledge", "create_escalation"]`
  (migration in D-2; D-1 ships the registry that honors it)

#### US-3 Disabled capabilities cannot leak

**As** the platform owner,
**I want** a disabled tool to be impossible at every layer,
**so that** gating is enforced, not cosmetic.

- [ ] Agent layer: tool not in the turn's tool set (model cannot call it)
- [ ] Validation layer: inspection rejects a draft that used a disabled tool
  (e.g. a quote-like reply from a lean tenant)
- [ ] API layer: routes behind disabled capabilities 404 for that tenant

#### US-4 No vertical branch anywhere

**As** the maintainer,
**I want** the registry to branch on the data only,
**so that** I8 holds.

- [ ] No business-type or tenant-name conditionals in tool selection

### Technical spec

- Registry module: `backend/app/agents/tools.py` (name -> spec/handler),
  assembled per tenant from `enabled_tools`
- The supervisor-with-tools flow (P-3) consumes the registry; until then the
  existing graph builds its tool list from the same source
- The pricing engine call sites check the enabled set before computing
  (dormant engine for lean tenants)

### Tests

- Unit: registry assembly for lean set, full set, legacy names
- Agent: model tool-call attempt for a disabled tool is impossible by
  construction (tool not offered)
- API: quote route 404s for a lean tenant

### Files touched

- `backend/app/agents/tools.py`, supervisor/graph wiring
- `backend/app/api/**` (capability-gated routes)
- `backend/tests/**`

### Definition of done

- [ ] Registry data-driven from `enabled_tools`
- [ ] Lean default = answer + escalate
- [ ] Disabled capability blocked at all three layers
- [ ] No vertical branch

---

## D-3: Business-tab tool toggle UI

### Summary

Add the enabled-tools section to the Business tab (S2): a compact toggle
group for the optional capabilities (recommendations, quoting, order
lookup), reflecting and writing `tenant_config.enabled_tools`. The lean pair
(answer + escalate) is always on and shown as fixed, not toggleable.

### Why

The owner decides what the assistant may do - the PRD names the Business tab
as the show-back surface, and the enabled-tools toggle is one of its thin,
product-required exceptions (decision 7 exception). Gating without a surface
is a hidden setting; hidden settings are exactly what the product rejects.

### User stories

#### US-1 The toggle group shows the truth

**As** Sam,
**I want** the Business tab to show what my assistant can currently do,
**so that** I can see and change it without a settings tree.

- [ ] A "What your assistant can do" section lists each optional capability
  with its current state
- [ ] Answering and escalating are listed as always-on (not toggles)

#### US-2 Toggling persists immediately

**As** Sam enabling quoting,
**I want** the toggle to write `enabled_tools` and take effect on the next
turn,
**so that** no deploy or restart is involved.

- [ ] Optimistic update with server confirmation; revert on failure with a
  calm toast
- [ ] Enabling quoting reveals the dependent hint ("quotes are computed
  exactly from your pricing rules")

#### US-3 No settings-tree creep

**As** the maintainer,
**I want** the section to stay two controls wide (the optional tools),
**so that** the Business tab never becomes a config form.

- [ ] Nothing else gains a toggle in this ticket; the share link + QR and
  live/not-live indicator are separate existing affordances, untouched

### Technical spec

- Tenant-config endpoint: `GET/PATCH tenant_config.enabled_tools`
  (tenant-scoped; PATCH validates against the known tool names, rejects
  unknown names - D-1 registry is the source of truth)
- UI: `frontend/src/app/(tenant-admin)/business/` section component; tokens
  only, no new visual language

### Tests

- API: PATCH round-trip, unknown-name rejection, cross-tenant isolation
- E2E: toggle off -> public page quote attempt refuses; toggle on -> quote
  path re-enabled (paired with D-4's agent tests)

### Files touched

- `backend/app/api/**` (tenant_config route)
- `frontend/src/app/(tenant-admin)/business/**`
- `frontend/e2e/**`

### Definition of done

- [ ] Toggle group renders truth from the DB
- [ ] PATCH persists and validates
- [ ] E2E proves the toggle changes behavior

---

## D-4: Tool gating tests

### Summary

The behavioral proof that gating works end to end: a lean tenant cannot
quote or recommend; an enabled tenant can; toggling flips behavior with no
restart; disabled-capability routes 404; cross-tenant state never leaks.

### Why

Gating is a product promise and a safety property (a lean tenant who is
quoted at is a trust failure - the money boundary loosened for the wrong
tenant). D-1/D-2/D-3 each carry unit tests; D-4 is the end-to-end teeth.

### User stories

#### US-1 Lean tenant cannot quote

**As** the platform owner,
**I want** a lean tenant's assistant to refuse quoting with the honest
handoff,
**so that** gating is real, not cosmetic.

- [ ] Public page: "how much for X?" on a lean tenant -> refusal + escalation
  path (never a computed figure, never a QuoteCard)
- [ ] The quote API route 404s for the lean tenant
- [ ] The pricing engine never runs for the lean tenant (no cost log rows)

#### US-2 Enabled tenant can

**As** a tenant with quoting on,
**I want** the same question to produce an engine-computed quote,
**so that** the capability works when chosen.

- [ ] QuoteCard renders engine output verbatim; figures reconcile to the
  engine (existing provenance check)

#### US-3 Toggling flips behavior

**As** the founder,
**I want** to flip quoting on and off from the Business tab and see the
behavior change on the next turn,
**so that** the toggle is the control plane.

- [ ] Off -> on -> off cycle verified through the real public page (E2E)
- [ ] No restart, no cache staleness (the registry reads per-turn)

#### US-4 Isolation under gating

**As** the maintainer,
**I want** one tenant's enabled set to never affect another's,
**so that** I5 holds under the new control.

- [ ] Two tenants with different sets, same queries: independent behavior
- [ ] Leakage suite still green (regression)

### Technical spec

- E2E specs over the seeded demo world (tenant 1 advanced, tenant 2 lean)
- API-level tests for 404s; cost-log assertion for engine dormancy

### Tests

- This ticket IS the tests; wired into CI (`make test-e2e`, `make test-backend`)

### Files touched

- `frontend/e2e/**`, `backend/tests/**`

### Definition of done

- [ ] Lean tenant refuses, enabled tenant quotes
- [ ] Toggle cycle flips behavior with no restart
- [ ] Cross-tenant independence green
