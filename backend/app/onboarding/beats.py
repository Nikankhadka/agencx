"""O-1/O-12: lean onboarding beats, the profile's single source of truth.

Free text is satisfied by extraction. Fixed chip and masked values use the
server-owned selection protocol so the saved beat, spoken question, and
composer cannot advance independently.

Two chips instead swap the composer to a different widget and submit nothing
until that widget's own value is sent - ``ChipSpec.widget`` says which. The
client never hardcodes a beat; it renders what the beat declares.

The same beats are asked of every tenant. Nothing here branches on a business
vertical (I8): ``business_type`` is captured as one more field and shapes the
tenant's system prompt at confirm, never the question set. ``abn``/``gst`` are
Australian by wording, not by vertical, and ``gst`` is conditional on the
answer to ``abn`` rather than on what the business does.

W-2 caps every beat at two asks. Which beat is required and which is skippable
follows one rule - skippable means nothing downstream reads it, or the owner
can still edit it after go-live - and ``next_beat`` runs the two passes that
cap implies.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, Field

WidgetKind = Literal["text", "chips", "masked", "cta", "phone"]

# The sentinel an owner without an ABN leaves in the draft. A blank would leave
# the beat unsatisfied forever; "none" is a stated answer, and it is what makes
# the GST beat skip itself.
NO_ABN = "none"

# W-2: the value the "Skip for now" chip submits. It is never stored in the
# draft - a skipped beat's field stays empty and the beat key is remembered
# separately, because `profile_tagline` reads `services` and `hours` straight
# into the public storefront subtitle and a sentinel there would show to
# customers. (NO_ABN is the opposite case: "no ABN" is a real answer that is
# meant to display.)
SKIP = "__skip__"


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
    """One question in the interview.

    W-2 splits the beats in two. A ``optional`` beat is one nothing downstream
    reads (``name``, ``headcount``) or one the owner can still edit after
    go-live (``services`` via Business > What you offer, ``abn``/``gst`` via
    Business > details) - it resolves to its ``default`` or to nothing rather
    than being asked a third time. A required beat has neither property, so it
    is deferred to a second pass instead of being dropped.

    ``example`` is fed to the reply model on a beat's second ask, to be worked
    into the acknowledgment. The question itself is always emitted verbatim.
    """

    key: str
    label: str
    ask: str
    kind: WidgetKind
    complete: Callable[[dict[str, Any]], bool]
    chips: tuple[ChipSpec, ...] = ()
    mask: str | None = None
    prefix: str | None = None
    suggest_owner_email: bool = False
    optional: bool = False
    default: str = ""
    example: str = ""


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


SKIP_CHIP = ChipSpec(label="Skip for now", value=SKIP, dashed=True)

BEAT_ORDER: tuple[Beat, ...] = (
    Beat(
        key="name",
        label="your name",
        ask="What name would you like me to use?",
        kind="text",
        complete=_complete("name"),
        # Nothing downstream reads the owner's name, and it cannot be guessed,
        # so this is the one beat that skips to a genuine blank.
        optional=True,
        chips=(SKIP_CHIP,),
    ),
    Beat(
        key="business_name",
        label="business name",
        ask="What does the business go by?",
        kind="text",
        complete=_complete("business_name"),
        example='even a short one works - "Bytefix" or "Sababa"',
    ),
    Beat(
        key="business_type",
        label="business type",
        ask="In a few words, what kind of business is it?",
        kind="text",
        complete=_complete("business_type"),
        example='a few words is plenty - "phone repair shop" or "family dental practice"',
    ),
    Beat(
        key="headcount",
        label="team size",
        ask="Is it just you, or do you work with a team?",
        kind="text",
        complete=_complete("headcount"),
        chips=(
            ChipSpec(label="Just me", value="just me"),
            ChipSpec(label="Got a team", value="got a team"),
        ),
        # Read by nothing downstream, and solo is the overwhelming majority of
        # businesses that self-onboard, so an unanswered team size takes it.
        optional=True,
        default="just me",
    ),
    Beat(
        key="hours",
        label="opening hours",
        ask="What are your opening hours, and which days of the week are you open?",
        kind="text",
        complete=_complete("hours"),
        example='"9 to 5, Monday to Friday" - or "online, always open"',
    ),
    Beat(
        key="services",
        label="what you offer",
        ask="What would you like customers to know you offer?",
        kind="text",
        complete=_complete("services"),
        # Editable after go-live at Business > What you offer, and an uploaded
        # menu or price list can fill the catalog instead.
        optional=True,
        chips=(SKIP_CHIP,),
    ),
    Beat(
        key="contact",
        label="contact details",
        ask="How should customers reach you?",
        kind="text",
        complete=_complete("contact"),
        # The business contact is often the address the owner logged in with,
        # and when it is not, the pill is right there. "Phone number" swaps the
        # composer to the country-code pill rather than submitting the words.
        chips=(ChipSpec(label="Phone number", value="phone", dashed=True, widget="phone"),),
        suggest_owner_email=True,
        example="an email or a phone number - whichever you'd rather they used",
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
            ChipSpec(label="No", value=NO_ABN),
        ),
        # Editable after go-live at Business > details > ABN & Tax. "No" is
        # already one tap away, so an unanswered ABN takes the same value.
        optional=True,
        default=NO_ABN,
    ),
    Beat(
        key="gst",
        label="GST registration",
        ask="Are you registered for GST?",
        kind="text",
        complete=_gst_complete,
        chips=(
            ChipSpec(label="Yes", value="yes"),
            ChipSpec(label="Not yet", value="not yet"),
        ),
        # Rarely reached: defaulting `abn` to NO_ABN satisfies this one too.
        optional=True,
        default="no",
    ),
)

BEATS: dict[str, Beat] = {beat.key: beat for beat in BEAT_ORDER}

# The prototype's placeholder convention: a beat offering chips invites typing
# past them ("or type…"), it never blocks free text.
CHIPPED_PLACEHOLDER = "or type…"


def next_beat(
    draft: dict[str, Any],
    skipped: Sequence[str] = (),
    deferred: Sequence[str] = (),
) -> Beat | None:
    """The beat to ask now, or None when nothing is left to ask.

    W-2 runs the interview in two passes. ``skipped`` beats are gone for good.
    A ``deferred`` beat is a required one the owner did not answer in two asks:
    it is held back so the interview keeps moving, and comes back once every
    other beat has been through pass one. That way a repeated question is never
    adjacent to itself, which is what made the founder's transcript read as a
    loop.
    """
    pending = [beat for beat in BEAT_ORDER if not beat.complete(draft) and beat.key not in skipped]
    if not pending:
        return None
    first_pass = [beat for beat in pending if beat.key not in deferred]
    # Nothing left in pass one means the deferred beats are all that remain.
    return first_pass[0] if first_pass else pending[0]


def is_skip(key: str, values: list[str]) -> bool:
    """Whether this selection is the "Skip for now" chip on a skippable beat."""
    beat = BEATS.get(key)
    return beat is not None and beat.optional and values == [SKIP]


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


def apply_selection(draft: dict[str, Any], key: str, values: list[str]) -> str:
    """Validate and store one deterministic answer, returning its user label."""
    beat = BEATS.get(key)
    if beat is None or len(values) != 1:
        raise ValueError("select one valid answer")
    value = values[0].strip()
    labels = {chip.value: chip.label for chip in beat.chips if chip.widget is None}

    if key == "headcount" and value in labels:
        draft[key] = value
        return labels[value]
    if key == "abn":
        if value == NO_ABN:
            draft[key] = value
            return labels[value]
        digits = "".join(char for char in value if char.isdigit())
        if len(digits) == 11:
            draft[key] = digits
            return value
    if key == "gst" and value in labels:
        draft[key] = "yes" if value == "yes" else "no"
        return labels[value]
    raise ValueError("select one valid answer")


# The optional website/documents ask (see agent._completion_reply) is not a
# beat - it never gates the profile - but it still needs a text composer, so it
# reuses the same InputSpec shape as the text beats it follows.
KNOWLEDGE_INPUT = InputSpec(kind="text", placeholder='Paste a link, attach a file, or say "skip"')


def check_completeness(draft: dict[str, Any], skipped: Sequence[str] = ()) -> list[str]:
    """Labels of every unsatisfied beat the owner has not skipped.

    A deferred beat is deliberately not excused here - pass two has to finish
    before go-live, or a required field would reach the storefront empty.
    """
    return [
        beat.label for beat in BEAT_ORDER if not beat.complete(draft) and beat.key not in skipped
    ]
