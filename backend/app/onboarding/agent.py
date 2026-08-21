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
    "they sell, and how customers reach them. Be friendly and concise. Answer "
    "meta questions in one line, then gently return to onboarding."
)

_EXTRACT_PROMPT = (
    "You are extracting business information from a small-business owner who is "
    "onboarding their assistant. Read the conversation and update the profile "
    "with anything new the owner stated: name, business_name, business_type, "
    "headcount, hours, services, contact. Fill only what the owner actually "
    "said - never invent a value. If the message is off-topic (a question about "
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


def _assistant_reply_for(draft: dict[str, Any]) -> str:
    nxt = beats.next_beat(draft)
    if nxt is None:
        return _activation_summary(draft)
    return f"Got it. {nxt.ask}"


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
    "leave a field empty when the page does not mention it. Set off_topic=false."
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
            summary=_assistant_reply_for(record.draft),
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
