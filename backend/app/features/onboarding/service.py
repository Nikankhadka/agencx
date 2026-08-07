"""Onboarding persistence: the ``tenant_config.config->onboarding`` record and
the one-shot confirm writes.

Moved from api/onboarding.py. All confirm writes happen inside one
``tenant_context`` transaction - a failing draft (e.g. a pricing rule without
a positive amount) raises and rolls the whole thing back, so a 422 never
leaves half-written catalog rows behind.
"""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from app.ingestion.pipeline import ingest_catalog_items
from app.llm.embedder import Embedder
from app.shared import db

_CONFIG_SELECT = "config->'onboarding'"


async def load_record(*, tenant_id: UUID) -> dict[str, Any]:
    async with db.tenant_context(tenant_id, "tenant_admin") as conn:
        raw = await conn.fetchval(
            f"select {_CONFIG_SELECT} from tenant_config where tenant_id = $1",
            tenant_id,
        )
    return json.loads(raw) if raw is not None else {}


async def set_onboarding_json(
    conn: db.AppConnection, tenant_id: UUID, record: dict[str, Any]
) -> None:
    await conn.execute(
        "update tenant_config set config = jsonb_set("
        "config, '{onboarding}', $2::jsonb, true), "
        "updated_at = now() where tenant_id = $1",
        tenant_id,
        json.dumps(record),
    )


async def save_record(*, tenant_id: UUID, record: dict[str, Any]) -> None:
    async with db.tenant_context(tenant_id, "tenant_admin") as conn:
        await set_onboarding_json(conn, tenant_id, record)


async def apply_confirmation(
    *,
    tenant_id: UUID,
    system_prompt: str,
    tone: str,
    escalation_threshold: float,
    services: list[dict[str, Any]],
    pricing_rules: list[dict[str, Any]],
    embedder: Embedder,
    completed_record: dict[str, Any],
) -> None:
    """Persist everything confirm() computed in one atomic transaction. Raises
    ValueError when any pricing rule lacks a positive amount - nothing is
    written."""
    async with db.tenant_context(tenant_id, "tenant_admin") as conn:
        await conn.execute(
            "update tenant_config set system_prompt=$2, tone=$3, "
            "escalation_threshold=$4, updated_at=now() where tenant_id=$1",
            tenant_id,
            system_prompt,
            tone,
            escalation_threshold,
        )
        for item in services:
            await conn.execute(
                "insert into catalog_items (tenant_id, name, description, "
                "price_cents) values ($1, $2, $3, $4)",
                tenant_id,
                item["name"],
                item["description"],
                item["price_cents"],
            )
        unpriced = sorted(
            rule["code"]
            for rule in pricing_rules
            if rule["unit_amount_cents"] is None or rule["unit_amount_cents"] <= 0
        )
        if unpriced:
            raise ValueError(f"pricing rules missing a positive amount: {sorted(set(unpriced))}")
        for rule in pricing_rules:
            await conn.execute(
                "insert into pricing_rules (tenant_id, code, label, "
                "unit_amount_cents, unit) values ($1, $2, $3, $4, $5)",
                tenant_id,
                rule["code"],
                rule["label"],
                rule["unit_amount_cents"],
                rule["unit"],
            )
        await ingest_catalog_items(conn, tenant_id=tenant_id, embedder=embedder)
        await set_onboarding_json(conn, tenant_id, completed_record)
