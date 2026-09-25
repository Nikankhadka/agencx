# Data retention policy

**Status:** in force from T-030 (ADR D36). Implemented by
`backend/app/shared/retention.py`; the public wording lives on the privacy page
(T-032) and must quote the numbers below.

Agencx stores what customers type into a business's chat verbatim, and that text
often carries a name, a phone number or an email address. This page says how long
it is kept, what is never deleted, and how deletion is run.

## The windows

| Rule | Selects | Window |
|---|---|---|
| Stale | A conversation whose last message (or, with no messages, its creation) is older than the window | **365 days** |
| Abandoned | A conversation older than the window with no assistant message and no escalation | **30 days** |

Both are constants at the top of the module (`STALE_CONVERSATION_DAYS`,
`ABANDONED_CONVERSATION_DAYS`) and can be overridden per run with `--days` and
`--abandoned-days`. Change the constants and this page together.

**Why 365 days.** A year covers a seasonal repeat customer and the practical
"what did I tell them last time?" lookup. Beyond it, verbatim chat text is
liability with no product value. The Australian Privacy Act (APP 11.2) requires
personal information to be destroyed or de-identified once it is no longer
needed for the purpose it was collected for; a year of idleness is a defensible
line for a support conversation.

**Why 30 days for abandoned.** A conversation the assistant never answered and
nobody escalated is bot-scan or bounce residue: a scanner probing the public
chat route, or a visitor who typed one line and left. Nobody will open it. The
per-IP limiter (D32) reduces how much of this arrives; this rule clears what
does.

**A conversation with a quote is never selected by either rule.** Quotes are
commercial records, kept for the five-year substantiation period that applies to
Australian business records, and they are tamper-proof by design (migration
`0006`). A quoted conversation is removed only through the operator offboarding
path (T-031).

A conversation that matches both rules is counted and deleted once, under
"abandoned".

## Never purged

| Data | Why it stays |
|---|---|
| `cost_logs` | Budgets and unit economics. `conversation_id` is `on delete set null` by design, so it stays whole when its conversation goes |
| `documents`, `knowledge_chunks`, `offerings`, `catalog_items`, `pricing_rules` | The business's own content. Purging it would silently degrade the agent's answers, the worst failure mode there is |
| `quotes`, `orders` | Commercial and tax records |
| `tenants`, `tenant_config`, `users`, `platform_admins`, `tenant_assets`, `tenant_media` | Identity and brand. Removing them is offboarding, not retention |
| `escalations` | Not purged on their own: they go with their conversation, so one a business still needs is protected while its conversation is |

Deleting a conversation removes its `messages`, `tool_calls` and `escalations`
through the composite foreign keys and nothing else.

## Running it

```sh
make retention                    # dry run: prints the table, writes nothing
make retention-apply              # deletes, one transaction per tenant
make retention TENANT=some-slug   # either target, one tenant only
```

Flags on `python -m app.shared.retention`: `--days N`, `--abandoned-days N`,
`--tenant SLUG`, `--apply`. Both windows must be at least 1 day. An unknown
`--tenant` exits 1 rather than reporting an empty success.

It reads `DATABASE_URL` and connects as the database owner, like the migration
runner, so against production it needs that variable pointed at the hosted
database. Run the dry run first and read the table.

**Cadence.** Run it monthly. It is idempotent, so a missed month only means one
larger run. There is deliberately no scheduler, no authenticated purge endpoint
and no new production secret: an unattended job that can delete customer data is
a larger risk than a calendar reminder is a cost, and the volume today does not
justify the machinery. Revisit when tenant count makes a monthly manual run
unreasonable; the upgrade path is a scheduled GitHub Action calling the same
module with a database URL held as a repository secret.

## What this does not delete

The module deletes rows in Postgres. It does not reach:

- **Langfuse traces and provider logs.** Tracing and the LLM providers keep their
  own copies under their own retention.
- **Database backups.** Managed backups age out on the platform's schedule (see
  the backups section of `deploy.md`, T-033).
- **Sentry.** Events carry no customer text (D33), so there is nothing to purge.

The privacy page states each of these rather than implying a deletion is total.
