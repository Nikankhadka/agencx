"""Data retention: delete customer conversations that have outlived their purpose.

Policy and reasoning: ``docs/agencx/design/retention.md`` (ADR D36). Two rules:

* **stale** - the last message is older than ``--days`` (default 365), or a
  conversation with no messages was created that long ago. A year covers a
  seasonal repeat customer; beyond it verbatim chat text is liability with no
  product value.
* **abandoned** - older than ``--abandoned-days`` (default 30) with no assistant
  message and no escalation: bot-scan and bounce residue nobody will ever open.

A conversation with a quote is never selected by either rule: quotes are
commercial records and ``quotes`` refuses deletes for the app role on purpose
(migration 0006). Those go through the operator offboarding path.

Dry run is the default: it prints what would go and writes nothing. ``--apply``
deletes, one transaction per tenant, so a tenant is either fully purged for this
run or untouched. Connects as the owner like ``app.shared.migrate``, so every
query names its ``tenant_id`` instead of leaning on RLS.

CLI: ``uv run python -m app.shared.retention [--apply] [--tenant SLUG]``
(``make retention`` / ``make retention-apply``).
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from dataclasses import dataclass
from typing import Any

import asyncpg

from app.shared.config import get_settings

# Windows in days. Change them here and in docs/agencx/design/retention.md together.
STALE_CONVERSATION_DAYS = 365
ABANDONED_CONVERSATION_DAYS = 30

# What this module deletes: conversations, and through their composite FKs the
# messages, tool_calls and escalations under them. Nothing else is touched.
#
# Never purged, and why:
#   cost_logs                       budget and unit economics; conversation_id is
#                                   on delete set null by design
#   documents, knowledge_chunks,
#   offerings, catalog_items,
#   pricing_rules                   the business's own content; purging it would
#                                   silently degrade the agent's answers
#   quotes, orders                  commercial and tax records (a conversation
#                                   with a quote is skipped by both rules)
#   tenants, tenant_config, users,
#   platform_admins, tenant_assets,
#   tenant_media                    identity and brand; removing them is
#                                   offboarding, not retention
#   escalations                     live and die with their conversation, so one
#                                   a business still needs is protected while
#                                   its conversation is

_NO_QUOTE = """not exists (select 1 from quotes q
                    where q.tenant_id = c.tenant_id and q.conversation_id = c.id)"""

# Both bind $1 tenant id and $2 the window in days (Postgres rejects an unused parameter).
_STALE = f"""
select c.id from conversations c
 where c.tenant_id = $1
   and coalesce(
         (select max(m.created_at) from messages m
           where m.tenant_id = c.tenant_id and m.conversation_id = c.id),
         c.created_at) < now() - make_interval(days => $2)
   and {_NO_QUOTE}
"""

_ABANDONED = f"""
select c.id from conversations c
 where c.tenant_id = $1
   and c.created_at < now() - make_interval(days => $2)
   and not exists (select 1 from messages m
                    where m.tenant_id = c.tenant_id and m.conversation_id = c.id
                      and m.role = 'assistant')
   and not exists (select 1 from escalations e
                    where e.tenant_id = c.tenant_id and e.conversation_id = c.id)
   and {_NO_QUOTE}
"""


@dataclass(frozen=True)
class RuleResult:
    tenant: str
    rule: str
    conversations: int
    messages: int


async def _purge_tenant(
    conn: asyncpg.Connection[Any],
    tenant_id: Any,
    slug: str,
    *,
    stale_days: int,
    abandoned_days: int,
    apply: bool,
) -> list[RuleResult]:
    results: list[RuleResult] = []
    async with conn.transaction():
        # Abandoned first: it is the narrower rule, so a year-old bounce is
        # counted once, under the rule that explains it.
        seen: set[Any] = set()
        for rule, sql, days in (
            ("abandoned", _ABANDONED, abandoned_days),
            ("stale", _STALE, stale_days),
        ):
            rows = await conn.fetch(sql, tenant_id, days)
            ids = [row["id"] for row in rows if row["id"] not in seen]
            seen.update(ids)
            messages: int = await conn.fetchval(
                "select count(*) from messages where tenant_id = $1 and conversation_id = any($2)",
                tenant_id,
                ids,
            )
            if apply and ids:
                await conn.execute(
                    "delete from conversations where tenant_id = $1 and id = any($2)",
                    tenant_id,
                    ids,
                )
            results.append(RuleResult(slug, rule, len(ids), messages))
    return results


async def run_retention(
    dsn: str | None = None,
    *,
    stale_days: int = STALE_CONVERSATION_DAYS,
    abandoned_days: int = ABANDONED_CONVERSATION_DAYS,
    tenant_slug: str | None = None,
    apply: bool = False,
) -> list[RuleResult]:
    """Run both rules for every tenant (or one). Writes only when ``apply``."""
    conn = await asyncpg.connect(dsn or get_settings().database_url)
    try:
        if tenant_slug is None:
            tenants = await conn.fetch("select id, slug from tenants order by slug")
        else:
            tenants = await conn.fetch("select id, slug from tenants where slug = $1", tenant_slug)
            if not tenants:
                raise LookupError(f"no tenant with slug {tenant_slug!r}")
        results: list[RuleResult] = []
        for tenant in tenants:
            results += await _purge_tenant(
                conn,
                tenant["id"],
                tenant["slug"],
                stale_days=stale_days,
                abandoned_days=abandoned_days,
                apply=apply,
            )
        return results
    finally:
        await conn.close()


def _positive_int(value: str) -> int:
    number = int(value)
    if number < 1:
        # 0 would select every conversation that exists; refuse rather than obey.
        raise argparse.ArgumentTypeError("must be at least 1 day")
    return number


def _render(results: list[RuleResult], *, apply: bool) -> str:
    lines = [f"{'tenant':<42}{'rule':<12}{'conversations':>14}{'messages':>10}"]
    for r in results:
        lines.append(f"{r.tenant:<42}{r.rule:<12}{r.conversations:>14}{r.messages:>10}")
    total_c = sum(r.conversations for r in results)
    total_m = sum(r.messages for r in results)
    lines.append(f"{'total':<54}{total_c:>14}{total_m:>10}")
    lines.append(
        "Deleted."
        if apply
        else "DRY RUN: nothing was deleted. Re-run with --apply to delete these rows."
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Delete customer conversations past retention.")
    parser.add_argument("--days", type=_positive_int, default=STALE_CONVERSATION_DAYS)
    parser.add_argument("--abandoned-days", type=_positive_int, default=ABANDONED_CONVERSATION_DAYS)
    parser.add_argument("--tenant", help="only this tenant slug (default: every tenant)")
    parser.add_argument("--apply", action="store_true", help="delete; the default is a dry run")
    args = parser.parse_args(argv)
    try:
        results = asyncio.run(
            run_retention(
                stale_days=args.days,
                abandoned_days=args.abandoned_days,
                tenant_slug=args.tenant,
                apply=args.apply,
            )
        )
    except LookupError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(_render(results, apply=args.apply))
    return 0


if __name__ == "__main__":
    sys.exit(main())
