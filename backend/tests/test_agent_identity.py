"""Escalation-scoped contact capture: pure message builders and coercion.

These are the identity helpers escalation reaches for. Nothing here touches
a database or an LLM, so this file carries no ``db`` mark; later slices add
the tool/DB-level cases on top of it.
"""

from __future__ import annotations

import pytest

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
    expected = (
        f"{HANDOFF_MESSAGE} {contact_ask(name_known=name_known, email_known=email_known)}"
    )
    assert handoff_message(name_known=name_known, email_known=email_known) == expected


# --- gate/inspection wrappers behave the same way ---------------------------


def test_gate_escalation_full_contact_is_byte_identical() -> None:
    assert (
        gate_escalation_message(name_known=True, email_known=True) == GATE_ESCALATION_MESSAGE
    )


@pytest.mark.parametrize(
    ("name_known", "email_known"),
    [(False, False), (True, False), (False, True)],
)
def test_gate_escalation_incomplete_appends_the_ask(
    name_known: bool, email_known: bool
) -> None:
    expected = (
        f"{GATE_ESCALATION_MESSAGE} "
        f"{contact_ask(name_known=name_known, email_known=email_known)}"
    )
    assert gate_escalation_message(name_known=name_known, email_known=email_known) == expected


def test_escalation_full_contact_is_byte_identical() -> None:
    assert escalation_message(name_known=True, email_known=True) == ESCALATION_MESSAGE


@pytest.mark.parametrize(
    ("name_known", "email_known"),
    [(False, False), (True, False), (False, True)],
)
def test_escalation_incomplete_appends_the_ask(name_known: bool, email_known: bool) -> None:
    expected = (
        f"{ESCALATION_MESSAGE} {contact_ask(name_known=name_known, email_known=email_known)}"
    )
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
