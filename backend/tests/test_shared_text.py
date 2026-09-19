"""Unit tests for app.shared.text - the deterministic text normalizations that
prove a prompt rule alone does not hold (em dashes, citation markers)."""

from __future__ import annotations

import pytest

from app.shared.text import plain_dashes, strip_citation_markers

UUID_A = "295feb16-a7f3-49e7-b771-e3b18fa0e76f"
UUID_B = "2d3b5827-2d62-40b2-8b4a-210ad29cee99"


def test_plain_dashes_replaces_em_dash_and_its_spacing() -> None:
    assert plain_dashes("Got it\u2014open Monday") == "Got it - open Monday"
    assert plain_dashes("no dashes here") == "no dashes here"


@pytest.mark.parametrize(
    "text",
    [
        "An answer [1].",
        "An answer [12].",
        "An answer [123].",
        "The combo [1, 2].",
        f"The combo [1, {UUID_A}].",
        f"The combo [{UUID_A}].",
        f"The combo [1, {UUID_A}, {UUID_B}].",
        f"The combo [catalog_id={UUID_A}].",
        f"The combo [id={UUID_A}].",
        f"The combo [catalog id: {UUID_A}].",
        f"The combo [1, {UUID_A}] and more [{UUID_B}].",
    ],
)
def test_removes_every_malformed_marker(text: str) -> None:
    assert "[" not in strip_citation_markers(text)
    assert "]" not in strip_citation_markers(text)
    assert UUID_A not in strip_citation_markers(text)
    assert UUID_B not in strip_citation_markers(text)


def test_removes_a_marker_with_no_matching_source() -> None:
    # The number is never validated against a source here - the customer
    # surface shows no bracket either way.
    assert strip_citation_markers("An answer [9].") == "An answer."


def test_stripped_text_still_reads_naturally() -> None:
    assert strip_citation_markers("The combo [1].") == "The combo."
    assert strip_citation_markers(f"Get six falafel [{UUID_A}]") == "Get six falafel"
    assert strip_citation_markers("Open [1] Monday [2].") == "Open Monday."
    assert strip_citation_markers("[1] Answer") == "Answer"
    assert strip_citation_markers("Answer [1]. Next [2].") == "Answer. Next."


@pytest.mark.parametrize(
    "text",
    [
        "Gluten-free [GF] options",
        "See [note] above",
        "Dated [2024-01-01]",
        "Circa [1999]",
        "Ratio [1.5]",
        "Empty [] brackets",
    ],
)
def test_leaves_non_marker_brackets_alone(text: str) -> None:
    assert strip_citation_markers(text) == text


def test_leaves_marker_free_text_byte_identical() -> None:
    # No markers means no whitespace tidying either - a double space the
    # author wrote is not this function's business.
    text = "A  plain  sentence, with punctuation ."
    assert strip_citation_markers(text) == text


def test_is_idempotent() -> None:
    once = strip_citation_markers(f"An answer [1, {UUID_A}]. Thanks.")
    assert strip_citation_markers(once) == once


def test_removes_markers_split_by_nothing_but_spacing() -> None:
    assert strip_citation_markers(f"An answer [ 1 , {UUID_A} ].") == "An answer."
