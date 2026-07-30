"""Shared OpenAI-SDK provider base for the openai_compat and Azure bindings.

Both vendors speak the identical OpenAI wire format through the same async SDK;
only client construction and the model-vs-deployment identifier differ. This
base holds the common ``extract``/``chat``/``chat_stream``/``chat_with_tools``
bodies, the usage->cost reporting, and - critically - the transient-failure
retry every live turn needs. The retry is ported from the eval harness (``evals/
trajectory_eval.py``), which already learned that free-tier models fail
transiently in two ways: upstream 429s, and occasionally emitting malformed
structured-output JSON (surfaces as a pydantic ``ValidationError`` from the
SDK's ``parse``). Without it, either one aborts a whole customer turn.

Never touched by tests directly - they stub ``LLMProvider``.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any, Literal

import httpx
from openai import LengthFinishReasonError, RateLimitError
from pydantic import BaseModel, Field, ValidationError

from app.llm.provider import ChatMessage, LLMProvider, SchemaT, ToolCall, ToolSpec, ToolTurn
from app.observability.cost import report_usage

logger = logging.getLogger(__name__)

# An explicit connect timeout so a hung TCP connect fails fast instead of
# silently consuming the tenant's whole llm_timeout budget. The generous
# overall read timeout is only a backstop - the real per-turn bound is the
# tenant's llm_timeout_s, enforced by TimeLimitedProvider one layer out (which
# also bounds the total time across the retries below).
CONNECT_TIMEOUT_S = 5.0
SDK_TIMEOUT_S = 60.0
SDK_TIMEOUT = httpx.Timeout(SDK_TIMEOUT_S, connect=CONNECT_TIMEOUT_S)

# Live turns are already time-bounded by TimeLimitedProvider, so retry here is
# deliberately short and cheap: it rides out a transient 429 or a one-off
# malformed-JSON resample, not a sustained outage. A longer backoff would just
# be cancelled by the outer timeout anyway.
_RETRY_ATTEMPTS = 3
_MAX_BACKOFF_S = 20.0


class UpstreamResponseError(RuntimeError):
    """The endpoint returned a 200 whose body is not a usable completion.

    Observed live against OpenRouter: when the upstream provider behind a
    ``:free`` model fails or is congested, the gateway forwards an
    ``{"error": ...}`` body with ``choices: null`` under a 200 status. The
    OpenAI SDK then iterates that null inside ``parse_chat_completion`` and
    raises a bare ``TypeError: 'NoneType' object is not iterable``, which is
    neither a ``RateLimitError`` nor a ``ValidationError`` - so before this
    class existed it escaped the retry below and killed the whole turn (the
    customer's SSE stream died mid-flight with no terminal event, leaving the
    chat bubble spinning forever).

    It is transient in practice, so it is retried like a 429.
    """


def _require_choices(completion: Any) -> None:
    """Raise a retryable error if a completion carries no choices, instead of
    letting an opaque TypeError/IndexError surface from attribute access."""
    if not getattr(completion, "choices", None):
        raise UpstreamResponseError(
            "provider returned a response with no choices (likely an upstream "
            "error body forwarded under a 200)"
        )


def _report(model: str, usage: Any) -> None:
    """Forward a completion's token usage to the T-030 cost sink, if any."""
    if usage is not None:
        report_usage(model, usage.prompt_tokens or 0, usage.completion_tokens or 0)


def _retry_after_seconds(error: RateLimitError, attempt: int) -> float:
    """Honor the provider's Retry-After header when present, else back off
    exponentially. Capped so a pathological header can't stall a live turn -
    the outer timeout would cancel it anyway."""
    header: str | None = error.response.headers.get("Retry-After")
    if header is not None:
        try:
            seconds = float(header)
        except ValueError:
            pass
        else:
            return min(_MAX_BACKOFF_S, max(1.0, seconds))
    return min(_MAX_BACKOFF_S, 2.0 * float(2**attempt))


