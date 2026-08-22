"""T-042: agentic onboarding copilot turn loop.

Two model calls per turn: one structured ``extract()`` to pull anything the
owner stated into the draft, then ``chat()`` to compose a conversational reply
from a server-computed directive. Structured extraction (rather than tool
calls) keeps capture robust on free/edge models that answer in prose; the
server's completeness gate stays authoritative.

Guardrails: scan_input, price echo check, bounded history. Off-topic/meta
questions are answered in one line then gently redirected - no escalating
firmness. Off-topic turns that collect nothing are not persisted (``persist``
flag), so greeting noise never lands in the stored history.
State: {version: 2, draft, history, off_topic_count, completed} in jsonb.
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
from app.llm.provider import ChatMessage, LLMProvider
from app.observability.logging import TRANSCRIPT_LOGGER_NAME
from app.onboarding import beats
from app.onboarding.flow import DraftUpdate
from app.onboarding.tools import save_profile

logger = logging.getLogger("app.onboarding.agent")
transcript = logging.getLogger(TRANSCRIPT_LOGGER_NAME)

_MAX_HIST = 20


def _ms(started: float) -> float:
    return round((time.perf_counter() - started) * 1000, 1)


@dataclass
class Directive:
    acknowledged: list[str] = field(default_factory=list)
    meta_answer: str = ""
    ask_for: str = ""

    def as_prompt(self) -> str:
        parts: list[str] = []
        if self.acknowledged:
            parts.append(f"Just captured: {', '.join(self.acknowledged)}.")
        if self.meta_answer:
            parts.append(f"Briefly answer: {self.meta_answer}")
        parts.append(f"Ask for: {self.ask_for}" if self.ask_for else "All info captured.")
        return " ".join(parts)


_COPILOT = (
    "You are an onboarding assistant. Help a small-business owner describe "
    "their name, business name, business type, team size, opening hours, what "
    "they sell, how customers reach them, and their ABN and GST registration. "
    "Be friendly and concise. Answer meta questions in one line, then gently "
    "return to onboarding."
)

# C-3: a figure the extractor rounds into the profile becomes a figure the
# customer-facing money gate will bless forever - the profile is one of its
# three allowed sources (C-1). So the copy-it-exactly rule belongs here too,
# not only on the customer side.
_EXTRACT_PROMPT = (
    "You are extracting business information from a small-business owner who is "
    "onboarding their assistant. Read the conversation and update the profile "
    "with anything new the owner stated: name, business_name, business_type, "
    "headcount, hours, services, contact, abn, gst. Fill only what the owner "
    "actually said - never invent a value. Copy any price or other amount "
    "exactly as the owner wrote it: never round it, convert it, tidy it up, or "
    "work one out. Two fields have a fixed vocabulary: set abn to the digits "
    'the owner gave, or to "none" if they said they do not have one yet; set '
    'gst to "yes" or "no". '
    "If the message is off-topic (a question about "
    "you, a greeting, or unrelated chat), set off_topic=true and put a one-line "
    "answer in meta_reply. Otherwise set off_topic=false and set next_question "
    "to the single most important question to ask next, given what is still "
    "missing. Leave the profile null when nothing new was stated."
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
            )
        return cls(
            version=3,
            draft={},
            history=[],
            off_topic_count=0,
            completed=raw.get("completed", False),
        )

    def to_jsonb(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "draft": self.draft,
            "history": self.history[-_MAX_HIST:],
            "off_topic_count": self.off_topic_count,
            "completed": self.completed,
            "knowledge_pending": self.knowledge_pending,
        }


@dataclass
class TurnPlan:
    """Everything ``prepare_turn`` computed, ready for either the streamed or
    non-streamed reply path.

    ``summary`` is set when the turn completes the profile - the
    reply is server-synthesized from the draft and never touches the model.
    ``reply_msgs`` is set otherwise and is what the reply path feeds the LLM.
    ``off_topic`` mirrors the extraction verdict for logging.
    """

    record: OnboardingRecord
    persist: bool
    summary: str | None
    reply_msgs: list[ChatMessage] | None
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
    'Paste a link, attach a file, or say "skip", and you can add more any '
    "time from Settings."
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


def progress(record: OnboardingRecord) -> tuple[str, beats.InputSpec | None, bool]:
    """The interview's (stage, composer widget, can-confirm) triple.

    The single source both ``_state_event`` and ``response_from_record`` read,
    so the SSE state and the REST state never disagree. A completed profile
    passes through the optional ``knowledge`` stage before ``confirm``.
    """
    nxt = beats.next_beat(record.draft)
    if nxt is not None:
        return nxt.key, beats.input_spec(nxt), False
    if record.knowledge_pending:
        return "knowledge", beats.KNOWLEDGE_INPUT, False
    return "confirm", None, not record.completed


def _extraction_input(record: OnboardingRecord, admin_message: str) -> str:
    lines: list[str] = []
    if record.draft:
        lines.append("Current draft (already captured):")
        lines.append(json.dumps(record.draft))
    for entry in record.history[-_MAX_HIST:]:
        lines.append(f"{entry['role']}: {entry['content']}")
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
            persist=False,
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
    if beats.next_beat(record.draft) is None:
        record.knowledge_pending = False
    record.history.append({"role": "user", "content": url})
    return TurnPlan(
        record=record,
        persist=True,
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
            persist=False,
            summary="Onboarding is already complete.",
            reply_msgs=None,
        )
    scan_input(admin_message)

    extract_started = time.perf_counter()
    update = await provider.extract(
        system_prompt=_EXTRACT_PROMPT,
        user_input=_extraction_input(record, admin_message),
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

    nxt = beats.next_beat(record.draft)
    ask_for = nxt.ask if nxt else ""
    persist = bool(acknowledged) or not update.off_topic
    directive = Directive(acknowledged=acknowledged)
    if update.off_topic:
        if persist:
            record.off_topic_count += 1
        directive.meta_answer = update.meta_reply or "I'm here to help you set up your business."
        directive.ask_for = update.next_question or ask_for
    else:
        directive.ask_for = update.next_question or ask_for

    state_parts = [
        f"captured={', '.join(sorted(record.draft)) or 'none'}",
        f"ask_for={directive.ask_for or 'all captured'}",
    ]
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

    if persist:
        record.history.append({"role": "user", "content": admin_message})

    if nxt is None:
        return TurnPlan(
            record=record,
            persist=persist,
            summary=_completion_reply(record),
            reply_msgs=None,
            off_topic=update.off_topic,
        )
    return TurnPlan(
        record=record,
        persist=persist,
        summary=None,
        reply_msgs=reply_msgs,
        off_topic=update.off_topic,
    )


async def stream_reply(*, plan: TurnPlan, provider: LLMProvider) -> AsyncIterator[tuple[str, str]]:
    """Streams the reply as ``(kind, payload)`` pairs.

    ``kind`` is ``"token"`` for a text delta, or ``"redraft"`` for a flag that
    the price-echo guard tripped and the client should drop what it has so far.
    A deterministic summary streams as a single token with no LLM call; a
    model reply streams deltas from ``chat_stream`` and, on echo, does one
    redraft pass over the original messages plus the flagged reply.
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
    transcript.info(f"[onboarding] assistant: {full}")


async def run_turn(
    *, admin_message: str, record: OnboardingRecord, provider: LLMProvider
) -> tuple[OnboardingRecord, str, bool]:
    """Runs one copilot turn (non-streamed). Returns ``(record, reply, persist)``.

    ``persist`` is False when the turn is off-topic and collected nothing, so
    the caller can skip writing it: greeting/noise turns stay ephemeral and the
    conversation effectively restarts clean on the next visit.
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

    if plan.persist:
        plan.record.history.append({"role": "assistant", "content": reply})
    transcript.info(f"[onboarding] assistant: {reply}")
    logger.info(
        "onboarding turn done",
        extra={
            "step": "turn_done",
            "total_ms": _ms(turn_started),
            "off_topic": plan.off_topic,
            "persist": plan.persist,
            "reply_chars": len(reply),
        },
    )
    return plan.record, reply, plan.persist


def _echo(reply: str, draft: dict[str, Any]) -> bool:
    """The lean profile captures no prices, so any monetary figure the
    assistant produces is invented (I1 - the money guardrail). Trip on the
    first one so the reply is redrafted without it."""
    return bool(re.findall(r"\$\s*\d", reply))
