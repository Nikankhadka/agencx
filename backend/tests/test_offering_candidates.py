"""The offering equality key.

The rest of this module's tests went with W-6: they pinned ``derive()``, the
first-figure line split that produced "Bowl is" from prose and has been replaced
by ``app.features.knowledge.offering_extraction``. Its coverage lives in
``test_offering_extraction.py``.

``normalize_name`` stayed, because it is not part of that parse - it decides
when two offerings are the same offering, everywhere in the system.
"""

from __future__ import annotations

from app.features.business import offering_candidates as offerings


def test_normalize_name_handles_unicode_punctuation_and_spacing() -> None:
    assert offerings.normalize_name("  Café—Menu!  ") == "café menu"


def test_normalize_name_is_the_equality_key_across_casing_and_punctuation() -> None:
    """Two spellings of one offering collapse to one key, so a document
    candidate and an owner-typed chip merge instead of duplicating."""
    assert offerings.normalize_name("Pita Pocket") == offerings.normalize_name("pita  pocket")
    assert offerings.normalize_name("Six Falafel") == offerings.normalize_name("Six-Falafel")


def test_normalize_name_keeps_distinct_offerings_distinct() -> None:
    assert offerings.normalize_name("Plate") != offerings.normalize_name("Super Plate")
