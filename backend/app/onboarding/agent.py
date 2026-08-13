"""T-042: agentic onboarding copilot turn loop.

Two model calls per turn: chat_with_tools for tool calls, then chat() to compose
a conversational reply from a server-computed directive.

Guardrails: scan_input, price echo check, redirection budget, bounded tool loop.
State: {version: 2, draft, history, off_topic_count, completed} in jsonb.
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel

from app.agents.spotlight import scan_input
from app.llm.provider import ChatMessage, LLMProvider, ToolSpec
from app.onboarding.tools import TOOL_REGISTRY, _check_completeness, request_finalize

logger = logging.getLogger("app.onboarding.agent")

_MAX_CALLS = 4
_MAX_HIST = 20


def _ms(started: float) -> float:
    return round((time.perf_counter() - started) * 1000, 1)


class _NoArgs(BaseModel):
    pass


@dataclass
class Directive:
    acknowledged: list[str] = field(default_factory=list)
    answer_meta: str | None = None
    ask_for: str = ""
    warn: str = ""
    redirect_firmness: int = 0

    def as_prompt(self) -> str:
        parts: list[str] = []
        if self.acknowledged:
            parts.append(f"Just captured: {', '.join(self.acknowledged)}.")
        if self.answer_meta:
            parts.append(f"Answer briefly: {self.answer_meta}")
        parts.append(f"Ask for: {self.ask_for}" if self.ask_for else "All info captured.")
        if self.warn:
            parts.append(f"Warning: {self.warn}")
        if self.redirect_firmness >= 2:
            parts.append("Decline and firmly redirect.")
        elif self.redirect_firmness == 1:
            parts.append("Keep short, redirect to onboarding.")
        return " ".join(parts)


_COPILOT = (
    "You are Agencx, an onboarding copilot. Collect identity, tone, services "
    "(with prices), pricing rules, and escalation posture. Call tools to record "
    "info. Be conversational. Redirect off-topic questions. Never invent prices."
)


def _build_specs() -> list[ToolSpec]:
    specs: list[ToolSpec] = []
    descs = {
        "save_identity": "Record business description.",
        "save_tone": "Record how the assistant should sound.",
        "save_services": "Record services/products with prices.",
        "save_pricing_rules": "Record specific pricing rules.",
        "save_escalation": "Record escalation posture.",
    }
    for name, (_, schema) in TOOL_REGISTRY.items():
        specs.append(ToolSpec(name=name, description=descs.get(name, ""), args_schema=schema))
    specs.append(
        ToolSpec(
            name="request_finalize",
            description="Request to finalize.",
            args_schema=_NoArgs,
        )
    )
    return specs


_TOOL_SPECS = _build_specs()


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


async def run_turn(
    *, admin_message: str, record: OnboardingRecord, provider: LLMProvider
) -> tuple[OnboardingRecord, str]:
    turn_started = time.perf_counter()
    logger.info(
        "onboarding turn start",
        extra={"step": "start", "msg_len": len(admin_message)},
    )
    if record.completed:
        return record, "Onboarding is already complete."
    scan_input(admin_message)

    messages: list[ChatMessage] = [{"role": "system", "content": _COPILOT}]
    for entry in record.history:
        messages.append({"role": entry["role"], "content": entry["content"]})
    messages.append({"role": "user", "content": admin_message})

    tools_started = time.perf_counter()
    turn = await provider.chat_with_tools(messages=messages, tools=_TOOL_SPECS, tool_choice="auto")
    logger.info(
        "onboarding step",
        extra={
            "step": "tools_model",
            "duration_ms": _ms(tools_started),
            "tool_calls": len(turn.tool_calls),
        },
    )
    calls = turn.tool_calls[:_MAX_CALLS]
    directive = Directive()

    for call in calls:
        call_started = time.perf_counter()
        ok = False
        if call.name == "request_finalize":
            result = request_finalize(record.draft)
            ok = True
            if not result.ok:
                directive.warn = f"Still missing: {'; '.join(result.missing)}."
        else:
            handler_info = TOOL_REGISTRY.get(call.name)
            if handler_info is not None:
                handler, schema = handler_info
                try:
                    parsed_args = schema.model_validate(call.args)
                except Exception:
                    pass
                else:
                    record.draft = handler(record.draft, parsed_args)
                    ok = True
        logger.info(
            "onboarding step",
            extra={"step": "tool", "name": call.name, "duration_ms": _ms(call_started), "ok": ok},
        )

    if not directive.warn:
        missing = _check_completeness(record.draft)
        directive.ask_for = missing[0] if missing else ""

    off = _off_topic(admin_message, not calls)
    if off:
        record.off_topic_count += 1
        directive.redirect_firmness = min(record.off_topic_count, 2)
    elif not calls and not directive.ask_for:
        directive.answer_meta = admin_message

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

    record.history.append({"role": "user", "content": admin_message})
    record.history.append({"role": "assistant", "content": reply})
    record.history = record.history[-_MAX_HIST * 2 :]
    logger.info(
        "onboarding turn done",
        extra={
            "step": "turn_done",
            "total_ms": _ms(turn_started),
            "tools_called": len(calls),
            "off_topic": bool(off),
            "reply_chars": len(reply),
        },
    )
    return record, reply


def _off_topic(msg: str, no_tools: bool) -> bool:
    if not no_tools:
        return False
    signals = [
        "business",
        "customer",
        "service",
        "product",
        "price",
        "cost",
        "pricing",
        "rule",
        "fee",
        "charge",
        "tone",
        "friendly",
        "formal",
        "professional",
        "escalat",
        "hand off",
        "human",
        "assistant",
        "phone",
        "repair",
        "shop",
        "offer",
        "help",
        "dental",
        "clinic",
    ]
    return not any(s in msg.lower() for s in signals)


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
