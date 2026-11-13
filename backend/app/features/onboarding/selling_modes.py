"""32: the four selling modes, their capability bundles, and their inference.

Everything here is data plus pure functions. The four presets are rows in a
table, not branches: an owner who sells food and an owner who cuts hair take the
same code path and differ only in which row was picked. No function in this
module reads a business type to decide behaviour, and none of it touches the
database or a model - ``infer_selling_mode`` is a keyword scorer over text that
was already extracted, so the confirmation is fast, repeatable, and explainable.

The label map is the tenant-facing vocabulary (``Item``, ``Items``, ``Work``,
``Add item``, ``Time``, ``Unavailable``, ``Action``). A mode preset supplies its
own wording for all seven keys; a stored map that is missing one falls back to
the neutral default here rather than at the render site, so the server-rendered
summary and the frontend can never disagree about what a missing label says.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator

Mode = Literal["orders", "bookings", "quotes", "products"]
Confidence = Literal["high", "medium", "low"]
ScheduleMode = Literal["none", "asap", "slot", "window"]
StockMode = Literal["none", "flag", "counted"]
FulfillmentMode = Literal["in_house", "pickup", "delivery", "onsite", "shipping"]
AcceptanceMode = Literal["auto", "owner", "deposit"]
PaymentMode = Literal["now", "later", "deposit"]

# The canonical order. Ties resolve in this order, and every candidate list the
# inference returns is ordered by it, so two runs of the same source are equal.
MODES: tuple[Mode, ...] = ("orders", "bookings", "quotes", "products")

# What the owner reads on a chip. Data, like every other vertical-shaped word
# here - nothing branches on it.
MODE_TITLES: dict[Mode, str] = {
    "orders": "Orders",
    "bookings": "Bookings",
    "quotes": "Quotes",
    "products": "Products",
}

# A missing label is a neutral word, never a vertical's own. The frontend
# mirrors this map in frontend/src/lib/selling-modes.ts; both sides are pinned
# by a test so a rename cannot land on one side only.
LABEL_DEFAULTS: dict[str, str] = {
    "item": "Item",
    "items": "Items",
    "work": "Work",
    "add_item": "Add item",
    "time": "Time",
    "sold_out": "Unavailable",
    "action": "Action",
}

# Settings will edit these later. One object, so a second writer cannot invent a
# different set of defaults (32, "Config").
ORDERING_DEFAULTS: dict[str, Any] = {
    "hold_ttl_minutes": 15,
    "owner_hold_ttl_minutes": 30,
    "slot_increment_minutes": 15,
    "lead_time_minutes": 30,
    "deposit_bps": 0,
    "timezone": "Australia/Sydney",
    "delivery_fee_cents": 0,
    "delivery_radius_km": 0,
}


class Capabilities(BaseModel):
    """The six independent switches the whole product reads.

    ``extra="forbid"`` is what makes an unknown axis a 422 instead of a key that
    is stored and then ignored: the config is the source of truth for every
    later screen, so a typo in an axis name has to fail loudly at the door.
    """

    model_config = ConfigDict(extra="forbid")

    sell: list[Mode] = Field(min_length=1)
    schedule: ScheduleMode
    stock: StockMode
    fulfillment: list[FulfillmentMode] = Field(min_length=1)
    acceptance: AcceptanceMode
    payment: PaymentMode


class SellingMode(BaseModel):
    """``tenant_config.config.ordering`` - what the rest of the product reads."""

    mode: Mode
    capabilities: Capabilities
    labels: dict[str, str]
    defaults: dict[str, Any] = Field(default_factory=lambda: dict(ORDERING_DEFAULTS))


class Suggestion(BaseModel):
    """What the inference says, with enough detail to explain a wrong guess.

    ``candidates`` is the list the card renders: one mode at high confidence,
    the two that tied at medium, all four at low. ``mode`` is always the first
    candidate, so a caller that only reads ``mode`` still gets a usable answer.
    """

    mode: Mode
    capabilities: Capabilities
    labels: dict[str, str]
    confidence: Confidence
    candidates: list[Mode]
    evidence: list[str]


@dataclass(frozen=True)
class SourceMaterial:
    """Everything the inference is allowed to read.

    Gathered by the caller (documents, profile, offerings, categories) so the
    scorer itself stays pure and a test can hand it four strings.
    """

    source_text: str = ""
    profile: Mapping[str, Any] = field(default_factory=dict)
    offerings: Sequence[str] = ()
    categories: Sequence[str] = ()


@dataclass(frozen=True)
class ModePreset:
    capabilities: dict[str, Any]
    labels: dict[str, str]


# The four default bundles from the ticket's table. A mode is a starting point,
# never a lock: every axis stays editable, and a second mode can be added.
MODE_PRESETS: dict[Mode, ModePreset] = {
    "orders": ModePreset(
        capabilities={
            "sell": ["orders"],
            "schedule": "asap",
            "stock": "flag",
            "fulfillment": ["in_house", "pickup"],
            "acceptance": "auto",
            "payment": "now",
        },
        labels={
            "item": "Dish",
            "items": "Menu",
            "work": "Orders",
            "add_item": "Add a dish",
            "time": "Prep time",
            "sold_out": "Sold out today",
            "action": "Order",
        },
    ),
    "bookings": ModePreset(
        capabilities={
            "sell": ["bookings"],
            "schedule": "slot",
            "stock": "none",
            "fulfillment": ["onsite"],
            "acceptance": "auto",
            "payment": "later",
        },
        labels={
            "item": "Service",
            "items": "Services",
            "work": "Bookings",
            "add_item": "Add a service",
            "time": "Duration",
            "sold_out": "Unavailable",
            "action": "Book",
        },
    ),
    "quotes": ModePreset(
        capabilities={
            "sell": ["quotes"],
            "schedule": "window",
            "stock": "none",
            "fulfillment": ["onsite"],
            "acceptance": "owner",
            "payment": "later",
        },
        labels={
            "item": "Job",
            "items": "Jobs",
            "work": "Requests",
            "add_item": "Add a job",
            "time": "Visit window",
            "sold_out": "Unavailable",
            "action": "Request a quote",
        },
    ),
    "products": ModePreset(
        capabilities={
            "sell": ["products"],
            "schedule": "none",
            "stock": "counted",
            "fulfillment": ["shipping", "pickup"],
            "acceptance": "auto",
            "payment": "now",
        },
        labels={
            "item": "Product",
            "items": "Products",
            "work": "Products",
            "add_item": "Add a product",
            "time": "Delivery time",
            "sold_out": "Out of stock",
            "action": "Add to cart",
        },
    ),
}


def normalize_labels(labels: Mapping[str, Any] | None) -> dict[str, str]:
    """Fill every known key, drop every unknown one, and stringify the values.

    Dropping an unknown key is the tolerant half: a label map written by an
    older build or a future Settings screen cannot break the summary. The
    capabilities are the strict half - an unknown axis there is a 422.
    """
    merged = dict(LABEL_DEFAULTS)
    for key, value in (labels or {}).items():
        if key in LABEL_DEFAULTS:
            merged[key] = str(value)
    return merged


class OrderingDefaults(BaseModel):
    """``config.ordering.defaults``, bounded where the ticket bounds it.

    The bounds are the ones the offering columns already carry (32, "Orders
    extension"), restated here because this block is where the ordering engine
    reads them: a deposit is ``total_cents * deposit_bps / 10000``, so a stored
    ``999999`` is a payable amount no clerk ever agreed to. ``extra="forbid"``
    keeps the key set closed, and every field is an ``int``/``str`` with the
    module default behind it, so a null or a word is a 422 at the door instead
    of a ``TypeError`` on the way to the row.
    """

    model_config = ConfigDict(extra="forbid")

    hold_ttl_minutes: int = Field(gt=0)
    owner_hold_ttl_minutes: int = Field(gt=0)
    slot_increment_minutes: int = Field(gt=0)
    lead_time_minutes: int = Field(ge=0)
    deposit_bps: int = Field(ge=0, le=10000)
    timezone: str
    delivery_fee_cents: int = Field(ge=0)
    delivery_radius_km: int = Field(ge=0)

    @field_validator("timezone")
    @classmethod
    def _real_zone(cls, value: str) -> str:
        """A timezone the scheduler can resolve, not just a non-empty word."""
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError(f"unknown timezone: {value}") from exc
        return value


def normalize_defaults(defaults: Mapping[str, Any] | None) -> dict[str, Any]:
    """The ordering defaults, with the owner's edits layered over them.

    Strict where it has to be: a key outside ``ORDERING_DEFAULTS`` is an error,
    not a silently stored value nothing reads, and every value is bounded by
    ``OrderingDefaults`` so the block the ordering engine divides by is always
    sane. Coercion is kept - a JSON number arriving as a string still lands as
    an int - but a value that has no int in it (null, a word, a fraction) is a
    validation error, never a truncation.
    """
    merged = {**ORDERING_DEFAULTS, **(defaults or {})}
    return OrderingDefaults.model_validate(merged).model_dump()


def normalize_selling_mode(
    *,
    mode: Mode,
    capabilities: Mapping[str, Any] | Capabilities | None,
    labels: Mapping[str, Any] | None,
    defaults: Mapping[str, Any] | None = None,
) -> SellingMode:
    """One stored ordering config, with the mode's preset under anything given.

    ``capabilities=None`` means "the preset", which is what a one-tap confirm
    sends. A partial mapping is layered over the preset so a single-axis
    correction does not have to restate the other five. ``defaults`` is the same
    shape one level down: absent keys keep the module constant.
    """
    preset = MODE_PRESETS[mode]
    merged: dict[str, Any] = dict(preset.capabilities)
    if isinstance(capabilities, Capabilities):
        merged.update(capabilities.model_dump())
    elif capabilities is not None:
        merged.update(dict(capabilities))
    return SellingMode(
        mode=mode,
        capabilities=Capabilities.model_validate(merged),
        labels=normalize_labels({**preset.labels, **(labels or {})}),
        defaults=normalize_defaults(defaults),
    )


# --- the scorer --------------------------------------------------------------

# Nav and page copy: the strong signal. Base weight 1 is "the word appears",
# 2 is a phrase that names the act of buying ("order online", "book now").
_SOURCE_PHRASES: dict[Mode, tuple[tuple[str, int], ...]] = {
    "orders": (
        ("order online", 2),
        ("order now", 2),
        ("order ahead", 2),
        ("pre-order", 2),
        ("reserve a table", 2),
        ("menu", 1),
        ("pickup", 1),
        ("pick up", 1),
        ("delivery", 1),
        ("eat in", 1),
        ("dine in", 1),
        ("takeaway", 1),
        ("take out", 1),
    ),
    "bookings": (
        ("book now", 2),
        ("book online", 2),
        ("book a", 1),
        ("appointment", 1),
        ("appointments", 1),
        ("booking", 1),
        ("bookings", 1),
        ("schedule", 1),
        ("reserve", 1),
        ("staff", 1),
    ),
    "quotes": (
        ("request a quote", 2),
        ("get a quote", 2),
        ("free quote", 2),
        ("free estimate", 2),
        ("site visit", 2),
        ("quote", 1),
        ("estimate", 1),
        ("custom", 1),
    ),
    "products": (
        ("add to cart", 2),
        ("add to bag", 2),
        ("buy now", 2),
        ("shop now", 2),
        ("free shipping", 2),
        ("shipping", 1),
        ("products", 1),
        ("product", 1),
        ("cart", 1),
        ("shop", 1),
        ("in stock", 1),
    ),
}

# Business type is the weak signal the ticket names: it never wins on its own.
_TYPE_PHRASES: dict[Mode, tuple[str, ...]] = {
    "orders": (
        "cafe",
        "restaurant",
        "takeaway",
        "bistro",
        "bakery",
        "pizzeria",
        "kitchen",
        "catering",
    ),
    "bookings": (
        "barber",
        "salon",
        "clinic",
        "studio",
        "dentist",
        "dental",
        "spa",
        "therapist",
        "tutor",
        "gym",
    ),
    "quotes": (
        "cleaning",
        "cleaner",
        "plumber",
        "plumbing",
        "repair",
        "repairs",
        "trades",
        "electrician",
        "builder",
        "landscaping",
        "handyman",
    ),
    "products": (
        "shop",
        "store",
        "boutique",
        "retail",
        "grocery",
        "supermarket",
    ),
}

# A duration is what a service list has and a menu does not.
_DURATION = re.compile(
    r"\b\d{1,3}\s*(?:minutes|minute|mins|min|hours|hour|hrs|hr)\b", re.IGNORECASE
)
# A price is what a menu or a product grid has, and neither of those is a quote.
_PRICE = re.compile(r"\$\s*\d")
# "From $X" is the quote tell the ticket names; a plain price is not.
_FROM_PRICE = re.compile(r"\b(?:from|starting at|starts at)\s*\$", re.IGNORECASE)


def _normalized(text: str) -> str:
    """Casefolded word text with one space either side, for phrase matching."""
    return " " + re.sub(r"[^a-z0-9]+", " ", text.casefold()).strip() + " "


def _text_of(value: Any) -> str:
    if isinstance(value, (list, tuple)):
        return " ".join(str(item) for item in value)
    return str(value or "")


def _segments(material: SourceMaterial) -> tuple[tuple[str, str, int], ...]:
    """Each field the scorer reads, the words it uses to name it, and its weight.

    Naming the field in the evidence is the whole point of ``evidence``: "menu
    in your website" is checkable, "scored 3" is not.
    """
    profile = material.profile
    return (
        ("your website", _text_of(material.source_text), 3),
        (
            "what you offer",
            " ".join(
                [
                    *[str(item) for item in material.offerings],
                    _text_of(profile.get("services")),
                ]
            ),
            3,
        ),
        ("your categories", " ".join(str(item) for item in material.categories), 2),
        (
            "your business type",
            " ".join(_text_of(profile.get(key)) for key in ("business_name", "business_type")),
            1,
        ),
    )


# Two modes within this many points of each other are a tie the owner should
# settle. One matched phrase is worth at least 3, so this means "equal".
_TIE_MARGIN = 2
# Below this, nothing the source said was worth calling a guess.
_WEAK_SCORE = 3


def infer_selling_mode(material: SourceMaterial) -> Suggestion:
    """Which of the four modes this source looks like, and why.

    Deterministic: same material in, same suggestion out. No clock, no random
    tie-break, no model - the owner's one-tap confirm is answering a value that
    was already computed before they saw the card.
    """
    scores: dict[Mode, int] = {mode: 0 for mode in MODES}
    scored: list[tuple[Mode, str]] = []

    for where, text, weight in _segments(material):
        if not text.strip():
            continue
        normalized = _normalized(text)
        for mode in MODES:
            for phrase, base in _SOURCE_PHRASES[mode]:
                if f" {phrase} " in normalized:
                    scores[mode] += base * weight
                    scored.append((mode, f'"{phrase}" in {where}'))
            for phrase in _TYPE_PHRASES[mode]:
                if f" {phrase} " in normalized:
                    scores[mode] += weight
                    scored.append((mode, f'"{phrase}" in {where}'))

        durations = _DURATION.findall(text)
        if durations:
            scores["bookings"] += 2 * weight
            scored.append(("bookings", f'"{durations[0]}" in {where}'))
        price = _PRICE.search(text)
        if price:
            scores["orders"] += weight
            scores["products"] += weight
            scored.append(("orders", f'"{price.group(0)}" in {where}'))
            scored.append(("products", f'"{price.group(0)}" in {where}'))
        if _FROM_PRICE.search(text):
            scores["quotes"] += 2 * weight
            scored.append(("quotes", f'"from $" in {where}'))

    ranked = sorted(MODES, key=lambda mode: scores[mode], reverse=True)
    top = scores[ranked[0]]
    second = scores[ranked[1]] if len(ranked) > 1 else 0

    if top < _WEAK_SCORE:
        candidates: list[Mode] = list(MODES)
        confidence: Confidence = "low"
    elif second > 0 and top - second <= _TIE_MARGIN:
        candidates = [ranked[0], ranked[1]]
        confidence = "medium"
    else:
        candidates = [ranked[0]]
        confidence = "high"

    primary = candidates[0]
    config = normalize_selling_mode(mode=primary, capabilities=None, labels=None)
    return Suggestion(
        mode=primary,
        capabilities=config.capabilities,
        labels=config.labels,
        confidence=confidence,
        candidates=candidates,
        evidence=[text for mode, text in scored if mode in candidates],
    )


# --- the read-back -----------------------------------------------------------

_SELL_CLAUSE: dict[Mode, str] = {
    "orders": "take orders from your {items}",
    "bookings": "take bookings for your {items}",
    "quotes": "take quote requests for your {items}",
    "products": "sell your {items}",
}
_SELL_NOUN: dict[Mode, str] = {
    "orders": "orders",
    "bookings": "bookings",
    "quotes": "quote requests",
    "products": "products",
}
_FULFILLMENT_WORD: dict[FulfillmentMode, str] = {
    "in_house": "eat in",
    "pickup": "pickup",
    "delivery": "delivery",
    # 32: every word here follows "offer", so it has to be a noun phrase. The
    # old "come to you" read as "offer come to you", and the confirm screen is
    # where the owner reads it.
    "onsite": "on-site visits",
    "shipping": "shipping",
}
_SCHEDULE_WORD: dict[ScheduleMode, str] = {
    "asap": "give a ready time",
    "slot": "offer time slots",
    "window": "offer a visit window",
}
_ACCEPTANCE_WORD: dict[AcceptanceMode, str] = {
    "owner": "check with you before you accept each one",
    "deposit": "take a deposit before you accept each one",
}
_PAYMENT_WORD: dict[PaymentMode, str] = {
    "now": "take payment up front",
    "later": "let them pay later",
    "deposit": "ask for a deposit",
}


def _and(parts: list[str]) -> str:
    if len(parts) <= 1:
        return "".join(parts)
    return f"{', '.join(parts[:-1])} and {parts[-1]}"


def _article(word: str) -> str:
    return "an" if word[:1] in "aeiou" else "a"


def summary_for(config: SellingMode | Mapping[str, Any]) -> str:
    """The card's read-back, composed from the stored config and nothing else.

    Every clause is a capability or a label, so renaming ``Menu`` to
    ``Treatments`` - or adding a second mode - changes the sentence with no
    code change and no model call.
    """
    stored = config if isinstance(config, SellingMode) else SellingMode.model_validate(config)
    capabilities = stored.capabilities
    labels = normalize_labels(stored.labels)
    items = labels["items"].lower()
    item = labels["item"].lower()

    clauses: list[str] = []
    if len(capabilities.sell) == 1:
        clauses.append(_SELL_CLAUSE[capabilities.sell[0]].format(items=items))
    else:
        clauses.append("take " + _and([_SELL_NOUN[mode] for mode in capabilities.sell]))

    clauses.append("offer " + _and([_FULFILLMENT_WORD[mode] for mode in capabilities.fulfillment]))
    if capabilities.schedule in _SCHEDULE_WORD:
        clauses.append(_SCHEDULE_WORD[capabilities.schedule])
    if capabilities.stock == "flag":
        clauses.append(f"mark {_article(item)} {item} sold out when you run out")
    elif capabilities.stock == "counted":
        clauses.append(f"keep a count of your {items}")
    if capabilities.acceptance in _ACCEPTANCE_WORD:
        clauses.append(_ACCEPTANCE_WORD[capabilities.acceptance])
    clauses.append(_PAYMENT_WORD[capabilities.payment])

    return f"Your assistant will {_and(clauses)}. You can change this later."
