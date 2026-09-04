"""Offering candidates read out of the owner's own published material.

**Nothing calls this at runtime yet - that is M-3, and this module is waiting
for it, not dead.** E-6 used it to derive the Booking page's Services list
because ``offerings`` had no owner-facing writer; M-1 built that writer, so the
screen now reads real rows and this read-time derivation came out of the path.
D24 keeps the module because M-3 (import-and-confirm) needs exactly this: an
uploaded menu or price list, processed by O-3 into readable sections, turned
into *candidate* offerings the owner confirms once rather than re-typing. It
was renamed from ``offerings.py`` when M-1 arrived, so the name says candidate
extractor rather than shadowing the writer in ``service.py``.

What a real owner has is their own material - a menu, a price list, the page
they pasted - processed by O-3 into readable sections they corrected and saved.
This module turns those sections into rows.

**No model runs here, and no figure is ever produced.** A price on this page is
a verbatim slice of the owner's own line, cut at the position the pricing gate's
own extractor reports. That is the money rule (no language model produces a
monetary amount) held by construction rather than by a check: there is nothing
here that could invent, round or recompute an amount.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from app.pricing.validation_gate import extract_monetary_figures

# The two O-3 headings that describe what a business sells. Anything else
# (About, Hours, Policies) says nothing about an offering.
OFFERING_HEADINGS = ("What we offer", "Prices")

# A line long enough to be prose rather than a list entry is not a service row.
# Menus and price lists are short lines; a paragraph about the business is not.
_MAX_ROW_CHARS = 120

# Leading list punctuation the owner's own formatting leaves behind.
_BULLETS = "-*•·–— \t"

# Words that belong to the price, not the name. "Catering box - from $285" is
# one price ("from $285"), not a service called "Catering box - from". Popped
# one word at a time so "starting at" and "up to" both come across.
_PRICE_QUALIFIERS = frozenset(
    {"from", "at", "starting", "starts", "up", "to", "about", "around", "approx", "approx."}
)


class Offering:
    """One row: a name, and the price exactly as the owner wrote it (or none)."""

    __slots__ = ("name", "price")

    def __init__(self, name: str, price: str | None) -> None:
        self.name = name
        self.price = price

    def as_dict(self) -> dict[str, str | None]:
        return {"name": self.name, "price": self.price}

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"Offering(name={self.name!r}, price={self.price!r})"


def normalize_name(value: str) -> str:
    """Return the equality key used for every offering boundary."""
    normalized = unicodedata.normalize("NFKC", value).strip().casefold()
    normalized = "".join(
        " " if unicodedata.category(char).startswith("P") else char for char in normalized
    )
    return re.sub(r"\s+", " ", normalized).strip()


def _source_lines(heading: str, body: str) -> list[str]:
    lines = [line for line in body.splitlines() if line.strip()]
    if len(lines) == 1:
        delimiter = ";" if heading == "Prices" else ","
        parts = [part.strip() for part in lines[0].split(delimiter) if part.strip()]
        if len(parts) >= 4 and all(len(part) <= _MAX_ROW_CHARS for part in parts):
            return parts
    return lines


def _split_line(line: str) -> Offering | None:
    """One source line -> a row, or None when it is not one.

    The split point is the first monetary figure the pricing gate finds. What
    precedes it is the name, what follows from that index is the price - taken
    as a slice of the owner's line, so the text is theirs character for
    character, trailing "· Pickup" and all.
    """
    text = line.strip().lstrip(_BULLETS).strip()
    if not text or len(text) > _MAX_ROW_CHARS:
        return None

    figures = extract_monetary_figures(text)
    if not figures:
        return Offering(text, None)

    cut = min(figure.start for figure in figures)
    # Walk the cut leftwards over any qualifier words, so the price keeps the
    # words that qualify it. Still a slice of the owner's line either way, so
    # the verbatim property survives.
    head = text[:cut]
    for _ in range(2):
        stripped = head.rstrip()
        word = stripped.rsplit(" ", 1)[-1] if " " in stripped else stripped
        if word.casefold() not in _PRICE_QUALIFIERS:
            break
        head = stripped[: len(stripped) - len(word)]
        cut = len(head)

    name = head.rstrip().rstrip(":;,-–—·|").rstrip()
    price = text[cut:].strip()
    # A line that opens with its price has no name to show ("$16" alone, or a
    # total at the foot of a list). Keeping the whole line beats showing a row
    # with an empty title.
    if not name:
        return Offering(text, None)
    return Offering(name, price)


def derive(records: list[dict[str, Any]]) -> list[dict[str, str | None]]:
    """Saved knowledge records -> the Services rows, in reading order.

    Only ``ready`` documents count: a draft the owner has not saved is not
    something to show a customer.

    Rows are de-duplicated by name, because a business that uploaded both a menu
    and a price list has said the same thing twice - but a later mention that
    carries a price *upgrades* an earlier one that does not. The headings arrive
    in reading order, so "What we offer" (bare names) is seen before "Prices"
    (the same names with figures); first-wins would have thrown every price away.
    """
    rows: list[Offering] = []
    by_name: dict[str, Offering] = {}
    for record in records:
        if record.get("status") != "ready":
            continue
        for section in record.get("sections") or []:
            if section.get("heading") not in OFFERING_HEADINGS:
                continue
            for line in _source_lines(section["heading"], section.get("body") or ""):
                row = _split_line(line)
                if row is None:
                    continue
                key = normalize_name(row.name)
                existing = by_name.get(key)
                if existing is None:
                    by_name[key] = row
                    rows.append(row)
                elif existing.price is None and row.price is not None:
                    existing.price = row.price
    return [row.as_dict() for row in rows]
