# Agencx Design

Frontend design system and database schema. The build's visual and data specifications.

---

## Part A: Frontend Design

### The one hard rule: nothing hardcoded

No raw color, font, radius, shadow, or duration value ever appears in a component, page, or Tailwind utility call. Every visual decision routes through CSS custom properties defined in exactly one file: `frontend/src/styles/theme.css`.

Changing the entire look must require editing that one file only (or overriding its variables at runtime for tenant branding).

**Machine-enforced:** `frontend/scripts/check-tokens.mjs`, wired as `npm run check:tokens`, fails the build if a color literal (hex/rgb/hsl) appears in any file under `src/` outside `theme.css`.

### Token values

#### Accent

| Token | Value | Use |
|---|---|---|
| `--accent` | `#1A6B6B` | Primary buttons, active chats, outgoing/tenant bubbles |
| `--accent-deep` | `#0E4E4E` | Hover / pressed |
| `--accent-soft` | `#627C7B` | Secondary accent text |
| `--accent-tint` | `#EDF3F2` | Agent bubble fill, chat bands |
| `--accent-tint-2` | `#DCE7E5` | Deep band fills |

The accent hex is **provisional** pending identity resolution; because names are role-based, changing it means editing five values here and nothing else.

#### Neutrals

| Token | Value | Use |
|---|---|---|
| `--ink` | `#1A1A18` | Primary text |
| `--ink-2` | `#3A3A37` | Secondary text |
| `--ink-3` | `#6B6B66` | Tertiary text |
| `--ink-4` | `#9C9C96` | Disabled / placeholder |
| `--line` | `#ECECE8` | Hairline dividers |
| `--paper` | `#FFFFFF` | Primary surface |
| `--paper-2` | `#F7F7F5` | Alternate surface |

#### Semantic

| Token | Value | Use |
|---|---|---|
| `--amber` | `#F5A623` | Attention: overdue, ratings, notification dot |
| `--error` | `#E84040` | Destructive text and actions **only** |

`--error` is never used for validation failures. The inactive send state is the only validation signal - no red error text in the product.

### Typography, spacing, elevation, motion

| Aspect | Value |
|---|---|
| Font | Plus Jakarta Sans 400/500/700 via `next/font` |
| Body copy | 15 / 1.62-1.7 |
| Meta | 12 / 1.4 |
| Card highlight | 500 15 / 1.4 |
| Row titles | 500 18 / 1 |
| Chips | 500 13 / 1 |
| Chat prose | 16 / 1.58 |
| Greeting headline | 700 36 / 1.1 |
| Spacing grid | 4px base - allowed steps 4, 8, 12, 16, 24, 32, 48, 64, 96 |
| Page gutter | 24px |
| Card padding | 16-18px |
| Minimum touch target | 44px |
| Radius - cards | 18px |
| Radius - chips | 20-100px |
| Radius - input / command pill | 30px |
| Card elevation | `0 2px 16px rgba(0,0,0,.055)` |
| Pill elevation | `0 2px 14px rgba(0,0,0,.07)` + hairline ring |
| Entrance motion | `fadeSlideUp` 220ms ease-out |
| Surface cross-fade | 240ms |
| Typing indicator | Three pulsing dots, 600-800ms |
| Agent prose | Typewriter, 46ms per word |

Motion is functional, never celebratory. Reduced motion: `prefers-reduced-motion` collapses animations to instant.

### The three screens and their states

#### S1 Chat (login-in-chat + interview + everyday chat)

The product opens into a conversation, not a home screen. The first conversation IS the product:

- **Login-in-chat:** The owner types their email, receives a 6-digit code by email, and types it back - inside the chat. No signup screen, no separate identity flow.
- **Interview:** The same conversation continues as the onboarding interview (name, business name, business type, headcount, hours, what they sell).
- **Everyday chat:** After go-live, the Chat tab holds the Copilot conversation.

The thread is the progress indicator: no progress bars, no "% complete" anywhere. When the owner goes live the app has exactly two destinations rendered as tabs: Chat and Business.

#### S2 Business (show-back of profile + knowledge)

The Business tab displays the profile and knowledge the owner gave the agent - what the assistant believes about the business, and the uploaded material it answers from - so the owner can trust and correct it. Editable through the Copilot ("change my rate to $160"), never through settings forms. No configuration that exists only as a toggle. The thin exceptions: a "live / not live" state and the share link + QR.

| State | Spec |
|---|---|
| Empty | Document upload prompt; no profile yet - the tenant hasn't onboarded |
| Active | Table of documents with per-file status (pending/processing/ready/failed + retry on failed); profile fields shown back |
| Uploading | FileDropzone with per-file progress |
| Re-ingesting | Re-processing existing documents after profile changes |

