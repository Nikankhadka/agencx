"""Shared LLMProvider / Embedder test doubles."""

from __future__ import annotations

from collections.abc import AsyncIterator

from app.core.config import get_settings
from app.llm.embedder import Embedder
from app.llm.provider import ChatMessage, LLMProvider, SchemaT, ToolSpec, ToolTurn

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
        self, *, messages: list[ChatMessage], tools: list[ToolSpec], tool_choice: str = "auto",
    ) -> ToolTurn:
        raise NotImplementedError


class ToolAwareFakeProvider(BaseFakeProvider):
    def __init__(
        self,
        tool_call_sequence: list[ToolTurn] | None = None,
        stream_text: str = "Hello! I'm the virtual assistant. How can I help?",
        extract_route: str = "knowledge",
        extract_confidence: float = 1.0,
    ) -> None:
        self._turns = list(tool_call_sequence or [])
        self._turn_index = 0
        self._stream_text = stream_text
        self._extract_route = extract_route
        self._extract_confidence = extract_confidence
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
            return schema.model_validate({})
        if "route" in schema.model_fields:
            return schema.model_validate({
                "route": self._extract_route,
                "confidence": self._extract_confidence,
                "reason": "test",
            })
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
        self, *, messages: list[ChatMessage], tools: list[ToolSpec], tool_choice: str = "auto",
    ) -> ToolTurn:
        self.tool_call_messages.append([dict(m) for m in messages])  # type: ignore[misc]
        if self._turn_index < len(self._turns):
            turn = self._turns[self._turn_index]
            self._turn_index += 1
            return turn
        return ToolTurn(text="", tool_calls=[])


class ZeroEmbedder(Embedder):
    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.0] * EMBEDDING_DIM for _ in texts]
