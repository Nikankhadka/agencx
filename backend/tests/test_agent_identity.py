"""Escalation-scoped contact capture: pure message builders and coercion.

These are the identity helpers escalation reaches for. Nothing here touches
a database or an LLM, so this file carries no ``db`` mark; later slices add
the tool/DB-level cases on top of it.
"""

from __future__ import annotations

from typing import Any, cast
from uuid import UUID, uuid4

import asyncpg
import pytest

from app.agents.agent_node import _set_customer_contact_impl, _SetCustomerContactArgs
from app.agents.escalation import (
    HANDOFF_MESSAGE,
    contact_ask,
    handoff_message,
    normalize_email,
)
from app.agents.inspection import ESCALATION_MESSAGE, escalation_message
from app.agents.price_gate import GATE_ESCALATION_MESSAGE, gate_escalation_message

# --- contact_ask: all four flag combinations, exact strings ------------------


def test_both_missing_asks_for_name_and_email() -> None:
    assert (
        contact_ask(name_known=False, email_known=False)
        == "Can I get your name and email so the business can follow up?"
    )


def test_name_missing_asks_for_name_only() -> None:
    assert (
        contact_ask(name_known=False, email_known=True)
        == "Can I get your name so the business can follow up?"
    )


def test_email_missing_asks_for_email_only() -> None:
    assert (
        contact_ask(name_known=True, email_known=False)
        == "Can I get your email so the business can follow up?"
    )


def test_both_known_asks_nothing() -> None:
    assert contact_ask(name_known=True, email_known=True) == ""


# --- handoff_message: base text, ask appended only when incomplete -----------


def test_handoff_full_contact_is_byte_identical() -> None:
    assert handoff_message(name_known=True, email_known=True) == HANDOFF_MESSAGE


@pytest.mark.parametrize(
    ("name_known", "email_known"),
    [(False, False), (True, False), (False, True)],
)
def test_handoff_incomplete_appends_exactly_one_space_plus_the_ask(
    name_known: bool, email_known: bool
) -> None:
    expected = f"{HANDOFF_MESSAGE} {contact_ask(name_known=name_known, email_known=email_known)}"
    assert handoff_message(name_known=name_known, email_known=email_known) == expected


# --- gate/inspection wrappers behave the same way ---------------------------


def test_gate_escalation_full_contact_is_byte_identical() -> None:
    assert gate_escalation_message(name_known=True, email_known=True) == GATE_ESCALATION_MESSAGE


@pytest.mark.parametrize(
    ("name_known", "email_known"),
    [(False, False), (True, False), (False, True)],
)
def test_gate_escalation_incomplete_appends_the_ask(name_known: bool, email_known: bool) -> None:
    expected = (
        f"{GATE_ESCALATION_MESSAGE} {contact_ask(name_known=name_known, email_known=email_known)}"
    )
    assert gate_escalation_message(name_known=name_known, email_known=email_known) == expected


def test_escalation_full_contact_is_byte_identical() -> None:
    assert escalation_message(name_known=True, email_known=True) == ESCALATION_MESSAGE


@pytest.mark.parametrize(
    ("name_known", "email_known"),
    [(False, False), (True, False), (False, True)],
)
def test_escalation_incomplete_appends_the_ask(name_known: bool, email_known: bool) -> None:
    expected = f"{ESCALATION_MESSAGE} {contact_ask(name_known=name_known, email_known=email_known)}"
    assert escalation_message(name_known=name_known, email_known=email_known) == expected


# --- normalize_email: store what they said, or nothing ----------------------


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, None),
        ("", None),
        ("   ", None),
        ("sam@example.com", "sam@example.com"),
        ("  sam@example.com  ", "sam@example.com"),
        ("sam", None),
        ("@example.com", None),
        ("sam@", None),
        ("sam @example.com", None),
        ("sam@@example.com", None),
        (("a" * 300) + "@example.com", None),
        ("a@b", "a@b"),
    ],
)
def test_normalize_email(value: str | None, expected: str | None) -> None:
    assert normalize_email(value) == expected


# --- set_customer_contact: the tool stores what the customer said ------------
#
# These exercise the real DB path. Each test inserts its own tenant (unique slug)
# and conversation through the superuser fixture, then deletes the tenant, whose
# FK cascade removes the conversation with it.


async def _make_conversation(
    superuser_conn: asyncpg.Connection[Any],
) -> tuple[UUID, UUID]:
    tenant_id = await superuser_conn.fetchval(
        "insert into tenants (slug, name) values ($1, 'Identity Test') returning id",
        f"id-{uuid4().hex[:12]}",
    )
    conversation_id = await superuser_conn.fetchval(
        "insert into conversations (tenant_id) values ($1) returning id", tenant_id
    )
    assert tenant_id is not None and conversation_id is not None
    return tenant_id, conversation_id


async def _read_contact(
    superuser_conn: asyncpg.Connection[Any], conversation_id: UUID
) -> asyncpg.Record:
    row = await superuser_conn.fetchrow(
        "select customer_ref, customer_email from conversations where id = $1",
        conversation_id,
    )
    assert row is not None
    return cast(asyncpg.Record, row)