#### S3 Public page (anonymous, per-tenant slug)

Single screen, centered column (max ~720px), tenant logo + display name header, message list, composer pinned bottom. No auth.

| State | Spec |
|---|---|
| Resolving tenant | Full-page centered skeleton; no flash of default branding |
| Unknown slug | Calm 404: "There's no business here." |
| Suspended tenant | "This assistant is currently unavailable." caption, composer hidden |
| Empty conversation | Tenant-configured greeting as the first assistant bubble |
| Streaming | StreamingText in assistant bubble; composer disabled with "answering..." hint; stop button |
| Citation chips | Inline CitationChips on grounded sentences |
| Escalated | EscalationBanner replaces composer-state messaging; conversation stays readable |
| Error / disconnect | Inline retry in the failed bubble, never a blank screen |

### Component wall (Stage 1 subset)

| Component | Notes | Required states |
|---|---|---|
| `ChatBubble` | roles: customer (accent-tint bg, right), assistant (surface, left) | static, streaming |
| `StreamingText` | renders SSE tokens; caret while open; `aria-live="polite"` | streaming, done, interrupted (retry) |
| `CitationChip` | inline `[1]`-style chip after cited sentences; popover shows source + snippet | default, hover/popover |
| `FileDropzone` | drag target; accepted types from the Business tab ticket | idle, drag-over, uploading (per-file progress), done, rejected (reason) |
| `Button` | primary (accent bg), secondary (surface + border), ghost, destructive; sm/md | default, hover, active, focus-visible ring, disabled, loading |
| `Input` / `Textarea` | label above, help/error text below; **no error-red for validation** | default, focus, disabled |
| `Toast` | auto-dismiss, functional-token edge; text only, no celebration | success/error/info |
| `Skeleton` | shimmer off in reduced-motion | n/a |
| `EmptyState` | icon + one-line explanation + primary action; never bare "no data" | n/a |
| `Tabs` | underline style, accent indicator | active, hover, focus |
| `Modal` / `Sheet` | sheet for mobile; scrim, focus trap | open/close, focus trap |
| `Icon` | vendored SVG paths, `fill="currentColor"`, `aria-hidden` | n/a |
| `EscalationBanner` | in-chat handoff state + status | active |
| `TraceTree` | collapsible run tree; mono font; **console only** - never customer-facing | loading, error, empty |

Stage 2 components (Badge, QuoteCard, MetricCard, Sparkline) are named as deferred, not specced here.

### SSE event contract for cross-surface state sync

| Event | When emitted | Subscribed surfaces update |
|---|---|---|
| `onboarding_beat_completed` | A capture beat promotes to confirmed | Business tab (show-back surface) |
| `escalation_triggered` | Agent escalates to tenant | Chat thread, EscalationBanner |

### Interaction rules (load-bearing)

- **No welcome screen, no progress bars, no celebration.** The thread is the progress indicator.
- **Typing indicator before static messages** - conversational pacing must feel consistent from the first beat.
- **Confirmation-card pattern** for every action that touches money or customer-facing records (Stage 2; Stage 1 has no autonomous writes).
- **No undo bar** - the confirmation card covers the same ground.
- **No raw structured data in user-facing output** - JSON, XML, markdown tables, or code blocks never render in chat. Parse and present through UI components, or show an honest fallback message.
- **Natural-language summaries only** - lists use conversational framing ("Here's what I know:"), never bullet points or markdown.
- **No impersonation** - every agent identifies as an assistant acting on behalf of Agencx, never as the business owner or as human.

### Accessibility bar

- WCAG AA contrast on every token pair used together
- Full keyboard navigation, `:focus-visible` ring on every interactive element
- Focus traps in modals, `aria-live` for streaming and toasts
- Responsive: tables collapse gracefully; chat is mobile-first; minimum touch target 44px

### Prototype reference

`design/prototypes/agencx-prototype-v6.html` and `agencx-storefront-customer-v3.html` are structural references only. Trust them for screen inventory, states, and interaction vocabulary. Do not trust them for navigation (the retired bottom tab bar), the cleaning-flavored copy, or the retired Hivee emblem.

---

## Part B: Database Design

### Stage 1 table catalog

Every tenant-scoped table carries `tenant_id` with RLS enforced (invariant I5). Money is integer cents everywhere, with one observability exception (`cost_logs.cost_usd`). UUID primary keys via `gen_random_uuid()`. Timestamps are `timestamptz`, default `now()`.

#### `tenants`

The business. One row per operator.

