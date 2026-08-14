-- 0014_onboarding_business_fields.sql - T-052: business name + payment
-- collection mode pulled into the tenants spine (ADR 2026-08-14). Everything
-- else from the onboarding business/tax/payment sections lives in
-- tenant_config.config jsonb, written by the confirm flow.

alter table tenants
  add column business_name text,
  add column payment_processing_mode text not null default 'DIRECT'
    check (payment_processing_mode in ('PLATFORM', 'DIRECT', 'DEFERRED'));

-- tenant admins could read but not write their own tenants row (only
-- tenant_self_read / platform_admin_all / service_signup_insert existed); the
-- confirm flow runs as tenant_admin and must persist the two columns above.
-- Mirrors tenant_self_read: a tenant owns its own row. tenant_isolation on the
-- tenant-scoped tables already grants tenants full CRUD on their own rows, so
-- this closes the one asymmetric gap on the tenants spine itself.
create policy tenant_self_update on tenants for update
  using (id = app_tenant_id()) with check (id = app_tenant_id());
