-- 0035_conversations_owner_read_at.sql - RF-18 owner read state for the chat queue.
--
-- One marker per conversation, written when the owner opens the thread. A
-- conversation is unread when the marker is null or a customer message is newer
-- than it. This is a plain column add: conversations already has FORCE ROW LEVEL
-- SECURITY plus its tenant_isolation and staff policies, and a new column is
-- governed by those unchanged, so the tenant boundary does not move.
alter table conversations add column owner_read_at timestamptz;
