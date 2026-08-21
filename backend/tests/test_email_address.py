"""Syntax rules for reading a typed answer as an email address (login-in-chat).

The login composer is a chat pill, not a form field, so these cases are the
real inputs: prose around the address, decoration, casing and whitespace, and
the malformed shapes that must be answered rather than accepted.
"""

from __future__ import annotations

import pytest

from app.services.email_address import MAX_LENGTH, extract


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("sam@example.com", "sam@example.com"),
        ("  Sam@Example.COM  ", "sam@example.com"),
        ("it's sam@example.com, thanks!", "sam@example.com"),
        ("mailto:sam@example.com", "sam@example.com"),
        ("<sam@example.com>", "sam@example.com"),
        ("my email is sam@example.com.", "sam@example.com"),
        ("sam.jones+shop@mail.example.co.uk", "sam.jones+shop@mail.example.co.uk"),
        ("sam_o'neill@example-shop.com", "sam_o'neill@example-shop.com"),
        ("Reach me on sam@example.com or call", "sam@example.com"),
    ],
)
def test_reads_an_address(raw: str, expected: str) -> None:
    assert extract(raw).address == expected


@pytest.mark.parametrize(
    "raw",
    ["", "   ", "no email here", "call me on 0412 345 678", "sam at example dot com"],
)
def test_missing_when_nothing_is_address_shaped(raw: str) -> None:
    check = extract(raw)
    assert check.address is None
    assert check.problem == "missing"


@pytest.mark.parametrize(
    "raw",
    [
        "sam@example",  # no TLD
        "sam@example.c",  # one-character TLD
        "sam@example.123",  # numeric TLD
        "sam@.com",  # empty label
        "sam@example..com",  # consecutive dots
        "sam@-example.com",  # leading hyphen
        "sam@example-.com",  # trailing hyphen
        ".sam@example.com",  # leading dot in local
        "sam.@example.com",  # trailing dot in local
        "sa..m@example.com",  # consecutive dots in local
        "@example.com",  # no local part
        "sam@@example.com",  # two separators
    ],
)
def test_malformed_when_address_shaped_but_invalid(raw: str) -> None:
    check = extract(raw)
    assert check.address is None
    assert check.problem == "malformed"


def test_length_limits() -> None:
    assert extract("a" * 64 + "@example.com").ok
    assert not extract("a" * 65 + "@example.com").ok  # local part over 64

    over = "a" * 60 + "@" + ("b" * 60 + ".") * 3 + "example.com"
    assert len(over) > MAX_LENGTH
    assert not extract(over).ok


def test_picks_the_first_valid_candidate_in_prose() -> None:
    """ "not@this" has no TLD, so it is skipped rather than accepted or fatal."""
    assert extract("not@this and sam@example.com").address == "sam@example.com"
