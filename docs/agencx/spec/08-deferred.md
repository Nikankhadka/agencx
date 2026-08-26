# Phase 2 / Deferred (B-2, D-1, D-3, D-4)

Tickets deferred out of Phase 1: the domain/CORS move (the founder buys a
domain) and the full per-tenant tool-gating machinery + toggle UI + tests
(Phase 2, with a merge-plan open question on scope). D-1's registry is the
machinery D-2 depends on, but D-2 itself stays in Phase 1.

Tickets in this file:

- B-2: Point agencx.app at the deployed stack (deferred - founder buys the domain)
- D-1: Tools built from the tenant enabled set (Phase 2)
- D-3: Business-tab tool toggle UI (Phase 2)
- D-4: Tool gating tests (Phase 2)

---

## B-2: Point agencx.app at the deployed stack

### Summary

Buy the domain and point it at the Vercel project. No wildcard: since **D22** a
tenant is a path (`agencx.app/{slug}`), so this is one A/CNAME record and one
certificate that Vercel issues automatically. Since **B-4** the frontend and the
backend are two services behind that one origin, so there is no second hostname
and no CORS to narrow either.

### Why

The product promise is a link the owner can hand out. Everything needed to
serve it already works on the deploy's auto URLs - D22 removed the wildcard DNS
and certificate that used to stand between the build and a reachable customer
page. What is left is the founder step of owning a domain.

### User stories

#### US-1 The surfaces serve on the real domain

**As** the founder,
**I want** `agencx.app` pointed at the deployed frontend and backend,
**so that** the link an owner hands out is the product's own address.

- [ ] `agencx.app` (apex + `www`) resolves to the Vercel project; `www`
  redirects to the apex so one address is canonical
- [ ] `agencx.app/{slug}`, `agencx.app/login` and `agencx.app/admin` all serve
- [ ] `agencx.app/api/*` and `agencx.app/health` reach the backend service on
  the same origin (B-4's rewrites), so the backend needs no hostname of its own

#### US-2 CORS names the real origin

**Void since B-4.** The deploy puts the frontend and the backend behind one
Vercel origin (`vercel.json` rewrites `/api/*` to the backend service), so the
browser makes no cross-origin request in production and there is no production
origin for `_ALLOWED_ORIGIN_REGEX` to name - it covers local dev only, which the
domain move does not touch. Recorded here rather than ticked, the way E-5's
live/not-live bullet was.

- [x] Nothing left to do: B-4 shrank `_ALLOWED_ORIGIN_REGEX` to `localhost` and
  moved `wren.app` and `agencx.app` into the reject half of
  `backend/tests/test_health.py`'s matrix, which a domain move cannot change

#### US-3 Nothing else changes

**As** the maintainer,
**I want** the resolver, slugs and tenant data untouched,
**so that** the domain move stays a configuration change.

- [ ] `resolve_tenant_slug` untouched; no migration
- [ ] Seeded slugs resolve identically on the new domain

### Technical spec

- **The TLD is open** (D22): `.com` reads as a website to the small-business
  customers who tap the link and is the default choice; `.app` is a fine
  fallback if `agencx.com` is taken, and is HSTS-preloaded so it is
  HTTPS-only by construction. Either is one DNS record.
- Origins are config, not code branches
- DNS and the Vercel domain binding are founder steps; the ticket delivers the
  config so the flip is one record

### Tests

- E2E unchanged - the specs are relative to `baseURL` and name no host

### Files touched

- `docs/agencx/deploy.md`, `README.md` (the domain appears in prose). Since B-4
  the ticket touches no application code at all - it is one DNS record and one
  Vercel domain binding.

### Definition of done

- [ ] All three surfaces serve on the real domain
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
