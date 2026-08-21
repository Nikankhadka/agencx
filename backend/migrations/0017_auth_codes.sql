-- 0017_auth_codes.sql - O-2: login-in-chat email codes.

-- The 6-digit code is issued and verified inside the chat. Only the sha-256
-- hash of the code is stored, never the raw code. ``tenant_id`` is null until
-- the code is exchanged for a tenant (login precedes tenant resolution); access
-- runs under the service role (``app_is_service()``), so the ``service_all``
-- policy is the working path. The ``tenant_isolation`` policy exists to satisfy
-- the schema-audit invariant ("every tenant_id table has RLS + tenant_isolation")
-- even though the pre-tenant login path never reads through it.
create table auth_codes (
  id          uuid primary key default gen_random_uuid(),
  tenant_id   uuid references tenants(id) on delete cascade,
  email       text not null,
  code_hash   text not null,
  expires_at  timestamptz not null,
  attempts    integer not null default 0,
  verified_at timestamptz,
  created_at  timestamptz not null default now()
);
create index auth_codes_email_created_idx on auth_codes (email, created_at desc);
alter table auth_codes enable row level security;
alter table auth_codes force row level security;
create policy tenant_isolation on auth_codes for all
  using (tenant_id = app_tenant_id()) with check (tenant_id = app_tenant_id());
create policy service_all on auth_codes for all
  using (app_is_service()) with check (app_is_service());
grant select, insert, update, delete on auth_codes to wren_app;
