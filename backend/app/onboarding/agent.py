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
from app.onboarding.tools import (
    save_business,
    save_escalation,
    save_identity,
    save_pricing_rules,
    save_services,
    save_tone,
)

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
    "You are Wren, an onboarding copilot. Help a small-business owner describe "
    "their business, tone, services (with prices), pricing rules, and escalation "
    "posture. Be friendly and concise. Answer meta questions in one line, then "
    "gently return to onboarding. Never invent prices."
)

_EXTRACT_PROMPT = (
    "You are extracting business information from a small-business owner who is "
    "onboarding their AI assistant. Read the conversation and update the draft "
    "with anything new the owner stated. Fill only what the owner actually said - "
    "never invent a value, and never invent a price; record prices only as the "
    "dollar figures the owner literally gave. If the message is off-topic (a "
    "question about you, a greeting, or unrelated chat), set off_topic=true and "
    "put a one-line answer in meta_reply. Otherwise set off_topic=false and set "
    "next_question to the single most important question to ask next, given what "
    "is still missing. Leave a section null when nothing new was stated."
)


@dataclass
class OnboardingRecord:
    version: int = 2
    draft: dict[str, Any] = field(default_factory=dict)
    history: list[dict[str, str]] = field(default_factory=list)
    off_topic_count: int = 0
    completed: bool = False

    @classmethod
    def from_jsonb(cls, raw: dict[str, Any]) -> OnboardingRecord:
        if raw.get("version") == 2:
            return cls(
                version=2,
                draft=raw.get("draft", {}),
                history=raw.get("history", []),
                off_topic_count=raw.get("off_topic_count", 0),
                completed=raw.get("completed", False),
            )
        legacy_state = raw.get("state", {}) or {}
        legacy_draft = legacy_state.get("draft", {}) if isinstance(legacy_state, dict) else {}
        return cls(
            version=2,
            draft=legacy_draft,
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

    ``summary`` is set when the turn lands on readback or completion - the
    reply is server-synthesized from the draft and never touches the model.
    ``reply_msgs`` is set otherwise and is what the reply path feeds the LLM.
    ``off_topic`` mirrors the extraction verdict for logging.
    """

    record: OnboardingRecord
    persist: bool
    summary: str | None
    reply_msgs: list[ChatMessage] | None
    off_topic: bool = False


def _fmt_dollars(dollars: float) -> str:
    return f"{dollars:g}"


def _readback_summary(draft: dict[str, Any]) -> str:
    business = draft.get("business") or {}
    identity = draft.get("identity") or {}
    services = draft.get("services") or {}
    tone = draft.get("tone") or {}
    lines: list[str] = []
    if business.get("name"):
        lines.append(f"Your business: {business['name']}")
    if identity.get("description"):
        lines.append(f"What you do: {identity['description']}")
    is_team = business.get("is_team")
    if is_team is not None:
        lines.append("You're a team" if is_team else "It's just you")
    items = services.get("items") or []
    priced = [i for i in items if i.get("price_dollars") is not None]
    if priced:
        lines.append(
            "Services: "
            + ", ".join(f"{i['name']} at ${_fmt_dollars(i['price_dollars'])}" for i in priced)
        )
    if tone.get("tone"):
        lines.append(f"Tone: {tone['tone']}")
    lines.append("Does everything look right?")
    return "\n".join(lines)


def _activation_summary(draft: dict[str, Any]) -> str:
    business = draft.get("business") or {}
    name = business.get("name")
    if name:
        intro = f"Your agent for {name} is ready to go live."
    else:
        intro = "Your agent is ready to go live."
    return f"{intro} Hit confirm to publish it."


def _assistant_reply_for(draft: dict[str, Any]) -> str:
    nxt = beats.next_beat(draft)
    if nxt is None:
        return _activation_summary(draft)
    if nxt.key == "readback":
        return _readback_summary(draft)
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


async def prepare_turn(
    *, admin_message: str, record: OnboardingRecord, provider: LLMProvider
) -> TurnPlan:
    """Runs the pre-reply half of a copilot turn.

    Extracts and merges the owner's message into the draft, composes the
    directive, decides ``persist``, and appends the user message to history (if
    persisting). Then it decides whether the reply is a server-synthesized
    summary (readback/completion) or a model-composed reply - without touching
    the LLM for the reply. Returns a :class:`TurnPlan` the reply path consumes.
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
    if update.business is not None:
        record.draft = save_business(record.draft, update.business)
        acknowledged.append("business details")
    if update.identity is not None:
        record.draft = save_identity(record.draft, update.identity)
        acknowledged.append("business description")
    if update.tone is not None:
        record.draft = save_tone(record.draft, update.tone)
        acknowledged.append("assistant tone")
    if update.services is not None:
        record.draft = save_services(record.draft, update.services)
        acknowledged.append("services")
    if update.pricing_rules is not None:
        record.draft = save_pricing_rules(record.draft, update.pricing_rules)
        acknowledged.append("pricing rules")
    if update.escalation is not None:
        record.draft = save_escalation(record.draft, update.escalation)
        acknowledged.append("escalation posture")

    nxt = beats.next_beat(record.draft)
    ask_for = nxt.ask if nxt else ""
    persist = bool(acknowledged) or not update.off_topic
    directive = Directive(acknowledged=acknowledged)
    if update.off_topic:
        if persist:
            record.off_topic_count += 1
        directive.meta_answer = update.meta_reply or "I'm Wren, your onboarding copilot."
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

    if nxt is None or nxt.key == "readback":
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
    figures = re.findall(r"\$\s*(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d{1,2}))?", reply)
    if not figures:
        return False
    known: set[int] = set()
    for item in draft.get("services", {}).get("items", []):
        if isinstance(item, dict) and item.get("price_dollars") is not None:
            known.add(round(item["price_dollars"] * 100))
    for rule in draft.get("pricing_rules", {}).get("rules", []):
        if isinstance(rule, dict) and rule.get("unit_amount_dollars") is not None:
            known.add(round(rule["unit_amount_dollars"] * 100))
    for whole, frac in figures:
        cents = int(whole.replace(",", "")) * 100
        if frac:
            cents += int(frac.ljust(2, "0"))
        if cents not in known and cents != 0:
            return True
    return False