@pytest.mark.db
async def test_name_only_stores_name_and_leaves_email_null(
    superuser_conn: asyncpg.Connection[Any],
) -> None:
    tenant_id, conversation_id = await _make_conversation(superuser_conn)
    try:
        stored = await _set_customer_contact_impl(
            superuser_conn, tenant_id, conversation_id, "Sam", None
        )
        assert stored == {"name": "Sam", "email": None}
        row = await _read_contact(superuser_conn, conversation_id)
        assert row["customer_ref"] == "Sam"
        assert row["customer_email"] is None
    finally:
        await superuser_conn.execute("delete from tenants where id = $1", tenant_id)


@pytest.mark.db
async def test_email_only_stores_email_and_leaves_name_null(
    superuser_conn: asyncpg.Connection[Any],
) -> None:
    tenant_id, conversation_id = await _make_conversation(superuser_conn)
    try:
        stored = await _set_customer_contact_impl(
            superuser_conn, tenant_id, conversation_id, None, "sam@example.com"
        )
        assert stored == {"name": None, "email": "sam@example.com"}
        row = await _read_contact(superuser_conn, conversation_id)
        assert row["customer_ref"] is None
        assert row["customer_email"] == "sam@example.com"
    finally:
        await superuser_conn.execute("delete from tenants where id = $1", tenant_id)


@pytest.mark.db
async def test_both_in_one_call_are_stored(
    superuser_conn: asyncpg.Connection[Any],
) -> None:
    tenant_id, conversation_id = await _make_conversation(superuser_conn)
    try:
        stored = await _set_customer_contact_impl(
            superuser_conn, tenant_id, conversation_id, "Sam", "sam@example.com"
        )
        assert stored == {"name": "Sam", "email": "sam@example.com"}
        row = await _read_contact(superuser_conn, conversation_id)
        assert row["customer_ref"] == "Sam"
        assert row["customer_email"] == "sam@example.com"
    finally:
        await superuser_conn.execute("delete from tenants where id = $1", tenant_id)


@pytest.mark.db
async def test_correction_overwrites_previous_values(
    superuser_conn: asyncpg.Connection[Any],
) -> None:
    tenant_id, conversation_id = await _make_conversation(superuser_conn)
    try:
        await _set_customer_contact_impl(
            superuser_conn, tenant_id, conversation_id, "Sam", "sam@example.com"
        )
        stored = await _set_customer_contact_impl(
            superuser_conn, tenant_id, conversation_id, "Alex", "alex@example.com"
        )
        assert stored == {"name": "Alex", "email": "alex@example.com"}
        row = await _read_contact(superuser_conn, conversation_id)
        assert row["customer_ref"] == "Alex"
        assert row["customer_email"] == "alex@example.com"
    finally:
        await superuser_conn.execute("delete from tenants where id = $1", tenant_id)


@pytest.mark.db
async def test_name_is_one_trimmed_space_joined_line_capped_at_80(
    superuser_conn: asyncpg.Connection[Any],
) -> None:
    tenant_id, conversation_id = await _make_conversation(superuser_conn)
    raw_name = "  Sam\n\nExample  " + ("x" * 100)
    expected = " ".join(raw_name.split())[:80]
    try:
        stored = await _set_customer_contact_impl(
            superuser_conn, tenant_id, conversation_id, raw_name, None
        )
        assert stored == {"name": expected, "email": None}
        assert len(stored["name"] or "") == 80
        assert "\n" not in (stored["name"] or "")
        row = await _read_contact(superuser_conn, conversation_id)
        assert row["customer_ref"] == expected
    finally:
        await superuser_conn.execute("delete from tenants where id = $1", tenant_id)


@pytest.mark.db
@pytest.mark.parametrize("bad_email", ["not-an-email", "sam @example.com"])
async def test_invalid_email_raises_and_leaves_row_unchanged(
    superuser_conn: asyncpg.Connection[Any], bad_email: str
) -> None:
    tenant_id, conversation_id = await _make_conversation(superuser_conn)
    try:
        await _set_customer_contact_impl(
            superuser_conn, tenant_id, conversation_id, "Sam", "sam@example.com"
        )
        with pytest.raises(ValueError):
            await _set_customer_contact_impl(
                superuser_conn, tenant_id, conversation_id, None, bad_email
            )
        row = await _read_contact(superuser_conn, conversation_id)
        assert row["customer_ref"] == "Sam"
        assert row["customer_email"] == "sam@example.com"
    finally:
        await superuser_conn.execute("delete from tenants where id = $1", tenant_id)


@pytest.mark.db
@pytest.mark.parametrize(("name", "email"), [(None, None), ("", "")])
async def test_neither_name_nor_email_raises(
    superuser_conn: asyncpg.Connection[Any], name: str | None, email: str | None
) -> None:
    tenant_id, conversation_id = await _make_conversation(superuser_conn)
    try:
        with pytest.raises(ValueError):
            await _set_customer_contact_impl(
                superuser_conn, tenant_id, conversation_id, name, email
            )
    finally:
        await superuser_conn.execute("delete from tenants where id = $1", tenant_id)


def test_set_customer_contact_schema_has_only_name_and_email() -> None:
    assert set(_SetCustomerContactArgs.model_fields) == {"name", "email"}
