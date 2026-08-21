"""O-1: onboarding schemas - the lean flat profile.

The pre-Agencx 16-beat, section-per-concern profile (business/identity/tone/
services/pricing_rules/escalation/tax/payment/kyc/readback) is collapsed to a
single flat profile - the PRD spine step 2 fields - extracted in one pass and
merged by one ``save_profile`` tool. Prices are absent by design: Stage 1
onboarding captures what the business is, not what it charges (the money
boundary stays with the customer assistant and the pricing engine).
"""

from __future__ import annotations

from pydantic import BaseModel


class ProfileDraft(BaseModel):
    """The lean business profile (PRD spine step 2)."""

    name: str = ""
    business_name: str = ""
    business_type: str = ""
    headcount: str = ""
    hours: str = ""
    services: str = ""
    contact: str = ""


class DraftUpdate(BaseModel):
    """Per-turn structured extraction result: what the owner stated this turn.

    Transient - never persisted. Any non-null ``profile`` field is merged into
    the accumulated draft by ``save_profile``; ``off_topic`` / ``next_question``
    / ``meta_reply`` drive the reply directive.
    """

    off_topic: bool = False
    profile: ProfileDraft | None = None
    next_question: str | None = None
    meta_reply: str | None = None
