"""Shared helpers for the direct-DB seeds (F-3 dedup).

Every seed repeats the same skeleton: pool creation/teardown, wipe-by-slug,
the service-context tenants + tenant_config insert, the offerings /
pricing_rules / orders loops, the conversations / messages / tool calls /
costs / escalations inserts, and the storage + ingestion-pipeline knowledge
upload. These helpers keep the seeds to their data and their story; behavior
is byte-identical to what each seed did inline (seed tests pin the counts).
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from app.features.business.offering_candidates import normalize_name
from app.features.escalations.service import RESOLUTION_STAMP
from app.ingestion.pipeline import ingest_offerings, process_document
from app.llm.embedder import Embedder
from app.onboarding.agent import OnboardingRecord
from app.onboarding.flow import ProfileDraft, customer_voice_for
from app.shared import db
from app.shared.config import get_settings
from app.shared.storage import document_key, get_storage

if TYPE_CHECKING:
    from app.shared.db import AppConnection


@asynccontextmanager
async def seed_pool() -> AsyncIterator[None]:
    """The pool boilerplate every direct-DB seed repeats: create the wren_app
    pool if none exists, close it on exit if this call created it."""
    created_pool = False
    try:
        db.get_pool()
    except RuntimeError:
        await db.create_pool()
        created_pool = True
    try:
        yield
    finally:
        if created_pool:
            await db.close_pool()


async def wipe_tenant(conn: AppConnection, slug: str) -> None:
    """Delete a tenant by slug (cascade wipes its data). A no-op when the
    slug is not present, which is what makes re-seeding idempotent."""
    existing_id = await conn.fetchval("select id from tenants where slug = $1", slug)
    if existing_id is not None:
        await conn.execute("delete from tenants where id = $1", existing_id)


async def insert_tenant_core(
    *,
    tenant_id: UUID,
    slug: str,
    name: str,
    brand: dict[str, Any] | None = None,
    config: dict[str, Any] | None = None,
    enabled_tools: list[str] | None = None,
    business_name: str | None = None,
    profile: dict[str, Any] | None = None,
) -> None:
    """The service-context tenants + tenant_config insert every seed starts with.

    ``enabled_tools`` is only included when given - the column's lean default
    (D-2) is the honest value for a tenant that never opted into the commerce
    tools, and writing it explicitly would blur that signal.

    ``profile`` pre-onboards the tenant: when given, the tenants row gains its
    ``business_name`` and the tenant_config row is written exactly as a real
    onboarding confirm leaves it (``profile``, ``customer_voice`` and a
    completed ``onboarding`` record in ``config``), so a seeded demo tenant
    never shows the interview. Built from the same dataclasses the confirm
    path uses - no duplicated shape to drift.
    """
    merged_config = dict(config or {})
    if profile is not None:
        business_name = business_name or profile.get("business_name")
        draft = ProfileDraft(**profile)
        merged_config["profile"] = draft.model_dump()
        merged_config["customer_voice"] = customer_voice_for(draft)
        merged_config["onboarding"] = OnboardingRecord(draft=profile, completed=True).to_jsonb()

    async with db.tenant_context(None, "service") as conn:
        await conn.execute(
            "insert into tenants (id, slug, name, business_name, status) "
            "values ($1, $2, $3, $4, 'active')",
            tenant_id,
            slug,
            name,
            business_name,
        )
        if enabled_tools is None:
            await conn.execute(
                "insert into tenant_config (tenant_id, brand, config) values ($1, $2, $3)",
                tenant_id,
                json.dumps(brand) if brand is not None else "{}",
                json.dumps(merged_config),
            )
        else:
            await conn.execute(
                "insert into tenant_config (tenant_id, brand, config, enabled_tools) "
                "values ($1, $2, $3, $4)",
                tenant_id,
                json.dumps(brand) if brand is not None else "{}",
                json.dumps(merged_config),
                json.dumps(enabled_tools),
            )


async def insert_offerings(
    conn: AppConnection,
    tenant_id: UUID,
    catalog: list[tuple[str, str, int | None, list[str]]],
) -> None:
    """(name, description, price_cents, ordered categories) rows.

    The label is written beside the category row it belongs to (D28), so a
    seeded world has the shape production writes and an owner can rename a
    seeded category the same way they rename one they created.
    """
    for position, (name, description, price_cents, categories) in enumerate(catalog):
        category_rows: list[tuple[UUID, str]] = []
        for category in categories:
            category_id = await conn.fetchval(
                "insert into offering_categories (tenant_id, name, normalized_key) "
                "values ($1, $2, $3) on conflict (tenant_id, normalized_key) "
                "do update set name = offering_categories.name returning id",
                tenant_id,
                category.strip(),
                normalize_name(category),
            )
            category_rows.append((category_id, category.strip()))
        offering_id = await conn.fetchval(
            "insert into offerings "
            "(tenant_id, name, description, price_cents, position, category, category_id) "
            "values ($1, $2, $3, $4, $5, $6, $7) returning id",
            tenant_id,
            name,
            description,
            price_cents,
            position,
            category_rows[0][1] if category_rows else None,
            category_rows[0][0] if category_rows else None,
        )
        for category_position, (category_id, _) in enumerate(category_rows):
            await conn.execute(
                "insert into offering_category_memberships "
                "(tenant_id, offering_id, category_id, position, is_primary) "
                "values ($1, $2, $3, $4, $5)",
                tenant_id,
                offering_id,
                category_id,
                category_position,
                category_position == 0,
            )


async def insert_media(
    conn: AppConnection,
    tenant_id: UUID,
    cover: dict[str, str] | None,
    offering_media: dict[str, dict[str, str]],
) -> None:
    """Cloudinary photo rows from a committed manifest (``{url, public_id}``).

    ``offering_media`` is keyed by offering name; the seed makes no Cloudinary
    call, it only records URLs a one-off upload script already produced.
    """
    if cover:
        await conn.execute(
            "insert into tenant_media (tenant_id, role, type, provider, url, public_id) "
            "values ($1, 'cover', 'image', 'cloudinary', $2, $3)",
            tenant_id,
            cover["url"],
            cover["public_id"],
        )
    rows = await conn.fetch("select id, name from offerings where tenant_id = $1", tenant_id)
    ids = {row["name"]: row["id"] for row in rows}
    for name, media in offering_media.items():
        await conn.execute(
            "insert into tenant_media "
            "(tenant_id, offering_id, role, type, provider, url, public_id) "
            "values ($1, $2, 'offering', 'image', 'cloudinary', $3, $4)",
            tenant_id,
            ids[name],
            media["url"],
            media["public_id"],
        )


async def insert_pricing_rules(
    conn: AppConnection, tenant_id: UUID, rules: list[tuple[str, str, int, str]]
) -> None:
    """(code, label, unit_amount_cents, unit) rows."""
    for code, label, unit_amount_cents, unit in rules:
        await conn.execute(
            "insert into pricing_rules (tenant_id, code, label, unit_amount_cents, unit) "
            "values ($1, $2, $3, $4, $5)",
            tenant_id,
            code,
            label,
            unit_amount_cents,
            unit,
        )


async def insert_orders(
    conn: AppConnection,
    tenant_id: UUID,
    rows: list[tuple[str, str, str, str, dict[str, Any]]],
) -> None:
    """(ref_code, kind, customer_ref, status, details) rows."""
    for ref_code, kind, customer_ref, status, details in rows:
        await conn.execute(
            "insert into orders (tenant_id, ref_code, kind, customer_ref, status, details) "
            "values ($1, $2, $3, $4, $5, $6)",
            tenant_id,
            ref_code,
            kind,
            customer_ref,
            status,
            json.dumps(details),
        )


async def seed_conversations(
    conn: AppConnection,
    tenant_id: UUID,
    specs: list[dict[str, Any]],
) -> None:
    """Conversation specs -> conversations, messages, tool calls, cost logs and
    escalations, in the exact shape a real chat leaves behind.

    One spec is::

        {
            "customer_ref": str, "status": str, "created_at": datetime,
            "customer_email": str | None,          # optional, ticket 19
            "messages": [(role, content, agent_node, metadata, offset_seconds)],
            "tool_calls": [{"on_message_index", "tool_name", "arguments",
                            "result", "success", "latency_ms"}],
            "escalation": {"reason", "status", "summary", "intent"} | None,
        }

    Every timestamp is explicit: ``now()`` is constant inside one
    ``tenant_context`` transaction, and ordering plus the cost attribution
    lateral join both depend on message time. A cost_log is placed just after
    each assistant message, and a resolved escalation writes the owner-only
    resolution stamp before its trailing human_agent reply, matching
    ``escalations/service.py``.
    """
    model = get_settings().llm_model or "demo-model"
    for spec in specs:
        conv_id = uuid4()
        created_at = spec["created_at"]
        assert isinstance(created_at, datetime)
        await conn.execute(
            "insert into conversations "
            "(id, tenant_id, customer_ref, customer_email, channel, status, created_at) "
            "values ($1, $2, $3, $4, 'web', $5, $6)",
            conv_id,
            tenant_id,
            spec["customer_ref"],
            spec.get("customer_email"),
            spec["status"],
            created_at,
        )

        messages: list[tuple[str, str, str | None, dict[str, Any] | None, int]] = spec["messages"]
        message_ids: list[UUID] = []
        msg_time = created_at
        escalation: dict[str, Any] | None = spec.get("escalation")
        # RF-16 consistency: a real resolution writes the owner-only stamp
        # before the optional human_agent reply (escalations/service.py). Seed
        # the same pair so the demo world matches shipped behavior instead of
        # carrying a bare human_agent message with no stamp.
        stamp_before_human = escalation is not None and escalation["status"] == "resolved"
        for role, content, agent_node, metadata, offset in messages:
            msg_time = created_at + timedelta(seconds=offset)
            if stamp_before_human and role == "human_agent":
                await conn.execute(
                    "insert into messages (id, tenant_id, conversation_id, role, content, "
                    "created_at) values ($1, $2, $3, 'system', $4, $5)",
                    uuid4(),
                    tenant_id,
                    conv_id,
                    RESOLUTION_STAMP,
                    msg_time - timedelta(seconds=1),
                )
            msg_id = uuid4()
            message_ids.append(msg_id)
            await conn.execute(
                "insert into messages (id, tenant_id, conversation_id, role, content, "
                "agent_node, created_at, metadata) "
                "values ($1, $2, $3, $4, $5, $6, $7, $8)",
                msg_id,
                tenant_id,
                conv_id,
                role,
                content,
                agent_node,
                msg_time,
                json.dumps(metadata) if metadata is not None else "{}",
            )
            # A cost_log for every assistant turn, placed just after the
            # message's created_at so the lateral-join window in
            # conversations.py attributes it to this message.
            if role == "assistant":
                cost_time = msg_time + timedelta(seconds=2)
                await conn.execute(
                    "insert into cost_logs (tenant_id, conversation_id, model, "
                    "input_tokens, output_tokens, cost_usd, created_at) "
                    "values ($1, $2, $3, $4, $5, $6, $7)",
                    tenant_id,
                    conv_id,
                    model,
                    1200,
                    180,
                    0.0021,
                    cost_time,
                )

        for tc in spec.get("tool_calls", []):
            target_msg = message_ids[tc["on_message_index"]]
            tc_id = uuid4()
            await conn.execute(
                "insert into tool_calls (id, tenant_id, message_id, tool_name, arguments, "
                "result, success, latency_ms, created_at) "
                "values ($1, $2, $3, $4, $5, $6, $7, $8, $9)",
                tc_id,
                tenant_id,
                target_msg,
                tc["tool_name"],
                json.dumps(tc["arguments"]),
                json.dumps(tc["result"]),
                tc["success"],
                tc["latency_ms"],
                # Place the tool call a hair before the assistant message it
                # belongs to (the assistant turn follows the tool result).
                created_at + timedelta(seconds=tc["on_message_index"]) - timedelta(seconds=1),
            )

        if escalation is not None:
            esc_id = uuid4()
            esc_created = created_at + timedelta(seconds=16)
            status = escalation["status"]
            resolved_at = None
            if status == "resolved":
                # Resolved escalation: resolved_at set, and the trailing
                # human_agent message (last in the spec) is the resolution reply.
                resolved_at = msg_time + timedelta(seconds=30)
            await conn.execute(
                "insert into escalations (id, tenant_id, conversation_id, reason, summary, "
                "intent, status, created_at, resolved_at) "
                "values ($1, $2, $3, $4, $5, $6, $7, $8, $9)",
                esc_id,
                tenant_id,
                conv_id,
                escalation["reason"],
                escalation.get("summary"),
                escalation.get("intent"),
                status,
                esc_created,
                resolved_at,
            )


async def ingest_documents(
    conn: AppConnection,
    tenant_id: UUID,
    docs: list[tuple[str, str, str]],
    embedder: Embedder,
) -> None:
    """(filename, doc_type, content) rows through the real ingestion pipeline:
    storage.put, a 'pending' documents row, process_document for each, then
    the synthetic catalog document from the tenant's offerings."""
    for filename, doc_type, content in docs:
        document_id = uuid4()
        await get_storage().put(
            document_key(tenant_id, document_id, ".md"), content.encode("utf-8")
        )
        await conn.execute(
            "insert into documents (id, tenant_id, filename, doc_type, status) "
            "values ($1, $2, $3, $4, 'pending')",
            document_id,
            tenant_id,
            filename,
            doc_type,
        )
        await process_document(
            conn, tenant_id=tenant_id, document_id=document_id, embedder=embedder
        )

    await ingest_offerings(conn, tenant_id=tenant_id, embedder=embedder)
