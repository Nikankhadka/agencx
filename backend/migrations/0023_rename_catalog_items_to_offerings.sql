-- 0023_rename_catalog_items_to_offerings.sql - D24/M-1: catalog_items becomes
-- offerings, its physical name now matching the one domain noun ("Offering")
-- used everywhere else - owner-facing copy, API DTOs, service functions.
-- D24 left this naming question open on purpose; M-1 (docs/agencx/spec/
-- 11-offerings-media.md) is where it gets decided and recorded.
--
-- RLS policies and the wren_app grants need no statement here: both are keyed
-- by the table's oid (pg_policy.polrelid, pg_class.relacl), so they follow it
-- through a rename. The index, trigger and constraint renames below are purely
-- so the catalog reads coherently - a table called offerings whose primary key
-- is catalog_items_pkey is the confusion this rename exists to end.
--
-- 0006_commerce.sql keeps its original CREATE TABLE and is never edited: the
-- runner records applied migrations by filename and never re-runs them, so
-- editing history would only change databases that have not run it yet.
alter table catalog_items rename to offerings;
alter index catalog_items_tenant_idx rename to offerings_tenant_idx;
alter trigger catalog_items_touch on offerings rename to offerings_touch;
alter table offerings rename constraint catalog_items_pkey to offerings_pkey;
alter table offerings rename constraint catalog_items_price_cents_check
  to offerings_price_cents_check;
alter table offerings rename constraint catalog_items_tenant_id_fkey
  to offerings_tenant_id_fkey;
