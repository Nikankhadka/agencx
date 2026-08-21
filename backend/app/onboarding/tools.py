"""O-1: onboarding tools - a single ``save_profile`` merge helper."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.onboarding import beats
from app.onboarding.flow import ProfileDraft

_PROFILE_FIELDS = tuple(ProfileDraft.model_fields)


class ToolResult(BaseModel):
    ok: bool = True
    message: str = Field(default="")
    missing: list[str] = Field(default_factory=list)


def save_profile(draft: dict[str, Any], args: ProfileDraft) -> dict[str, Any]:
    """Merge any non-empty profile field into the flat draft."""
    for field in _PROFILE_FIELDS:
        value = getattr(args, field)
        if value:
            draft[field] = value
    return draft


def _check_completeness(draft: dict[str, Any]) -> list[str]:
    return beats.check_completeness(draft)


def request_finalize(draft: dict[str, Any]) -> ToolResult:
    missing = _check_completeness(draft)
    if missing:
        return ToolResult(ok=False, missing=missing)
    return ToolResult(ok=True, message="All required fields complete.")
