"""P-2: the latency budget - transparent failover between provider legs.

Each ``FailoverProvider`` is one link in the chain the tier config builds
(``FailoverProvider(primary, FailoverProvider(fallback, failover))``), so the
behavior below composes: a slow primary races "everything after it", and if that
is itself a chain, it races internally on the same rules.

**The budget** (D16, PRD section 9). The primary gets ``TTFT_BUDGET_S`` to
produce something - a completed call, or the first token of a stream. Past that
it is not cancelled: it may still be about to answer. Instead the next leg
starts alongside it and the two race, **first wins**; the loser is cancelled and
whatever it produced is discarded, so the customer never sees two answers or a
torn stream. A leg that *fails* (rather than being slow) hands over immediately,
which is the behavior this module had before the budget existed.

**What fails over**: a 429 that survived three internal backoff retries, an
unusable upstream error body under a 200, a network-level failure, or repeatedly
malformed structured output. **What does not**: a ValueError (e.g. the extract
cap being too small - the next leg has the same cap) and ``LimitTimeout`` (a
tenant budget protection, not a provider failure - the outer TimeLimitedProvider
raises it after this layer runs).

**Hard 429s** (quota exhausted, as opposed to "slow down") mark that leg
skipped, so the rest of the turn stops paying its timeout. The skip lives on the
provider instance, which is built per request - so it is per turn rather than
per conversation. A hard 429 fails fast, so re-learning it next turn costs an
error round trip, not a stall; a longer-lived skip belongs with a shared cache
rather than in a per-request object.

``chat_stream`` races only the first delta. Once tokens have flowed the winner
owns the stream: a mid-stream failure surfaces to the caller, because a second
attempt would duplicate what was already yielded.

Never touched by tests directly - they stub ``LLMProvider``.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import AsyncIterator, Callable, Coroutine, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any, TypeVar

from openai import APIConnectionError, APIStatusError, RateLimitError
from pydantic import ValidationError

from app.llm.openai_base import UpstreamResponseError
from app.llm.provider import ChatMessage, LLMProvider, SchemaT, ToolSpec, ToolTurn

logger = logging.getLogger(__name__)

# Failures that mean "this provider is unusable right now" - retrying it
# again is pointless, so the next leg gets the call instead. The SDK
# wraps every raw httpx failure as APIConnectionError, so nothing else escapes.
_FAILOVER_ERRORS = (
    RateLimitError,
    APIConnectionError,
    UpstreamResponseError,
    ValidationError,
)

# How long the primary gets to produce a first token before the next leg starts
# racing it. The product promise is <= 4s to first token (PRD section 9); this is
# the trigger, not the promise - the race is what keeps the promise when a leg
# is having a bad minute.
TTFT_BUDGET_S = 4.0

_T = TypeVar("_T")


# --- turn-level telemetry -------------------------------------------------------


@dataclass
class LegOutcome:
    """What the provider chain did for one turn, as scalars fit for a trace.

    No prompts, no completions, no tenant content - just which leg answered, how
    fast it produced anything, and whether the race was needed.
    """

    ttft_ms: float | None = None
    leg: str | None = None
    failover_engaged: bool = False
    skip_reasons: list[str] = field(default_factory=list)

    def as_attributes(self) -> dict[str, object]:
        attrs: dict[str, object] = {"failover_engaged": self.failover_engaged}
        if self.ttft_ms is not None:
            attrs["ttft_ms"] = self.ttft_ms
        if self.leg is not None:
            attrs["leg"] = self.leg
        if self.skip_reasons:
            attrs["skip_reason"] = ",".join(sorted(set(self.skip_reasons)))
        return attrs


_leg_sink: ContextVar[LegOutcome | None] = ContextVar("_leg_sink", default=None)


@contextmanager
def collect_legs() -> Iterator[LegOutcome]:
    """Activate a fresh leg record for the duration of a turn.

    Mirrors ``collect_usage`` in app/observability/cost.py, including why it is a
    mutable object rather than a value: the race runs in child tasks, which get a
    *copy* of the context, so only mutation of a shared object is visible to the
    turn that opened the record.
    """
    outcome = LegOutcome()
    token = _leg_sink.set(outcome)
    try:
        yield outcome
    finally:
        _leg_sink.reset(token)


def _record(**fields: object) -> None:
    outcome = _leg_sink.get()
    if outcome is None:
        return
    for key, value in fields.items():
        if key == "skip_reason":
            outcome.skip_reasons.append(str(value))
        else:
            setattr(outcome, key, value)


def _is_hard_rate_limit(error: BaseException) -> bool:
    """A 429 that means "your quota is gone", not "slow down".

    The provider's own retry/backoff has already run by the time anything
    reaches this layer, so a surviving 429 is treated as terminal for the leg
    only when the upstream says so - insufficient quota, exhausted daily limit.
    """
    if not isinstance(error, APIStatusError) or error.status_code != 429:
        return False
    body = str(getattr(error, "message", "")) + str(getattr(error, "body", ""))
    haystack = body.lower()
    return any(
        phrase in haystack
        for phrase in ("quota", "insufficient_quota", "exceeded your current", "daily limit")
    )


class FailoverProvider(LLMProvider):
    """Delegates every call to ``primary``; when the primary is slow past the
    TTFT budget the ``fallback`` races it, and when the primary fails outright
    the fallback takes the call."""

    def __init__(
        self,
        primary: LLMProvider,
        fallback: LLMProvider,
        *,
        ttft_budget_s: float = TTFT_BUDGET_S,
    ) -> None:
        self._primary = primary
        self._fallback = fallback
        self._ttft_budget_s = ttft_budget_s
        self._skipped: set[str] = set()

    @property
    def supports_tools(self) -> bool:
        # Mirror the primary: it is what serves every call that succeeds, and
        # the emulated-vs-native decision is made from its capability.
        return self._primary.supports_tools

    def _note_failure(self, leg: str, error: BaseException) -> None:
        if _is_hard_rate_limit(error):
            self._skipped.add(leg)
            _record(skip_reason=f"{leg}:hard_429")
            logger.warning("llm %s leg hard rate-limited; skipping it for this turn", leg)

    async def _race(
        self,
        what: str,
        primary_call: Callable[[], Coroutine[Any, Any, _T]],
        fallback_call: Callable[[], Coroutine[Any, Any, _T]],
    ) -> _T:
        started = time.perf_counter()
        if "primary" in self._skipped:
            return await self._await_leg("fallback", fallback_call, started)

        primary_task: asyncio.Task[_T] = asyncio.create_task(primary_call())
        done, _ = await asyncio.wait({primary_task}, timeout=self._ttft_budget_s)

        if done:
            try:
                result: _T = primary_task.result()
            except _FAILOVER_ERRORS as error:
                self._note_failure("primary", error)
                logger.warning(
                    "primary llm %s failed (%s: %s); failing over",
                    what,
                    type(error).__name__,
                    error,
                )
                return await self._await_leg("fallback", fallback_call, started)
            _record(ttft_ms=_elapsed_ms(started), leg="primary")
            return result

        # Slow, not failed: the primary keeps running and the next leg starts
        # alongside it. Whichever produces first owns the answer.
        _record(failover_engaged=True)
        logger.info(
            "primary llm %s exceeded the %.1fs first-token budget; racing the next leg",
            what,
            self._ttft_budget_s,
        )
        fallback_task: asyncio.Task[_T] = asyncio.create_task(fallback_call())
        return await self._first_win(
            what, {primary_task: "primary", fallback_task: "fallback"}, started
        )

    async def _await_leg(
        self, leg: str, call: Callable[[], Coroutine[Any, Any, _T]], started: float
    ) -> _T:
        result = await call()
        _record(ttft_ms=_elapsed_ms(started), leg=leg)
        return result

    async def _first_win(self, what: str, legs: dict[asyncio.Task[_T], str], started: float) -> _T:
        pending = set(legs)
        last_error: BaseException | None = None
        while pending:
            done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                leg = legs[task]
                try:
                    result = task.result()
                except Exception as error:  # noqa: BLE001 - the other leg may still win
                    last_error = error
                    self._note_failure(leg, error)
                    logger.warning(
                        "llm %s leg %s lost the race by failing (%s)",
                        what,
                        leg,
                        type(error).__name__,
                    )
                    continue
                await _cancel(pending)
                _record(ttft_ms=_elapsed_ms(started), leg=leg)
                return result
        assert last_error is not None
        raise last_error

    async def extract(
        self, *, system_prompt: str, user_input: str, schema: type[SchemaT]
    ) -> SchemaT:
        return await self._race(
            "extract",
            lambda: self._primary.extract(
                system_prompt=system_prompt, user_input=user_input, schema=schema
            ),
            lambda: self._fallback.extract(
                system_prompt=system_prompt, user_input=user_input, schema=schema
            ),
        )

    async def chat(self, messages: list[ChatMessage]) -> str:
        return await self._race(
            "chat",
            lambda: self._primary.chat(messages),
            lambda: self._fallback.chat(messages),
        )

    async def chat_with_tools(
        self,
        *,
        messages: list[ChatMessage],
        tools: list[ToolSpec],
        tool_choice: str = "auto",
    ) -> ToolTurn:
        return await self._race(
            "chat_with_tools",
            lambda: self._primary.chat_with_tools(
                messages=messages, tools=tools, tool_choice=tool_choice
            ),
            lambda: self._fallback.chat_with_tools(
                messages=messages, tools=tools, tool_choice=tool_choice
            ),
        )

    async def chat_stream(self, messages: list[ChatMessage]) -> AsyncIterator[str]:
        """Race the first delta only; the winner then owns the stream.

        The race is over time-to-first-token, which is the number the budget is
        written in. After that the streams are not interchangeable - a switch
        mid-answer would either duplicate or truncate what the customer already
        has - so the loser is cancelled and the winner runs to completion.
        """
        winner, first = await self._race(
            "chat_stream",
            lambda: _open_stream(self._primary.chat_stream(messages)),
            lambda: _open_stream(self._fallback.chat_stream(messages)),
        )
        if first is not None:
            yield first
        async for delta in winner:
            yield delta


async def _open_stream(stream: AsyncIterator[str]) -> tuple[AsyncIterator[str], str | None]:
    """Start a stream and pull its first delta, so "produced something" means the
    same thing for a stream as it does for a completed call. ``None`` means the
    stream ended without producing anything."""
    try:
        first = await stream.__anext__()
    except StopAsyncIteration:
        return stream, None
    return stream, first


async def _cancel[T](tasks: set[asyncio.Task[T]]) -> None:
    """Cancel the losing legs and swallow whatever they were about to raise."""
    for task in tasks:
        task.cancel()
    for task in tasks:
        try:
            await task
        except (asyncio.CancelledError, Exception):  # noqa: BLE001 - a loser's fate is irrelevant
            pass


def _elapsed_ms(started: float) -> float:
    return round((time.perf_counter() - started) * 1000, 1)
