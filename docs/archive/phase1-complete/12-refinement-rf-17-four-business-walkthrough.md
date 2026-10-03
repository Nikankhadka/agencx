# 12 (RF-17): Four-business walkthroughs with visual and behavioral evidence

**Status:** Done - merged in `236000e434333a3710f9da9b19bfc135a52145ef` on 2026-10-03.
**Branch:** `feat/rf-17-four-business-walkthrough`.
**Phase 1 area:** Refinement.

Delivered: the four seeded businesses (cafe/`sababa`, retail-repair/`bytefix`,
dental/`lumident`, general clinic/`wellspring`) are walked on identical workflow
code with config-only differences; a new deterministic five-test Playwright spec
plus a cross-tenant isolation check; 24 screenshots mapped to the named tests in
the evidence ledger `docs/agencx/evidence/rf-17-2026-10-03/README.md`; the fourth
business is a config-only seed (no API/DB/schema change, no vertical branching).

## Agreed behavior

- **RF-17** - Four businesses (cafe, retail/repair, dental clinic, and general
  clinic) are walked on identical workflow code with configuration-driven
  content, with screenshots per state and E2E checks, plus a ledger of what was
  verified where.

## Ticket detail

- **Visible outcome:** Four businesses (cafe, retail/repair, dental clinic, and
  general clinic) are walked on identical workflow code with
  configuration-driven content, with screenshots per state and E2E checks, plus
  a ledger of what was verified where.
- **Current vs proposed:** Current: four-business visual and behavioral
  walkthroughs and the evidence ledger are specified but not yet assembled for
  the refined experience. Proposed: run every ticket's existing checks within
  each ticket, then verify the assembled experience once across all four
  businesses. RF-17 verifies the assembled experience rather than postponing
  testing.
- **Design reference:** Existing walkthrough evidence under
  `docs/agencx/evidence/` and the four seeded businesses; no prototype change.
  Shipped: `frontend/e2e/`.
- **Dependencies:** RF-1 through RF-16.
- **API/DB changes:** None.
- **Acceptance scenarios:** Each business completes the refined owner queue,
  business page, storefront, and customer chat flows with config-only
  differences; every screenshot maps to a named E2E check; the ledger names the
  environment and date; a cross-tenant check proves isolation.
- **Regression checks:** `make test-e2e`, `make eval-skip-llm`, and the
  deterministic pricing and domain-agnostic invariant tests.
- **OPEN:** none.

## Decisions

- **Decision (2026-10-03):** **The fourth "general clinic" did not exist, so it
  was added as config-only seed data** (`wellspring`, general medical practice)
  mirroring `seed_sababa.py`. Seeds are data, so the domain-agnostic invariant
  holds: no code branches on a vertical.
- **Decision (2026-10-03):** **The evidence environment is the local Docker
  Compose stack** (`make dev` + `make seed`), dated 2026-10-03, so the
  walkthrough is deterministic and never touches the production-sharing preview.
- **Decision (2026-10-03):** **The RF-17 spec is a permanent regression spec**
  with screenshot capture opt-in via `RF17_CAPTURE`, viewport-only, so CI never
  rewrites tracked files.
- **Decision (2026-10-03):** **The cross-tenant check is the customer-surface
  proof**, with the data layer pinned by the existing leakage eval and tests.
- **Decision (2026-10-03):** **Review fix: use `getByRole("main")`** because
  Next dev streaming leaves a hidden cloned `<main>` (a pre-existing flake), and
  hide the dev indicator during capture.

## Verification

- `make test-e2e` - 239 passed, 0 failed, 0 flaky.
- `make seed-tenant1 && make eval-skip-llm` - GATE PASSED: money guardrail,
  leakage both directions, retrieval recall@5 1.000.
- `npm run gen:types -- --check` - api-types up to date (host).
- `make lint` - passed.
- `make typecheck` - passed.
- `make format-check` - passed.
- `make build` - passed.
- CI on PR [#78](https://github.com/Nikankhadka/agencx/pull/78) - all green:
  backend, frontend, api-types, infra, security, e2e, eval-gate, Vercel.
- Independent reviewer pass (one SHIP, one SHIP-WITH-FIXES); findings fixed:
  test-count delta documented, ledger wording corrected, dev indicator hidden
  and 24 screenshots regenerated, unnecessary serial mode removed, README tenant
  count.

Two follow-ups are recorded, unfixed and out of scope, in the evidence ledger:
the in-container `gen:types` command-table inaccuracy, and the pre-existing
1440px Chats filter-strip clipping.
