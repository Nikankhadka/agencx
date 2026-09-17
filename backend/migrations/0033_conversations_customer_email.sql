-- 0033_conversations_customer_email.sql - contact email captured at escalation.
--
-- Collected at the point of escalation only (never at conversation start, never
-- required to answer), so it is nullable and never blocks a handoff. Owner
-- surfaces only: the owner conversation detail returns it; no public chat
-- endpoint selects it. Preferred name lives in the existing customer_ref column.
alter table conversations add column customer_email text;
