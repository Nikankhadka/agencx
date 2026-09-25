"""T-030 (ADR D36): app.shared.retention against real Postgres.

Rows are backdated straight into the tables as the superuser, then the module is
run against the same database. Every scenario names its own tenant and passes
``tenant_slug`` so other test modules' data can never leak into a count.
"""

from __future__ import annotations

import uuid
from typing import Any

import asyncpg
import pytest

from app.shared.retention import RuleResult, _render, main, run_retention

pytestmark = pytest.mark.db


async def _tenant(conn: asyncpg.Connection[Any]) -> tuple[uuid.UUID, str]:
    slug = f"retention-{uuid.uuid4().hex[:8]}"
    tenant_id: uuid.UUID = await conn.fetchval(
        "insert into tenants (slug, name) values ($1, 'Retention Test Co') returning id", slug
    )
    return tenant_id, slug


async def _conversation(
    conn: asyncpg.Connection[Any],
    tenant_id: uuid.UUID,
    *,
    age_days: int,
    messages: tuple[tuple[str, int], ...] = (),
    escalation: bool = False,
    quote: bool = False,
) -> uuid.UUID:
    """A conversation created ``age_days`` ago. ``messages`` are (role, days ago)."""
    conversation_id: uuid.UUID = await conn.fetchval(
        "insert into conversations (tenant_id, created_at) "
        "values ($1, now() - make_interval(days => $2)) returning id",
        tenant_id,
        age_days,
    )
    for role, days_ago in messages:
        await conn.execute(
            "insert into messages (tenant_id, conversation_id, role, content, created_at) "
            "values ($1, $2, $3, 'hello', now() - make_interval(days => $4))",
            tenant_id,
            conversation_id,
            role,
            days_ago,
        )
    if escalation:
        await conn.execute(
            "insert into escalations (tenant_id, conversation_id, reason, summary) "
            "values ($1, $2, 'price_provenance', 'asked for a price')",
            tenant_id,
            conversation_id,
        )
    if quote:
        await conn.execute(
            "insert into quotes (tenant_id, conversation_id, line_items, subtotal_cents, "
            "total_cents) values ($1, $2, '[]', 1000, 1000)",
            tenant_id,
            conversation_id,
        )
    return conversation_id


async def _alive(conn: asyncpg.Connection[Any], tenant_id: uuid.UUID) -> set[uuid.UUID]:
    rows = await conn.fetch("select id from conversations where tenant_id = $1", tenant_id)
    return {row["id"] for row in rows}


CUSTOMER_ONLY = (("customer", 40),)
ANSWERED = (("customer", 40), ("assistant", 40))


async def _seed_world(conn: asyncpg.Connection[Any], tenant_id: uuid.UUID) -> dict[str, uuid.UUID]:
    """One conversation per branch of the two rules, named for what should happen."""
    return {
        # goes: last message 400 days ago, no quote
        "stale": await _conversation(
            conn,
            tenant_id,
            age_days=420,
            messages=(("customer", 400), ("assistant", 400)),
            escalation=True,
        ),
        # goes: 40 days old, the customer spoke and nothing ever answered
        "abandoned": await _conversation(conn, tenant_id, age_days=40, messages=CUSTOMER_ONLY),
        # stays: created long ago but the customer wrote back this week
        "recently_active": await _conversation(
            conn,
            tenant_id,
            age_days=420,
            messages=(("customer", 400), ("assistant", 400), ("customer", 3)),
        ),
        # stays: young
        "fresh": await _conversation(conn, tenant_id, age_days=2, messages=(("customer", 2),)),
        # stays: past the abandoned window, but the assistant did answer
        "answered": await _conversation(conn, tenant_id, age_days=40, messages=ANSWERED),
        # stays: nobody answered, but it was escalated to the owner
        "escalated": await _conversation(
            conn, tenant_id, age_days=40, messages=CUSTOMER_ONLY, escalation=True
        ),
        # stays: would be stale, but a quote is a commercial record
        "quoted": await _conversation(
            conn,
            tenant_id,
            age_days=420,
            messages=(("customer", 400), ("assistant", 400)),
            quote=True,
        ),
    }


async def test_a_dry_run_reports_and_writes_nothing(
    migrated_db: str, superuser_conn: asyncpg.Connection[Any]
) -> None:
    tenant_id, slug = await _tenant(superuser_conn)
    await _seed_world(superuser_conn, tenant_id)
    count_messages = "select count(*) from messages where tenant_id = $1"
    before = await superuser_conn.fetchval(count_messages, tenant_id)

    results = await run_retention(migrated_db, tenant_slug=slug)

    assert results == [
        RuleResult(slug, "abandoned", 1, 1),
        RuleResult(slug, "stale", 1, 2),
    ]
    assert len(await _alive(superuser_conn, tenant_id)) == 7
    assert await superuser_conn.fetchval(count_messages, tenant_id) == before
    assert "DRY RUN" in _render(results, apply=False)


