"""T-042: agentic onboarding copilot turn loop.

Two model calls per turn: one structured ``extract()`` to pull anything the
owner stated into the draft, then ``chat()`` to compose a conversational reply
from a server-computed directive. Structured extraction (rather than tool
calls) keeps capture robust on free/edge models that answer in prose; the
server's completeness gate stays authoritative.

The model writes only an acknowledgment; the server appends the beat's ``ask``
verbatim (W-2), so the question the owner sees is always the one the beat
cursor chose. Every turn is persisted - skipping the write let a later turn
reload an older row and rewind the beat pointer.

Guardrails: scan_input, price echo check, bounded history. Off-topic/meta
questions are answered in one line then gently redirected - no escalating
firmness, and they never burn one of a beat's two asks.
State: {version: 3, draft, history, off_topic_count, completed,
knowledge_pending, offering_candidates, skipped, deferred, ask_beat,
ask_count} in jsonb.
"""

from __future__ import annotations

import json
import logging
import re
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

from app.agents.spotlight import scan_input
from app.features.business.offering_candidates import normalize_name
from app.llm.provider import ChatMessage, LLMProvider
from app.observability.logging import TRANSCRIPT_LOGGER_NAME
from app.onboarding import beats
from app.onboarding.flow import DraftUpdate, PendingOffering
from app.onboarding.tools import save_profile

logger = logging.getLogger("app.onboarding.agent")
transcript = logging.getLogger(TRANSCRIPT_LOGGER_NAME)

_MAX_HIST = 20


def _ms(started: float) -> float:
    return round((time.perf_counter() - started) * 1000, 1)


@dataclass
class Directive:
    """What the reply model is asked to write - an acknowledgment, never a question.

    W-2: the visible question is the beat's own ``ask``, appended verbatim by
    the server after whatever this produces. Before W-2 the directive said
    ``"Ask for: {ask}"`` and let the model phrase the question itself, which is
    how a beat that was already filled kept getting asked again.
    """

    acknowledged: list[str] = field(default_factory=list)
    meta_answer: str = ""
    nudge: str = ""

    def as_prompt(self) -> str:
        parts: list[str] = []
        if self.acknowledged:
            parts.append(f"Just captured: {', '.join(self.acknowledged)}.")
        if self.meta_answer:
            parts.append(f"Briefly answer: {self.meta_answer}")
        if self.nudge:
            parts.append(self.nudge)
        parts.append(
            "Write only a short, warm acknowledgment of what the owner just said. "
            "Do not ask a question - the next question is added after your words."
        )
        return " ".join(parts)


_COPILOT = (
    "You are the owner's Agencx setup assistant. Help a small-business owner describe "
    "their name, business name, business type, team size, opening hours, what "
    "they sell, how customers reach them, and their ABN and GST registration. "
    "Warmly acknowledge what the owner tells you, in wording close to their own. "
    "You never choose or write the question - the server appends it to your reply. "
    "Answer meta questions in one line."
)

# C-3: a figure the extractor rounds into the profile becomes a figure the
# customer-facing money gate will bless forever - the profile is one of its
# three allowed sources (C-1). So the copy-it-exactly rule belongs here too,
# not only on the customer side.
_EXTRACT_PROMPT = (
    "You are extracting business information from a small-business owner who is "
    "onboarding their assistant. Read the conversation and update the profile "
    "with anything new the owner stated: name, business_name, business_type, "
    "headcount, hours, services, contact, abn, gst. Also list offering_names "
    "only when the owner explicitly names individual offerings. Fill only what the owner "
    "actually said - never invent a value. Copy any price or other amount "
    "exactly as the owner wrote it: never round it, convert it, tidy it up, or "
    "work one out. Two fields have a fixed vocabulary: set abn to the digits "
    'the owner gave, or to "none" if they said they do not have one yet; set '
    'gst to "yes" or "no". Never infer or invent offering names, and never add prices '
    "or descriptions to offering_names. Split a run-on list into one entry per item "
    'even when it has no commas: "we offer pita coffee and wraps" is offering_names '
    '["pita", "coffee", "wraps"], not a single entry. '
    "If the message is off-topic (a question about "
    "you, a greeting, or unrelated chat), set off_topic=true and put a one-line "
    "answer in meta_reply. Otherwise set off_topic=false. Leave the profile null "
    "when nothing new was stated. The server chooses the next question."
)


