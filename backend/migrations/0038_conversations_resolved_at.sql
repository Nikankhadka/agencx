-- 0038_conversations_resolved_at.sql - conversation-level resolution marker.
--
-- One nullable marker per conversation, written when the owner resolves the
-- thread (or the lazy auto-resolve sweep does). Resolution is deliberately not
-- a conversations.status value: status stays the ownership axis (open/human/
-- escalated), and a customer reply reopens the thread by clearing this marker
-- rather than by moving status. Same shape as 0035's owner_read_at - a plain
-- column add governed by the existing FORCE ROW LEVEL SECURITY policies, so
-- the tenant boundary does not move.
alter table conversations add column resolved_at timestamptz;
