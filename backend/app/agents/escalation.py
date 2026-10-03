"""T-020/C-5: the Escalation Agent - a recorded handoff, not a dead end.

Creates the escalations row and drafts the handoff message. Reason comes
from ``state.get("escalation_reason")``, set upstream by whichever path
routed here (the agent's ``create_escalation`` tool; price_gate.py's
second-violation escalation; inspection's second failure) - this node never
guesses why it's running, it only records what it's told.

**C-5: this no longer flips ``conversations.status``.** It used to, which
made every handoff terminal: the next customer message got a bare
``escalated`` event with no agent turn, and the composer locked. One
unanswerable pricing question could therefore end an entire support session
that was working fine for everything else. An escalation is a notification -
"a human should look at this" - not a statement about who is replying. The
conversation stays open, the next message gets a full agent turn, and the
owner's reply reaches a live chat instead of a closed one.

Limit escalations (T-028: budget, step cap, turn budget, provider error)
still flip the status and stay terminal. Those are a hard stop by design -
see ``service.record_limit_escalation``.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from langgraph.config import get_stream_writer
from langgraph.runtime import get_runtime

from app.agents.intent import as_intent
from app.agents.state import AgentState, GraphContext
from app.shared import db

# Names what is being handed off and keeps the door open. Deliberately not a
# sign-off: "someone will get back to you" reads as the end of a conversation,
# and after C-5 the conversation is not over.
HANDOFF_MESSAGE = "I’ve forwarded your query to the business. They can reply to you here."


def contact_ask(*, name_known: bool, email_known: bool) -> str:
    """The one-time ask for escalation contact details.

    One ask covers name and email together; a name-only answer is always
    accepted. The email is what lets the business follow up on an order,
    quote, or booking, so a name-only reply to one of those gets one more
    ask - that is the caller's job, not this helper's.
    """
    if name_known and email_known:
        return ""
    if name_known:
        return "Can I get your email so the business can follow up?"
    if email_known:
        return "Can I get your name so the business can follow up?"
    return "Can I get your name and email so the business can follow up?"


def handoff_message(*, name_known: bool, email_known: bool) -> str:
    """The handoff text, plus a contact ask only when something is missing."""
    ask = contact_ask(name_known=name_known, email_known=email_known)
    return f"{HANDOFF_MESSAGE} {ask}" if ask else HANDOFF_MESSAGE


def normalize_email(value: str | None) -> str | None:
    """Store what the customer said, or nothing - never a half-parsed address.

    Deliberately lenient (one '@', non-empty sides, no whitespace, <= 254
    chars): the tool asks again when this returns None, so a false negative
    costs one question, while a false positive would store garbage the owner
    cannot use.
    """
    if value is None:
        return None
    trimmed = value.strip()
    parts = trimmed.split("@")
    if len(parts) != 2 or not parts[0] or not parts[1]:
        return None
    if any(ch.isspace() for ch in trimmed) or len(trimmed) > 254:
        return None
    return trimmed


_DEFAULT_REASON = "unspecified"

# RF-11: the reason recorded when the customer asks for a person from the
# visible control. Named here, not only in the endpoint, because the
# deterministic endpoint and the assistant tool must describe the same handoff.
HUMAN_REQUESTED_REASON = "human_requested"


async def record_escalation(
    *,
    conn: db.AppConnection,
    tenant_id: UUID,
    conversation_id: UUID,
    reason: str,
    intent: str | None = None,
    summary: str | None = None,
) -> bool:
    """The one escalation-row writer, shared by every handoff path.

    The assistant's ``create_escalation`` tool, this module's escalation node,
    and RF-11's customer-initiated endpoint all insert through here, so the
    dedupe semantics cannot drift between them. 0011_escalations_dedupe.sql's
    partial unique index makes the insert a no-op whenever a still-open
    escalation already exists on this conversation - the "already open" case
    that keeps the owner's queue at one item per conversation while the chat
    continues and may hand off again. Returns False in that case, and the
    caller must not hand off a second time. ``intent`` is coerced through
    ``as_intent`` (unknown/None -> NULL), never trusted.
    """
    created = await conn.fetchval(
        "insert into escalations (tenant_id, conversation_id, reason, summary, intent) "
        "values ($1, $2, $3, $4, $5) "
        "on conflict (tenant_id, conversation_id) where status = 'open' do nothing "
        "returning id",
        tenant_id,
        conversation_id,
        reason,
        summary or None,
        as_intent(intent),
    )
    return created is not None


async def run(state: AgentState) -> dict[str, Any]:
    runtime = get_runtime(GraphContext)
    ctx = runtime.context
    writer = get_stream_writer()

    reason = state.get("escalation_reason") or _DEFAULT_REASON
    conversation_id = UUID(state["conversation_id"])

    async with db.tenant_context(ctx.tenant_id, "customer") as conn:
        # A concurrent turn on the same conversation may already have recorded
        # this handoff; the shared writer dedupes it against the partial unique
        # index and the owner sees one open item, not one per attempt.
        await record_escalation(
            conn=conn,
            tenant_id=ctx.tenant_id,
            conversation_id=conversation_id,
            reason=reason,
            intent=state.get("intent"),
        )
    # A producing node upstream (price_gate on its second violation) may have
    # already streamed and set a handoff message - don't stream a second one.
    if state["draft_response"]:
        writer({"type": "handoff"})
        return {"escalated": True}

    message = handoff_message(
        name_known=state.get("customer_name_known", False),
        email_known=state.get("customer_email_known", False),
    )
    writer({"type": "refusal", "text": message})
    writer({"type": "handoff"})
    return {"escalated": True, "draft_response": message, "author_node": "escalation"}