@dataclass
class OnboardingRecord:
    version: int = 3
    draft: dict[str, Any] = field(default_factory=dict)
    history: list[dict[str, str]] = field(default_factory=list)
    off_topic_count: int = 0
    completed: bool = False
    # O-3 follow-up: the optional website/documents ask is pending until the
    # owner answers it (paste a link, attach a file, or say "skip"). It never
    # gates go-live - confirm still requires only the seven profile fields.
    knowledge_pending: bool = False
    offering_candidates: list[PendingOffering] = field(default_factory=list)
    # W-2's two-pass cursor and ask counter. ``skipped`` beats are gone for
    # good; ``deferred`` ones are required beats held back to pass two.
    # ``ask_beat``/``ask_count`` track only the beat being asked right now,
    # since that is the only one whose repeat count matters.
    skipped: list[str] = field(default_factory=list)
    deferred: list[str] = field(default_factory=list)
    ask_beat: str = ""
    ask_count: int = 0

    @classmethod
    def from_jsonb(cls, raw: dict[str, Any]) -> OnboardingRecord:
        """Load a record, migrating anything older than v3 to the lean profile.

        v3 is O-1's flat profile. A v1/v2 draft holds the retired nested
        sections (business/identity/tone/services/...), which share no key with
        the lean fields, so it is dropped rather than carried as orphan data -
        an in-flight interview restarts. ``completed`` survives, so a tenant
        that already went live is never re-interviewed.
        """
        if raw.get("version") == 3:
            return cls(
                version=3,
                draft=raw.get("draft", {}),
                history=raw.get("history", []),
                off_topic_count=raw.get("off_topic_count", 0),
                completed=raw.get("completed", False),
                knowledge_pending=raw.get("knowledge_pending", False),
                offering_candidates=_load_offerings(raw.get("offering_candidates", [])),
                # W-2's fields read through a default rather than forcing a
                # version bump: absence is indistinguishable from "fresh", and
                # bumping would restart every interview in flight at deploy.
                skipped=list(raw.get("skipped", [])),
                deferred=list(raw.get("deferred", [])),
                ask_beat=raw.get("ask_beat", ""),
                ask_count=raw.get("ask_count", 0),
            )
        return cls(
            version=3,
            draft={},
            history=[],
            off_topic_count=0,
            completed=raw.get("completed", False),
            offering_candidates=[],
        )

    def to_jsonb(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "draft": self.draft,
            "history": self.history[-_MAX_HIST:],
            "off_topic_count": self.off_topic_count,
            "completed": self.completed,
            "knowledge_pending": self.knowledge_pending,
            "offering_candidates": [item.model_dump() for item in self.offering_candidates],
            "skipped": self.skipped,
            "deferred": self.deferred,
            "ask_beat": self.ask_beat,
            "ask_count": self.ask_count,
        }


def _load_offerings(raw: Any) -> list[PendingOffering]:
    offerings: list[PendingOffering] = []
    for item in raw if isinstance(raw, list) else []:
        try:
            offering = PendingOffering.model_validate(
                {"name": item, "sources": ["owner"]} if isinstance(item, str) else item
            )
        except (TypeError, ValueError):
            continue
        if normalize_name(offering.name) not in {
            normalize_name(existing.name) for existing in offerings
        }:
            offerings.append(offering)
    return offerings


def _merge_owner_offerings(record: OnboardingRecord, names: list[str]) -> None:
    documents = [item for item in record.offering_candidates if "document" in item.sources]
    owner: list[PendingOffering] = []
    seen: set[str] = set()
    for raw_name in names:
        name = raw_name.strip()
        key = normalize_name(name)
        if name and key not in seen:
            seen.add(key)
            owner.append(PendingOffering(name=name, sources=["owner"]))
    combined = owner + documents
    merged: dict[str, PendingOffering] = {}
    for item in combined:
        key = normalize_name(item.name)
        existing = merged.get(key)
        if existing is None:
            merged[key] = item.model_copy(deep=True)
            continue
        sources = list(dict.fromkeys([*existing.sources, *item.sources]))
        if "owner" in item.sources:
            merged[key] = item.model_copy(update={"sources": sources})
        else:
            merged[key] = existing.model_copy(update={"sources": sources})
    record.offering_candidates = list(merged.values())


