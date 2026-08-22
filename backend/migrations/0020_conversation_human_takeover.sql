-- 0020_conversation_human_takeover.sql - C-6: staff step into a conversation,
-- and give it back.

-- The schema conflated two different things into one terminal status. They are
-- separate concerns and now say so:
--
--   'open'      the assistant is answering
--   'human'     a staff member is answering; the assistant stays silent
--   'escalated' a tenant limit stopped the conversation (the only hard stop,
--               written solely by record_limit_escalation since C-5)
--   'closed'    unchanged
--
-- An escalation row is a notification - "a human should look at this" - and
-- says nothing about who is replying. A takeover is what changes that, and it
-- is reversible. Strictly additive: no existing row changes meaning.
alter table conversations drop constraint conversations_status_check;
alter table conversations add constraint conversations_status_check
  check (status in ('open', 'human', 'escalated', 'closed'));

-- What the customer actually wants, in one line, written by the assistant in
-- the create_escalation call it already makes. The owner reads this in the
-- Chats list instead of a reason code, which is the difference between
-- triaging a queue at a glance and opening every thread.
--
-- Owner-facing only: the escalations API returns it and no public chat endpoint
-- does. The money guardrail deliberately does not apply - no customer reads it,
-- and it restates the customer's own request (founder ruling, 2026-08-22).
-- Null on rows written before this, and on any turn where the model omitted it;
-- both fall back to `reason`.
alter table escalations add column summary text;
