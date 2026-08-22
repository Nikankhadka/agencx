"""O-1: onboarding beat system - the lean flat profile (single source of truth).

One :class:`Beat` per lean profile field, in ``BEAT_ORDER``. Every beat is
still satisfied by LLM extraction via ``save_profile`` - there is no
deterministic selection path, and the ``selection`` payload stays refused.

**O-6: chips are presentation, not a protocol.** The prototype answers "are you
running this on your own, or have you got a team?" with tappable ``Just me`` /
``Got a team`` chips above the composer (``buildCmdPill(placeholder, onSubmit,
chips)``). Tapping one **submits its label as ordinary text** on the same
streaming route a typed answer uses, so extraction reads "Just me" exactly as
if the owner had typed it. That keeps the one-tool loop, the completeness gate
and the free-tier reliability O-1 bought, and costs the backend one field.

Two chips instead swap the composer to a different widget and submit nothing
until that widget's own value is sent - ``ChipSpec.widget`` says which. The
client never hardcodes a beat; it renders what the beat declares.

The same beats are asked of every tenant. Nothing here branches on a business
vertical (I8): ``business_type`` is captured as one more field and shapes the
tenant's system prompt at confirm, never the question set. ``abn``/``gst`` are
Australian by wording, not by vertical, and ``gst`` is conditional on the
answer to ``abn`` rather than on what the business does.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, Field

WidgetKind = Literal["text", "chips", "masked", "cta", "phone"]

# The sentinel an owner without an ABN leaves in the draft. A blank would leave
# the beat unsatisfied forever; "none" is a stated answer, and it is what makes
# the GST beat skip itself.
NO_ABN = "none"


class ChipSpec(BaseModel):
    label: str
    value: str
    dashed: bool = False
    # O-6: when set, tapping this chip swaps the composer to that widget instead
    # of submitting the label. The phone pill and the ABN pill arrive this way.
    widget: WidgetKind | None = None


class InputSpec(BaseModel):
    kind: WidgetKind = "text"
    placeholder: str = ""
    chips: list[ChipSpec] = Field(default_factory=list)
    mask: str | None = None
    cta_label: str | None = None
    # O-6: the label welded inside the pill's left edge (the prototype's
    # `.abn-pre`). Presentation only - the value submitted is the field's own.
    prefix: str | None = None
    # O-6: prepend a one-tap chip carrying the address the owner logged in with.
    # The value is not in this payload on purpose - the client already holds it
    # in its session, and the server has no email column to read it from (the
    # address lives in Supabase auth, not in `users`). The beat declares that
    # the chip belongs here; the client supplies the label.
    suggest_owner_email: bool = False


@dataclass(frozen=True)
class Beat:
    key: str
    label: str
    ask: str
    kind: WidgetKind
    complete: Callable[[dict[str, Any]], bool]
    chips: tuple[ChipSpec, ...] = ()
    mask: str | None = None
    prefix: str | None = None
    suggest_owner_email: bool = False


def _complete(field: str) -> Callable[[dict[str, Any]], bool]:
    return lambda draft: bool(draft.get(field))


def _gst_complete(draft: dict[str, Any]) -> bool:
    """GST only applies to a business that has an ABN.

    An owner who answered "no, not yet" is not asked a follow-up about a
    registration they cannot hold - the prototype skips straight past it. This
    is a conditional beat expressed in the predicate the gate already calls, so
    it needs no branching anywhere else.
    """
    if str(draft.get("abn", "")).strip().lower() == NO_ABN:
        return True
    return bool(draft.get("gst"))


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
        chips=(
            ChipSpec(label="Just me", value="just me"),
            ChipSpec(label="Got a team", value="got a team"),
        ),
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
        ask="What's the best way for customers to reach you?",
        kind="text",
        complete=_complete("contact"),
        # The business contact is often the address the owner logged in with,
        # and when it is not, the pill is right there. "Phone number" swaps the
        # composer to the country-code pill rather than submitting the words.
        chips=(ChipSpec(label="Phone number", value="phone", dashed=True, widget="phone"),),
        suggest_owner_email=True,
    ),
    Beat(
        key="abn",
        label="ABN",
        ask="Do you have an ABN?",
        kind="text",
        complete=_complete("abn"),
        mask="XX XXX XXX XXX",
        prefix="ABN",
        chips=(
            ChipSpec(label="Yes", value="yes", widget="masked"),
            ChipSpec(label="No, not yet", value=NO_ABN),
        ),
    ),
    Beat(
        key="gst",
        label="GST registration",
        ask="And are you registered for GST?",
        kind="text",
        complete=_gst_complete,
        chips=(
            ChipSpec(label="Yes", value="yes"),
            ChipSpec(label="Not yet", value="not yet"),
        ),
    ),
)

BEATS: dict[str, Beat] = {beat.key: beat for beat in BEAT_ORDER}

# The prototype's placeholder convention: a beat offering chips invites typing
# past them ("or type…"), it never blocks free text.
CHIPPED_PLACEHOLDER = "or type…"


def next_beat(draft: dict[str, Any]) -> Beat | None:
    """The first unsatisfied beat, or None when the draft is complete."""
    for beat in BEAT_ORDER:
        if not beat.complete(draft):
            return beat
    return None


def input_spec(beat: Beat) -> InputSpec:
    """The composer widget for a beat."""
    return InputSpec(
        kind=beat.kind,
        placeholder=CHIPPED_PLACEHOLDER if beat.chips else beat.ask,
        chips=list(beat.chips),
        mask=beat.mask,
        prefix=beat.prefix,
        suggest_owner_email=beat.suggest_owner_email,
    )


# The optional website/documents ask (see agent._completion_reply) is not a
# beat - it never gates the profile - but it still needs a text composer, so it
# reuses the same InputSpec shape as the text beats it follows.
KNOWLEDGE_INPUT = InputSpec(kind="text", placeholder='Paste a link, attach a file, or say "skip"')


def check_completeness(draft: dict[str, Any]) -> list[str]:
    """Labels of every unsatisfied beat."""
    return [beat.label for beat in BEAT_ORDER if not beat.complete(draft)]
