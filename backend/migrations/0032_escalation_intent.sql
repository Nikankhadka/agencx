-- 0032_escalation_intent.sql - the intent family an escalation came from.
--
-- Three broad families only (information/offer/support); escalation itself is
-- an action, not an intent, so an escalated conversation can carry any of the
-- three. Nullable by design: limit escalations and rows written before this
-- column stay null. Every writer coerces through app/agents/intent.py's
-- as_intent, so the check can never reject a recorded row - it exists to keep a
-- future writer honest, not to gate the agent.
alter table escalations add column intent text;
alter table escalations add constraint escalations_intent_check
  check (intent is null or intent in ('information', 'offer', 'support'));
