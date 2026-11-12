# 32: Selling modes, lead capture, and the order kernel

**Status:** Active - todo.
**Phase 2 area:** Onboarding, lead capture, ordering, booking, quotes, stock, calendar, owner console, payments ledger.

Depends on ticket 29 (source-first onboarding) and ticket 31 (review
surface), both on `development`. Starts from `development` at `e2ddb96`.
Reserves migrations `0039` through `0042` in slice order.

## Intent

The owner should never configure a capacity model. They confirm how customers
buy, in their own words, and the app enables only the capabilities that
business needs. A restaurant gets orders, a barber gets bookings, a cleaner
gets quotes, a shop gets products. Any owner can add a second capability later
without a new app or a settings matrix.

Underneath, one order object and one capacity kernel handle every combination:
a restaurant can take a pickup order for an item that is sold out or limited
by kitchen capacity; a barber can sell a product alongside a booking; a
cleaner can turn a quote into a scheduled job. No code branches on a vertical.
The mode, capabilities, and labels are tenant data.

## Locked decisions

| # | Decision |
|---|---|
| 1 | Four selling modes: Orders, Bookings, Quotes, Products. A mode is a default capability bundle, never a lock. |
| 2 | Capabilities are independent switches. The owner enables extras one at a time. |
| 3 | Labels are tenant data, inferred from the source and renameable. No hardcoded vertical keyword reaches a screen. |
| 4 | Onboarding infers the mode from the source and asks one confirmation. Wrong inference is corrected in one tap. |
| 5 | The calendar is a first-class view over any commitment with a time. It is not a separate mode. |
| 6 | Lead capture is channel-agnostic: chat, form, phone, walk-in, social all write the same lead row. |
| 7 | One work object. A booking is an order with a time. There is no separate `bookings` table or state machine. |
| 8 | Stock is one capacity kind with three levels: `none`, `flag`, `counted`. No suppliers, purchase orders, barcodes, or warehouses. |
| 9 | An offering can require several capacity pools. One order transaction reserves all of them atomically. |
| 10 | Holds are `held` -> `committed`, `released`, or `expired`. Default TTL 15 minutes; 30 minutes while owner approval is pending. |
| 11 | Payments start as an owner-kept ledger (cash, bank, terminal). Stripe Connect is a follow-up ticket, not this one. |
| 12 | The customer agent never authors money or times. Totals come from the pricing engine; slots come from availability. |
| 13 | Owner console is four destinations: Home, Work, Chats, Money. Settings lives behind the avatar. |
| 14 | Home, Work, Chats, and Money render from capability flags and labels, never from a business type. |
| 15 | Delivery is a fulfillment mode with address, fee, and window. No courier dispatch, routing, or tracking. |
| 16 | Email and SMS notifications are a follow-up ticket. This ticket shows confirmation and status in chat plus a read-only order page. |

## Current behaviour this changes

| Today | Where | Change |
|---|---|---|
| `orders` is mock data with free-text `status` and a `details` blob | `backend/migrations/0007_operations.sql:3`, `seeds/_helpers.py:242` | Add a canonical `state`, fulfillment and time columns; keep `status` as the display label |
| No `order_lines`, `leads`, `capacity_*`, `payments` tables | `docs/agencx/design/database.md` | Add them in slices B, C, D, G |
| `offerings` has no purchase, fulfillment, duration, stock, or acceptance fields | `backend/migrations/0023_rename_catalog_items_to_offerings.sql` | Add the six config axes in slice B |
| `quotes` only moves `draft -> sent -> expired` and has no order link | `backend/migrations/0006_commerce.sql:68` | Add `accepted`/`declined`, `order_id`, `lead_id`, `source` |
| `lookup_order_or_ticket` returns free-text status and `details` | `backend/app/agents/tools.py:38` | Return `state`, time, lines, and payment state; keep the old fields |
| The chat tool list has no ordering or booking tools | `backend/app/agents/agent_node.py:549` | Add availability, order, status, and payment tools behind identity and state gates |
| Onboarding ends at confirm with no selling-mode step | `backend/app/onboarding/agent.py`, `frontend/.../onboarding/page.tsx` | Add one inferred confirmation beat before the final summary |
| Console has Home, Chats, Business only | `frontend/src/app/(tenant-admin)/(console)/layout.tsx` | Add Work and Money; Home becomes the daily command centre |
| `tenant_config.config` has no ordering block | `backend/migrations/0003_tenancy.sql:19` | Add `config.ordering` in slice A |

## The four selling modes

| Mode | Feels like | Default capabilities | Primary Work screen |
|---|---|---|---|
| `orders` | Restaurant, cafe, takeaway | `instant`, `in_house`/`pickup`, `asap`, stock `flag` | Orders board |
| `bookings` | Barber, salon, clinic, tutor | `instant`, `onsite`, `slot`, resource pool | Day calendar |
| `quotes` | Cleaner, trades, repair | `quote`, `onsite`, `window`, owner approval | Requests inbox |
| `products` | Retail, e-commerce, grocery | `instant`, `shipping`/`pickup`, stock `counted` | Products and orders |

A tenant can hold more than one selling mode. The Work screen shows one tab
per enabled mode. Onboarding sets one primary mode; Settings adds a second
through "Add another way to sell". There is no `mixed` preset and no
`business_type` column.

## Capabilities and labels

Six capability axes, stored in `tenant_config.config.ordering`:

| Axis | Values | Owner wording |
|---|---|---|
| `sell` | array of `orders`, `bookings`, `quotes`, `products` | "What do customers do?" |
| `schedule` | `none`, `asap`, `slot`, `window` | "Do customers pick a time?" |
| `stock` | `none`, `flag`, `counted` | "Do you run out of items?" |
| `fulfillment` | `in_house`, `pickup`, `delivery`, `onsite`, `shipping` | "How do they get it?" |
| `acceptance` | `auto`, `owner`, `deposit` | "Do you approve each one?" |
| `payment` | `now`, `later`, `deposit` | "When do they pay?" |

The mode sets defaults for these axes. Every axis stays editable. A restaurant
can be `orders` plus `pickup` plus `slot` plus `counted` stock. A barber can be
`bookings` plus `products`. A cleaner can be `quotes` plus `window` plus a
booking after acceptance.

Labels live beside the capabilities:

