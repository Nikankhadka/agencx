-- 0024_business_offers.sql - ordered, owner-managed storefront offers.
--
-- A short-lived development branch renamed `catalog_items` to `offerings`.
-- The current application and pricing engine consistently use `catalog_items`,
-- so bring that local schema back before adding the storefront ordering column.
-- Fresh databases never enter this branch.

do $$
begin
  if to_regclass('public.catalog_items') is null and to_regclass('public.offerings') is not null then
    alter table offerings rename to catalog_items;
  end if;
end
$$;

alter table catalog_items add column position integer not null default 0;
update catalog_items set position = ordered.position
from (
  select id, row_number() over (partition by tenant_id order by created_at, id) - 1 as position
  from catalog_items
) as ordered
where catalog_items.id = ordered.id;
create index catalog_items_storefront_order on catalog_items (tenant_id, active, position, created_at);