@dataclass
class TurnPlan:
    """Everything ``prepare_turn`` computed, ready for either the streamed or
    non-streamed reply path.

    ``summary`` is set when the turn completes the profile - the
    reply is server-synthesized from the draft and never touches the model.
    ``reply_msgs`` is set otherwise and is what the reply path feeds the LLM.
    ``question`` is the next beat's ``ask``, verbatim; the reply path appends
    it after the model's acknowledgment so the model never phrases it (W-2).
    ``off_topic`` mirrors the extraction verdict for logging.
    """

    record: OnboardingRecord
    summary: str | None
    reply_msgs: list[ChatMessage] | None
    question: str | None = None
    off_topic: bool = False


def _activation_summary(draft: dict[str, Any]) -> str:
    name = draft.get("business_name") or draft.get("name")
    if name:
        intro = f"Your assistant for {name} is ready to go live."
    else:
        intro = "Your assistant is ready to go live."
    return f"{intro} Hit confirm to publish it."


# The optional website/documents ask (founder request): asked once when the
# profile completes, never a gate. Skipping is one word, and the same offer
# names the Settings > Knowledge fallback so knowledge can always wait.
_KNOWLEDGE_OFFER = (
    " Do you have a website or any documents - a menu, price list, or FAQs? "
    'You can paste a link, attach a file, or say "skip". Anything you save '
    "becomes a reference I can use when answering your customers, and you can "
    "add more any time from Settings."
)


def _completion_reply(record: OnboardingRecord) -> str:
    """The server-synthesized reply once the seven fields are captured.

    First call fires the website/documents offer and opens the ``knowledge``
    stage; every later call is the activation summary, so the offer never
    repeats and "skip" (or a pasted link, cleared by ``prepare_url_turn``)
    advances the owner to confirm.
    """
    if not record.knowledge_pending:
        record.knowledge_pending = True
        return _activation_summary(record.draft) + _KNOWLEDGE_OFFER
    record.knowledge_pending = False
    return _activation_summary(record.draft)


def selection_reply(record: OnboardingRecord) -> str:
    """A deterministic acknowledgement followed by the authoritative next ask."""
    nxt = _advance(record)
    return f"Got it. {nxt.ask}" if nxt is not None else _completion_reply(record)


def progress(record: OnboardingRecord) -> tuple[str, beats.InputSpec | None, bool]:
    """The interview's (stage, composer widget, can-confirm) triple.

    The single source both ``_state_event`` and ``response_from_record`` read,
    so the SSE state and the REST state never disagree. A completed profile
    passes through the optional ``knowledge`` stage before ``confirm``.
    """
    nxt = beats.next_beat(record.draft, record.skipped, record.deferred)
    if nxt is not None:
        return nxt.key, beats.input_spec(nxt), False
    if record.knowledge_pending:
        return "knowledge", beats.KNOWLEDGE_INPUT, False
    return "confirm", None, not record.completed


def _advance(record: OnboardingRecord) -> beats.Beat | None:
    """The beat to ask now, against this record's skipped and deferred keys.

    ``deferred`` is never cleared: once pass one runs out of beats,
    ``next_beat`` falls through to the deferred ones on its own, and keeping
    the list is what lets the caller tell a second ask from a final one.
    """
    return beats.next_beat(record.draft, record.skipped, record.deferred)


def _resolve(record: OnboardingRecord, beat: beats.Beat, admin_message: str) -> None:
    """Close a beat the owner has not answered in two asks.

    A skippable beat takes its default or is dropped. A required beat is
    deferred on pass one; on pass two there is nowhere left to defer it to, so
    the owner's own words are taken verbatim - these four fields have no
    validation, so whatever they typed *is* the answer, and the confirm screen
    reads the name and type back for correction before anything is published.
    """
    if beat.optional:
        if beat.default:
            record.draft[beat.key] = beat.default
        else:
            record.skipped.append(beat.key)
    elif beat.key not in record.deferred:
        record.deferred.append(beat.key)
    elif admin_message.strip():
        record.draft[beat.key] = admin_message.strip()
    record.ask_beat = ""
    record.ask_count = 0


