"""O-1: onboarding tools - a single ``save_profile`` merge helper."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pydantic import BaseModel, Field

from app.onboarding import beats
from app.onboarding.flow import ProfileDraft

# W-9: the voice fields are server-owned. They are written only by the voice
# beat's own selection (`beats.apply_selection`) and are left out of the
# extraction prompt's field list, so a model that names one anyway still cannot
# get it into the draft.
SERVER_OWNED_FIELDS = ("customer_voice_preset", "customer_voice_custom_style")

_PROFILE_FIELDS = tuple(
    field for field in ProfileDraft.model_fields if field not in SERVER_OWNED_FIELDS
)


class ToolResult(BaseModel):
    ok: bool = True
    message: str = Field(default="")
    missing: list[str] = Field(default_factory=list)


def is_blank(value: Any) -> bool:
    """Whether a draft value carries nothing: absent, whitespace, or a list of
    blanks.

    ``draft.get(field)`` alone reads "  " and ["  "] as filled, which is how a
    source merge could skip a field the owner never actually answered (29). The
    draft's values are strings and string lists; this says empty for both.
    """
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, tuple)):
        return all(is_blank(item) for item in value)
    return not value


def save_profile(
    draft: dict[str, Any], args: ProfileDraft, *, only_empty: bool = False
) -> dict[str, Any]:
    """Merge any non-empty profile field into the flat draft.

    ``only_empty`` makes the merge additive for a source: a field the owner has
    already answered is left exactly as they wrote it, and only blanks are
    filled. Owner answers always win; the source is a convenience, never an
    overwrite. "Blank" is ``is_blank``'s answer, so a whitespace string or a
    list of empty strings is fillable. The ``abn`` normalisation is unchanged
    either way - a stated number is stored in digits, a stated "no" stays the
    sentinel.
    """
    for field in _PROFILE_FIELDS:
        value = getattr(args, field)
        if field == "abn" and value:
            stated = value.strip().lower()
            if stated == beats.NO_ABN:
                value = beats.NO_ABN
            else:
                digits = "".join(char for char in value if char.isdigit())
                value = digits if len(digits) == 11 else ""
        if value and not (only_empty and not is_blank(draft.get(field))):
            draft[field] = value
    return draft


def _check_completeness(draft: dict[str, Any], skipped: Sequence[str] = ()) -> list[str]:
    return beats.check_completeness(draft, skipped)


def request_finalize(draft: dict[str, Any], skipped: Sequence[str] = ()) -> ToolResult:
    missing = _check_completeness(draft, skipped)
    if missing:
        return ToolResult(ok=False, missing=missing)
    return ToolResult(ok=True, message="All required fields complete.")
