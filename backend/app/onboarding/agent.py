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
from dataclasses import dataclass, field
from typing import Any

from app.agents.spotlight import scan_input
from app.llm.provider import ChatMessage, LLMProvider
from app.observability.logging import TRANSCRIPT_LOGGER_NAME
from app.onboarding.flow import DraftUpdate
from app.onboarding.tools import (
    _check_completeness,
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
    "You are Agencx, an onboarding copilot. Help a small-business owner describe "
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


def _extraction_input(record: OnboardingRecord, admin_message: str) -> str:
    lines: list[str] = []
    if record.draft:
        lines.append("Current draft (already captured):")
        lines.append(json.dumps(record.draft))
    for entry in record.history[-_MAX_HIST:]:
        lines.append(f"{entry['role']}: {entry['content']}")
    lines.append(f"user: {admin_message}")
    return "\n".join(lines)


async def run_turn(
    *, admin_message: str, record: OnboardingRecord, provider: LLMProvider
) -> tuple[OnboardingRecord, str, bool]:
    """Runs one copilot turn. Returns ``(record, reply, persist)``.

    ``persist`` is False when the turn is off-topic and collected nothing, so
    the caller can skip writing it: greeting/noise turns stay ephemeral and the
    conversation effectively restarts clean on the next visit.
    """
    turn_started = time.perf_counter()
    logger.info(
        "onboarding turn start",
        extra={"step": "start", "msg_len": len(admin_message)},
    )
    transcript.info(f"[onboarding] admin: {admin_message}")
    if record.completed:
        return record, "Onboarding is already complete.", False
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

    missing = _check_completeness(record.draft)
    persist = bool(acknowledged) or not update.off_topic
    directive = Directive(acknowledged=acknowledged)
    if update.off_topic:
        if persist:
            record.off_topic_count += 1
        directive.meta_answer = update.meta_reply or "I'm Agencx, your onboarding copilot."
        directive.ask_for = update.next_question or (missing[0] if missing else "")
    else:
        directive.ask_for = update.next_question or (missing[0] if missing else "")

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

    reply_started = time.perf_counter()
    reply = await provider.chat(reply_msgs)
    logger.info(
        "onboarding step",
        extra={"step": "reply_compose", "duration_ms": _ms(reply_started), "chars": len(reply)},
    )
    if _echo(reply, record.draft):
        redraft_started = time.perf_counter()
        reply_msgs.append({"role": "assistant", "content": reply})
        reply_msgs.append({"role": "user", "content": "Redraft - drop invented figures."})
        reply = await provider.chat(reply_msgs)
        logger.info(
            "onboarding step",
            extra={
                "step": "reply_redraft",
                "duration_ms": _ms(redraft_started),
                "chars": len(reply),
            },
        )

    if persist:
        record.history.append({"role": "user", "content": admin_message})
        record.history.append({"role": "assistant", "content": reply})
        record.history = record.history[-_MAX_HIST * 2 :]
    transcript.info(f"[onboarding] assistant: {reply}")
    logger.info(
        "onboarding turn done",
        extra={
            "step": "turn_done",
            "total_ms": _ms(turn_started),
            "off_topic": bool(update.off_topic),
            "persist": persist,
            "reply_chars": len(reply),
        },
    )
    return record, reply, persist


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
