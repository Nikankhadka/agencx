"""T-051: onboarding beat system - the single source of truth for both the
composer widget the client renders and the completeness gate the server
enforces.

One :class:`Beat` per onboarding question, in ``BEAT_ORDER``. Each beat
declares the widget the client renders (``kind``/``chips``/``mask``/
``cta_label``), when it is satisfied (``complete``), and how a chip selection
folds into the draft (``apply``). The agent turn loop and the controller both
derive their behavior from this module, so the gate and the composer can never
disagree. Chip beats are deterministic and never touch the LLM.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal, cast

from pydantic import BaseModel, Field

from app.onboarding.flow import EscalationDraft, resolve_threshold

WidgetKind = Literal["text", "chips", "masked", "cta"]
Posture = Literal["rarely", "balanced", "cautious"]


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
    apply: Callable[[dict[str, Any], list[str]], dict[str, Any]]
    chips: tuple[ChipSpec, ...] = ()
    mask: str | None = None
    cta_label: str | None = None


def _chips(pairs: list[tuple[str, str]], *, dashed: bool = False) -> tuple[ChipSpec, ...]:
    return tuple(ChipSpec(label=label, value=value, dashed=dashed) for label, value in pairs)


def _get(draft: dict[str, Any], key: str) -> dict[str, Any]:
    section = draft.get(key)
    return section if isinstance(section, dict) else {}


# --- completeness -------------------------------------------------------------


def _complete_business_name(draft: dict[str, Any]) -> bool:
    return bool(_get(draft, "business").get("name"))


def _complete_team(draft: dict[str, Any]) -> bool:
    return _get(draft, "business").get("is_team") is not None


def _complete_description(draft: dict[str, Any]) -> bool:
    return bool(_get(draft, "identity").get("description"))


def _complete_readback(draft: dict[str, Any]) -> bool:
    return _get(draft, "readback").get("confirmed") is True


def _complete_hours_contact(draft: dict[str, Any]) -> bool:
    business = _get(draft, "business")
    return bool(business.get("hours") and business.get("contact"))


def _complete_services(draft: dict[str, Any]) -> bool:
    items = _get(draft, "services").get("items") or []
    return bool(items) and all(
        isinstance(item, dict) and item.get("price_dollars") is not None for item in items
    )


def _complete_pricing_rules(draft: dict[str, Any]) -> bool:
    rules = _get(draft, "pricing_rules").get("rules") or []
    return all(
        isinstance(rule, dict)
        and rule.get("unit_amount_dollars") is not None
        and (rule.get("unit_amount_dollars") or 0) > 0
        for rule in rules
    )


def _complete_business_number(draft: dict[str, Any]) -> bool:
    tax = _get(draft, "tax")
    has_number = tax.get("has_business_number")
    if has_number is None:
        return False
    return has_number is False or bool(tax.get("business_number"))


def _complete_tax_registered(draft: dict[str, Any]) -> bool:
    return _get(draft, "tax").get("tax_registered") is not None


def _complete_payment_mode(draft: dict[str, Any]) -> bool:
    return _get(draft, "payment").get("processing_mode") is not None


def _complete_kyc(draft: dict[str, Any]) -> bool:
    if _get(draft, "payment").get("processing_mode") != "PLATFORM":
        return True
    kyc = _get(draft, "kyc")
    return bool(kyc.get("requested") or kyc.get("skipped"))


def _complete_payment_terms(draft: dict[str, Any]) -> bool:
    return _get(draft, "payment").get("terms") is not None


def _complete_deposit_pct(draft: dict[str, Any]) -> bool:
    payment = _get(draft, "payment")
    if payment.get("terms") != "deposit":
        return True
    pct = payment.get("deposit_pct")
    return isinstance(pct, int) and 1 <= pct <= 100


def _complete_inbound_channels(draft: dict[str, Any]) -> bool:
    return len(_get(draft, "business").get("inbound_channels") or []) >= 1


def _complete_tone(draft: dict[str, Any]) -> bool:
    return bool(_get(draft, "tone").get("tone"))


def _complete_escalation_posture(draft: dict[str, Any]) -> bool:
    return bool(_get(draft, "escalation_threshold").get("_resolved_threshold"))


# --- apply (chip selections fold into the draft) ------------------------------


# Text beats are satisfied by LLM extraction, never by a chip selection, so
# their apply() is a passthrough that leaves the section unchanged. It is only
# defined for completeness; run_selection only ever applies chip/cta/masked
# beats (their keys are the only ones next_beat can surface mid-selection).
def _passthrough(section_key: str) -> Callable[[dict[str, Any], list[str]], dict[str, Any]]:
    def _apply(draft: dict[str, Any], values: list[str]) -> dict[str, Any]:
        return dict(_get(draft, section_key))

    return _apply


def _apply_team(draft: dict[str, Any], values: list[str]) -> dict[str, Any]:
    business = dict(_get(draft, "business"))
    business["is_team"] = values[0] == "team"
    return business


def _apply_readback(draft: dict[str, Any], values: list[str]) -> dict[str, Any]:
    return {"confirmed": values[0] == "confirm"}


def _apply_business_number(draft: dict[str, Any], values: list[str]) -> dict[str, Any]:
    tax = dict(_get(draft, "tax"))
    if values and values[0] == "none":
        tax["has_business_number"] = False
        tax["business_number"] = ""
    else:
        tax["has_business_number"] = True
        tax["business_number"] = values[0] if values else ""
    return tax


def _apply_tax_registered(draft: dict[str, Any], values: list[str]) -> dict[str, Any]:
    tax = dict(_get(draft, "tax"))
    tax["tax_registered"] = values[0] == "yes"
    return tax


def _apply_payment_mode(draft: dict[str, Any], values: list[str]) -> dict[str, Any]:
    payment = dict(_get(draft, "payment"))
    payment["processing_mode"] = values[0]
    return payment


def _apply_kyc(draft: dict[str, Any], values: list[str]) -> dict[str, Any]:
    kyc = dict(_get(draft, "kyc"))
    if values and values[0] == "skip":
        kyc["skipped"] = True
    else:
        kyc["requested"] = True
    return kyc


def _apply_payment_terms(draft: dict[str, Any], values: list[str]) -> dict[str, Any]:
    payment = dict(_get(draft, "payment"))
    payment["terms"] = values[0]
    return payment


def _apply_deposit_pct(draft: dict[str, Any], values: list[str]) -> dict[str, Any]:
    payment = dict(_get(draft, "payment"))
    payment["deposit_pct"] = int(values[0])
    return payment


def _apply_inbound_channels(draft: dict[str, Any], values: list[str]) -> dict[str, Any]:
    business = dict(_get(draft, "business"))
    business["inbound_channels"] = list(values)
    return business


def _apply_tone(draft: dict[str, Any], values: list[str]) -> dict[str, Any]:
    return {"tone": values[0]}


def _apply_escalation_posture(draft: dict[str, Any], values: list[str]) -> dict[str, Any]:
    posture = cast(Posture, values[0])
    return {
        "posture": values[0],
        "threshold": None,
        "_resolved_threshold": resolve_threshold(EscalationDraft(posture=posture, threshold=None)),
    }


# --- the beat table -----------------------------------------------------------

BEAT_ORDER: tuple[Beat, ...] = (
    Beat(
        key="business_name",
        label="business name",
        ask="What is your business called?",
        kind="text",
        complete=_complete_business_name,
        apply=_passthrough("business"),
    ),
    Beat(
        key="team",
        label="team size",
        ask="Is it just you, or do you have a team?",
        kind="chips",
        chips=_chips([("Just me", "solo"), ("We're a team", "team")]),
        complete=_complete_team,
        apply=_apply_team,
    ),
    Beat(
        key="description",
        label="business description",
        ask="What does your business do?",
        kind="text",
        complete=_complete_description,
        apply=_passthrough("identity"),
    ),
    Beat(
        key="readback",
        label="confirmation of your details",
        ask="Does everything look right so far?",
        kind="chips",
        chips=_chips([("All good", "confirm"), ("Something's off", "edit")]),
        complete=_complete_readback,
        apply=_apply_readback,
    ),
    Beat(
        key="hours_contact",
        label="business hours and contact details",
        ask="What are your opening hours, and how can customers reach you?",
        kind="text",
        complete=_complete_hours_contact,
        apply=_passthrough("business"),
    ),
    Beat(
        key="services",
        label="at least one service or product with a price",
        ask="What services or products do you offer, and what do they cost?",
        kind="text",
        complete=_complete_services,
        apply=_passthrough("services"),
    ),
    Beat(
        key="pricing_rules",
        label="amounts for pricing rules",
        ask="Do you have any pricing rules, like rush fees or surcharges?",
        kind="text",
        complete=_complete_pricing_rules,
        apply=_passthrough("pricing_rules"),
    ),
    Beat(
        key="business_number",
        label="business number",
        ask="What's your business registration number?",
        kind="masked",
        mask="000 000 000",
        chips=_chips([("I don't have one", "none")]),
        complete=_complete_business_number,
        apply=_apply_business_number,
    ),
    Beat(
        key="tax_registered",
        label="tax registration",
        ask="Are you registered for tax?",
        kind="chips",
        chips=_chips([("Yes", "yes"), ("No", "no")]),
        complete=_complete_tax_registered,
        apply=_apply_tax_registered,
    ),
    Beat(
        key="payment_mode",
        label="payment collection method",
        ask="How would you like to collect payments?",
        kind="chips",
        chips=_chips(
            [
                ("Collect through Wren", "PLATFORM"),
                ("I collect directly", "DIRECT"),
                ("Decide later", "DEFERRED"),
            ]
        ),
        complete=_complete_payment_mode,
        apply=_apply_payment_mode,
    ),
    Beat(
        key="kyc",
        label="identity check",
        ask="To collect payments through Wren, you'll need to verify your identity.",
        kind="cta",
        cta_label="Start ID check",
        chips=_chips([("Skip for now", "skip")]),
        complete=_complete_kyc,
        apply=_apply_kyc,
    ),
    Beat(
        key="payment_terms",
        label="payment terms",
        ask="When should customers pay?",
        kind="chips",
        chips=_chips(
            [
                ("Take a deposit", "deposit"),
                ("Full payment before", "full_before"),
                ("Full payment after", "full_after"),
                ("Decide later", "later"),
            ]
        ),
        complete=_complete_payment_terms,
        apply=_apply_payment_terms,
    ),
    Beat(
        key="deposit_pct",
        label="deposit percentage",
        ask="How much deposit should you take?",
        kind="chips",
        chips=_chips([("20%", "20"), ("30%", "30"), ("50%", "50")]),
        complete=_complete_deposit_pct,
        apply=_apply_deposit_pct,
    ),
    Beat(
        key="inbound_channels",
        label="how customers can reach you",
        ask="How can customers reach you?",
        kind="chips",
        chips=_chips(
            [
                ("My website", "website"),
                ("Phone", "phone"),
                ("SMS", "sms"),
                ("Email", "email"),
                ("Facebook", "facebook"),
                ("Word of mouth", "word_of_mouth"),
            ],
            dashed=True,
        ),
        complete=_complete_inbound_channels,
        apply=_apply_inbound_channels,
    ),
    Beat(
        key="tone",
        label="assistant tone",
        ask="How should your assistant sound?",
        kind="chips",
        chips=_chips(
            [("Friendly", "friendly"), ("Professional", "professional"), ("Casual", "casual")]
        ),
        complete=_complete_tone,
        apply=_apply_tone,
    ),
    Beat(
        key="escalation_posture",
        label="escalation posture",
        ask="When should your assistant hand things over to you?",
        kind="chips",
        chips=_chips([("Rarely", "rarely"), ("Balanced", "balanced"), ("Cautiously", "cautious")]),
        complete=_complete_escalation_posture,
        apply=_apply_escalation_posture,
    ),
)

BEATS: dict[str, Beat] = {beat.key: beat for beat in BEAT_ORDER}

_DRAFT_KEYS: dict[str, str] = {
    "business_name": "business",
    "team": "business",
    "description": "identity",
    "readback": "readback",
    "hours_contact": "business",
    "services": "services",
    "pricing_rules": "pricing_rules",
    "business_number": "tax",
    "tax_registered": "tax",
    "payment_mode": "payment",
    "kyc": "kyc",
    "payment_terms": "payment",
    "deposit_pct": "payment",
    "inbound_channels": "business",
    "tone": "tone",
    "escalation_posture": "escalation_threshold",
}


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
        placeholder=beat.ask,
        chips=list(beat.chips),
        mask=beat.mask,
        cta_label=beat.cta_label,
    )


def check_completeness(draft: dict[str, Any]) -> list[str]:
    """Labels of every unsatisfied beat."""
    return [beat.label for beat in BEAT_ORDER if not beat.complete(draft)]


def apply_selection(draft: dict[str, Any], key: str, values: list[str]) -> dict[str, Any]:
    """Merge a chip selection for ``key`` into ``draft`` and return it."""
    beat = BEATS[key]
    draft[_DRAFT_KEYS[key]] = beat.apply(draft, values)
    return draft
