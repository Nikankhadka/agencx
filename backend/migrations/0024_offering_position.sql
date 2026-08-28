-- 0024_offering_position.sql - M-4: the order the owner puts their offerings in.
--
-- The storefront lists offerings in the owner's own order rather than
-- alphabetically, so the row has to carry that order. Existing rows are
-- backfilled oldest-first, which is the order they were already displayed in,
-- so no tenant's page changes the moment this runs.
--
-- No RLS or grant statement is needed: both are table-level and adding a
-- column does not change either.
alter table offerings add column position integer not null default 0;

update offerings set position = ordered.position
from (
  select id, row_number() over (partition by tenant_id order by created_at, id) - 1 as position
  from offerings
) as ordered
where offerings.id = ordered.id;

create index offerings_storefront_order on offerings (tenant_id, active, position, created_at);
