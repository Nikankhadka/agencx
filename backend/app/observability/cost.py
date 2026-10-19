"""T-030: LLM cost accounting.

Every LLM call the app makes reports its token usage through a per-turn sink
(a contextvar), so the singleton provider stays stateless and thread-safe
while the caller that knows the tenant/conversation (chat.py) collects usage
for the whole turn and writes it to ``cost_logs`` once.

USD is computed deterministically from a per-model price table (dollars per
million tokens). The free-first default models cost $0 - the machinery is
correct regardless, and a hosted model just needs a price-table entry.
Aggregation queries back the per-tenant/day budget (T-028) and the
per-conversation cost shown in the Surface-2 trace (T-031/T-034).

A usage record carries two model ids. ``model`` is what the provider's response
named (the **served** model, e.g. a versioned ``gpt-4o-mini-2024-07-18``), kept
for history and model identity. ``price_model`` is the id the app actually
configured (the Azure deployment or the requested model), and it is what
``PRICE_TABLE`` is keyed on - so a provider that answers with a versioned name
still prices correctly instead of silently costing $0.

The provider abstraction still returns only its parsed/text result - usage is
a side channel via :func:`report_usage`, so no call site changed and a
provider that can't report usage (a test fake) simply reports nothing.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from app.shared import db


@dataclass(frozen=True)
class TokenUsage:
    # The served model, as the provider's response named it. Recorded to
    # ``cost_logs.model`` for history and integrity.
    model: str
    input_tokens: int
    output_tokens: int
    # The configured id (deployment/model the app asked for), which
    # ``PRICE_TABLE`` keys on. ``None`` means "same as ``model``" - a provider
    # whose response names the requested id exactly (or a caller that does not
    # distinguish them, including every test fake).
    price_model: str | None = None
    # Slice 5: tokens the provider served from its prompt cache (a subset of
    # ``input_tokens``). 0 when the provider reports none - it is observability,
    # not cost: a cache read still bills as input on the free-first tiers.
    cached_tokens: int = 0

    @property
    def price_key(self) -> str:
        return self.price_model or self.model


# Dollars per 1,000,000 tokens: (input, output). Unknown models cost $0 (the
# free-first default) - add an entry to price a hosted model. Keys match the
# CONFIGURED deployment/model id the app asks for (``price_model``), not the
# served name the provider's response may report - a versioned served name like
# ``gpt-4o-mini-2024-07-18`` prices via the configured ``gpt-4o-mini``.
PRICE_TABLE: dict[str, tuple[Decimal, Decimal]] = {
    # Reference paid models (Azure/OpenAI list prices) so a swap prices itself.
    "gpt-4o-mini": (Decimal("0.15"), Decimal("0.60")),
    "text-embedding-3-small": (Decimal("0.02"), Decimal("0")),
}


def compute_cost_usd(model: str, input_tokens: int, output_tokens: int) -> Decimal:
    """Deterministic USD for one call. Unknown/free models -> 0."""
    input_price, output_price = PRICE_TABLE.get(model, (Decimal("0"), Decimal("0")))
    cost = (Decimal(input_tokens) * input_price + Decimal(output_tokens) * output_price) / Decimal(
        1_000_000
    )
    # cost_logs.cost_usd is numeric(12,6) - quantize to match, so the stored
    # value and any reconciliation math agree exactly.
    return cost.quantize(Decimal("0.000001"))


# --- per-turn usage sink --------------------------------------------------------

_usage_sink: ContextVar[list[TokenUsage] | None] = ContextVar("_usage_sink", default=None)


@contextmanager
def collect_usage() -> Iterator[list[TokenUsage]]:
    """Activate a fresh usage sink for the duration of a turn. Every
    :func:`report_usage` call inside appends to the yielded list. Nesting
    replaces the sink and restores the previous one on exit (contextvars are
    task-local, so concurrent turns never share a sink)."""
    sink: list[TokenUsage] = []
    token = _usage_sink.set(sink)
    try:
        yield sink
    finally:
        _usage_sink.reset(token)


def report_usage(
    model: str,
    input_tokens: int,
    output_tokens: int,
    *,
    price_model: str | None = None,
    cached_tokens: int = 0,
) -> None:
    """Called by a provider after a completion. No active sink (e.g. an eval
    or a test not collecting cost) -> silently dropped.

    ``model`` is the served id; ``price_model`` is the configured id to price
    by (defaults to ``model`` when the caller does not distinguish them);
    ``cached_tokens`` is the provider's prompt-cache read count, defaulting to
    0 so a provider that reports none stays backward compatible."""
    sink = _usage_sink.get()
    if sink is not None:
        sink.append(
            TokenUsage(
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                price_model=price_model,
                cached_tokens=cached_tokens,
            )
        )


# --- persistence + aggregation --------------------------------------------------


async def record_costs(
    conn: db.AppConnection,
    tenant_id: UUID,
    conversation_id: UUID,
    usages: list[TokenUsage],
) -> Decimal:
    """Write one cost_logs row per LLM call of a turn; return the turn's total
    USD. ``conn`` must already be in the tenant's context (RLS scopes the
    write). Empty usage list writes nothing."""
    total = Decimal("0")
    for usage in usages:
        cost = compute_cost_usd(usage.price_key, usage.input_tokens, usage.output_tokens)
        total += cost
        await conn.execute(
            "insert into cost_logs "
            "(tenant_id, conversation_id, model, input_tokens, output_tokens, cost_usd) "
            "values ($1, $2, $3, $4, $5, $6)",
            tenant_id,
            conversation_id,
            usage.model,
            usage.input_tokens,
            usage.output_tokens,
            cost,
        )
    return total


async def cost_for_conversation(conn: db.AppConnection, conversation_id: UUID) -> Decimal:
    value = await conn.fetchval(
        "select coalesce(sum(cost_usd), 0) from cost_logs where conversation_id = $1",
        conversation_id,
    )
    return Decimal(str(value))


async def cost_for_tenant_day(conn: db.AppConnection, tenant_id: UUID) -> Decimal:
    value = await conn.fetchval(
        "select coalesce(sum(cost_usd), 0) from cost_logs "
        "where tenant_id = $1 and created_at >= date_trunc('day', now())",
        tenant_id,
    )
    return Decimal(str(value))
