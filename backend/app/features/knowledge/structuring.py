"""O-3: raw extracted text -> the readable sections an owner reviews.

A file or a scraped page arrives as one undifferentiated wall of text. Before it
answers anything, one model call reorganises it under a fixed set of headings so
the owner can read what their assistant learned, correct it, and only then save
it. The headings are the same for every business - a butcher and a dental clinic
both get "What we offer" - so nothing here branches on a vertical (I8).

The model reorganises; it never authors. Two guards hold that line:

- the extraction schema is a set of named text fields, not free prose, so the
  model cannot invent structure the page did not have;
- **the money guard**: every monetary figure in the result must already appear in
  the source, checked deterministically with the pricing gate's own extractor. A
  price list is exactly the material this runs on, so a model that rounds "$16.50"
  to "$17" would otherwise quietly become the tenant's published price. On any
  mismatch the model's version is discarded and the source text is kept as-is.
  C-1 (figures verbatim from owner material) should use the same helper.
"""

from __future__ import annotations

import logging
import re
from collections import Counter
from typing import Any

from pydantic import BaseModel, Field

from app.llm.provider import LLMProvider
from app.pricing.validation_gate import extract_monetary_figures

logger = logging.getLogger("app.knowledge.structuring")

# ponytail: one call over the head of the document. A long PDF keeps its tail
# unstructured (appended verbatim as its own section) rather than being cut or
# split into many calls - section-by-section structuring is the upgrade path if
# real sources turn out to be long.
STRUCTURE_MAX_CHARS = 12_000

_PROMPT = (
    "You are reorganising a small business's own material so its owner can read "
    "it back. Sort what the text says under the given fields, keeping the "
    "owner's own words and every number exactly as written. Never invent, "
    "summarise away, round, or calculate anything - especially prices. Leave a "
    "field empty when the text says nothing about it, and put anything that fits "
    "nowhere else in `other`. Write plain sentences or short lines, no markdown."
)


class StructuredKnowledge(BaseModel):
    """The fixed, vertical-neutral skeleton the model fills."""

    about: str = Field(default="", description="What the business is, in a sentence or two")
    offerings: str = Field(default="", description="Services or products offered")
    prices: str = Field(default="", description="Prices exactly as the source states them")
    hours: str = Field(default="", description="Opening hours or availability")
    location_contact: str = Field(default="", description="Where they are and how to reach them")
    policies: str = Field(default="", description="Booking, delivery, returns, warranty, payment")
    other: str = Field(default="", description="Anything else the source states")


# Field -> the heading the owner sees. Order is the reading order of the page.
_HEADINGS: tuple[tuple[str, str], ...] = (
    ("about", "About"),
    ("offerings", "What we offer"),
    ("prices", "Prices"),
    ("hours", "Hours"),
    ("location_contact", "Location and contact"),
    ("policies", "Policies"),
    ("other", "Other details"),
)

# The heading used when the text is kept exactly as it arrived - the model call
# failed, or its result did not survive the money guard.
AS_WRITTEN = "As written"


def clean_text(raw: str) -> str:
    """Collapse runs of blank lines and trailing spaces - the same text, read
    without the scrape's whitespace."""
    lines = [line.rstrip() for line in raw.replace("\r\n", "\n").split("\n")]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def render_sections(sections: list[dict[str, Any]]) -> str:
    """Sections -> the plain text that gets chunked and embedded. This is what
    the assistant answers from, so it is the owner's edited text, never the
    original scrape."""
    return "\n\n".join(
        f"{section['heading']}\n{section['body']}".strip()
        for section in sections
        if str(section.get("body", "")).strip()
    )


def figures_preserved(source: str, produced: str) -> bool:
    """True when every monetary figure in ``produced`` appears in ``source``.

    Multiset containment, not set: three mentions of $16 may not become four.
    Dropping a figure is allowed (the model kept less), inventing one is not.
    """
    allowed = Counter(figure.cents for figure in extract_monetary_figures(source))
    produced_figures = Counter(figure.cents for figure in extract_monetary_figures(produced))
    return not (produced_figures - allowed)


def _sections_from(structured: StructuredKnowledge) -> list[dict[str, str]]:
    return [
        {"heading": heading, "body": value.strip()}
        for field, heading in _HEADINGS
        if (value := getattr(structured, field)).strip()
    ]


async def structure_document(raw_text: str, *, provider: LLMProvider) -> list[dict[str, str]]:
    """Readable sections for one document's extracted text.

    Always returns something readable: a model failure or a money-guard failure
    degrades to the source text under one heading, never to an error. The caller
    stores the result and shows it to the owner for review.
    """
    text = clean_text(raw_text)
    if not text:
        return []
    head, tail = text[:STRUCTURE_MAX_CHARS], text[STRUCTURE_MAX_CHARS:]

    try:
        structured = await provider.extract(
            system_prompt=_PROMPT, user_input=head, schema=StructuredKnowledge
        )
    except Exception:
        logger.warning("structuring failed, keeping the source text", exc_info=True)
        return _as_written(text)

    sections = _sections_from(structured)
    if not sections:
        return _as_written(text)
    if not figures_preserved(head, render_sections(sections)):
        logger.warning("structuring produced a figure absent from the source - discarded")
        return _as_written(text)
    if tail.strip():
        sections.append({"heading": f"{AS_WRITTEN} (continued)", "body": tail.strip()})
    return sections


def _as_written(text: str) -> list[dict[str, str]]:
    return [{"heading": AS_WRITTEN, "body": text}]
