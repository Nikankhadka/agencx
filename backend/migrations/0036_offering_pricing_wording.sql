-- 0036_offering_pricing_wording.sql - RF-4 owner-confirmed pricing wording.
--
-- A display-only alternative to a fixed price ("from $12 a head"). It is never
-- an input to the pricing engine and no code derives an amount from it; the
-- column is nullable and independent, while the API enforces mutual exclusivity
-- with price_cents. Additive column only: offerings already has FORCE ROW LEVEL
-- SECURITY and its tenant_isolation policy, unchanged by a new column.
alter table offerings add column pricing_wording text;
