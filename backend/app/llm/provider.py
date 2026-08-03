"""The chat LLM provider abstraction (T-006, extended T-041 for tool calling).

Every call site that needs a chat model (onboarding extraction; agents and
the pricing-adjacent generation calls in later phases) goes through this
interface, never a vendor SDK directly - so tests stub a provider instead of
hitting a real API, and swapping providers never touches call sites.
Embeddings are a separate, independently swappable seam: app/llm/embedder.py.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import TypedDict, TypeVar

from pydantic import BaseModel

SchemaT = TypeVar("SchemaT", bound=BaseModel)


class ChatMessage(TypedDict, total=False):
    role: str
    content: str
    # T-041: tool-call-aware history. ``tool_calls`` is a list of dicts the
    # provider serializes as JSON on the wire (assistant messages carrying a
    # tool-use request). ``tool_call_id`` is set on a tool-result message so
    # the provider can correlate it back to the assistant's request. Both are
    # optional (``total=False``) so every existing ``ChatMessage`` literal
    # stays valid.
    tool_calls: list[dict[str, object]]
    tool_call_id: str


@dataclass(frozen=True)
class ToolCall:
    """One tool-use request returned by the model in a tool turn."""

    id: str
    name: str
    args: dict[str, object]


@dataclass
class ToolSpec:
    """A tool the model may call, with its Pydantic args schema.

    ``description`` tells the model what the tool does and when to call it.
    ``args_schema`` is a Pydantic model whose JSON schema the provider
    includes in the tool definition so the model knows what args to supply.
    """

    name: str
    description: str
    args_schema: type[BaseModel]


@dataclass
class ToolTurn:
    """The result of a single ``chat_with_tools`` call.

    ``text`` is set when the model responds with prose (no tool called, or
    after tool results are consumed). ``tool_calls`` is set when the model
    wants to call one or more tools, in which order they should be executed.
    At least one of the two is populated.
    """

    text: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)


class LLMProvider(ABC):
    @abstractmethod
    async def extract(
        self, *, system_prompt: str, user_input: str, schema: type[SchemaT]
    ) -> SchemaT:
        """Extract structured data matching ``schema`` from freeform ``user_input``.

        ``system_prompt`` carries the extraction instructions; ``user_input`` is
        the caller's freeform text (e.g. an onboarding admin's chat reply).
        Implementations must return an instance of exactly ``schema`` - never a
        raw string or dict - so callers never hand-parse model output.
        """
        raise NotImplementedError

    @abstractmethod
    async def chat(self, messages: list[ChatMessage]) -> str:
        """Freeform, non-streamed chat completion - for callers that need the
        whole response before doing anything with it (tool-calling reasoning
        in phase 2's agents). T-011's bare customer chat uses ``chat_stream``
        instead."""
        raise NotImplementedError

    @abstractmethod
    def chat_stream(self, messages: list[ChatMessage]) -> AsyncIterator[str]:
        """Freeform chat completion, yielding text deltas as they arrive - for
        callers that stream to a client (T-011's bare customer chat, over SSE)."""
        raise NotImplementedError

    # T-041: tool calling -------------------------------------------------------

    @property
    def supports_tools(self) -> bool:
        """Whether this provider supports native tool calling (function calling
        via the OpenAI wire format). When False, ``chat_with_tools`` falls back
        to an emulated path via ``extract()`` using a Literal-typed union schema,
        returning the same ``ToolTurn`` shape."""
        return True

    @abstractmethod
    async def chat_with_tools(
        self,
        *,
        messages: list[ChatMessage],
        tools: list[ToolSpec],
        tool_choice: str = "auto",
    ) -> ToolTurn:
        """Send a conversation with tool definitions and get back either prose
        or tool-call requests.

        ``tools`` is the set of tools the model may request. ``tool_choice``
        controls whether the model *must* call a tool (``"required"``), *may*
        call one or none (``"auto"``, the default), or *must not* call one
        (``"none"`` - useful for the final composition turn).

        Returns a ``ToolTurn`` whose ``text`` or ``tool_calls`` (or both, for a
        model that both calls a tool and writes a prose prefix) captures the
        model's decision.
        """
        raise NotImplementedError
