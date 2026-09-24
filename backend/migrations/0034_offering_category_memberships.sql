-- 0034_offering_category_memberships.sql - many-to-many browse categories.
-- The legacy offerings.category/category_id pair remains the primary-category
-- compatibility projection while new reads use this table.

create table offering_category_memberships (
  tenant_id uuid not null references tenants(id) on delete cascade,
  offering_id uuid not null,
  category_id uuid not null,
  position integer not null default 0 check (position >= 0),
  is_primary boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key (tenant_id, offering_id, category_id),
  unique (tenant_id, offering_id, position),
  foreign key (tenant_id, offering_id)
    references offerings (tenant_id, id) on delete cascade,
  foreign key (tenant_id, category_id)
    references offering_categories (tenant_id, id) on delete cascade
);

create unique index offering_category_memberships_one_primary
  on offering_category_memberships (tenant_id, offering_id)
  where is_primary;
create index offering_category_memberships_category_idx
  on offering_category_memberships (tenant_id, category_id, offering_id);

-- A composite `on delete set null` also nulls tenant_id in Postgres. That
-- column is deliberately not nullable, so category deletion is coordinated by
-- the service: clear/promote the compatibility projection, then delete.
alter table offerings drop constraint offerings_category_fk;
alter table offerings add constraint offerings_category_fk
  foreign key (tenant_id, category_id)
  references offering_categories (tenant_id, id);

insert into offering_category_memberships
  (tenant_id, offering_id, category_id, position, is_primary)
select tenant_id, id, category_id, 0, true
from offerings
where category_id is not null;

alter table offering_category_memberships enable row level security;
alter table offering_category_memberships force row level security;
create policy tenant_isolation on offering_category_memberships for all
  using (tenant_id = app_tenant_id() and app_role() in ('tenant_admin', 'customer'))
  with check (tenant_id = app_tenant_id() and app_role() = 'tenant_admin');
create policy platform_admin_read on offering_category_memberships for select
  using (app_is_platform_admin());
create policy service_read on offering_category_memberships for select
  using (app_is_service());
create trigger offering_category_memberships_touch
  before update on offering_category_memberships
  for each row execute function touch_updated_at();
grant select, insert, update, delete on offering_category_memberships to wren_app;
