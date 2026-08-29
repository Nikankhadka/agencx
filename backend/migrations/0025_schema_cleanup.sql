-- F-3: schema cleanup - drop dead columns/table, add app_role(), and branch the
-- RLS policies by member role (owner/staff).
--
-- Drops:
--   tenant_config.escalation_threshold - its only reader was the dead supervisor
--     module (deleted with this ticket); the live graph escalates via the LLM
--     tool and price_gate, never a numeric threshold.
--   offerings.attributes - zero references anywhere (app, frontend, evals, seeds).
--   eval_cases - write-only bookkeeping: eval runners load cases from JSONL and
--     nothing ever reads the table back. eval_runs stays (the gate and the
--     dashboards read it).
--
-- Adds:
--   app_role() - names the transaction-local app.role setting the backend sets,
--     the way app_is_platform_admin() names its check. NULL when unset, so every
--     comparison fails closed.
--
-- Policy branches (G3.1): tenant_isolation on admin tables now requires
-- tenant_admin to write, while customer keeps read (chat, retrieval and the
-- storefront read them under the customer context). Staff gets read-only on the
-- conversation tables plus exactly its narrow write surfaces: the human
-- takeover (conversations.status <-> human/open), the human reply and
-- takeover stamp (messages roles human_agent/system), and escalations
-- claim/resolve. RLS evaluates policies per command with OR semantics, so
-- these coexist with the existing platform_admin and service policies
-- unchanged.

create or replace function app_role() returns text
  language sql stable as
$$ select current_setting('app.role', true) $$;

alter table tenant_config drop column escalation_threshold;
alter table offerings drop column attributes;
drop table eval_cases;

-- --- tenants (special-cased: no tenant_id column) ---
drop policy tenant_self_read on tenants;
create policy tenant_self_read on tenants for select
  using (id = app_tenant_id() and app_role() in ('tenant_admin', 'customer'));
drop policy tenant_self_update on tenants;
create policy tenant_self_update on tenants for update
  using (id = app_tenant_id() and app_role() = 'tenant_admin')
  with check (id = app_tenant_id() and app_role() = 'tenant_admin');

-- --- admin tables: tenant_admin writes, customer keeps read ---
drop policy tenant_isolation on tenant_config;
create policy tenant_isolation on tenant_config for all
  using (tenant_id = app_tenant_id() and app_role() in ('tenant_admin', 'customer'))
  with check (tenant_id = app_tenant_id() and app_role() = 'tenant_admin');

-- users: nothing reads it under the customer context, so no customer branch.
drop policy tenant_isolation on users;
create policy tenant_isolation on users for all
  using (tenant_id = app_tenant_id() and app_role() = 'tenant_admin')
  with check (tenant_id = app_tenant_id() and app_role() = 'tenant_admin');

drop policy tenant_isolation on documents;
create policy tenant_isolation on documents for all
  using (tenant_id = app_tenant_id() and app_role() in ('tenant_admin', 'customer'))
  with check (tenant_id = app_tenant_id() and app_role() = 'tenant_admin');

drop policy tenant_isolation on knowledge_chunks;
create policy tenant_isolation on knowledge_chunks for all
  using (tenant_id = app_tenant_id() and app_role() in ('tenant_admin', 'customer'))
  with check (tenant_id = app_tenant_id() and app_role() = 'tenant_admin');

drop policy tenant_isolation on offerings;
create policy tenant_isolation on offerings for all
  using (tenant_id = app_tenant_id() and app_role() in ('tenant_admin', 'customer'))
  with check (tenant_id = app_tenant_id() and app_role() = 'tenant_admin');

drop policy tenant_isolation on pricing_rules;
create policy tenant_isolation on pricing_rules for all
  using (tenant_id = app_tenant_id() and app_role() in ('tenant_admin', 'customer'))
  with check (tenant_id = app_tenant_id() and app_role() = 'tenant_admin');

drop policy tenant_isolation on tenant_assets;
create policy tenant_isolation on tenant_assets for all
  using (tenant_id = app_tenant_id() and app_role() in ('tenant_admin', 'customer'))
  with check (tenant_id = app_tenant_id() and app_role() = 'tenant_admin');

-- --- staff tables: tenant_admin/customer as today, plus staff's narrow slice ---

-- conversations: staff reads; staff may only flip status open <-> human
-- (C-6 takeover/handback; the takeover endpoints pass admin.role through).
drop policy tenant_isolation on conversations;
create policy tenant_isolation on conversations for all
  using (tenant_id = app_tenant_id() and app_role() in ('tenant_admin', 'customer'))
  with check (tenant_id = app_tenant_id() and app_role() in ('tenant_admin', 'customer'));
create policy staff_read on conversations for select
  using (tenant_id = app_tenant_id() and app_role() = 'staff');
create policy staff_takeover on conversations for update
  using (tenant_id = app_tenant_id() and app_role() = 'staff')
  with check (tenant_id = app_tenant_id() and app_role() = 'staff' and status in ('human', 'open'));

