-- D-2: lean by default. `tenant_config.enabled_tools` shipped listing every
-- tool the agent has, which made recommending, quoting and order lookup the
-- default posture for a business that never asked for them. The PRD's default
-- is the opposite: a tenant answers questions and escalates, and the commerce
-- tools are opt-ins (PRD section 8, D-1/D-3).
--
-- Number: 0016 was reserved for this ticket and skipped while 0017-0020
-- landed. The runner applies files in filename order and skips what is already
-- applied, so a later database picks this up out of sequence without harm -
-- it depends on nothing after 0003.
--
-- Tool names are the ones `app/agents/agent_node.py::_tools_for` actually
-- registers. The spec drafted this default as
-- `["answer_from_knowledge","create_escalation"]`; there is no
-- `answer_from_knowledge` tool - answering is the model's prose, not a call -
-- and the retrieval tool is `search_knowledge`, which stays on because it is
-- how a corpus too large for the fast path gets read at all (O-4). What goes
-- off is the commerce three.
--
-- NOTE: nothing reads this column yet. D-1 wires `_tools_for` to it in Phase
-- 2. The data has to be honest BEFORE the reader exists, or D-1's arrival
-- would silently switch quoting on for every tenant onboarded before it.

alter table tenant_config
  alter column enabled_tools
  set default '["search_knowledge", "create_escalation"]'::jsonb;

-- Targeted: only rows still carrying the old default, byte for byte. A tenant
-- who has chosen a set - once D-3's toggle exists, or by hand - has said
-- something, and a backfill must not overrule it.
update tenant_config
set enabled_tools = '["search_knowledge", "create_escalation"]'::jsonb
where enabled_tools = '["search_knowledge", "recommend_items", "lookup_order_or_ticket", "get_quote_inputs", "create_escalation"]'::jsonb;
