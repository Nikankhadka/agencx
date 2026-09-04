"""Async escalation summariser (app/agents/escalation_summary.py): fills a
NULL escalations.summary from the conversation tail, out-of-band from the
customer's turn - see the module docstring for why it must never run inside
the turn budget."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import Any

import asyncpg
import pytest

from app.agents import escalation_summary
from app.llm.provider import SchemaT
from app.shared import db
from tests.conftest import _app_dsn_for
from tests.fakes import BaseFakeProvider

pytestmark = pytest.mark.db


class _SummaryFake(BaseFakeProvider):
    """Records the prompt it was given and returns a fixed summary, so a test
    can assert both what the module asked for and what it wrote."""

    def __init__(self, *, summary: str = "Wants a repair quote.", fail: bool = False) -> None:
        self.summary = summary
        self.fail = fail
        self.system_prompt: str | None = None
        self.user_input: str | None = None

    async def extract(
        self, *, system_prompt: str, user_input: str, schema: type[SchemaT]
    ) -> SchemaT:
        if self.fail:
            raise RuntimeError("provider is down")
        self.system_prompt = system_prompt
        self.user_input = user_input
        return schema.model_validate({"summary": self.summary})


@pytest.fixture(autouse=True)
async def _pool(migrated_db: str) -> AsyncIterator[None]:
    await db.create_pool(dsn=_app_dsn_for(migrated_db), min_size=1, max_size=4)
    yield
    await db.close_pool()


async def _seed_tenant_with_conversation(
    conn: asyncpg.Connection[Any],
) -> tuple[uuid.UUID, uuid.UUID]:
    tenant_id: uuid.UUID = await conn.fetchval(
        "insert into tenants (slug, name) values ($1, 'Escalation Summary Test Co') returning id",
        f"escalation-summary-{uuid.uuid4().hex[:8]}",
    )
    await conn.execute("insert into tenant_config (tenant_id) values ($1)", tenant_id)
    conversation_id: uuid.UUID = await conn.fetchval(
        "insert into conversations (tenant_id) values ($1) returning id", tenant_id
    )
    return tenant_id, conversation_id


async def _escalate(
    conn: asyncpg.Connection[Any],
    tenant_id: uuid.UUID,
    conversation_id: uuid.UUID,
    *,
    reason: str = "price_provenance",
    summary: str | None = None,
) -> None:
    await conn.execute(
        "insert into escalations (tenant_id, conversation_id, reason, summary) "
        "values ($1, $2, $3, $4)",
        tenant_id,
        conversation_id,
        reason,
        summary,
    )


async def _current_summary(
    conn: asyncpg.Connection[Any], tenant_id: uuid.UUID, conversation_id: uuid.UUID
) -> str | None:
    value: str | None = await conn.fetchval(
        "select summary from escalations where tenant_id = $1 and conversation_id = $2",
        tenant_id,
        conversation_id,
    )
    return value


async def test_fills_a_null_summary_from_the_conversation_tail(
    superuser_conn: asyncpg.Connection[Any],
) -> None:
    tenant_id, conversation_id = await _seed_tenant_with_conversation(superuser_conn)
    await superuser_conn.execute(
        "insert into messages (tenant_id, conversation_id, role, content) "
        "values ($1, $2, 'customer', 'How much for a screen replacement?')",
        tenant_id,
        conversation_id,
    )
    await _escalate(superuser_conn, tenant_id, conversation_id)

    provider = _SummaryFake(summary="Wants a price for a screen replacement.")
    await escalation_summary._generate(
        tenant_id=tenant_id, conversation_id=conversation_id, provider=provider
    )

    assert (
        await _current_summary(superuser_conn, tenant_id, conversation_id)
        == "Wants a price for a screen replacement."
    )
    assert provider.user_input is not None
    assert "screen replacement" in provider.user_input
    # The hard rule: this prose is customer-facing to the owner, and pricing
    # is never a model's to state.
    assert "price" in (provider.system_prompt or "").lower()
    assert "monetary" in (provider.system_prompt or "").lower()


async def test_never_overwrites_an_existing_summary(
    superuser_conn: asyncpg.Connection[Any],
) -> None:
    """create_escalation's own model-authored line (written with full turn
    context) must survive - the summariser only fills what is still NULL."""
    tenant_id, conversation_id = await _seed_tenant_with_conversation(superuser_conn)
    await superuser_conn.execute(
        "insert into messages (tenant_id, conversation_id, role, content) "
        "values ($1, $2, 'customer', 'hi')",
        tenant_id,
        conversation_id,
    )
    await _escalate(
        superuser_conn,
        tenant_id,
        conversation_id,
        summary="Catering for 20 on Friday, wants a price",
    )

    provider = _SummaryFake(summary="A different generated line.")
    await escalation_summary._generate(
        tenant_id=tenant_id, conversation_id=conversation_id, provider=provider
    )

    assert (
        await _current_summary(superuser_conn, tenant_id, conversation_id)
        == "Catering for 20 on Friday, wants a price"
    )
    # Never even called the provider - the read-first check is what stops a
    # wasted call on every one of the tool path's own escalations.
    assert provider.user_input is None


async def test_a_failed_provider_leaves_the_summary_null_and_does_not_raise(
    superuser_conn: asyncpg.Connection[Any],
) -> None:
    tenant_id, conversation_id = await _seed_tenant_with_conversation(superuser_conn)
    await superuser_conn.execute(
        "insert into messages (tenant_id, conversation_id, role, content) "
        "values ($1, $2, 'customer', 'hi')",
        tenant_id,
        conversation_id,
    )
    await _escalate(superuser_conn, tenant_id, conversation_id)

    await escalation_summary._generate(
        tenant_id=tenant_id, conversation_id=conversation_id, provider=_SummaryFake(fail=True)
    )

    assert await _current_summary(superuser_conn, tenant_id, conversation_id) is None


async def test_no_messages_leaves_the_summary_null(
    superuser_conn: asyncpg.Connection[Any],
) -> None:
    """No customer content to summarise - not the fail path, just nothing to
    generate from (e.g. a limit stop before any message landed)."""
    tenant_id, conversation_id = await _seed_tenant_with_conversation(superuser_conn)
    await _escalate(superuser_conn, tenant_id, conversation_id)

    provider = _SummaryFake()
    await escalation_summary._generate(
        tenant_id=tenant_id, conversation_id=conversation_id, provider=provider
    )

    assert await _current_summary(superuser_conn, tenant_id, conversation_id) is None
    assert provider.user_input is None


async def test_a_resolved_escalation_is_left_alone(
    superuser_conn: asyncpg.Connection[Any],
) -> None:
    tenant_id, conversation_id = await _seed_tenant_with_conversation(superuser_conn)
    await superuser_conn.execute(
        "insert into messages (tenant_id, conversation_id, role, content) "
        "values ($1, $2, 'customer', 'hi')",
        tenant_id,
        conversation_id,
    )
    await superuser_conn.execute(
        "insert into escalations (tenant_id, conversation_id, reason, status, resolved_at) "
        "values ($1, $2, 'price_provenance', 'resolved', now())",
        tenant_id,
        conversation_id,
    )

    provider = _SummaryFake()
    await escalation_summary._generate(
        tenant_id=tenant_id, conversation_id=conversation_id, provider=provider
    )

    assert provider.user_input is None
    assert await _current_summary(superuser_conn, tenant_id, conversation_id) is None
