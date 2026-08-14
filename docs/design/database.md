# WREN - Database Design

> The implementation truth for schema shape. Supabase Postgres 15+ with `pgvector`. SQL below is meant to be pasted into migrations nearly verbatim.

## 1. Principles (apply to every table and migration)

1. **RLS on every tenant-scoped table, enforced AND forced.** Every table with `tenant_id` gets `ENABLE ROW LEVEL SECURITY` and `FORCE ROW LEVEL SECURITY` - `FORCE` matters because on Supabase the `postgres` role owns tables and would silently bypass RLS otherwise.
2. **Integer cents everywhere.** No `numeric`, floats, or dollar columns. Every monetary column is `*_cents integer`. The one exception is `cost_logs.cost_usd` (observability metadata, never customer-facing pricing).
3. **Domain-agnostic names only.** Columns describe generic concepts (items, rules, kinds, refs). A column that only makes sense for one vertical belongs in a `jsonb` config/attributes value instead.
4. **Denormalized `tenant_id` on `messages` and `tool_calls`.** RLS can then check it directly instead of joining through the parent.
5. **Quotes are immutable once sent.** Only `status` may change after insert. Enforced by trigger (section 7).
6. **Text + CHECK instead of native enums.** Easier to evolve in migrations, equally safe.
7. **UUID primary keys** via `gen_random_uuid()`. Timestamps are `timestamptz`, default `now()`.

## 2. Roles and tenant context

### 2.1 Connection roles

| Role | Used by | Properties |
|---|---|---|
| `postgres` (Supabase-managed) | migrations only | table owner; FORCE RLS still applies to it |
| `wren_app` | the FastAPI backend (its only DB identity) | `LOGIN`, no `BYPASSRLS`, granted CRUD on app tables |
| `wren_resolver` | owns `resolve_tenant_slug` only | `NOLOGIN`, `BYPASSRLS` - the single, audited RLS bypass in the system |

```sql
-- 0002_roles.sql. The migration runner substitutes ${WREN_APP_DB_PASSWORD} from env.
create role wren_app login password '${WREN_APP_DB_PASSWORD}';
grant usage on schema public to wren_app;
alter default privileges in schema public
  grant select, insert, update, delete on tables to wren_app;

create role wren_resolver nologin bypassrls;
```

### 2.2 Tenant context (the RLS key)

The backend sets two transaction-local settings before any query runs (FastAPI middleware):

```sql
select set_config('app.tenant_id', :tenant_id, true);  -- '' when none resolved
select set_config('app.role', :role, true);            -- 'customer' | 'tenant_admin' | 'platform_admin' | 'service'
```

`'service'` is the backend acting for itself in exactly one flow: the signup transaction. Its powers are the Shape C policies below and nothing else.

Helper functions every policy uses:

```sql
create or replace function app_tenant_id() returns uuid
  language sql stable as
$$ select nullif(current_setting('app.tenant_id', true), '')::uuid $$;

create or replace function app_is_platform_admin() returns boolean
  language sql stable as
$$ select current_setting('app.role', true) = 'platform_admin' $$;

create or replace function app_is_service() returns boolean
  language sql stable as
$$ select current_setting('app.role', true) = 'service' $$;
```

### 2.3 The three standard policy shapes

```sql
-- Shape A: tenant-scoped table (the default for everything below)
alter table <t> enable row level security;
alter table <t> force row level security;

create policy tenant_isolation on <t>
  for all
  using (tenant_id = app_tenant_id())
  with check (tenant_id = app_tenant_id());

create policy platform_admin_read on <t>
  for select
  using (app_is_platform_admin());
```

Platform-admin access is read-only through policies plus explicit writes on `tenants`/`platform_admins` only.

```sql
-- Shape B: platform-global table (no tenant_id): platform_admins, tenants (special-cased below)

-- Shape C: service role (signup transaction only). Applied to exactly three
-- tables - tenants, tenant_config, users - and only for INSERT:
create policy service_signup_insert on <t>
  for insert
  with check (app_is_service());
```

