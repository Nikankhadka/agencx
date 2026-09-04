"""Async escalation summariser: fills ``escalations.summary`` after the turn.

Runs out-of-band from the customer's turn. T-028's 10s turn budget
(``DEFAULT_TURN_BUDGET_S``) has no room for an extra LLM call at the point an
escalation actually fires - late in the turn, when the least of the budget is
left - so a synchronous summariser would itself become a cause of
``turn_budget`` escalations. Scheduled by ``chat/controller.py`` once a turn's
graph path or limit-stop has written an escalation row.

The ``create_escalation`` tool (``agent_node.py``) already captures a
model-authored summary with the whole turn as context; ``generate`` only fills
a row that is still NULL - the price_gate/inspection/limit paths, which write
no summary at all today.
"""

from __future__ import annotations

import asyncio
import logging
from uuid import UUID

from pydantic import BaseModel, Field

from app.features.chat import service as chat_service
from app.llm.provider import LLMProvider
from app.shared import db

logger = logging.getLogger("app.agents.escalation_summary")

# Independent of the tenant's llm_timeout_s - this runs after the customer's
# response is already on the wire, so it answers to nothing but its own budget.
_TIMEOUT_S = 6.0
_HISTORY_MESSAGES = 6

# asyncio only holds a weak reference to a running task, so a fire-and-forget
# task can be garbage collected mid-flight; keeping it here until it is done
# is the documented way to stop that (mirrors
# features/tenants/controller.py's _preload_tasks).
_tasks: set[asyncio.Task[None]] = set()

_SYSTEM_PROMPT = (
    "A customer support conversation was handed off to the business owner "
    "because the assistant could not finish it. Write one or two plain "
    "sentences, addressed to the business owner, saying what the customer "
    "wants and why the assistant could not finish it. Never state or imply "
    "any price or monetary amount - pricing is decided by the business, not "
    "described here. Plain prose only: no lists, no markdown, no headings."
)


class _EscalationSummary(BaseModel):
    summary: str = Field(max_length=300)


async def _generate(*, tenant_id: UUID, conversation_id: UUID, provider: LLMProvider) -> None:
    async with db.tenant_context(tenant_id, "customer") as conn:
        # fetchrow, not fetchval: a resolved-or-never-escalated conversation
        # and an open escalation with a still-NULL summary both read as "no
        # value" through fetchval, but only the latter should spend a call.
        row = await conn.fetchrow(
            "select summary from escalations "
            "where tenant_id = $1 and conversation_id = $2 and status <> 'resolved' "
            "order by created_at desc limit 1",
            tenant_id,
            conversation_id,
        )
    if row is None:
        # No open escalation left to summarise - resolved already, or the
        # dedupe index meant this conversation's row was never this one.
        return
    if row["summary"]:
        # Already has one - either create_escalation's own line, or a prior
        # run of this same task. Never overwrite a real summary.
        return

    try:
        history = await chat_service.recent_messages(
            tenant_id=tenant_id, conversation_id=conversation_id, limit=_HISTORY_MESSAGES
        )
        if not history:
            return
        transcript = "\n".join(f"{message['role']}: {message['content']}" for message in history)
        result = await asyncio.wait_for(
            provider.extract(
                system_prompt=_SYSTEM_PROMPT,
                user_input=transcript,
                schema=_EscalationSummary,
            ),
            timeout=_TIMEOUT_S,
        )
    except Exception:
        # A failed summary is a NULL summary, never an error - the customer's
        # turn already completed, and the owner still sees the reason code.
        logger.warning("escalation summary generation failed", exc_info=True)
        return

    summary = result.summary.strip()
    if not summary:
        return

    async with db.tenant_context(tenant_id, "customer") as conn:
        # summary is null guards against a racing duplicate schedule and
        # against ever overwriting a summary written since the read above.
        await conn.execute(
            "update escalations set summary = $3 "
            "where tenant_id = $1 and conversation_id = $2 "
            "and status <> 'resolved' and summary is null",
            tenant_id,
            conversation_id,
            summary,
        )


def schedule(*, tenant_id: UUID, conversation_id: UUID, provider: LLMProvider) -> None:
    """Fire-and-forget: the caller does not await this, so it runs after the
    customer's response is already on the wire."""
    task = asyncio.create_task(
        _generate(tenant_id=tenant_id, conversation_id=conversation_id, provider=provider)
    )
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)
