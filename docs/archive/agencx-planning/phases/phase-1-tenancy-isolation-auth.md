# Phase 1: Tenancy, Isolation, Auth

**Calendar slot:** Week 1

## Goal

Multi-tenant database with RLS enforced on every tenant-scoped table, a schema audit with teeth, slug-based tenant resolution, email+6-digit-code auth, and a cross-tenant leakage test suite that is 100/100. At the end, `make test` proves that tenant A can never read tenant B's data.

## Tickets

| Ticket | Name | What it delivers | Files/modules | Depends on |
|---|---|---|---|---|
| T-005 | Migrations runner | `backend/app/core/migrate.py` that reads `backend/migrations/` and applies forward-only `NNNN_name.sql` files against `schema_migrations` table | `backend/app/core/migrate.py`, `backend/migrations/0001_extensions.sql` (vector, helper functions, touch_updated_at trigger) | T-003 |
| T-006 | RLS roles + tenant_context + schema audit with teeth | Connection roles (`postgres`, `agencx_app`, `agencx_resolver`), `set_config('app.tenant_id', ...)` middleware, Shape A/B/C RLS policies, schema audit test that queries `pg_tables`/`pg_policies` and the teeth test that proves the audit bites | `backend/migrations/0002_roles.sql`, `backend/app/shared/db.py` (tenant context middleware), `backend/tests/test_schema_audit.py` | T-005 |
| T-007 | Tenant creation + resolve_tenant_slug + business_types seeds | `tenants`, `business_types`, `platform_admins` tables with RLS; `resolve_tenant_slug()` SECURITY DEFINER function owned by `agencx_resolver`; seed rows for `restaurant-catering`, `cleaning`, `dental-clinic` | `backend/migrations/0003_tenancy.sql`, `backend/app/routes/tenants.py`, `backend/tests/test_rls.py` | T-006 |
| T-008 | Auth codes issue/verify | `auth_codes` table; `send_login_code` tool (hashes 6-digit code, sends email); `verify_login_code` tool (checks hash, TTL, attempts); email sender via free-tier transactional provider | `backend/migrations/0003_tenancy.sql` (auth_codes portion), `backend/app/services/auth.py`, `backend/app/services/email.py` | T-007 |
| T-009 | Sessions + actor_id | `users` table; session management (JWT or signed cookie); `actor_id` on every row; FastAPI dependency that sets tenant context from the session | `backend/migrations/0003_tenancy.sql` (users portion), `backend/app/shared/auth.py`, `backend/app/shared/session.py` | T-008 |
| T-010 | Cross-tenant leakage test | Test suite that authenticates as tenant A, inserts data, then queries as tenant B and asserts zero rows - per table, both directions, with positive controls | `backend/tests/test_leakage.py` | T-009 |

## Gate

The four high-consequence area gates:

- [ ] **RLS isolation:** Every table with `tenant_id` has RLS enabled, forced, and the `tenant_isolation` policy. The cross-tenant leakage test is 100/100 both directions per table. The teeth test proves the schema audit bites.
- [ ] **Schema audit:** Every monetary column matches `%_cents` and is integer-typed (except `cost_logs.cost_usd`). The teeth test: deliberately dropping one policy goes red in CI.
- [ ] **Tenant resolution:** `resolve_tenant_slug()` returns only `(id, business_name, status, brand)` for valid slugs. Unknown slugs return empty set.
- [ ] **Auth:** Email + 6-digit code issued and verified. Attempt budget enforced. Expired codes rejected.

## Done when

- [ ] Six tickets complete
- [ ] `make test` passes including test_rls, test_schema_audit, test_leakage
- [ ] Cross-tenant leakage test is 100/100 both directions, with positive controls
- [ ] Schema audit with teeth test runs in CI and goes red when a policy is dropped
- [ ] Business type seed rows exist and are queryable
- [ ] Fits or observed slip