**Leakage test rule:** with `app.tenant_id` set to tenant A, every query against every tenant-scoped table must return zero tenant-B rows - including through joins, retrieval, and tool paths.

## 3. Tenancy & identity

```sql
create table tenants (
  id          uuid primary key default gen_random_uuid(),
  slug        text not null unique check (slug ~ '^[a-z0-9](-?[a-z0-9])*$' and length(slug) between 3 and 40),
  name        text not null,
  status      text not null default 'active' check (status in ('provisioning', 'active', 'suspended')),
  created_at  timestamptz not null default now()
);
alter table tenants enable row level security;
alter table tenants force row level security;
create policy tenant_self_read   on tenants for select using (id = app_tenant_id());
create policy platform_admin_all on tenants for all
  using (app_is_platform_admin()) with check (app_is_platform_admin());
create policy service_signup_insert on tenants for insert with check (app_is_service());

-- Slug -> tenant resolution. The unauthenticated customer surface must resolve a
-- slug BEFORE any tenant context exists, and FORCE RLS binds even the table owner.
-- So the resolver is owned by wren_resolver (NOLOGIN, BYPASSRLS), SECURITY DEFINER,
-- takes only a slug, and returns only public columns (including brand, needed pre-auth).
create or replace function resolve_tenant_slug(p_slug text)
  returns table (id uuid, name text, status text, brand jsonb)
  language sql stable security definer set search_path = public as
$$ select t.id, t.name, t.status, coalesce(c.brand, '{}'::jsonb)
     from tenants t left join tenant_config c on c.tenant_id = t.id
    where t.slug = p_slug $$;
alter function resolve_tenant_slug(text) owner to wren_resolver;
revoke all on function resolve_tenant_slug(text) from public;
grant execute on function resolve_tenant_slug(text) to wren_app;

create table tenant_config (
  tenant_id             uuid primary key references tenants(id) on delete cascade,
  system_prompt         text not null default '',
  tone                  text not null default 'friendly',
  enabled_tools         jsonb not null default '["search_knowledge","recommend_items","lookup_order_or_ticket","get_quote_inputs","create_escalation"]',
  escalation_threshold  real not null default 0.5 check (escalation_threshold between 0 and 1),
  brand                 jsonb not null default '{}',   -- {"accent":"#RRGGBB","logo_url":...,"display_name":...}
  config                jsonb not null default '{}',   -- tax {"rate_bps":int,"label":text}, hours, locale...
  updated_at            timestamptz not null default now()
);
-- Shape A + Shape C. Anonymous customers never read this table directly;
-- the pre-auth brand value arrives via resolve_tenant_slug.

create table users (
  id          uuid primary key,                        -- = Supabase auth.users.id
  tenant_id   uuid not null references tenants(id) on delete cascade,
  role        text not null default 'owner' check (role in ('owner', 'staff')),
  created_at  timestamptz not null default now()
);
-- Shape A + Shape C.

create table platform_admins (
  user_id     uuid primary key,                        -- = Supabase auth.users.id
  created_at  timestamptz not null default now()
);
alter table platform_admins enable row level security;
alter table platform_admins force row level security;
create policy platform_admin_only on platform_admins for all
  using (app_is_platform_admin()) with check (app_is_platform_admin());
-- Seeds for this table run with set_config('app.role','platform_admin',true) - FORCE RLS would block them otherwise.
```

Indexes: `tenants(slug)` is covered by the unique constraint; `users(tenant_id)`.

## 4. Knowledge & retrieval