| Column | Type | Notes |
|---|---|---|
| `id` | uuid PK | `default gen_random_uuid()` |
| `slug` | text, unique | `check (slug ~ '^[a-z0-9](-?[a-z0-9])*$' and length(slug) between 3 and 40)` |
| `business_name` | text | captured first; reaching it sets onboarding state |
| `status` | text | `check (status in ('provisioning','active','suspended'))` |
| `onboarding_state` | text | `account_created` / `lead_capable` / `invoice_capable`. Forward-only trigger |
| `payment_processing_mode` | text | `PLATFORM` / `DIRECT` / `DEFERRED` |
| `discovery_mode_lite` | boolean | geographic fork; survives (decision 9) |
| `config` | jsonb | locale, hours, defaults |
| `brand` | jsonb | `{"accent":"#RRGGBB","logo_url":...,"display_name":...}` |
| `created_at` / `updated_at` | timestamptz | |

#### `business_types`

The I8 mechanism. One row per business type. Data, never a branch.

| Column | Type | Notes |
|---|---|---|
| `slug` | text PK | seeded: `restaurant-catering`, `cleaning`, `dental-clinic` |
| `profile_template` | jsonb | the fields the onboarding agent asks about |
| `prompt_fragments` | jsonb | vocabulary and phrasing fragments the assistant uses |
| `created_at` | timestamptz | |

Seeded, idempotent, in migration `0003_tenancy`. Adding a vertical = a new row, never a code change.

#### `users`

| Column | Type | Notes |
|---|---|---|
| `id` | uuid PK | |
| `tenant_id` | uuid | FK to tenants, `on delete cascade` |
| `email` | text, unique | primary identity - 6-digit code is sent here (decision 6) |
| `phone` | text | profile field only, never an identity anchor |
| `role` | text | `check (role in ('owner','staff'))` - `staff` is Stage 2 |
| `email_verified_at` / `created_at` | timestamptz | |

#### `auth_codes`

The 6-digit email code, issued and verified inside the chat by the onboarding agent's tools.

| Column | Type | Notes |
|---|---|---|
| `id` | uuid PK | |
| `tenant_id` | uuid | FK to tenants |
| `email` | text | destination of the code |
| `code_hash` | text | sha-256 hashed; never the raw code |
| `expires_at` | timestamptz | short TTL |
| `attempts` | integer | attempt budget; exceeding it invalidates |
| `verified_at` | timestamptz, null | set once |
| `created_at` | timestamptz | |

#### `documents`

| Column | Type | Notes |
|---|---|---|
| `id` / `tenant_id` | uuid | |
| `filename` | text | user-provided |
| `doc_type` | text | `check (doc_type in ('policy','faq','catalog','price_list','other'))` |
| `status` | text | `pending -> processing -> ready -> failed` |
| `error` | text | populated only on `failed` |
| `uploaded_at` | timestamptz | |

#### `knowledge_chunks`

The retrieval unit. Produced by the ingestion pipeline (~400 tokens, 15% overlap, heading-aware).

| Column | Type | Notes |
|---|---|---|
| `id` / `tenant_id` / `document_id` | uuid | FKs: tenants, documents (`on delete cascade`) |
| `content` | text | chunk text |
| `embedding` | vector | dimension follows the embedder config |
| `tsv` | tsvector | `GENERATED ALWAYS AS (to_tsvector('english', content)) STORED` |
| `metadata` | jsonb | `{"source": filename, "chunk_index": n, ...}` |
| `created_at` | timestamptz | |

Indexes: HNSW on `embedding` (`vector_cosine_ops`), GIN on `tsv`, btree on `(tenant_id, document_id)`.

#### `conversations` + `messages`

Tenant-scoped chat with denormalised `tenant_id` and composite FKs.

`conversations`: `id` (uuid PK), `tenant_id`, `status` (`open/escalated/closed`), `created_at`, `unique (tenant_id, id)`.

`messages`:

| Column | Type | Notes |
|---|---|---|
| `id` / `tenant_id` | uuid | |
| `conversation_id` | uuid | FK `(tenant_id, conversation_id)` -> `conversations (tenant_id, id)` on delete cascade |
| `role` | text | `check (role in ('customer','assistant','system','human_agent'))` |
| `actor_id` | uuid | the tenant user; null pre-auth/customer side |
| `agent_node` | text | which graph node authored it: `supervisor` / `knowledge` / `guardrail` / `inspection` / `stream` |
| `content` | text | |
| `created_at` | timestamptz | |

#### `unmet_asks`

When the Copilot acknowledges an ask it cannot fulfil.

