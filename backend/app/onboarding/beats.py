"""O-1: onboarding beat system - the lean flat profile (single source of truth).

One :class:`Beat` per lean profile field, in ``BEAT_ORDER``. Every beat is a
text beat (satisfied by LLM extraction via ``save_profile``, never by a chip
selection), so the composer always renders the text pill and the completeness
gate can never disagree with the interview. The pre-Agencx chip/masked/cta
beats (team/tone/payment/kyc/escalation/tax) are gone from the active flow,
and with them the selection path - onboarding is text-only.

The same seven beats are asked of every tenant. Nothing here branches on a
business vertical (I8): ``business_type`` is captured as one more field and
shapes the tenant's system prompt at confirm, never the question set.

``InputSpec`` keeps its ``chips``/``mask``/``cta_label`` members so the wire
contract the client already types stays stable; every lean beat leaves them at
their empty defaults. E-1 rebuilds this surface as the command pill and
retires them.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, Field

WidgetKind = Literal["text", "chips", "masked", "cta"]


class ChipSpec(BaseModel):
    label: str
    value: str
    dashed: bool = False


class InputSpec(BaseModel):
    kind: WidgetKind = "text"
    placeholder: str = ""
    chips: list[ChipSpec] = Field(default_factory=list)
    mask: str | None = None
    cta_label: str | None = None


@dataclass(frozen=True)
class Beat:
    key: str
    label: str
    ask: str
    kind: WidgetKind
    complete: Callable[[dict[str, Any]], bool]


def _complete(field: str) -> Callable[[dict[str, Any]], bool]:
    return lambda draft: bool(draft.get(field))


BEAT_ORDER: tuple[Beat, ...] = (
    Beat(
        key="name",
        label="your name",
        ask="What's your name?",
        kind="text",
        complete=_complete("name"),
    ),
    Beat(
        key="business_name",
        label="business name",
        ask="What is your business called?",
        kind="text",
        complete=_complete("business_name"),
    ),
    Beat(
        key="business_type",
        label="business type",
        ask="What kind of business is it?",
        kind="text",
        complete=_complete("business_type"),
    ),
    Beat(
        key="headcount",
        label="team size",
        ask="Is it just you, or do you have a team?",
        kind="text",
        complete=_complete("headcount"),
    ),
    Beat(
        key="hours",
        label="opening hours",
        ask="What are your opening hours?",
        kind="text",
        complete=_complete("hours"),
    ),
    Beat(
        key="services",
        label="what you offer",
        ask="What do you sell or offer?",
        kind="text",
        complete=_complete("services"),
    ),
    Beat(
        key="contact",
        label="contact details",
        ask="How can customers reach you?",
        kind="text",
        complete=_complete("contact"),
    ),
)

BEATS: dict[str, Beat] = {beat.key: beat for beat in BEAT_ORDER}


def next_beat(draft: dict[str, Any]) -> Beat | None:
    """The first unsatisfied beat, or None when the draft is complete."""
    for beat in BEAT_ORDER:
        if not beat.complete(draft):
            return beat
    return None


def input_spec(beat: Beat) -> InputSpec:
    """The composer widget for a beat.

    Every lean beat is text, so ``chips``/``mask``/``cta_label`` stay at their
    empty defaults - present in the payload, never populated.
    """
    return InputSpec(kind=beat.kind, placeholder=beat.ask)


def check_completeness(draft: dict[str, Any]) -> list[str]:
    """Labels of every unsatisfied beat."""
    return [beat.label for beat in BEAT_ORDER if not beat.complete(draft)]