def _nudge(beat: beats.Beat, *, final_pass: bool) -> str:
    """The extra instruction on a beat's second ask - acknowledgment only."""
    if beat.optional:
        return (
            "The owner has not answered this yet. Say warmly that it can wait, and "
            'mention they can tap "Skip for now".'
        )
    if final_pass:
        return (
            "The owner still has not answered this. Say plainly and kindly that you "
            f"need it to publish their page. Work in this example: {beat.example}."
        )
    return (
        "The owner has not answered this yet. Acknowledge that warmly and work in "
        f"this example: {beat.example}."
    )


def _extraction_input(
    record: OnboardingRecord, admin_message: str, asked: beats.Beat | None = None
) -> str:
    lines: list[str] = []
    if record.draft:
        lines.append("Current draft (already captured):")
        lines.append(json.dumps(record.draft))
    for entry in record.history[-_MAX_HIST:]:
        lines.append(f"{entry['role']}: {entry['content']}")
    # A hint, never a filter: it only helps disambiguate a reply that could be
    # an answer to several fields. The full schema stays available, so an
    # answer to some *other* question is still captured into its own field.
    if asked is not None:
        lines.append(f"The question asked this turn was: {asked.ask}")
    lines.append(f"user: {admin_message}")
    return "\n".join(lines)


# O-3 site-as-shortcut: a page is bounded to this window before it is handed to
# the extractor - the whole page (up to the 2MB fetch cap) would blow the
# extract call's budget, and a homepage states who the business is up front.
_URL_EXTRACT_CHARS = 4000

_URL_EXTRACT_PROMPT = (
    "You are extracting business information from a website a small-business "
    "owner just linked during onboarding. Read the page text and fill any of "
    "these fields the page states: business_name, business_type, services, "
    "hours. Fill only what the page actually says - never invent a value, and "
    "leave a field empty when the page does not mention it. Copy any price or "
    "other amount exactly as the page states it: never round it, convert it, or "
    "work one out. Set off_topic=false."
)

# O-3: the fields a homepage reliably states, read back to the owner for
# confirmation. name/headcount/contact stay conversationally asked (a page
# rarely states them cleanly).
_URL_READBACK_FIELDS = ("business_type", "services", "hours")


def _url_readback(draft: dict[str, Any]) -> str:
    parts = [
        f"{field.replace('_', ' ')}: {draft[field]}"
        for field in _URL_READBACK_FIELDS
        if draft.get(field)
    ]
    if parts:
        return (
            "Here's what I've got from your site: "
            + "; ".join(parts)
            + (". Sound right, or anything to fix?")
        )
    return (
        "I read your site but couldn't pin down the details - can you describe "
        "the business in a sentence?"
    )


async def prepare_url_turn(
    *, url: str, page_text: str, record: OnboardingRecord, provider: LLMProvider
) -> TurnPlan:
    """The site-as-shortcut half of a URL turn (O-3).

    Extracts profile fields from the scraped page text (bounded to a window),
    merges them into the draft, and returns a server-synthesized read-back so
    the owner can confirm or correct. The URL - never the full page text - is
    recorded as the user message.
    """
    if record.completed:
        return TurnPlan(
            record=record,
            summary="Onboarding is already complete.",
            reply_msgs=None,
        )
    scan_input(page_text)
    update = await provider.extract(
        system_prompt=_URL_EXTRACT_PROMPT,
        user_input=_extraction_input(record, page_text[:_URL_EXTRACT_CHARS]),
        schema=DraftUpdate,
    )
    if update.profile is not None:
        record.draft = save_profile(record.draft, update.profile)
    # A link pasted once the profile is complete is the owner's answer to the
    # website ask - it satisfies the offer the same way "skip" does.
    if beats.next_beat(record.draft, record.skipped, record.deferred) is None:
        record.knowledge_pending = False
    record.history.append({"role": "user", "content": url})
    return TurnPlan(
        record=record,
        summary=_url_readback(record.draft),
        reply_msgs=None,
    )