```sql
create extension if not exists vector;

create table documents (
  id           uuid primary key default gen_random_uuid(),
  tenant_id    uuid not null references tenants(id) on delete cascade,
  filename     text not null,
  doc_type     text not null check (doc_type in ('policy', 'faq', 'catalog', 'price_list', 'other', 'website')),
  status       text not null default 'pending' check (status in ('pending', 'processing', 'ready', 'failed')),
  error        text,
  uploaded_at  timestamptz not null default now()
);
create index documents_tenant_idx on documents (tenant_id, status);

create table knowledge_chunks (
  id           uuid primary key default gen_random_uuid(),
  tenant_id    uuid not null references tenants(id) on delete cascade,
  document_id  uuid not null references documents(id) on delete cascade,
  content      text not null,
  embedding    vector(1536),                            -- text-embedding-3-small
  metadata     jsonb not null default '{}',             -- {"source":filename,"chunk_index":n,"kind":"prose"|"catalog_item"...}
  tsv          tsvector generated always as (to_tsvector('english', content)) stored,
  created_at   timestamptz not null default now()
);
create index knowledge_chunks_tenant_idx    on knowledge_chunks (tenant_id, document_id);
create index knowledge_chunks_embedding_idx on knowledge_chunks using hnsw (embedding vector_cosine_ops);
create index knowledge_chunks_tsv_idx       on knowledge_chunks using gin (tsv);
```

Both tables get Shape A. **Every retrieval query still carries `where tenant_id = :tenant_id` explicitly** - RLS is the net, not the filter; the explicit predicate lets the planner combine the HNSW/GIN indexes with tenant scoping.

Dense query: `order by embedding <=> :query_embedding limit :n`. Sparse: `where tsv @@ websearch_to_tsquery('english', :query) order by ts_rank(...) desc limit :n`. Fuse with RRF in Python, then cross-encoder rerank.

## 5. Catalog & pricing (the deterministic-pricing tables)

```sql
create table catalog_items (
  id           uuid primary key default gen_random_uuid(),
  tenant_id    uuid not null references tenants(id) on delete cascade,
  name         text not null,
  description  text not null default '',
  attributes   jsonb not null default '{}',             -- generic: {"category":..., "tags":[...]}
  price_cents  integer check (price_cents is null or price_cents >= 0),  -- null = priced via a rule
  active       boolean not null default true,
  created_at   timestamptz not null default now(),
  updated_at   timestamptz not null default now()
);
create index catalog_items_tenant_idx on catalog_items (tenant_id, active);

create table pricing_rules (
  id                 uuid primary key default gen_random_uuid(),
  tenant_id          uuid not null references tenants(id) on delete cascade,
  code               text not null,                     -- stable selector the agent emits, e.g. 'screen-repair-tier-a'
  label              text not null,
  unit_amount_cents  integer not null check (unit_amount_cents >= 0),
  unit               text not null default 'each',      -- 'each' | 'hour' | 'session' | free text, display-only
  conditions         jsonb not null default '{}',       -- {"min_qty":..,"applies_to":..} - engine-interpreted
  active             boolean not null default true,
  created_at         timestamptz not null default now(),
  updated_at         timestamptz not null default now(),
  unique (tenant_id, code)
);
create index pricing_rules_tenant_idx on pricing_rules (tenant_id, active);

create table quotes (
  id               uuid primary key default gen_random_uuid(),
  tenant_id        uuid not null references tenants(id) on delete cascade,
  conversation_id  uuid not null,
  foreign key (tenant_id, conversation_id) references conversations (tenant_id, id) on delete cascade,
  line_items       jsonb not null,     -- [{"kind":"rule"|"item","code"|"item_id":..,"label":..,"quantity":n,"unit_amount_cents":n,"line_total_cents":n}]
  subtotal_cents   integer not null check (subtotal_cents >= 0),
  tax_cents        integer not null default 0 check (tax_cents >= 0),
  total_cents      integer not null check (total_cents = subtotal_cents + tax_cents),
  status           text not null default 'draft' check (status in ('draft', 'sent', 'expired')),
  created_at       timestamptz not null default now()
);
create index quotes_tenant_idx on quotes (tenant_id, conversation_id);
```

All Shape A. **Only the pricing engine writes `quotes`** - it computes `line_items/subtotal/tax/total`; no other code path constructs those values.

## 6. Conversations & operations