async def test_apply_deletes_exactly_what_the_dry_run_reported(
    migrated_db: str, superuser_conn: asyncpg.Connection[Any]
) -> None:
    tenant_id, slug = await _tenant(superuser_conn)
    world = await _seed_world(superuser_conn, tenant_id)
    await superuser_conn.execute(
        "insert into cost_logs (tenant_id, conversation_id, model, input_tokens, output_tokens, "
        "cost_usd) values ($1, $2, 'gpt-4o-mini', 10, 5, 0.1)",
        tenant_id,
        world["stale"],
    )

    reported = await run_retention(migrated_db, tenant_slug=slug)
    applied = await run_retention(migrated_db, tenant_slug=slug, apply=True)

    assert applied == reported
    survivors = await _alive(superuser_conn, tenant_id)
    assert survivors == {v for k, v in world.items() if k not in {"stale", "abandoned"}}

    # The children went with their conversation ...
    gone = [world["stale"], world["abandoned"]]
    for table in ("messages", "escalations"):
        assert (
            await superuser_conn.fetchval(
                f"select count(*) from {table} where conversation_id = any($1)",  # noqa: S608
                gone,
            )
            == 0
        )
    # ... the quote did not, and neither did the cost record, now detached.
    assert (
        await superuser_conn.fetchval("select count(*) from quotes where tenant_id = $1", tenant_id)
        == 1
    )
    assert (
        await superuser_conn.fetchval(
            "select count(*) from cost_logs where tenant_id = $1 and conversation_id is null",
            tenant_id,
        )
        == 1
    )

    # Idempotent: a second run finds nothing.
    assert [r.conversations for r in await run_retention(migrated_db, tenant_slug=slug)] == [0, 0]


async def test_a_year_old_bounce_is_counted_once_under_the_abandoned_rule(
    migrated_db: str, superuser_conn: asyncpg.Connection[Any]
) -> None:
    tenant_id, slug = await _tenant(superuser_conn)
    await _conversation(superuser_conn, tenant_id, age_days=420, messages=(("customer", 400),))

    results = await run_retention(migrated_db, tenant_slug=slug)

    assert [(r.rule, r.conversations) for r in results] == [("abandoned", 1), ("stale", 0)]


async def test_the_windows_are_arguments(
    migrated_db: str, superuser_conn: asyncpg.Connection[Any]
) -> None:
    tenant_id, slug = await _tenant(superuser_conn)
    answered = await _conversation(superuser_conn, tenant_id, age_days=40, messages=ANSWERED)

    default = await run_retention(migrated_db, tenant_slug=slug, apply=True)
    assert answered in await _alive(superuser_conn, tenant_id)
    assert [r.conversations for r in default] == [0, 0]

    shorter = await run_retention(migrated_db, tenant_slug=slug, stale_days=10, apply=True)
    assert [(r.rule, r.conversations) for r in shorter] == [("abandoned", 0), ("stale", 1)]
    assert answered not in await _alive(superuser_conn, tenant_id)


async def test_tenant_scoping_leaves_other_tenants_alone(
    migrated_db: str, superuser_conn: asyncpg.Connection[Any]
) -> None:
    mine, my_slug = await _tenant(superuser_conn)
    theirs, _ = await _tenant(superuser_conn)
    await _conversation(superuser_conn, mine, age_days=40, messages=CUSTOMER_ONLY)
    other = await _conversation(superuser_conn, theirs, age_days=40, messages=CUSTOMER_ONLY)

    results = await run_retention(migrated_db, tenant_slug=my_slug, apply=True)

    assert {r.tenant for r in results} == {my_slug}
    assert await _alive(superuser_conn, mine) == set()
    assert await _alive(superuser_conn, theirs) == {other}


async def test_an_unknown_tenant_is_an_error_not_a_silent_no_op(migrated_db: str) -> None:
    with pytest.raises(LookupError):
        await run_retention(migrated_db, tenant_slug="no-such-tenant-anywhere")


def test_a_zero_day_window_is_refused() -> None:
    # 0 would select every conversation that exists.
    with pytest.raises(SystemExit) as exc:
        main(["--days", "0"])
    assert exc.value.code == 2
