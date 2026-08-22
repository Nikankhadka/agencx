-- 0021_tenant_assets.sql - E-6: the Booking page's cover photo.

-- The prototype's booking screen opens on a cover photo, and a business page
-- without one looks unfinished. There is nowhere to put it: uploaded documents
-- are extracted to text and the bytes discarded, and this project has no object
-- store (Supabase Storage is not available in local dev, which every other
-- surface here runs against).
--
-- ponytail: the bytes live in Postgres. One small image per tenant, capped at
-- 2MB by the API and resized client-side before it is sent, is well inside what
-- a row can carry, and it works identically in dev and in production with no
-- new dependency and no new credential. Object storage is the upgrade path if
-- this ever holds galleries rather than one cover.
--
-- Kept out of `tenant_config` deliberately: `brand` and `config` are read on
-- hot paths (the public tenant lookup primes the chat's context package, P-3),
-- and a base64 image on that path would be a latency regression wearing a
-- feature's clothes. A separate table is only read when someone asks for it.
create table tenant_assets (
  tenant_id   uuid not null references tenants(id) on delete cascade,
  kind        text not null check (kind in ('cover')),
  mime        text not null,
  bytes       bytea not null,
  updated_at  timestamptz not null default now(),
  primary key (tenant_id, kind)
);
alter table tenant_assets enable row level security;
alter table tenant_assets force row level security;
create policy tenant_isolation    on tenant_assets for all
  using (tenant_id = app_tenant_id()) with check (tenant_id = app_tenant_id());
create policy platform_admin_read on tenant_assets for select using (app_is_platform_admin());
-- The customer-facing page is anonymous, so the public reader must be able to
-- serve a cover the same way it serves the tenant's name.
create policy service_read        on tenant_assets for select using (app_is_service());
create trigger tenant_assets_touch before update on tenant_assets
  for each row execute function touch_updated_at();
grant select, insert, update, delete on tenant_assets to wren_app;