```sql
create table conversations (
  id            uuid primary key default gen_random_uuid(),
  tenant_id     uuid not null references tenants(id) on delete cascade,
  customer_ref  text,                                   -- anonymous session id or handle; no auth at core scope
  channel       text not null default 'web' check (channel in ('web')),
  status        text not null default 'open' check (status in ('open', 'escalated', 'closed')),
  created_at    timestamptz not null default now(),
  unique (tenant_id, id)     -- composite-FK target
);
create index conversations_tenant_idx on conversations (tenant_id, status, created_at desc);

-- Denormalized tenant_id is only safe if it cannot drift from the parent row's
-- tenant. FK checks bypass RLS, so the composite FKs below make a cross-tenant
-- attach impossible at the schema level.
create table messages (
  id               uuid primary key default gen_random_uuid(),
  tenant_id        uuid not null references tenants(id) on delete cascade,
  conversation_id  uuid not null,
  foreign key (tenant_id, conversation_id) references conversations (tenant_id, id) on delete cascade,
  unique (tenant_id, id),
  role             text not null check (role in ('customer', 'assistant', 'system', 'human_agent')),
  content          text not null,
  agent_node       text,                                -- which graph node authored it
  created_at       timestamptz not null default now()
);
create index messages_conversation_idx on messages (conversation_id, created_at);
create index messages_tenant_idx       on messages (tenant_id);

create table tool_calls (
  id          uuid primary key default gen_random_uuid(),
  tenant_id   uuid not null references tenants(id) on delete cascade,
  message_id  uuid not null,
  foreign key (tenant_id, message_id) references messages (tenant_id, id) on delete cascade,
  tool_name   text not null,
  arguments   jsonb not null default '{}',
  result      jsonb,
  success     boolean not null,
  latency_ms  integer,
  created_at  timestamptz not null default now()
);
create index tool_calls_message_idx on tool_calls (message_id);
create index tool_calls_tenant_idx  on tool_calls (tenant_id, tool_name);

-- orders: mock order/ticket data, seeded per tenant. Generic on purpose - a phone
-- shop's repair ticket and a store's order are both "an order of some kind with a status".
create table orders (
  id            uuid primary key default gen_random_uuid(),
  tenant_id     uuid not null references tenants(id) on delete cascade,
  ref_code      text not null,                          -- what a customer quotes back: 'R-1042', 'ORD-77'
  kind          text not null,                          -- tenant-defined: 'repair','order','booking'... data, not code
  customer_ref  text,
  status        text not null,                          -- tenant-defined vocabulary, stored as data
  details       jsonb not null default '{}',
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now(),
  unique (tenant_id, ref_code)
);

create table escalations (
  id               uuid primary key default gen_random_uuid(),
  tenant_id        uuid not null references tenants(id) on delete cascade,
  conversation_id  uuid not null,
  foreign key (tenant_id, conversation_id) references conversations (tenant_id, id) on delete cascade,
  reason           text not null,
  status           text not null default 'open' check (status in ('open', 'claimed', 'resolved')),
  created_at       timestamptz not null default now(),
  resolved_at      timestamptz
);
create index escalations_tenant_idx on escalations (tenant_id, status, created_at desc);
```

All Shape A.

## 7. Eval & cost

```sql
create table eval_cases (
  id          uuid primary key default gen_random_uuid(),
  tenant_id   uuid not null references tenants(id) on delete cascade,
  case_type   text not null check (case_type in ('retrieval', 'generation', 'trajectory', 'injection', 'leakage')),
  input       jsonb not null,          -- {"query":...} or {"messages":[...],"persona":...}
  expected    jsonb not null,          -- {"relevant_chunk_ids":[...]} or {"tools":[...],"must_not_contain":[...]}
  created_at  timestamptz not null default now()
);

create table eval_runs (
  id          uuid primary key default gen_random_uuid(),
  tenant_id   uuid not null references tenants(id) on delete cascade,
  run_type    text not null check (run_type in ('retrieval', 'generation', 'trajectory', 'injection', 'leakage', 'full')),
  metrics     jsonb not null,          -- {"recall_at_5":0.87,"mrr":...}
  git_sha     text not null default '',
  created_at  timestamptz not null default now()
);
create index eval_runs_tenant_idx on eval_runs (tenant_id, run_type, created_at desc);

create table cost_logs (
  id               uuid primary key default gen_random_uuid(),
  tenant_id        uuid not null references tenants(id) on delete cascade,
  conversation_id  uuid references conversations(id) on delete set null,
  model            text not null,
  input_tokens     integer not null default 0,
  output_tokens    integer not null default 0,
  cost_usd         numeric(12,6) not null default 0,   -- the one non-cents money column (observability only)
  created_at       timestamptz not null default now()
);
create index cost_logs_tenant_idx on cost_logs (tenant_id, created_at desc);
create index cost_logs_conversation_idx on cost_logs (conversation_id);
```