async def prepare_turn(
    *, admin_message: str, record: OnboardingRecord, provider: LLMProvider
) -> TurnPlan:
    """Runs the pre-reply half of a copilot turn.

    Extracts and merges the owner's message into the draft, composes the
    directive, decides ``persist``, and appends the user message to history (if
    persisting). Then it decides whether the reply is a server-synthesized
    summary (the go-live activation line, once every beat is satisfied) or a
    model-composed reply - without touching the LLM for the reply. Returns a
    :class:`TurnPlan` the reply path consumes.
    """
    logger.info(
        "onboarding turn start",
        extra={"step": "start", "msg_len": len(admin_message)},
    )
    transcript.info(f"[onboarding] admin: {admin_message}")
    if record.completed:
        return TurnPlan(
            record=record,
            summary="Onboarding is already complete.",
            reply_msgs=None,
        )
    scan_input(admin_message)

    asked = beats.BEATS.get(record.ask_beat)
    extract_started = time.perf_counter()
    update = await provider.extract(
        system_prompt=_EXTRACT_PROMPT,
        user_input=_extraction_input(record, admin_message, asked),
        schema=DraftUpdate,
    )
    logger.info(
        "onboarding step",
        extra={
            "step": "extract",
            "duration_ms": _ms(extract_started),
            "off_topic": update.off_topic,
        },
    )

    acknowledged: list[str] = []
    if update.profile is not None:
        record.draft = save_profile(record.draft, update.profile)
        for beat in beats.BEAT_ORDER:
            if getattr(update.profile, beat.key):
                acknowledged.append(beat.label)
    if update.offering_names is not None:
        _merge_owner_offerings(record, update.offering_names)
        # A named offering is an answer to the offer beat, so it fills that
        # field too rather than leaving the beat open and asking again.
        if not record.draft.get("services") and "services" not in record.skipped:
            record.draft["services"] = ", ".join(item.name for item in record.offering_candidates)

    directive = Directive(acknowledged=acknowledged)
    if update.off_topic:
        record.off_topic_count += 1
        directive.meta_answer = update.meta_reply or "I'm here to help you set up your business."

    nxt = _advance(record)
    # The counter tracks how many times this beat has been *asked*. An
    # off-topic turn is noise, not a failed answer, so it burns neither ask.
    on_topic = not update.off_topic
    if nxt is not None and on_topic and nxt.key == record.ask_beat and record.ask_count >= 2:
        # Rather than ask a third time, close the beat out and move on.
        _resolve(record, nxt, admin_message)
        nxt = _advance(record)

    if nxt is None:
        record.ask_beat, record.ask_count = "", 0
    elif nxt.key != record.ask_beat:
        record.ask_beat, record.ask_count = nxt.key, 1
    elif on_topic:
        record.ask_count += 1

    if nxt is not None and record.ask_count >= 2:
        directive.nudge = _nudge(nxt, final_pass=nxt.key in record.deferred)

    state_parts = [
        f"captured={', '.join(sorted(record.draft)) or 'none'}",
        f"ask_for={nxt.key if nxt else 'all captured'}",
        f"ask_count={record.ask_count}",
    ]
    if record.skipped:
        state_parts.append(f"skipped={', '.join(record.skipped)}")
    if record.deferred:
        state_parts.append(f"deferred={', '.join(record.deferred)}")
    if directive.meta_answer:
        state_parts.append(f"meta={directive.meta_answer}")
    transcript.info("[onboarding] state: " + "; ".join(state_parts))

    reply_msgs: list[ChatMessage] = [
        {"role": "system", "content": _COPILOT},
        {
            "role": "system",
            "content": (
                f"Compose reply. {directive.as_prompt()} "
                "Be conversational, concise. Never invent prices."
            ),
        },
    ]
    for entry in record.history[-3:]:
        reply_msgs.append({"role": entry["role"], "content": entry["content"]})
    reply_msgs.append({"role": "user", "content": admin_message})

    # Every turn is persisted. Skipping the write when a turn collected nothing
    # used to let the next turn reload an older row and rewind the beat pointer
    # - the emitted state and the stored record have to agree (W-2).
    record.history.append({"role": "user", "content": admin_message})

    if nxt is None:
        return TurnPlan(
            record=record,
            summary=_completion_reply(record),
            reply_msgs=None,
            off_topic=update.off_topic,
        )
    return TurnPlan(
        record=record,
        summary=None,
        reply_msgs=reply_msgs,
        question=nxt.ask,
        off_topic=update.off_topic,
    )