```json
{
  "mode": "orders",
  "capabilities": {
    "sell": ["orders"],
    "schedule": "slot",
    "stock": "flag",
    "fulfillment": ["in_house", "pickup"],
    "acceptance": "auto",
    "payment": "now"
  },
  "labels": {
    "item": "Dish",
    "items": "Menu",
    "work": "Orders",
    "add_item": "Add a dish",
    "time": "Prep time",
    "sold_out": "Sold out today",
    "action": "Order"
  }
}
```

The UI reads `capabilities` and `labels`. It never reads `mode` for logic; the
mode is only a default bundle and a copy hint. A missing label falls back to a
neutral default (`Item`, `Items`, `Work`, `Add item`, `Time`, `Unavailable`).

## Onboarding

The ticket 29 flow gains one beat:

1. Name
2. Website or document
3. Review business details
4. **How customers buy from you** (inferred, one-tap confirm)
5. Missing required beats
6. Optional beats
7. Final summary -> go live

### Inference

| Signal | Likely mode |
|---|---|
| Nav: Menu, Order online, Pickup, Delivery | `orders` |
| Nav: Book now, Appointments, Schedule, Staff | `bookings` |
| Nav: Get a quote, Free estimate, Request a quote | `quotes` |
| Nav: Shop, Products, Cart, Shipping | `products` |
| PDF menu with prices | `orders` or `products` |
| PDF service list with durations | `bookings` |
| "From $X", "custom", "site visit" | `quotes` |
| Business name/type: cafe, restaurant, takeaway | `orders` |
| barber, salon, clinic, studio | `bookings` |
| cleaning, plumbing, repairs, trades | `quotes` or `bookings` |
| shop, store, boutique | `products` |

The inference returns `{mode, capabilities, labels, confidence, evidence}`.
Business type is a weak signal; the source content wins. If the source has two
strong signals, return both and ask which is primary. If there is no source,
ask the four modes directly.

The classifier is deterministic: keyword scoring over the source text and the
already-extracted profile, offerings, and categories. It adds no model call, so
the confirmation is fast and repeatable. The evidence list names the signals it
used, so a wrong prediction is explainable.

### Confirmation card

High confidence, one card in the owner's words:

> It looks like customers **order food** from you. They can eat in, pick up, or
> get delivery. You sometimes run out of dishes. They pay when they order.
>
> Is that right?
>
> [Yes, that's right] [Change something]

Medium confidence:

> It looks like customers either **order food** or **book a table**. Which is
> closer?

Low confidence: show the four modes as cards.

`Change something` opens the four modes as a multi-select, then only the
follow-ups for what was picked:

| Mode | Follow-ups |
|---|---|
| Orders | How do they get it? How long does an order take? Do you run out of items? Pay now or on pickup? |
| Bookings | What do they book? Who do they book with? How long is each service? Approve each booking? Deposit? |
| Quotes | Quote each job or use a rate card? What do you need to know? Deposit? How soon do you respond? |
| Products | Track stock or just sold out? Ship, pickup, or delivery? Time slots? Pay now or on delivery? |

The owner can skip any follow-up; defaults apply. The final summary is rendered
from the stored capabilities and labels, never from a model. It repeats the
enabled capabilities in plain language:

> Your assistant will take orders from your menu, offer eat-in and pickup, mark
> dishes sold out, and take payment when the order is placed. You can change
> this later.
>
> [Go live] [Edit]

### Endpoints

- `GET /api/onboarding/selling-mode/suggestion` returns the inference and its
  evidence.
- `POST /api/onboarding/selling-mode` accepts `{mode, capabilities, labels}`,
  validates, and writes `tenant_config.config.ordering`.
- `GET /api/onboarding/selling-mode` returns the current config for the review
  card.
- The confirmation beat is deterministic: a confirmation writes the config and
  advances the cursor without a model call.

## Owner console

Four destinations. Settings sits behind the avatar.

| Destination | Contents |
|---|---|
| Home | Today, Needs you, Money summary, Share your page |
| Work | One tab per enabled selling mode: Orders, Calendar, Requests, Products |
| Chats | Conversations and handoffs |
| Money | To collect, collected, refunds |

### Work by mode

| Mode | Primary view | Secondary view | Empty state |
|---|---|---|---|
| Orders | Board: New, Preparing, Ready, Completed | Calendar when pickup or delivery slots exist | "Add your first dish" |
| Bookings | Day calendar | Services list | "Add your first service" |
| Quotes | Requests: New, Quoted, Won | Calendar after acceptance | "Share your page to get requests" |
| Products | Products and orders | Calendar when slots exist | "Add your first product" |

The Work screen shows `Board` and `Calendar` as a segmented control when both
are useful. A restaurant with in-house only sees the board. A restaurant with
pickup slots sees both. A barber sees the calendar and services. A cleaner sees
requests, then the calendar after a quote is accepted.

### Daily loop

- Orders: tap New -> Preparing -> Ready -> Completed. Tap a dish -> "Sold out
  today".
- Bookings: tap a booking -> Confirm, Complete, No-show. Block time in two taps.
- Quotes: open a request -> "Send quote" -> customer accepts -> pick a date.
- Products: adjust stock with +/-, mark sold out, pack and ship.

The owner never sees `capacity_pool`, `hold`, `throughput`, `resource`,
`state`, or `quantity_per_unit` in any owner-facing string.

## Customer surface

The chat is the same. The cards adapt to the order's fulfillment and time:

| Card | Shown when | Contents |
|---|---|---|
| Offering card | catalog or recommendation | name, price/wording, sold-out state |
| Availability card | `schedule` is `slot` or `window` | up to 3 slots, timezone, duration |
| Order card | `start_order` succeeds | lines, total, fulfillment, time, reference |
| Quote card | `purchase_mode=quote` | engine total, accept/decline, expiry |
| Payment card | `confirm_order` or deposit due | amount, hosted pay link, due time |
| Status card | `get_order_status` | state, lines, time, payment state |

Cards never show capacity or hold language. A sold-out item says "Sold out
today" and offers alternatives. A full slot says "That time is taken" and
offers the next three.

## Domain model

All new tables are Shape A: `tenant_id`, `ENABLE` and `FORCE ROW LEVEL
SECURITY`, `tenant_isolation`, `platform_admin_read`, grants to `wren_app`.
Every monetary column is `*_cents integer`. Every timestamp is `timestamptz`.

### Orders extension (migration 0039)

`orders` keeps `ref_code`, `kind`, `customer_ref`, `status`, and `details`.
`status` stays the tenant-facing display label. Add:

```sql
alter table orders
  add column state text not null default 'draft'
    check (state in ('draft','quoted','pending_owner','confirmed','in_progress',
                     'ready','fulfilled','completed','cancelled','declined',
                     'expired','no_show')),
  add column conversation_id uuid,
  add column lead_id uuid,
  add column quote_id uuid,
  add column fulfillment_mode text
    check (fulfillment_mode is null or fulfillment_mode in
           ('in_house','pickup','delivery','onsite','remote','digital','shipping')),
  add column time_mode text
    check (time_mode is null or time_mode in ('none','asap','slot','window','scheduled')),
  add column promise_at timestamptz,
  add column starts_at timestamptz,
  add column ends_at timestamptz,
  add column timezone text,
  add column acceptance_mode text not null default 'auto'
    check (acceptance_mode in ('auto','owner','deposit')),
  add column total_cents integer check (total_cents is null or total_cents >= 0),
  add column payment_state text not null default 'unpaid'
    check (payment_state in ('unpaid','deposit_due','deposit_paid','paid',
                             'refunded','partially_refunded','failed')),
  add column accepted_at timestamptz,
  add column confirmed_at timestamptz,
  add column completed_at timestamptz,
  add column cancelled_at timestamptz;

alter table orders add constraint orders_tenant_id_id_key unique (tenant_id, id);
create index orders_tenant_state_idx on orders (tenant_id, state, created_at desc);
create index orders_tenant_time_idx on orders (tenant_id, starts_at, ends_at);
create index orders_tenant_conversation_idx on orders (tenant_id, conversation_id);
```

Backfill: `state='completed'` where `status in ('closed','completed','fulfilled')`,
otherwise `state='confirmed'`. Existing mock rows keep their `status`.

### Order lines (migration 0039)

```sql
create table order_lines (
  id                uuid primary key default gen_random_uuid(),
  tenant_id         uuid not null references tenants(id) on delete cascade,
  order_id          uuid not null,
  offering_id       uuid,
  name_snapshot     text not null,
  quantity          integer not null check (quantity > 0),
  unit_price_cents  integer not null check (unit_price_cents >= 0),
  line_total_cents  integer not null check (line_total_cents >= 0),
  line_state        text not null default 'pending'
    check (line_state in ('pending','ready','fulfilled','cancelled','substituted')),
  modifiers         jsonb not null default '{}',
  notes             text not null default '',
  created_at        timestamptz not null default now(),
  updated_at        timestamptz not null default now(),
  unique (tenant_id, id),
  foreign key (tenant_id, order_id) references orders (tenant_id, id) on delete cascade,
  foreign key (tenant_id, offering_id) references offerings (tenant_id, id) on delete set null
);
create index order_lines_order_idx on order_lines (tenant_id, order_id);
```

`unit_price_cents` and `line_total_cents` are written only by the pricing
engine or copied from the offering's fixed price. No request body carries them.

### Leads (migration 0039)

```sql
create table leads (
  id               uuid primary key default gen_random_uuid(),
  tenant_id        uuid not null references tenants(id) on delete cascade,
  conversation_id  uuid,
  source           text not null default 'chat'
    check (source in ('chat','form','phone','walk_in','social','other')),
  intent           text not null check (intent in ('order','booking','quote','contact')),
  customer_name    text,
  customer_email   text,
  customer_phone   text,
  offering_id      uuid,
  preferred_start  timestamptz,
  preferred_end    timestamptz,
  notes            text not null default '',
  status           text not null default 'new'
    check (status in ('new','contacted','quoted','won','lost','expired')),
  order_id         uuid,
  created_at       timestamptz not null default now(),
  updated_at       timestamptz not null default now(),
  unique (tenant_id, id),
  foreign key (tenant_id, offering_id) references offerings (tenant_id, id) on delete set null
);
create index leads_tenant_status_idx on leads (tenant_id, status, created_at desc);
```

A lead exists for quote-mode demand and for any owner-created request. Instant
orders may create and convert a lead in the same transaction, or skip it. The
`source` is the channel, never a vertical.

### Offering ordering fields (migration 0039)

```sql
alter table offerings
  add column purchase_mode text not null default 'instant'
    check (purchase_mode in ('instant','quote')),
  add column fulfillment_modes jsonb not null default '["in_house"]',
  add column time_mode text not null default 'none'
    check (time_mode in ('none','asap','slot','window','scheduled')),
  add column duration_minutes integer check (duration_minutes is null or duration_minutes > 0),
  add column buffer_before_minutes integer not null default 0 check (buffer_before_minutes >= 0),
  add column buffer_after_minutes integer not null default 0 check (buffer_after_minutes >= 0),
  add column capacity_per_slot integer not null default 1 check (capacity_per_slot > 0),
  add column stock_mode text not null default 'none'
    check (stock_mode in ('none','flag','counted')),
  add column sold_out boolean not null default false,
  add column acceptance_mode text not null default 'auto'
    check (acceptance_mode in ('auto','owner','deposit')),
  add column deposit_bps integer not null default 0 check (deposit_bps between 0 and 10000),
  add column lead_time_minutes integer not null default 0 check (lead_time_minutes >= 0);
```

`fulfillment_modes` is validated in the service against the allowed set.
`stock_mode='flag'` reads `sold_out`; `counted` reads a stock pool.

### Quotes extension (migration 0039)

```sql
alter table quotes
  add column order_id uuid,
  add column lead_id uuid,
  add column source text not null default 'instant'
    check (source in ('instant','owner')),
  add column accepted_at timestamptz,
  add column declined_at timestamptz;

alter table quotes drop constraint if exists quotes_status_check;
alter table quotes add constraint quotes_status_check
  check (status in ('draft','sent','accepted','declined','expired'));
alter table quotes add constraint quotes_tenant_id_id_key unique (tenant_id, id);
```

The immutability trigger keeps amounts immutable and extends the allowed status
transitions: `draft -> sent`, `sent -> accepted`, `sent -> declined`,
`sent -> expired`, `accepted -> expired`, and identity transitions. Accepted and
declined are terminal for the customer.

### Capacity kernel (migration 0040)

```sql
create table capacity_pools (
  id              uuid primary key default gen_random_uuid(),
  tenant_id       uuid not null references tenants(id) on delete cascade,
  kind            text not null check (kind in ('stock','throughput','slot','resource')),
  name            text not null,
  offering_id     uuid,
  location_key    text not null default 'default',
  capacity        integer not null check (capacity >= 0),
  bucket_minutes  integer check (bucket_minutes is null or bucket_minutes > 0),
  timezone        text,
  active          boolean not null default true,
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now(),
  unique (tenant_id, id),
  foreign key (tenant_id, offering_id) references offerings (tenant_id, id) on delete cascade
);
create index capacity_pools_tenant_kind_idx on capacity_pools (tenant_id, kind, active);

create table offering_capacity_requirements (
  id                 uuid primary key default gen_random_uuid(),
  tenant_id          uuid not null references tenants(id) on delete cascade,
  offering_id        uuid not null,
  pool_id            uuid not null,
  quantity_per_unit  integer not null default 0 check (quantity_per_unit >= 0),
  per_order          integer not null default 0 check (per_order >= 0),
  created_at         timestamptz not null default now(),
  unique (tenant_id, offering_id, pool_id),
  check (quantity_per_unit > 0 or per_order > 0),
  foreign key (tenant_id, offering_id) references offerings (tenant_id, id) on delete cascade,
  foreign key (tenant_id, pool_id) references capacity_pools (tenant_id, id) on delete cascade
);

create table capacity_holds (
  id               uuid primary key default gen_random_uuid(),
  tenant_id        uuid not null references tenants(id) on delete cascade,
  order_id         uuid not null,
  order_line_id    uuid,
  pool_id          uuid not null,
  quantity         integer not null check (quantity > 0),
  starts_at        timestamptz,
  ends_at          timestamptz,
  state            text not null default 'held'
    check (state in ('held','committed','released','expired')),
  expires_at       timestamptz,
  idempotency_key  text not null,
  created_at       timestamptz not null default now(),
  updated_at       timestamptz not null default now(),
  unique (tenant_id, idempotency_key),
  foreign key (tenant_id, order_id) references orders (tenant_id, id) on delete cascade,
  foreign key (tenant_id, order_line_id) references order_lines (tenant_id, id) on delete cascade,
  foreign key (tenant_id, pool_id) references capacity_pools (tenant_id, id) on delete cascade
);
create index capacity_holds_pool_state_idx
  on capacity_holds (tenant_id, pool_id, state, starts_at, ends_at);
create index capacity_holds_order_idx on capacity_holds (tenant_id, order_id);

create table capacity_adjustments (
  id          uuid primary key default gen_random_uuid(),
  tenant_id   uuid not null references tenants(id) on delete cascade,
  pool_id     uuid not null,
  delta       integer not null,
  reason      text not null
    check (reason in ('restock','sale','return','correction','owner_override')),
  order_id    uuid,
  actor       text not null default 'owner'
    check (actor in ('owner','system','agent')),
  note        text not null default '',
  created_at  timestamptz not null default now(),
  foreign key (tenant_id, pool_id) references capacity_pools (tenant_id, id) on delete cascade
);
create index capacity_adjustments_pool_idx on capacity_adjustments (tenant_id, pool_id, created_at);
```

`capacity_pools.capacity` is the baseline on-hand for `stock` and the maximum
concurrent quantity per interval for the other kinds. `bucket_minutes` is set
for `throughput` (for example 15) and for fixed `slot` pools; it is null for
`resource` and `stock`.

### Availability (migration 0041)

```sql
create table availability_rules (
  id              uuid primary key default gen_random_uuid(),
  tenant_id       uuid not null references tenants(id) on delete cascade,
  pool_id         uuid not null,
  weekday         smallint not null check (weekday between 0 and 6),
  starts_at       time not null,
  ends_at         time not null,
  timezone        text not null,
  effective_from  date,
  effective_to    date,
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now(),
  check (starts_at < ends_at),
  foreign key (tenant_id, pool_id) references capacity_pools (tenant_id, id) on delete cascade
);
create index availability_rules_pool_idx on availability_rules (tenant_id, pool_id, weekday);

create table availability_exceptions (
  id          uuid primary key default gen_random_uuid(),
  tenant_id   uuid not null references tenants(id) on delete cascade,
  pool_id     uuid not null,
  starts_at   timestamptz not null,
  ends_at     timestamptz not null,
  kind        text not null check (kind in ('blocked','extra')),
  note        text not null default '',
  created_at  timestamptz not null default now(),
  check (starts_at < ends_at),
  foreign key (tenant_id, pool_id) references capacity_pools (tenant_id, id) on delete cascade
);
create index availability_exceptions_pool_idx
  on availability_exceptions (tenant_id, pool_id, starts_at, ends_at);
```

### Payments (migration 0042)

```sql
create table payments (
  id            uuid primary key default gen_random_uuid(),
  tenant_id     uuid not null references tenants(id) on delete cascade,
  order_id      uuid not null,
  quote_id      uuid,
  kind          text not null check (kind in ('deposit','balance','full','refund')),
  amount_cents  integer not null check (amount_cents >= 0),
  currency      text not null default 'AUD',
  state         text not null default 'due'
    check (state in ('due','processing','paid','failed','refunded')),
  provider      text not null default 'ledger'
    check (provider in ('ledger','stripe')),
  provider_ref  text,
  paid_at       timestamptz,
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now(),
  unique (tenant_id, provider, provider_ref),
  foreign key (tenant_id, order_id) references orders (tenant_id, id) on delete cascade,
  foreign key (tenant_id, quote_id) references quotes (tenant_id, id) on delete set null
);
create index payments_order_idx on payments (tenant_id, order_id, state);
```

`provider_ref` is nullable for ledger payments; the unique constraint allows
multiple nulls. Mark-paid is idempotent: a paid row stays paid, and a repeat
request returns the same row.

### Config

`tenant_config.config.ordering`:

```json
{
  "mode": "orders",
  "capabilities": {
    "sell": ["orders"],
    "schedule": "slot",
    "stock": "flag",
    "fulfillment": ["in_house", "pickup"],
    "acceptance": "auto",
    "payment": "now"
  },
  "labels": {
    "item": "Dish",
    "items": "Menu",
    "work": "Orders",
    "add_item": "Add a dish",
    "time": "Prep time",
    "sold_out": "Sold out today",
    "action": "Order"
  },
  "defaults": {
    "hold_ttl_minutes": 15,
    "owner_hold_ttl_minutes": 30,
    "slot_increment_minutes": 15,
    "lead_time_minutes": 30,
    "deposit_bps": 0,
    "timezone": "Australia/Sydney",
    "delivery_fee_cents": 0,
    "delivery_radius_km": 0
  }
}
```

The config is written by the onboarding confirmation and by Settings. The
ordering service reads it; the frontend receives it from the owner bootstrap
and the public business payload.

## State machines

### Order

```text
draft --auto--> confirmed
draft --owner--> pending_owner --accept--> confirmed
draft --quote--> quoted --accept--> confirmed
                     \--owner--> pending_owner --accept--> confirmed
                     \--decline--> declined
pending_owner --decline--> declined
confirmed -> in_progress -> ready -> fulfilled -> completed
any non-terminal -> cancelled
any non-terminal -> expired
confirmed -> no_show
```

- `draft`: lines are being built; holds are active.
- `quoted`: a quote has been sent; holds are active for instant capacity.
- `pending_owner`: the owner must accept or decline.
- `confirmed`: holds are committed; payment may be due or paid.
- `in_progress`: kitchen or service has started.
- `ready`: pickup or delivery is ready, or the service is complete pending
  payment.
- `fulfilled`: handed over, delivered, or performed.
- `completed`: payment settled or pay-later recorded.
- `cancelled`, `declined`, `expired`, `no_show`: terminal.

Transitions are written only by the orders service. The agent may request
`confirm_order` and `cancel_order`; it may never set `state` directly.

### Payment

```text
unpaid -> deposit_due -> deposit_paid -> paid
       \-> failed
paid -> refunded / partially_refunded
```

`orders.payment_state` is a cached projection of the payments ledger. The
ledger is the source of truth.

### Lead

```text
new -> contacted -> quoted -> won / lost
   \-> expired
```

A lead becomes `won` when its order is confirmed; `lost` when the owner
declines; `expired` when the owner does not respond within the configured
window.

### Hold

```text
held -> committed -> released
  \-> released
  \-> expired
```

- `held`: active reservation; counts against availability.
- `committed`: the order is confirmed; the reservation is permanent.
- `released`: cancelled or declined; stops counting.
- `expired`: TTL elapsed before confirmation; stops counting.

## Capacity

### Reservation transaction

1. Resolve the offering's `offering_capacity_requirements`.
2. Lock every pool in ascending `pool_id` order with `SELECT ... FOR UPDATE`.
   This is the deadlock rule.
3. For `stock`: `available = pool.capacity + sum(adjustments.delta) -
   sum(holds.quantity where state='held')`. Reject when `available < requested`.
4. For `throughput`, `slot`, `resource`: count holds whose interval overlaps the
   candidate interval and whose state is `held` or `committed`. Reject when
   `count + requested > pool.capacity`.
5. Insert holds per requirement. For a per-unit requirement, one row per order
   line with `order_line_id` set and
   `quantity = line_quantity * quantity_per_unit`. For a per-order requirement,
   one row with `order_line_id` null and `quantity = per_order`. The interval is
   the candidate interval, `expires_at = now + hold_ttl`, and the idempotency
   key is `order_id:order_line_id:pool_id:starts_at`, with an empty segment for
   an order-level hold.
6. If any pool rejects, roll back the whole order; return the blocking pool and
   the next three alternatives.

The pool row lock serialises reservations per pool. At small-business volume
this is milliseconds, and it is simpler than a distributed reservation store.
Shopify's per-unit rows and `SKIP LOCKED` are a scale optimisation this product
does not need.

### Commit and release

- Commit: mark holds `committed`; for `stock`, write a `sale` adjustment of
  `-quantity`. The stock `available` formula ignores `committed`, so the sale
  adjustment is the only decrement.
- Release before commit: mark holds `released`.
- Release after commit: mark holds `released`; for `stock`, write a `return`
  adjustment of `+quantity`.
- Expire: the lazy sweeper marks `held` rows past `expires_at` as `expired`.
  The sweeper runs on order reads, chat turns, and the owner Home load; it is
  throttled, like the D45 auto-resolve sweep. No new queue.

### Availability

Inputs: `offering_id`, date range, party size, location.

1. Resolve the offering's pools and the tenant timezone.
2. For `stock`: return `sold_out` when the flag is set or the counted available
   is below the requested quantity.
3. For `throughput` and `asap`: find the earliest bucket with capacity for the
   requested quantity; add the offering's prep time; return `promise_at`.
4. For `slot` and `resource`: generate candidate starts from `availability_rules`
   for each day, step by `slot_increment_minutes`, subtract
   `availability_exceptions` of kind `blocked`, add `extra` windows, require
   `start >= now + lead_time`, require `duration + buffers` to fit, and check
   overlapping holds against `pool.capacity`.
5. Return up to three candidates with `start`, `end`, `timezone`, and optional
   `resource_id`. Slots are derived, never persisted.
6. `check_availability` reads without locking. `start_order` re-checks under
   lock and returns `slot_taken` with alternatives if another order won.

## Agent tools

| Tool | Access | Gate |
|---|---|---|
| `check_availability` | read | offering exists; no identity |
| `start_order` | draft write | name plus one contact; capacity available |
| `update_order` | draft write | same conversation and order reference; `state=draft` |
| `create_lead` | write | name plus one contact; `purchase_mode=quote` |
| `confirm_order` | commit | explicit customer confirmation; quote accepted; capacity re-check |
| `get_order_status` | read | reference plus matching contact, or magic link |
| `create_payment_link` | financial | confirmed order; amount from the ledger; hosted page only |
| `cancel_order` | write | identity; policy window; releases holds |
| `reschedule_order` | write | identity; policy window; new slot hold |

Rules:

- The model selects offering ids and quantities. It never supplies `total_cents`,
  `unit_price_cents`, `starts_at`, `ends_at`, `state`, or `payment_state`.
- `check_availability` returns each candidate with an opaque, server-signed
  `slot_token`. `start_order` and `reschedule_order` accept only that token,
  never a timestamp. A token expires with the hold TTL and is re-checked under
  lock.
- `check_availability` returns server-computed times. The model may repeat them
  verbatim, never invent or round them. A quote-mode preferred window is
  customer input, not a commitment; the owner confirms the actual time.
- `confirm_order` requires an explicit customer yes in the conversation, not a
  model inference.
- `create_payment_link` never returns card data; it returns a hosted URL and an
  amount copied from the ledger.
- Reads run before identity. Writes require name plus at least one of email or
  phone. Order actions require the reference plus matching contact or a magic
  link.
- Reads are cheap; the agent may call `check_availability` freely. Writes are
  one per turn unless the customer asks for a change.

Tools live in `backend/app/features/orders/tools.py` and are added to
`_tools_for` only when the tenant has an enabled selling mode. The existing
`lookup_order_or_ticket` stays for legacy rows and delegates to the same
service.

## API surface

### Public and chat

- `GET /api/public/tenant/{slug}/ordering` returns capabilities, labels, and the
  ordering fields of active offerings.
- `GET /api/public/order/{ref}?contact=` returns the read-only order page. It
  requires the reference plus the matching email or phone, or a signed token.
- Chat tools call the services directly; no new public chat endpoint.

### Owner

- `GET /api/orders?state=&from=&to=&limit=` returns the Work list.
- `GET /api/orders/{id}` returns the order, lines, holds, payments, and
  conversation.
- `POST /api/orders/{id}/accept`, `/decline`, `/ready`, `/fulfill`, `/complete`,
  `/cancel`, `/no-show`.
- `POST /api/orders/{id}/mark-paid` writes a ledger payment; idempotent.
- `GET /api/schedule?from=&to=` returns time-based commitments for the calendar.
- `GET /api/leads?status=` and `POST /api/leads/{id}/quote`.
- `GET /api/payments?state=` and `POST /api/payments/{id}/mark-paid`.
- `PATCH /api/offerings/{id}/ordering` updates the six axes and labels.
- `POST /api/offerings/{id}/sold-out` toggles `sold_out`.
- `POST /api/capacity/{pool_id}/adjust` writes a stock adjustment.
- `POST /api/availability/exceptions` blocks or adds time.

All owner routes use `require_owner` and run inside `tenant_context`. RLS Shape
A is the second boundary.

## Slices

Each slice is one commit. Later slices may merge before earlier ones only when
the migration numbers still follow merge order; the reserved numbers are 0039,
0040, 0041, 0042.

### Slice A - Selling-mode inference and config

No migration. Goal: infer, confirm, correct, and store the mode.

Files:

- `backend/app/onboarding/beats.py` - the new `selling_mode` stage and its
  `InputSpec`.
- `backend/app/onboarding/agent.py` - `progress()`, `sell_mode` default, and the
  deterministic confirmation branch.
- `backend/app/features/onboarding/service.py` - `infer_selling_mode(source)` and
  `write_selling_mode(...)`.
- `backend/app/features/onboarding/api.py` - the three selling-mode routes.
- `frontend/src/app/(tenant-admin)/(console)/onboarding/page.tsx` - the
  confirmation card and the change path.
- `frontend/src/lib/selling-modes.ts` - the mode defaults, label defaults, and
  the confirm/correct payload.
- `frontend/src/lib/selling-modes.test.ts` - inference copy, label fallback,
  multi-select.

Contract:

- Inference reads the extracted profile, offerings, categories, and the source
  text. It returns `{mode, capabilities, labels, confidence, evidence}`.
- The confirmation is deterministic and writes
  `tenant_config.config.ordering` without a model call. A correction writes the
  new config and leaves existing orders untouched.
- The final summary is read from the stored config, not from the model.

Tests:

- Unit: a menu source -> orders; a service list -> bookings; "get a quote" ->
  quotes; a product grid -> products; an ambiguous source returns two modes; no
  source returns four.
- Unit: a correction changes capabilities and labels; unknown label keys fall
  back.
- E2E: source -> confirmation -> correct -> final summary -> go live; the
  owner's Home shows the chosen Work label.

### Slice B - Leads, orders, and lines

Migration 0039. Goal: one work object with lines, leads, and a canonical state.

Files:

- `backend/migrations/0039_selling_modes.sql`.
- `backend/app/features/orders/{__init__,service,schemas,api}.py`.
- `backend/app/features/leads/{__init__,service,schemas,api}.py`.
- `backend/app/features/orders/ref.py` - reference code generation.
- `backend/app/agents/tools.py` - `lookup_order_or_ticket` reads the new fields.

Contract:

- `orders` extension, `order_lines`, `leads`, `offerings` extension, `quotes`
  extension, composite uniqueness, backfill.
- Reference code: `O-<base36>` for orders, `Q-<base36>` for quotes, unique per
  tenant. The customer-facing code is never a UUID.
- `create_order(conversation_id, lines, fulfillment, time, acceptance)` writes
  the order, lines, and total in one transaction. The total comes from the
  pricing engine; the request carries offering ids and quantities only.
- `lookup_order_or_ticket` returns `state`, `status`, `lines`, `starts_at`,
  `payment_state`, and the legacy `details`.

Tests:

- State transitions allowed and rejected.
- Composite FK isolation: a line cannot join another tenant's order.
- Reference uniqueness and case-insensitive lookup.
- Legacy seed rows backfill and still resolve.
- A request carrying a total is rejected.

### Slice C - Capacity kernel

Migration 0040. Goal: reserve, commit, release, and adjust capacity.

Files:

- `backend/migrations/0040_capacity_kernel.sql`.
- `backend/app/features/capacity/{__init__,service,schemas}.py`.
- `backend/app/features/orders/service.py` - call the capacity service inside the
  order transaction.

Contract:

- The reservation transaction in "Capacity" above, with pools locked in
  ascending id order.
- Stock modes: `none` skips capacity; `flag` reads `sold_out`; `counted` uses a
  stock pool and adjustments.
- `reserve(order)`, `commit(order)`, `release(order, reason)`, and
  `adjust(pool, delta, reason, actor)`.
- `available(pool)` is the single read used by availability, the owner screen,
  and the chat.

Tests:

- Two concurrent reservations for the last unit: one wins, one gets
  `sold_out`.
- Two concurrent reservations for the last interval: one wins, one gets
  `slot_taken`.
- A hold expires after TTL and frees the slot.
- Commit writes one sale adjustment; release after commit writes one return
  adjustment; a duplicate release writes none.
- An owner override can overbook and records `owner_override`.

### Slice D - Availability and calendar

Migration 0041. Goal: derive slots, block time, and power the calendar.

Files:

- `backend/migrations/0041_availability.sql`.
- `backend/app/features/scheduling/{__init__,service,schemas,api}.py`.
- `backend/app/features/orders/service.py` - schedule read model.
- `frontend/src/app/(tenant-admin)/(console)/work/` - the calendar view.

Contract:

- Availability rules are weekly windows per pool in the tenant timezone;
  exceptions are absolute intervals.
- The algorithm returns up to three candidates and never persists a slot.
- Buffers extend the occupied interval; the customer-facing duration stays the
  service duration.
- DST uses `zoneinfo`; the tenant timezone is the default.
- `GET /api/schedule` returns orders with `promise_at`, `starts_at`, or a
  window, sorted by time.

Tests:

- A 30-minute service with 15-minute buffers consumes 60 minutes.
- A blocked exception removes slots; an extra exception adds them.
- A full slot returns the next three.
- A DST transition day still produces the expected local times.
- A slot is not persisted: deleting the hold removes it from availability.

### Slice E - Payments ledger

Migration 0042. Goal: cash, bank, and terminal payments, deposits, and refunds.

Files:

- `backend/migrations/0042_payments.sql`.
- `backend/app/features/payments/{__init__,service,schemas,api}.py`.
- `frontend/src/app/(tenant-admin)/(console)/money/page.tsx`.
- `frontend/src/app/[slug]/pay/[token]/page.tsx` - the read-only pay page for
  later provider links; this slice can render a "Pay in person" state.

Contract:

- `payments` shape above; `mark_paid(payment_id)` is idempotent.
- A deposit creates a `deposit` payment at `total_cents * deposit_bps / 10000`;
  the balance is a second payment at confirmation or completion.
- A refund writes a `refund` payment and sets `orders.payment_state` to
  `refunded` or `partially_refunded`.
- The owner sees To collect and Collected; the customer sees the payment card
  and the read-only order page.
- No card data is stored.

Tests:

- Mark-paid twice writes one paid row.
- Deposit plus balance equals the total.
- Refund sets the order payment state.
- A payment for another tenant's order is not found.

### Slice F - Agent tools

No migration. Goal: the customer can check, order, book, confirm, and look up.

Files:

- `backend/app/features/orders/tools.py`.
- `backend/app/agents/agent_node.py` - `_tools_for` gates and dispatch.
- `backend/app/agents/contract.py` - the tool schemas.
- `backend/app/agents/intent.py` - descriptive intent only, no gating.

Contract:

- The nine tools in "Agent tools" above.
- Tool availability: `check_availability` and `get_order_status` are always
  present when the tenant has a selling mode; `start_order` and `create_lead`
  appear only after identity; `confirm_order`, `create_payment_link`,
  `cancel_order`, and `reschedule_order` appear only when an order is open.
- The schemas have no `total_cents`, `unit_price_cents`, `starts_at`,
  `state`, or `payment_state` fields.
- The prompt says: quote the total and time the tool returned verbatim; never
  estimate.

Tests:

- A selection schema carries no money or time fields.
- `start_order` returns the engine total, not a model figure.
- `confirm_order` without an explicit customer yes is refused.
- `get_order_status` with the wrong contact returns not found.
- A sold-out item returns `sold_out` and alternatives.
- A full slot returns `slot_taken` and alternatives.

### Slice G - Owner console

No migration. Goal: Home, Work, Chats, Money, and Settings in the owner's words.

Files:

- `frontend/src/app/(tenant-admin)/(console)/home/page.tsx` - Today, Needs you,
  Money, Share.
- `frontend/src/app/(tenant-admin)/(console)/work/page.tsx` - mode tabs and the
  Board/Calendar switch.
- `frontend/src/app/(tenant-admin)/(console)/work/orders/`,
  `work/calendar/`, `work/requests/`, `work/products/`.
- `frontend/src/app/(tenant-admin)/(console)/money/page.tsx`.
- `frontend/src/app/(tenant-admin)/(console)/layout.tsx` - four destinations.
- `frontend/src/lib/labels.ts` - label lookup and fallback.
- `frontend/src/lib/capabilities.ts` - capability gates.

Contract:

- The nav renders Home, Work, Chats, Money. Settings is behind the avatar.
- The Work tabs come from `capabilities.sell`; the view comes from
  `capabilities.schedule` and `capabilities.stock`.
- Every owner-facing string that names an item, collection, or action comes
  from the label map.
- The board groups by `state`; the calendar groups by day and time.
- The Money screen reads the payments ledger; the Home card shows the same
  numbers.

Tests:

- Unit: labels fall back; capability gates hide and show the right tabs.
- E2E: Orders board, Bookings calendar, Quotes inbox, Products list.
- E2E: a mixed tenant shows two Work tabs and one shared calendar.
- E2E: renaming Menu to Treatments changes the Work tab and the add button.

### Slice H - Evidence and closeout

Goal: prove the matrix and close the ticket.

- E2E matrix: Orders, Bookings, Quotes, Products, mixed tenant, sold out, last
  slot, cancel, decline, payment.
- Screenshots for Home and Work for each mode at 360px and 1024px.
- Concurrency test evidence for the last unit and the last slot.
- `make ci` green at the tip.
- `docs/agencx/progress.md` row.
- `docs/agencx/design/database.md` section for the new tables.
- `docs/agencx/design/frontend.md` section for Home, Work, Money, and the
  labels.
- ADRs D51-D53 in `docs/agencx/design/decisions.md`.

## Acceptance criteria

| # | Scenario | Passes when |
|---|---|---|
| 1 | Restaurant with a menu source | Inferred as `orders`; confirmation accepted; Home and Work show Orders and Menu; a customer orders two dishes and sees the engine total |
| 2 | Restaurant pickup with a slot | The customer picks a pickup time; the order holds stock, kitchen throughput, and the slot; the owner sees it on the board and the calendar |
| 3 | Restaurant item sold out | The chat says sold out and offers alternatives; the owner's sold-out toggle blocks the item immediately |
| 4 | Restaurant slot full | The chat offers the next three slots; no order is created until a slot is held |
| 5 | Barbershop with a service source | Inferred as `bookings`; a customer picks a slot, enters name and email, and confirms; the order appears on the day calendar |
| 6 | Barber deposit | A 20% deposit is requested; the deposit is recorded; the balance remains due |
| 7 | Cleaner with a quote source | Inferred as `quotes`; a request becomes a lead; the owner sends a quote; the customer accepts; the owner schedules a window |
| 8 | E-commerce with a product source | Inferred as `products`; stock counts decrement on confirmation; the order moves to ship/pickup |
| 9 | Grocery with delivery slots | A delivery slot is held with the stock; an out-of-stock line is substituted or cancelled with the customer's approval |
| 10 | Mixed tenant | Orders and Products are both enabled; Work shows two tabs; one calendar shows pickup slots and delivery windows |
| 11 | Owner corrects the inference | Adding Bookings changes capabilities, labels, and Work without a code change or a data migration |
| 12 | Owner renames a label | "Menu" becomes "Treatments"; the Work tab, add button, and empty state all change |
| 13 | Lead from chat, form, and phone | The same lead row is created with `source` set and the same conversion path |
| 14 | Last unit concurrency | Two orders race; one wins; the other gets sold out; no negative stock |
| 15 | Last slot concurrency | Two orders race; one wins; the other gets the next slot; no double booking |
| 16 | Cancel and decline | Cancel releases holds and refunds per policy; decline releases holds and notifies the customer |
| 17 | No vertical branch | Backend and frontend logic branch on capabilities, never on a business type or a vertical name; the preset table and label defaults may name modes, but no runtime conditional reads them; the two-tenant E2E passes |
| 18 | No model money or committed time | Tool schemas have no money or timestamp fields; `slot_token` is opaque and server-signed, and a quote preferred window is customer input; the inspection gate stays green; every total and slot in the transcript traces to a service |

## Test seams

- `backend/tests/test_selling_modes.py` - inference, confirmation, correction,
  label fallback.
- `backend/tests/test_orders_service.py` - state machine, reference codes,
  composite FKs, legacy backfill.
- `backend/tests/test_capacity_service.py` - stock, throughput, slot, resource,
  last unit, last slot, TTL, commit, release, adjustment.
- `backend/tests/test_availability.py` - buffers, lead time, DST, exceptions,
  three candidates.
- `backend/tests/test_order_tools.py` - schema guard, gating, total from engine,
  slot from service, explicit confirmation.
- `backend/tests/test_payments_ledger.py` - idempotent mark-paid, deposit plus
  balance, refund, tenant isolation.
- `frontend/src/lib/labels.test.ts` - fallback and rename.
- `frontend/src/lib/capabilities.test.ts` - tab and view gates.
- `frontend/e2e/selling-modes-orders.spec.ts`
- `frontend/e2e/selling-modes-bookings.spec.ts`
- `frontend/e2e/selling-modes-quotes.spec.ts`
- `frontend/e2e/selling-modes-products.spec.ts`
- `frontend/e2e/selling-modes-mixed.spec.ts`

**Verify**

```bash
make lint
make typecheck
make test
make build
make test-e2e
```

The E2E suite needs `make dev` and `make seed`; the concurrency tests run
against the test database.

## Out of scope

- Stripe Connect, hosted card checkout, refunds through a provider (follow-up
  ticket).
- Email and SMS notifications, receipts by email, reminders (follow-up ticket).
- Invoicing, PDFs, tax invoices, GST statements.
- Multi-location, staff shifts, payroll, commissions.
- Supplier inventory, purchase orders, barcodes, warehouses, stocktakes.
- Weight-based grocery and decimal quantities.
- Age verification, tips, service charges beyond the existing pricing engine.
- Two-way Google or Outlook calendar sync.
- Courier dispatch, routing, driver tracking.
- Recurring appointments, waitlists, dynamic pricing.
- Owner copilot.
- Reviews, loyalty, marketing.
- A `mixed` onboarding preset. Multi-capability is supported; the owner adds a
  second mode in Settings.

## Definition of done

- All eight slices merged to `development`, one commit per slice.
- `make ci` green at the tip: lint, typecheck, format-check, tests, build.
- `make test-e2e` green for the 18 acceptance scenarios.
- Every scenario has evidence in the ticket's Verification section.
- `docs/agencx/design/database.md` documents the new tables and the state
  machines.
- `docs/agencx/design/frontend.md` documents Home, Work, Money, the label map,
  and the four mode screens.
- `docs/agencx/design/decisions.md` carries D51-D53.
- `docs/agencx/progress.md` and `docs/agencx/spec/README.md` updated.
- No vertical branch in backend or frontend logic.
- No model-authored monetary amount or time in any transcript or stored row.
- The owner can complete the daily loop for each mode in three taps per order
  or booking.

## Blockers

None. Stripe Connect and email delivery are follow-up tickets, not blockers for
the ledger and chat surfaces.

## Verification

To be filled at the branch tip. The table will list, per slice: the exact
commands, the pass counts, and the evidence links. Concurrency evidence must
show the race, not just a single-threaded pass.

## ADRs to add

- **D51: Selling modes are capability presets, not verticals.** The mode is a
  default bundle of six independent axes; the UI branches on capabilities and
  labels, never on a business type.
- **D52: One order object with capacity holds.** A booking is an order with a
  time; there is no separate `bookings` table or state machine. Stock, kitchen
  throughput, slots, and resources are capacity pools behind one hold lifecycle.
- **D53: The calendar is a projection.** Any commitment with a time appears on
  the calendar; slots are derived from availability and never persisted.

## Risks

| Risk | Mitigation |
|---|---|
| The mode confirmation feels like a setup quiz | One card, one tap, and a final summary; the change path is optional |
| A wrong inference locks the owner into the wrong screens | The correction writes capabilities and labels; Settings can change it later |
| The owner expects a full inventory system | `stock_mode=counted` is a simple ledger with +/-, not suppliers or POs |
| Double-booking through an external calendar | The app is the source of truth in Phase 2; no two-way sync; block time in the app |
| The label map drifts from the UI | One `labels` module and unit tests for fallback |
| Pool-row locking slows a busy restaurant | Locks are per pool and held for milliseconds; a single tenant has one kitchen pool |
| The state machine grows into a workflow engine | Twelve states, fixed transitions, no per-tenant custom states |
| The agent promises a slot it cannot hold | `check_availability` is advisory; `start_order` re-checks under lock and returns alternatives |