async def _with_retry[T](factory: Callable[[], Awaitable[T]]) -> T:
    """Await ``factory()``, retrying transient failures: a 429 (backed off,
    honoring Retry-After) or a malformed structured-output resample (short
    fixed delay). Any other exception, and the final attempt, propagate."""
    for attempt in range(_RETRY_ATTEMPTS):
        try:
            return await factory()
        except UpstreamResponseError:
            if attempt == _RETRY_ATTEMPTS - 1:
                raise
            logger.warning(
                "llm returned an unusable response body; retrying (attempt %d/%d)",
                attempt + 1,
                _RETRY_ATTEMPTS,
            )
            await asyncio.sleep(1.0)
        except RateLimitError as error:
            if attempt == _RETRY_ATTEMPTS - 1:
                raise
            delay = _retry_after_seconds(error, attempt)
            logger.warning(
                "llm rate-limited; retrying in %.0fs (attempt %d/%d)",
                delay,
                attempt + 1,
                _RETRY_ATTEMPTS,
            )
            await asyncio.sleep(delay)
        except ValidationError:
            if attempt == _RETRY_ATTEMPTS - 1:
                raise
            logger.warning(
                "llm produced malformed structured output; resampling (attempt %d/%d)",
                attempt + 1,
                _RETRY_ATTEMPTS,
            )
            await asyncio.sleep(1.0)
    # range(_RETRY_ATTEMPTS) with _RETRY_ATTEMPTS >= 1 always returns or raises
    # inside the loop; this satisfies the static return-type checker.
    raise AssertionError("unreachable")


# --- emulated tool calling schema -----------------------------------------------
# When native tool calling is unavailable (free OpenRouter models that don't
# support function calling), the emulated path uses extract() with a union
# schema that names the chosen tool (or "no_tool" for a prose response).
# This is the same pattern RouteDecision and QuoteSelectionResult already use.


def _build_emulated_schema(tools: list[ToolSpec]) -> type[BaseModel]:
    """Build a Literal-typed union schema for the emulated tool-calling path.

    The model chooses one tool name (or ``__no_tool__``) and supplies its
    args as a freeform dict. The caller then validates the args against the
    real tool's Pydantic schema.
    """
    tool_names = ["__no_tool__"] + [t.name for t in tools]
    tool_name_literal: Any = Literal.__getitem__(tuple(tool_names))
    return type(
        "_ToolChoice",
        (BaseModel,),
        {
            "__annotations__": {
                "tool_name": tool_name_literal,
                "tool_args": dict[str, object],
            },
            "tool_name": Field(description="The tool to call, or __no_tool__ to respond in prose"),
            "tool_args": Field(default_factory=dict),
        },
    )


