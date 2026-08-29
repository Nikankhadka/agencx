"""Conversations handlers: assemble the Surface-2 transcript + trace shape.

Handler logic that moved out of api/conversations.py. The persistence layer
(service.py) returns raw rows; this layer joins them into the API contract
shape that api.py's response models validate against.
"""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status

from app.features.conversations import service


async def list_conversations(
    *,
    tenant_id: str,
    status_filter: str | None,
    limit: int,
    offset: int,
    role: str = "tenant_admin",
) -> list[dict[str, Any]]:
    return await service.list_conversations(
        tenant_id=tenant_id,
        status_filter=status_filter,
        limit=limit,
        offset=offset,
        role=role,
    )


async def get_conversation_detail(
    *, tenant_id: str, conversation_id: str, role: str = "tenant_admin"
) -> dict[str, Any]:
    rows = await service.get_conversation(
        tenant_id=tenant_id, conversation_id=conversation_id, role=role
    )
    if rows is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="conversation not found")

    conversation: dict[str, Any] = rows["conversation"]
    message_rows: list[dict[str, Any]] = rows["messages"]
    tool_rows: list[dict[str, Any]] = rows["tool_calls"]
    cost_rows: list[dict[str, Any]] = rows["cost_rows"]

    tool_calls_by_message: dict[UUID, list[dict[str, Any]]] = {}
    for row in tool_rows:
        tool_calls_by_message.setdefault(row["message_id"], []).append(
            {
                "id": row["id"],
                "tool_name": row["tool_name"],
                "arguments": json.loads(row["arguments"]),
                "result": json.loads(row["result"]) if row["result"] is not None else None,
                "success": row["success"],
                "latency_ms": row["latency_ms"],
            }
        )
    cost_by_message: dict[UUID, float] = {
        row["message_id"]: float(row["cost_usd"]) for row in cost_rows
    }

    messages = [
        {
            "id": row["id"],
            "role": row["role"],
            "content": row["content"],
            "agent_node": row["agent_node"],
            "created_at": row["created_at"],
            "metadata": json.loads(row["metadata"]) if row["metadata"] else {},
            "cost_usd": cost_by_message.get(row["id"]),
            "tool_calls": tool_calls_by_message.get(row["id"], []),
        }
        for row in message_rows
    ]

    return {
        "id": conversation["id"],
        "customer_ref": conversation["customer_ref"],
        "channel": conversation["channel"],
        "status": conversation["status"],
        "created_at": conversation["created_at"],
        "total_cost_usd": float(rows["total_cost"]),
        "messages": messages,
    }