| Column | Type | Notes |
|---|---|---|
| `id` / `tenant_id` | uuid | |
| `ask` | text | normalised ask text |
| `source` | text | `check (source in ('quote_refusal','price_not_found','unknown'))` |
| `capability` | text | the capability tag the handler assigns |
| `resolved` | boolean | false until the roadmap picks it up |
| `created_at` | timestamptz | |

#### `escalations`

A human or tenant takeover, reached from the graph's escalation edge.

| Column | Type | Notes |
|---|---|---|
| `id` / `tenant_id` / `conversation_id` | uuid | composite FK to conversations |
| `reason` | text | human-readable |
| `status` | text | `check (status in ('open','claimed','resolved'))` |
| `created_at` / `resolved_at` | timestamptz | |

#### `cost_logs`

The observability exception - `cost_usd` is numeric(12,6), the one non-cents money column.

| Column | Type | Notes |
|---|---|---|
| `id` / `tenant_id` / `conversation_id` | uuid | |
| `model` | text | |
| `input_tokens` / `output_tokens` | integer | |
| `cost_usd` | numeric(12,6) | observability only, never customer-facing |
| `created_at` | timestamptz | |

#### `eval_cases` + `eval_runs`

`eval_cases`: `id`, `tenant_id`, `case_type` (`retrieval`/`generation`/`trajectory`/`injection`/`leakage`), `input` jsonb, `expected` jsonb, `created_at`.

`eval_runs`: `id`, `tenant_id`, `run_type`, `metrics` jsonb, `git_sha`, `created_at`. Written only on completion - no partial rows.

#### `platform_admins`

No `tenant_id`; platform-global. `user_id` (uuid PK), `created_at`.

### Connection roles

| Role | Who uses it | Properties |
|---|---|---|
| `postgres` | migrations only | table owner; FORCE RLS still applies |
| `agencx_app` | the FastAPI backend | `LOGIN`, **no** `BYPASSRLS` |
| `agencx_resolver` | owns `resolve_tenant_slug()` only | `NOLOGIN`, **`BYPASSRLS`** - the single, audited RLS bypass |

Plus `app.role = 'service'` for signup bootstrap (INSERT only).

### The three RLS policy shapes

**Shape A** (every tenant-scoped table): `tenant_isolation` using `tenant_id = app_tenant_id()` for all operations, plus `platform_admin_read` for select only.

**Shape B** (platform-global): platform_admin_all on `platform_admins`; tenants table special-cased for tenant self-read, platform_admin_all, and service_signup_insert.

**Shape C** (signup bootstrap): service_signup_insert, INSERT only, service role.

### Migration runner

One migration per numbered step, `backend/migrations/NNNN_<name>.sql`, applied in order by `backend/app/core/migrate.py`:

```
0001_extensions.sql      vector; helper functions; touch_updated_at trigger
0002_roles.sql            postgres / agencx_app / agencx_resolver roles
0003_tenancy.sql          tenants, business_types, users, auth_codes, platform_admins (+ RLS, resolve_tenant_slug, seeds)
0004_knowledge.sql        documents, knowledge_chunks (+ RLS, HNSW + GIN indexes)
0005_conversations.sql    conversations, messages, unmet_asks, escalations (+ RLS)
0006_eval_cost.sql        eval_cases, eval_runs, cost_logs (+ RLS)
```

Every migration ends with RLS policies + grants. Forward-only: append, never edit.

### Schema audit (ships with Phase 1, runs in CI forever)

A test queries `pg_tables` / `pg_policies` and asserts:
1. Every table with a `tenant_id` column has RLS enabled and forced, with at least the `tenant_isolation` policy
2. Every monetary column matches `%_cents` and is integer-typed - `cost_logs.cost_usd` is the single allowed exception
3. The teeth test: deliberately drops one policy on a throwaway branch and must go red

### Seed plan

| Seed | Contents |
|---|---|
| `seed_tenant_sababa.py` | The anchor tenant - Sababa, business_type `restaurant-catering`, menu + catering-rate + FAQ documents (via real upload + ingestion path) |
| `seed_generalization.py` | Cleaning and dental tenants, created through the conversational onboarding flow + uploads - raw inputs, never direct table writes |
| `seed_leakage_pair.py` | Two throwaway tenants with disjoint secret token strings for the leakage eval |
| `seed_platform_admin.py` | The founder's user id into `platform_admins` |

### Stage 2 table names (deferred)

`catalog_items`, `pricing_rules`, `quotes` + `quote_line_items`, `invoices`, `credit_notes`, `payments`, `refunds`, `approvals`, `jobs` + `recurring_series`, `events`, `i_dont_know_classifications`, `inbound_communications`, `tenant_tax_profiles`.

Full column specs live in `docs/stage-2-backlog.md` and the Stage 2 feature builds, not here.