class OpenAISDKProvider(LLMProvider):
    """Common OpenAI-SDK chat/extract/stream/tool-calling behavior. Subclasses
    only build the async client and pass the model (or Azure deployment)
    identifier."""

    def __init__(
        self,
        client: Any,
        model_id: str,
        *,
        max_tokens_draft: int = 0,
        max_tokens_extract: int = 0,
        # T-041: tool-calling support. Default on; set to False when the
        # configured model lacks native function calling and the emulated
        # extract()-based fallback should be used.
        supports_tools: bool = True,
    ) -> None:
        self._client = client
        self._model = model_id
        self._max_tokens_draft = max_tokens_draft
        self._max_tokens_extract = max_tokens_extract
        self._supports_tools = supports_tools

    @property
    def supports_tools(self) -> bool:
        return self._supports_tools

    def _cap(self, tokens: int) -> dict[str, int]:
        """Kwargs for an output cap, or nothing when the cap is disabled (0).
        Spread into the call so an uncapped provider sends no max_tokens field
        at all, exactly as before this existed."""
        return {"max_tokens": tokens} if tokens > 0 else {}

    # --- native tool definitions (OpenAI wire format) ---------------------------

    @staticmethod
    def _tool_defs(tools: list[ToolSpec]) -> list[dict[str, object]]:
        """Convert ``ToolSpec`` list into the format the OpenAI SDK expects."""
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.args_schema.model_json_schema(),
                },
            }
            for t in tools
        ]

    # --- chat_with_tools: native path -------------------------------------------

    async def _chat_with_tools_native(
        self, messages: list[ChatMessage], tools: list[ToolSpec], tool_choice: str
    ) -> ToolTurn:
        """Native tool calling via the OpenAI SDK's create() with tools.

        Deliberately NOT using the SDK's parse() - the model may return tool
        calls, text, or both, and we need the raw message to disambiguate
        which tool was called with what args.
        """

        async def _call() -> Any:
            return await self._client.chat.completions.create(
                model=self._model,
                messages=[dict(message) for message in messages],
                tools=self._tool_defs(tools),
                tool_choice=tool_choice,
                **self._cap(self._max_tokens_draft),
            )

        completion = await _with_retry(_call)
        _report(self._model, completion.usage)
        _require_choices(completion)
        message = completion.choices[0].message

        text: str | None = message.content
        tool_calls: list[ToolCall] = []
        if message.tool_calls:
            for tc in message.tool_calls:
                try:
                    args: dict[str, object] = json.loads(tc.function.arguments)
                except json.JSONDecodeError as e:
                    raise UpstreamResponseError(
                        f"tool call '{tc.function.name}' returned unparseable arguments: "
                        f"{tc.function.arguments[:200]}"
                    ) from e
                tool_calls.append(
                    ToolCall(id=tc.id, name=tc.function.name, args=args)
                )
        return ToolTurn(text=text, tool_calls=tool_calls)

    # --- chat_with_tools: emulated path -----------------------------------------

    async def _chat_with_tools_emulated(
        self, messages: list[ChatMessage], tools: list[ToolSpec], tool_choice: str
    ) -> ToolTurn:
        """Emulated tool calling via extract() when native tool calling is off.

        Builds a ``ToolChoice`` union schema whose ``tool_name`` is a Literal
        of all known tool names plus ``__no_tool__``, and whose ``tool_args``
        is a freeform dict. When ``tool_choice`` is ``"required"``, the
        Literal excludes ``__no_tool__``.

        Uses the multi-message history through extract()'s user_input, so the
        model sees the full conversation. This is the pattern
        ``supervisor.RouteDecision`` and ``quoting.QuoteSelectionResult``
        already use - proven code, not a stub.
        """
        tool_names: list[str] = [t.name for t in tools]

        if tool_choice == "required" and not tool_names:
            # No tools configured but the caller asked for one - return empty.
            return ToolTurn()

        if tool_choice == "none":
            # Caller wants prose only, no tools. Use chat() directly.
            text = await self.chat(messages)
            return ToolTurn(text=text)

        # Render the conversation tail into a user_input string.
        conv_lines: list[str] = []
        for m in messages:
            role = m["role"]
            content = m.get("content", "")
            if m.get("tool_calls"):
                calls_desc = json.dumps([tc["function"] for tc in m["tool_calls"]])
                conv_lines.append(f"{role}: TOOL_CALLS: {calls_desc}")
            elif m.get("tool_call_id"):
                conv_lines.append(f"{role} (tool result for {m['tool_call_id']}): {content}")
            else:
                conv_lines.append(f"{role}: {content}")
        user_input = "\n".join(conv_lines)

        # Build the system prompt describing tools.
        tool_descriptions = "\n".join(
            f"  - {t.name}: {t.description}"
            f"\n    args schema: {t.args_schema.model_json_schema()}"
            for t in tools
        )
        system_prompt = (
            f"You have the following tools available:\n{tool_descriptions}\n\n"
            "Choose one tool to call and provide its arguments, or respond with "
            "tool_name='__no_tool__' and no args to respond directly.\n"
            "Always respond in the exact format expected - never invent tool names.\n"
            + ("You MUST call one of the listed tools." if tool_choice == "required" else "")
        )

        # Build a dynamic ToolChoice schema with the allowed Literal values.
        dynamic_schema = _build_emulated_schema(tools)

        # If tool_choice is "required", we need a schema that excludes __no_tool__.
        choice: Any
        if tool_choice == "required":
            allowed_literal: Any = Literal.__getitem__(tuple(tool_names))
            required_schema = type(
                "_RequiredToolChoice",
                (BaseModel,),
                {
                    "__annotations__": {
                        "tool_name": allowed_literal,
                        "tool_args": dict[str, object],
                    },
                    "tool_name": Field(
                        description=(
                            "The tool to call "
                            "(note: __no_tool__ is not available)"
                        )
                    ),
                    "tool_args": Field(default_factory=dict),
                },
            )
            choice = await self.extract(
                system_prompt=system_prompt, user_input=user_input, schema=required_schema
            )
        else:
            choice = await self.extract(
                system_prompt=system_prompt, user_input=user_input, schema=dynamic_schema
            )

        name: str = getattr(choice, "tool_name", "__no_tool__")
        if name == "__no_tool__":
            return ToolTurn()

        args: dict[str, object] = getattr(choice, "tool_args", {}) or {}
        tool_call = ToolCall(id=f"emulated-{name}", name=name, args=args)
        return ToolTurn(tool_calls=[tool_call])

    # ------------------------------------------------------------------------

    async def chat_with_tools(
        self,
        *,
        messages: list[ChatMessage],
        tools: list[ToolSpec],
        tool_choice: str = "auto",
    ) -> ToolTurn:
        if tool_choice not in ("auto", "required", "none"):
            raise ValueError(
                f"tool_choice must be 'auto', 'required', or 'none', got {tool_choice!r}"
            )

        if self._supports_tools:
            return await self._chat_with_tools_native(messages, tools, tool_choice)

        return await self._chat_with_tools_emulated(messages, tools, tool_choice)

    async def extract(
        self, *, system_prompt: str, user_input: str, schema: type[SchemaT]
    ) -> SchemaT:
        async def _call() -> SchemaT:
            try:
                completion = await self._client.chat.completions.parse(
                    model=self._model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_input},
                    ],
                    response_format=schema,
                    **self._cap(self._max_tokens_extract),
                )
            except LengthFinishReasonError as error:
                # The output cap was hit before the model finished the JSON.
                # Retrying is pointless (same cap, same outcome), so fail with
                # the actual cause named. Overwhelmingly this means the cap is
                # too low for a REASONING model, whose hidden thinking tokens
                # are spent before any answer is emitted.
                raise ValueError(
                    "structured output hit the "
                    f"{self._max_tokens_extract}-token LLM_MAX_TOKENS_EXTRACT cap before "
                    "completing. If this model is a reasoning model, its thinking tokens "
                    "consume that budget first - raise the cap or set it to 0 (uncapped)."
                ) from error
            except TypeError as error:
                # The SDK iterates completion.choices inside its own parser, so
                # a null-choices error body surfaces here as a bare TypeError
                # before any of our code can inspect it. Narrow re-raise, so it
                # joins the retry path instead of aborting the turn.
                raise UpstreamResponseError(
                    "provider returned an unparseable completion body"
                ) from error
            _report(self._model, completion.usage)
            _require_choices(completion)
            parsed = completion.choices[0].message.parsed
            if parsed is None:
                raise ValueError("model produced no parseable structured output")
            return parsed  # type: ignore[no-any-return]

        return await _with_retry(_call)

    async def chat(self, messages: list[ChatMessage]) -> str:
        async def _call() -> str:
            completion = await self._client.chat.completions.create(
                model=self._model,
                messages=[dict(message) for message in messages],
                **self._cap(self._max_tokens_draft),
            )
            _report(self._model, completion.usage)
            _require_choices(completion)
            content = completion.choices[0].message.content
            if content is None:
                raise ValueError("model produced no chat content")
            return content  # type: ignore[no-any-return]

        return await _with_retry(_call)

    async def chat_stream(self, messages: list[ChatMessage]) -> AsyncIterator[str]:
        # Retry only the stream *establishment*: once tokens start flowing a
        # mid-stream retry would duplicate already-yielded deltas, so the
        # retry wraps the create() call, not the iteration.
        async def _open() -> Any:
            return await self._client.chat.completions.create(
                model=self._model,
                messages=[dict(message) for message in messages],
                stream=True,
                # Ask for a final usage-only chunk so streamed calls are costed too.
                stream_options={"include_usage": True},
                **self._cap(self._max_tokens_draft),
            )

        stream = await _with_retry(_open)
        async for chunk in stream:
            # The usage-only final chunk carries no choices.
            if getattr(chunk, "usage", None) is not None:
                _report(self._model, chunk.usage)
            delta = chunk.choices[0].delta.content if chunk.choices else None
            if delta:
                yield delta