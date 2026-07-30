"""T-042: agentic onboarding copilot turn loop."""
from __future__ import annotations
import json, re
from dataclasses import dataclass, field
from typing import Any
from app.llm.provider import ChatMessage, LLMProvider
from app.onboarding.flow import _REQUIRED_SECTIONS
from app.onboarding.tools import ONBOARDING_TOOLS, TOOL_HANDLERS
from app.pricing.validation_gate import extract_monetary_figures

MAX_TOOL_CALLS = 4
MAX_HISTORY = 20

_SYS = "You are an onboarding copilot helping a business owner. Have a friendly conversation while collecting information.\n\nTools: save_identity, save_tone, save_services, save_pricing_rules, save_escalation.\n\nAsk one question at a time. Capture volunteered info early. When all five sections are captured, tell the admin they can confirm.\nNever invent services, prices, or details not mentioned."

@dataclass
class TurnDirective:
    acknowledged: list[str] = field(default_factory=list)
    answer_meta: str | None = None
    ask_for: str | None = None
    warn: str | None = None
    redirect_firmness: int = 0
    def to_system_prompt_append(self):
        lines = []
        if self.acknowledged: lines.append("Acknowledged: " + ", ".join(self.acknowledged))
        if self.answer_meta == "off_topic":
            if self.redirect_firmness >= 2: lines.append("Decline and redirect ONLY to onboarding.")
            elif self.redirect_firmness == 1: lines.append("Brief answer, firmly redirect.")
            else: lines.append("Briefly acknowledge, gently redirect.")
        if self.ask_for: lines.append("Ask about: " + self.ask_for)
        if self.warn: lines.append("Warning: " + self.warn)
        return "\n".join(lines)

def _addendum(draft):
    caps = [k for k in ("identity","tone","services","pricing_rules","escalation_threshold") if k in draft]
    if caps: return "\n\nAlready captured: " + ", ".join(caps) + ". Do not re-ask."
    return ""

def _is_off_topic(msg):
    for p in (r"what('?s| is) your name", r"who (are|made) you", r"^(hi|hello|hey)\b", r"^(thanks|thank you)", r"tell me (a )?(joke|story)"):
        if re.search(p, msg.lower().strip()): return True
    return False

def _price_echo_violations(reply, draft):
    allowed = set()
    for k in ("services","pricing_rules"):
        s = draft.get(k)
        if not s: continue
        items = s.get("items") or s.get("rules") or []
        for item in items:
            d = item.get("price_dollars") or item.get("unit_amount_dollars")
            if d is not None and isinstance(d, (int, float)): allowed.add(round(float(d)*100))
    return ["'" + f.raw + "' not admin-stated" for f in extract_monetary_figures(reply) if f.cents not in allowed]

def _missing(d): return [s for s in _REQUIRED_SECTIONS if s not in d]

def _next_q(missing):
    qs = {"identity":"what the business does","tone":"how assistant should sound","services":"what services they offer","pricing_rules":"any pricing rules","escalation_threshold":"when to hand off"}
    for s in missing:
        if s in qs: return qs[s]
    return None

@dataclass
class OnboardingTurnResult:
    assistant_text: str
    updated_draft: dict[str, Any]
    tools_called: list[str]
    off_topic_count: int

async def run_onboarding_turn(*, provider, history, draft, user_message, off_topic_count, turn_count):
    is_ot = _is_off_topic(user_message)
    ot_count = off_topic_count + 1 if is_ot else 0
    rf = min(ot_count, 2)

    msgs = [{"role":"system","content":_SYS + _addendum(draft)}]
    for e in history[-MAX_HISTORY:]:
        m = {"role":e["role"],"content":e.get("content","")}
        if e.get("tool_calls"): m["tool_calls"] = e["tool_calls"]  # type: ignore[typeddict-item]
        if e.get("tool_call_id"): m["tool_call_id"] = e["tool_call_id"]  # type: ignore[typeddict-item]
        msgs.append(m)
    msgs.append({"role":"user","content":user_message})

    tools_called = []
    ud = dict(draft)
    for _ in range(MAX_TOOL_CALLS):
        turn = await provider.chat_with_tools(messages=msgs, tools=ONBOARDING_TOOLS, tool_choice="auto")
        if not turn.tool_calls: break
        for tc in turn.tool_calls:
            handler = TOOL_HANDLERS.get(tc.name)
            if handler is None: continue
            handler(ud, tc.args)
            tools_called.append(tc.name)
            msgs.append({"role":"assistant","content":turn.text or "","tool_calls":[{"id":tc.id,"type":"function","function":{"name":tc.name,"arguments":json.dumps(tc.args)}}]})
            msgs.append({"role":"tool","content":json.dumps({"ok":True,"tool":tc.name}),"tool_call_id":tc.id})

    directive = TurnDirective(acknowledged=list(tools_called), redirect_firmness=rf)
    if is_ot: directive.answer_meta = "off_topic"
    missing = _missing(ud)
    if missing:
        q = _next_q(missing)
        if q: directive.ask_for = q

    compose = _SYS + _addendum(ud) + "\n\n" + directive.to_system_prompt_append()
    reply = await provider.chat([{"role":"system","content":compose},{"role":"user","content":user_message}])

    vios = _price_echo_violations(reply, ud)
    if vios:
        reply = await provider.chat([{"role":"system","content":compose},{"role":"user","content":user_message},{"role":"assistant","content":reply},{"role":"user","content":"Drop invented figures. Rewrite."}])

    return OnboardingTurnResult(assistant_text=reply, updated_draft=ud, tools_called=tools_called, off_topic_count=ot_count)
