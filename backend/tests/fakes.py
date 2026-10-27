"""Shared LLMProvider / Embedder test doubles."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

from app.llm.embedder import Embedder
from app.llm.provider import ChatMessage, LLMProvider, SchemaT, ToolSpec, ToolTurn
from app.shared.config import get_settings

EMBEDDING_DIM = get_settings().embedding_dim


class BaseFakeProvider(LLMProvider):
    async def extract(
        self, *, system_prompt: str, user_input: str, schema: type[SchemaT]
    ) -> SchemaT:
        raise NotImplementedError

    async def chat(self, messages: list[ChatMessage]) -> str:
        raise NotImplementedError

    async def chat_stream(self, messages: list[ChatMessage]) -> AsyncIterator[str]:
        raise NotImplementedError
        yield

    async def chat_with_tools(
        self,
        *,
        messages: list[ChatMessage],
        tools: list[ToolSpec],
        tool_choice: str = "auto",
    ) -> ToolTurn:
        raise NotImplementedError


class ToolAwareFakeProvider(BaseFakeProvider):
    def __init__(
        self,
        tool_call_sequence: list[ToolTurn] | None = None,
        stream_text: str = "Hello! I'm the virtual assistant. How can I help?",
        extract_route: str = "knowledge",
        extract_confidence: float = 1.0,
        extract_intent: str | None = None,
        extract_action: str | None = None,
    ) -> None:
        self._turns = list(tool_call_sequence or [])
        self._turn_index = 0
        self._stream_text = stream_text
        self._extract_route = extract_route
        self._extract_confidence = extract_confidence
        self._extract_intent = extract_intent
        self._extract_action = extract_action
        # Messages seen by each chat_with_tools call, so a test can assert what
        # the agent loop actually feeds back to the model (tool results are
        # tenant-authored data and must arrive spotlight-wrapped).
        self.tool_call_messages: list[list[ChatMessage]] = []
        # System prompt of each draft call, so a test can assert what the draft
        # node composed (spotlight wrapping, redraft violations).
        self.draft_prompts: list[str] = []

    async def extract(
        self, *, system_prompt: str, user_input: str, schema: type[SchemaT]
    ) -> SchemaT:
        if "grounding" in schema.model_fields:
            return schema.model_validate(
                {"intent": self._extract_intent, "action": self._extract_action}
            )
        if "route" in schema.model_fields:
            return schema.model_validate(
                {
                    "route": self._extract_route,
                    "confidence": self._extract_confidence,
                    "reason": "test",
                }
            )
        if "ref_code" in schema.model_fields:
            return schema.model_validate({"ref_code": "R-1042", "customer_ref": None})
        if "needs" in schema.model_fields:
            return schema.model_validate({"needs": [], "constraints": []})
        raise NotImplementedError

    async def chat_stream(self, messages: list[ChatMessage]) -> AsyncIterator[str]:
        self.draft_prompts.append(
            next((m["content"] for m in messages if m["role"] == "system"), "")
        )
        yield self._stream_text

    async def chat_with_tools(
        self,
        *,
        messages: list[ChatMessage],
        tools: list[ToolSpec],
        tool_choice: str = "auto",
    ) -> ToolTurn:
        self.tool_call_messages.append([dict(m) for m in messages])  # type: ignore[misc]
        if self._turn_index < len(self._turns):
            turn = self._turns[self._turn_index]
            self._turn_index += 1
            if turn.tool_calls and turn.history_message is None:
                turn.history_message = {
                    "role": "assistant",
                    "content": turn.text or "",
                    "tool_calls": [
                        {
                            "id": call.id,
                            "type": "function",
                            "function": {
                                "name": call.name,
                                "arguments": json.dumps(call.args),
                            },
                        }
                        for call in turn.tool_calls
                    ],
                }
            return turn
        return ToolTurn(text="", tool_calls=[])


class ZeroEmbedder(Embedder):
    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.0] * EMBEDDING_DIM for _ in texts]


class ConcurrencyProbe(BaseFakeProvider):
    """An extract() double that answers every schema and records overlap (29).

    It spends ``delay`` inside each call and counts how many calls are in
    flight at once, so two passes meant to run together overlap while a serial
    implementation peaks at one. Answers are keyed by schema: offerings,
    profile, or (anything else) the structuring pass.
    """

    def __init__(
        self,
        *,
        offerings: list[dict[str, str]] | None = None,
        profile: dict[str, str] | None = None,
        delay: float = 0.05,
    ) -> None:
        self.offerings = list(offerings or [])
        self.profile = dict(profile or {})
        self.delay = delay
        self.in_flight = 0
        self.max_in_flight = 0
        self.events: list[tuple[str, int, str]] = []

    @staticmethod
    def _kind(schema: type[SchemaT]) -> str:
        if "offerings" in schema.model_fields:
            return "offerings"
        if "profile" in schema.model_fields:
            return "profile"
        return "structure"

    async def extract(
        self, *, system_prompt: str, user_input: str, schema: type[SchemaT]
    ) -> SchemaT:
        kind = self._kind(schema)
        self.in_flight += 1
        self.max_in_flight = max(self.max_in_flight, self.in_flight)
        self.events.append(("start", self.in_flight, kind))
        try:
            await asyncio.sleep(self.delay)
            return schema.model_validate(self._payload(kind, user_input))
        finally:
            self.in_flight -= 1
            self.events.append(("finish", self.in_flight, kind))

    def _payload(self, kind: str, user_input: str) -> dict[str, object]:
        if kind == "offerings":
            visible = [
                item
                for item in self.offerings
                if not item.get("price_block") or f"[{item['price_block']}]" in user_input
            ]
            return {"offerings": visible}
        if kind == "profile":
            return {"profile": self.profile}
        return {"about": "A phone and laptop repair shop."}

    def _first(self, event: str, kind: str) -> int:
        return next(
            index
            for index, entry in enumerate(self.events)
            if entry[0] == event and entry[2] == kind
        )

    def started(self, kind: str) -> int:
        return self._first("start", kind)

    def finished(self, kind: str) -> int:
        return self._first("finish", kind)
