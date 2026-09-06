"""O-3: raw extracted text -> the readable sections an owner reviews.

A file or a scraped page arrives as one undifferentiated wall of text. Before it
answers anything, one model call reorganises it under a fixed set of headings so
the owner can read what their assistant learned, correct it, and only then save
it. The groups are the same for every business, so nothing here branches on a
vertical (I8). Offerings are extracted separately into catalog-review candidates.

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

from pydantic import BaseModel, Field, field_validator, model_validator

from app.llm.provider import LLMProvider
from app.pricing.validation_gate import extract_monetary_figures

logger = logging.getLogger("app.knowledge.structuring")

STRUCTURE_MAX_CHARS = 12_000

_PROMPT = (
    "You are reorganising a small business's own material so its owner can read "
    "it back. Sort what the text says under the given fields, keeping the "
    "owner's own words and every number exactly as written. Never invent, "
    "summarise away, round, or calculate anything - especially prices. Leave a "
    "field empty when the text says nothing about it, and put anything that fits "
    "nowhere else in `other`. Keep offerings and prices out of these fields: "
    "they are reviewed in a separate catalog pass. "
    "Write plain sentences or short lines, no markdown."
)


class StructuredKnowledge(BaseModel):
    """The fixed, vertical-neutral skeleton the model fills."""

    business_overview: list[str] = Field(
        default_factory=list, description="What the business is, in a sentence or two"
    )
    hours: list[str] = Field(default_factory=list, description="Opening hours or availability")
    location: list[str] = Field(default_factory=list, description="Where they are")
    contact: list[str] = Field(default_factory=list, description="How to contact them")
    policies: list[str] = Field(
        default_factory=list, description="Booking, delivery, returns, warranty, payment"
    )
    other: list[str] = Field(default_factory=list, description="Anything else the source states")

    @model_validator(mode="before")
    @classmethod
    def _accept_pre_w8_fields(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        value = dict(value)
        if "business_overview" not in value and "about" in value:
            value["business_overview"] = value["about"]
        if "location" not in value and "location_contact" in value:
            value["location"] = value["location_contact"]
        return value

    @field_validator(
        "business_overview",
        "hours",
        "location",
        "contact",
        "policies",
        "other",
        mode="before",
    )
    @classmethod
    def _accept_legacy_strings(cls, value: Any) -> list[str]:
        if isinstance(value, str):
            return [value] if value.strip() else []
        return value or []


# Field -> the heading the owner sees. Order is the reading order of the page.
_HEADINGS: tuple[tuple[str, str, str], ...] = (
    ("business_overview", "Business overview", "business_overview"),
    ("hours", "Hours", "hours"),
    ("location", "Location", "location"),
    ("contact", "Contact", "other"),
    ("policies", "Policies", "other"),
    ("other", "Other information", "other"),
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
        and str(section.get("heading", "")).casefold()
        not in {"what we offer", "prices", AS_WRITTEN.casefold()}
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
        {"heading": heading, "body": "\n".join(value).strip(), "kind": kind}
        for field, heading, kind in _HEADINGS
        if (value := getattr(structured, field))
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
    merged: dict[str, list[str]] = {heading: [] for _, heading, _ in _HEADINGS}
    as_written: list[str] = []
    for segment in segments(text):
        try:
            structured = await provider.extract(
                system_prompt=_PROMPT, user_input=segment, schema=StructuredKnowledge
            )
            sections = _sections_from(structured)
            rendered = render_sections(sections)
            if not sections or not figures_preserved(segment, rendered):
                raise ValueError("structured segment failed validation")
        except Exception:
            logger.warning("structuring segment failed, keeping source text", exc_info=True)
            as_written.append(segment)
            continue
        for section in sections:
            merged[section["heading"]].append(section["body"])

    result = [
        {"heading": heading, "body": "\n".join(merged[heading]).strip(), "kind": kind}
        for _, heading, kind in _HEADINGS
        if merged[heading]
    ]
    if as_written:
        result.append({"heading": AS_WRITTEN, "body": "\n\n".join(as_written), "kind": "other"})
    return result or _as_written(text)


def segments(text: str) -> list[str]:
    """Split on source line boundaries while keeping each model input bounded.

    Shared with W-6's offering extraction so both passes cut a document the same
    way and a block maps back to the segment it was read in."""
    chunks: list[str] = []
    current: list[str] = []
    size = 0
    for line in text.splitlines(keepends=True):
        if current and size + len(line) > STRUCTURE_MAX_CHARS:
            chunks.append("".join(current).strip())
            current = []
            size = 0
        if len(line) > STRUCTURE_MAX_CHARS:
            if current:
                chunks.append("".join(current).strip())
                current = []
                size = 0
            chunks.extend(
                line[index : index + STRUCTURE_MAX_CHARS].strip()
                for index in range(0, len(line), STRUCTURE_MAX_CHARS)
            )
        else:
            current.append(line)
            size += len(line)
    if current:
        chunks.append("".join(current).strip())
    return [chunk for chunk in chunks if chunk]


def _as_written(text: str) -> list[dict[str, str]]:
    return [{"heading": AS_WRITTEN, "body": text, "kind": "other"}]
