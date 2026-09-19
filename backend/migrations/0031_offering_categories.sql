-- 0031_offering_categories.sql - stable tenant-scoped offering categories.
-- The legacy offerings.category label remains during the compatibility window;
-- category_id is the durable identity used by new writes and owner edits.

create table offering_categories (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  name text not null check (length(trim(name)) > 0),
  normalized_key text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (tenant_id, id),
  unique (tenant_id, normalized_key)
);

create index offering_categories_tenant_idx on offering_categories (tenant_id, normalized_key);

alter table offerings add column category_id uuid;
alter table offerings add constraint offerings_category_fk
  foreign key (tenant_id, category_id)
  references offering_categories (tenant_id, id)
  on delete set null;

-- The key has to be the one `normalize_name` computes in the application -
-- casefolded, punctuation turned into spaces, whitespace collapsed - or an
-- owner renaming a legacy label like "Plates & Bowls" would miss the row
-- backfilled here and open a second category for the same name.
insert into offering_categories (tenant_id, name, normalized_key)
select distinct on (tenant_id, normalized_key)
  tenant_id,
  trim(category),
  normalized_key
from (
  select
    tenant_id,
    category,
    trim(lower(regexp_replace(regexp_replace(category, '[[:punct:]]', ' ', 'g'), '\s+', ' ', 'g'))) as normalized_key
  from offerings
  where category is not null and length(trim(category)) > 0
) legacy
order by tenant_id, normalized_key, category;

update offerings o
set category_id = c.id
from offering_categories c
where c.tenant_id = o.tenant_id
  and c.normalized_key = trim(lower(regexp_replace(regexp_replace(o.category, '[[:punct:]]', ' ', 'g'), '\s+', ' ', 'g')));

alter table offering_categories enable row level security;
alter table offering_categories force row level security;
create policy tenant_isolation on offering_categories for all
  using (tenant_id = app_tenant_id() and app_role() in ('tenant_admin', 'customer'))
  with check (tenant_id = app_tenant_id() and app_role() = 'tenant_admin');
create policy platform_admin_read on offering_categories for select using (app_is_platform_admin());
create policy service_read on offering_categories for select using (app_is_service());
create trigger offering_categories_touch before update on offering_categories
  for each row execute function touch_updated_at();
grant select, insert, update, delete on offering_categories to wren_app;