-- messages: staff reads; staff may insert its own human_agent replies and
-- the takeover/handback system stamp (C-6 writes both inside the same
-- transaction as the status flip; system rows never reach the customer poll,
-- which filters to customer/assistant/human_agent).
drop policy tenant_isolation on messages;
create policy tenant_isolation on messages for all
  using (tenant_id = app_tenant_id() and app_role() in ('tenant_admin', 'customer'))
  with check (tenant_id = app_tenant_id() and app_role() in ('tenant_admin', 'customer'));
create policy staff_read on messages for select
  using (tenant_id = app_tenant_id() and app_role() = 'staff');
create policy staff_conversation_write on messages for insert
  with check (tenant_id = app_tenant_id() and app_role() = 'staff' and role in ('human_agent', 'system'));

drop policy tenant_isolation on tool_calls;
create policy tenant_isolation on tool_calls for all
  using (tenant_id = app_tenant_id() and app_role() in ('tenant_admin', 'customer'))
  with check (tenant_id = app_tenant_id() and app_role() in ('tenant_admin', 'customer'));
create policy staff_read on tool_calls for select
  using (tenant_id = app_tenant_id() and app_role() = 'staff');

-- escalations: staff reads; staff claims and resolves.
drop policy tenant_isolation on escalations;
create policy tenant_isolation on escalations for all
  using (tenant_id = app_tenant_id() and app_role() in ('tenant_admin', 'customer'))
  with check (tenant_id = app_tenant_id() and app_role() in ('tenant_admin', 'customer'));
create policy staff_read on escalations for select
  using (tenant_id = app_tenant_id() and app_role() = 'staff');
create policy staff_claim on escalations for update
  using (tenant_id = app_tenant_id() and app_role() = 'staff')
  with check (tenant_id = app_tenant_id() and app_role() = 'staff' and status in ('claimed', 'resolved'));

-- quotes and cost_logs keep customer in the with-check (the graph persists
-- them under the customer context); orders and eval_runs are written only by
-- tenant_admin-scoped code (nothing app-side inserts orders), so no customer
-- branch there. Staff gets read-only on all four.
drop policy tenant_isolation on quotes;
create policy tenant_isolation on quotes for all
  using (tenant_id = app_tenant_id() and app_role() in ('tenant_admin', 'customer'))
  with check (tenant_id = app_tenant_id() and app_role() in ('tenant_admin', 'customer'));
create policy staff_read on quotes for select
  using (tenant_id = app_tenant_id() and app_role() = 'staff');

drop policy tenant_isolation on orders;
create policy tenant_isolation on orders for all
  using (tenant_id = app_tenant_id() and app_role() in ('tenant_admin', 'customer'))
  with check (tenant_id = app_tenant_id() and app_role() = 'tenant_admin');
create policy staff_read on orders for select
  using (tenant_id = app_tenant_id() and app_role() = 'staff');

drop policy tenant_isolation on cost_logs;
create policy tenant_isolation on cost_logs for all
  using (tenant_id = app_tenant_id() and app_role() in ('tenant_admin', 'customer'))
  with check (tenant_id = app_tenant_id() and app_role() in ('tenant_admin', 'customer'));
create policy staff_read on cost_logs for select
  using (tenant_id = app_tenant_id() and app_role() = 'staff');

drop policy tenant_isolation on eval_runs;
create policy tenant_isolation on eval_runs for all
  using (tenant_id = app_tenant_id() and app_role() in ('tenant_admin', 'customer'))
  with check (tenant_id = app_tenant_id() and app_role() = 'tenant_admin');
create policy staff_read on eval_runs for select
  using (tenant_id = app_tenant_id() and app_role() = 'staff');

-- M-2 (combined into 0025): one Cloudinary-backed cover per tenant and one
-- optional visual per offering.
alter table offerings add column category text;
alter table offerings add constraint offerings_tenant_id_id_key unique (tenant_id, id);

create table tenant_media (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  offering_id uuid,
  role text not null check (role in ('cover', 'offering')),
  type text not null check (type in ('image', 'video')),
  provider text not null check (provider in ('cloudinary', 'youtube', 'vimeo')),
  url text not null,
  public_id text,
  poster_url text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  foreign key (tenant_id, offering_id) references offerings(tenant_id, id) on delete cascade,
  check ((role = 'cover' and offering_id is null) or (role = 'offering' and offering_id is not null)),
  check ((provider = 'cloudinary' and public_id is not null) or (provider <> 'cloudinary'))
);
create unique index tenant_media_cover_key on tenant_media (tenant_id) where role = 'cover';
create unique index tenant_media_offering_key on tenant_media (tenant_id, offering_id) where role = 'offering';
create index tenant_media_tenant_idx on tenant_media (tenant_id);
alter table tenant_media enable row level security;
alter table tenant_media force row level security;
create policy tenant_isolation on tenant_media for all
  using (tenant_id = app_tenant_id() and app_role() in ('tenant_admin', 'customer'))
  with check (tenant_id = app_tenant_id() and app_role() = 'tenant_admin');
create policy platform_admin_read on tenant_media for select using (app_is_platform_admin());
create policy service_read on tenant_media for select using (app_is_service());
create trigger tenant_media_touch before update on tenant_media for each row execute function touch_updated_at();
grant select, insert, update, delete on tenant_media to wren_app;
