"""Shared, compatibility-safe shapes for owner-reviewed knowledge."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Literal

from pydantic import BaseModel, Field, model_validator

KnowledgeSectionKind = Literal["business_overview", "hours", "location", "other"]


class KnowledgeSection(BaseModel):
    """One readable group in an owner's reviewed document.

    Old documents used arbitrary headings. Reading them through this model gives
    them the structured shape without an eager data migration; their next save
    writes the normalized form back to ``documents.structured``.
    """

    heading: str = Field(min_length=1, max_length=120)
    body: str = Field(min_length=1, max_length=20_000)
    kind: KnowledgeSectionKind | None = None

    @model_validator(mode="after")
    def normalize_legacy_heading(self) -> KnowledgeSection:
        heading = self.heading.strip()
        key = heading.casefold()
        kind = self.kind
        if kind is None:
            if key in {"about", "business overview", "business information"}:
                kind = "business_overview"
            elif key == "hours":
                kind = "hours"
            elif key in {"location", "location and contact"}:
                kind = "location"
            else:
                kind = "other"
        self.kind = kind
        self.heading = {
            "business_overview": "Business overview",
            "hours": "Hours",
            "location": "Location",
        }.get(kind, heading)
        return self


def normalize_sections(sections: Sequence[Mapping[str, object]]) -> list[dict[str, str]]:
    """Normalize legacy headings and omit blank edits before persistence."""
    return [
        section.model_dump()
        for item in sections
        if str(item.get("body", "")).strip()
        if (section := KnowledgeSection.model_validate(item))
    ]