All Shape A.

## 8. Triggers

```sql
-- updated_at maintenance (tenant_config, catalog_items, pricing_rules, orders)
create or replace function touch_updated_at() returns trigger language plpgsql as
$$ begin new.updated_at = now(); return new; end $$;
create trigger <t>_touch before update on <t> for each row execute function touch_updated_at();

-- quote immutability: after insert, only draft->sent->expired status transitions are allowed
create or replace function quotes_immutable() returns trigger language plpgsql as
$$
begin
  if new.line_items      is distinct from old.line_items
  or new.subtotal_cents  is distinct from old.subtotal_cents
  or new.tax_cents       is distinct from old.tax_cents
  or new.total_cents     is distinct from old.total_cents
  or new.tenant_id       is distinct from old.tenant_id
  or new.conversation_id is distinct from old.conversation_id then
    raise exception 'quotes are immutable except status';
  end if;
  if not ((old.status, new.status) in (('draft','sent'), ('draft','expired'), ('sent','expired'), (old.status, old.status))) then
    raise exception 'invalid quote status transition % -> %', old.status, new.status;
  end if;
  return new;
end
$$;
create trigger quotes_immutable_trg before update on quotes for each row execute function quotes_immutable();
```

## 9. Migration order

One migration file per numbered step, `backend/migrations/NNNN_<name>.sql`, applied in order by a plain runner (a simple Python runner over `schema_migrations(version text primary key, applied_at timestamptz)` - no heavy framework):

```
0001_extensions.sql        vector; helper functions app_tenant_id/app_is_platform_admin; touch_updated_at
0002_roles.sql             wren_app role + default privileges
0003_tenancy.sql           tenants, tenant_config, users, platform_admins (+ RLS, resolve_tenant_slug)
0004_knowledge.sql         documents, knowledge_chunks (+ RLS, HNSW/GIN indexes)
0005_conversations.sql     conversations, messages, tool_calls (+ RLS)   -- before quotes (FK target)
0006_commerce.sql          catalog_items, pricing_rules, quotes (+ RLS, quotes_immutable)
0007_operations.sql        orders, escalations (+ RLS)
0008_eval_cost.sql         eval_cases, eval_runs, cost_logs (+ RLS)
```

Every table migration ends with its RLS + policies + grants to `wren_app`. A table without RLS must never survive a migration - the schema audit (below) enforces this.

## 10. Seed plan

`backend/seeds/` (idempotent scripts, runnable per environment):

- `seed_tenant1_phoneshop.py` - Tenant 1 (anchor): slug `bytefix`, config (tone, threshold, tax), ~15 catalog_items, ~12 pricing_rules, ~20 mock orders, knowledge docs via the real ingestion pipeline.
- `seed_tenant2_dental.py` - Tenant 2 (generalization proof): created only through the conversational onboarding flow + uploads; holds just raw input documents and the interview script, never direct table writes.
- `seed_leakage_pair.py` - two throwaway tenants with disjoint secret facts for the leakage test.
- `seed_platform_admin.py` - the founder's auth user id into `platform_admins`.

## 11. Schema audit (runs in CI)

A test queries `pg_tables`/`pg_policies` and asserts: every table with a `tenant_id` column has RLS enabled and forced with at least the `tenant_isolation` policy; every monetary column matches `%_cents` and is integer-typed (`cost_logs.cost_usd` is the single allowed exception). This turns principles 1-2 from prose into a failing test.