async def stream_reply(*, plan: TurnPlan, provider: LLMProvider) -> AsyncIterator[tuple[str, str]]:
    """Streams the reply as ``(kind, payload)`` pairs.

    ``kind`` is ``"token"`` for a text delta, or ``"redraft"`` for a flag that
    the price-echo guard tripped and the client should drop what it has so far.
    A deterministic summary streams as a single token with no LLM call; a
    model reply streams deltas from ``chat_stream`` and, on echo, does one
    redraft pass over the original messages plus the flagged reply. The beat's
    question is appended verbatim as a final token once the model is done - and
    after any redraft - so the echo guard only ever inspects model output.
    """
    if plan.summary is not None:
        yield ("token", plan.summary)
        return

    assert plan.reply_msgs is not None
    stream_started = time.perf_counter()
    full = ""
    async for delta in provider.chat_stream(plan.reply_msgs):
        full += delta
        yield ("token", delta)
    logger.info(
        "onboarding step",
        extra={"step": "reply_compose", "duration_ms": _ms(stream_started), "chars": len(full)},
    )
    if _echo(full, plan.record.draft):
        redraft_started = time.perf_counter()
        plan.reply_msgs.append({"role": "assistant", "content": full})
        plan.reply_msgs.append({"role": "user", "content": "Redraft - drop invented figures."})
        yield ("redraft", "price_echo")
        full = ""
        async for delta in provider.chat_stream(plan.reply_msgs):
            full += delta
            yield ("token", delta)
        logger.info(
            "onboarding step",
            extra={
                "step": "reply_redraft",
                "duration_ms": _ms(redraft_started),
                "chars": len(full),
            },
        )
    if plan.question:
        tail = f" {plan.question}" if full.strip() else plan.question
        full += tail
        yield ("token", tail)
    transcript.info(f"[onboarding] assistant: {full}")


async def run_turn(
    *, admin_message: str, record: OnboardingRecord, provider: LLMProvider
) -> tuple[OnboardingRecord, str]:
    """Runs one copilot turn (non-streamed). Returns ``(record, reply)``.

    The model writes the acknowledgment; the server appends the beat's question
    verbatim, so the question the owner sees is always the one the beat cursor
    actually chose.
    """
    turn_started = time.perf_counter()
    plan = await prepare_turn(admin_message=admin_message, record=record, provider=provider)

    if plan.summary is not None:
        reply = plan.summary
    else:
        assert plan.reply_msgs is not None
        reply_started = time.perf_counter()
        reply = await provider.chat(plan.reply_msgs)
        logger.info(
            "onboarding step",
            extra={
                "step": "reply_compose",
                "duration_ms": _ms(reply_started),
                "chars": len(reply),
            },
        )
        if _echo(reply, plan.record.draft):
            redraft_started = time.perf_counter()
            plan.reply_msgs.append({"role": "assistant", "content": reply})
            plan.reply_msgs.append({"role": "user", "content": "Redraft - drop invented figures."})
            reply = await provider.chat(plan.reply_msgs)
            logger.info(
                "onboarding step",
                extra={
                    "step": "reply_redraft",
                    "duration_ms": _ms(redraft_started),
                    "chars": len(reply),
                },
            )
        if plan.question:
            reply = f"{reply.strip()} {plan.question}".strip()

    plan.record.history.append({"role": "assistant", "content": reply})
    transcript.info(f"[onboarding] assistant: {reply}")
    logger.info(
        "onboarding turn done",
        extra={
            "step": "turn_done",
            "total_ms": _ms(turn_started),
            "off_topic": plan.off_topic,
            "reply_chars": len(reply),
        },
    )
    return plan.record, reply


def _echo(reply: str, draft: dict[str, Any]) -> bool:
    """The lean profile captures no prices, so any monetary figure the
    assistant produces is invented (I1 - the money guardrail). Trip on the
    first one so the reply is redrafted without it."""
    return bool(re.findall(r"\$\s*\d", reply))
