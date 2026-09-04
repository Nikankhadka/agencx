"""O-1: onboarding schemas - the lean flat profile.

The pre-Agencx 16-beat, section-per-concern profile (business/identity/tone/
services/pricing_rules/escalation/tax/payment/kyc/readback) is collapsed to a
single flat profile - the PRD spine step 2 fields - extracted in one pass and
merged by one ``save_profile`` tool. Prices are absent by design: Stage 1
onboarding captures what the business is, not what it charges (the money
boundary stays with the customer assistant and the pricing engine).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class ProfileDraft(BaseModel):
    """The lean business profile (PRD spine step 2)."""

    name: str = ""
    business_name: str = ""
    business_type: str = ""
    headcount: str = ""
    hours: str = ""
    services: str = ""
    contact: str = ""
    # O-6: an ABN is what a business puts on an invoice, so the interview asks
    # for it. "none" is the stated answer of an owner who does not have one -
    # a distinct value from "not asked yet", which is the empty string.
    abn: str = ""
    gst: str = ""


class DraftUpdate(BaseModel):
    """Per-turn structured extraction result: what the owner stated this turn.

    Transient - never persisted. Any non-null ``profile`` field is merged into
    the accumulated draft by ``save_profile``; ``off_topic`` / ``meta_reply``
    drive the reply directive. The server's current beat owns the next question.
    """

    off_topic: bool = False
    profile: ProfileDraft | None = None
    meta_reply: str | None = None
    offering_names: list[str] | None = None


class PendingOffering(BaseModel):
    """An offering waiting for owner review before it reaches the catalog."""

    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    price_cents: int | None = Field(default=None, ge=0)
    sources: list[Literal["owner", "document"]] = Field(default_factory=list, validate_default=True)

    @field_validator("name")
    @classmethod
    def _strip_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("offering name must not be empty")
        return value

    @field_validator("sources")
    @classmethod
    def _require_source(cls, value: list[str]) -> list[str]:
        return list(dict.fromkeys(value)) or ["owner"]
