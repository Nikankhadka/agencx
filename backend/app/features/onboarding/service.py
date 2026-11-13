"""Onboarding persistence: the ``tenant_config.config->onboarding`` record and
the one-shot confirm writes.

Moved from api/onboarding.py. All confirm writes happen inside one
``tenant_context`` transaction, so a failure never leaves a tenant half
published.
"""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

import asyncpg

from app.features.business import service as business_service
from app.features.business.service import reconcile_offerings_batch
from app.features.knowledge import service as knowledge_service
from app.features.onboarding import selling_modes
from app.features.tenants import service as tenant_service
from app.llm.embedder import Embedder
from app.onboarding.flow import PendingOffering
from app.shared import db

_CONFIG_SELECT = "config->'onboarding'"


class PublicSlugTakenError(RuntimeError):
    """The requested public page address belongs to another tenant."""


class RevisionConflictError(RuntimeError):
    """Another request checkpointed this tenant's onboarding first."""


async def load_record(*, tenant_id: UUID) -> dict[str, Any]:
    async with db.tenant_context(tenant_id, "tenant_admin") as conn:
        raw = await conn.fetchval(
            f"select {_CONFIG_SELECT} from tenant_config where tenant_id = $1",
            tenant_id,
        )
    return json.loads(raw) if raw is not None else {}


async def set_onboarding_json(
    conn: db.AppConnection,
    tenant_id: UUID,
    record: dict[str, Any],
    *,
    expected_revision: int | None = None,
    profile_patch: dict[str, Any] | None = None,
    ordering: dict[str, Any] | None = None,
) -> None:
    where = "where tenant_id = $1"
    args: list[Any] = [tenant_id, json.dumps(record)]
    # The profile lives in two jsonb copies. A batch that carries profile edits
    # writes both in this one statement, the way write_profile does - one
    # statement is what keeps them from silently diverging.
    target = "config"
    if profile_patch is not None:
        args.append(json.dumps(profile_patch))
        target = (
            "jsonb_set(config, '{profile}', "
            f"coalesce(config->'profile', '{{}}'::jsonb) || ${len(args)}::jsonb, true)"
        )
    # 32: the selling-mode confirmation writes `config.ordering` and the
    # onboarding record together. One UPDATE is what makes "the mode was asked"
    # and "the product has a mode" the same fact rather than two that can drift.
    if ordering is not None:
        args.append(json.dumps(ordering))
        target = f"jsonb_set({target}, '{{ordering}}', ${len(args)}::jsonb, true)"
    if expected_revision is not None:
        args.append(expected_revision)
        where += f" and coalesce((config->'onboarding'->>'revision')::bigint, 0) = ${len(args)}"
    result = await conn.execute(
        f"update tenant_config set config = jsonb_set("
        f"{target}, '{{onboarding}}', $2::jsonb, true), "
        f"updated_at = now() {where}",
        *args,
    )
    if expected_revision is not None and result != "UPDATE 1":
        raise RevisionConflictError


async def save_record(
    *,
    tenant_id: UUID,
    record: dict[str, Any],
    profile_patch: dict[str, Any] | None = None,
    ordering: dict[str, Any] | None = None,
) -> None:
    expected_revision = int(record.get("revision", 0) or 0)
    record["revision"] = expected_revision + 1
    async with db.tenant_context(tenant_id, "tenant_admin") as conn:
        await set_onboarding_json(
            conn,
            tenant_id,
            record,
            expected_revision=expected_revision,
            profile_patch=profile_patch,
            ordering=ordering,
        )


async def load_ordering_config(*, tenant_id: UUID) -> dict[str, Any] | None:
    """The stored ``config.ordering`` block, or None before it was written.

    None is the honest absence: no selling mode has been confirmed, so the
    review card shows nothing rather than an empty object that would read like a
    tenant configured to sell nothing.
    """
    async with db.tenant_context(tenant_id, "tenant_admin") as conn:
        raw = await conn.fetchval(
            "select config->'ordering' from tenant_config where tenant_id = $1",
            tenant_id,
        )
    if raw is None:
        return None
    parsed = json.loads(raw) if isinstance(raw, str) else raw
    return parsed if isinstance(parsed, dict) else None


async def load_selling_mode_material(
    *, tenant_id: UUID, record: dict[str, Any]
) -> selling_modes.SourceMaterial:
    """Everything the inference may read, gathered from what onboarding stored.

    The source text is the documents' own sections, so the nav words an owner's
    page uses ("Order online", "Book now") reach the scorer; the profile and the
    reviewed offerings come from the record, which is the same data the review
    sheet showed. Categories are included because an owner who filed their
    offerings under "Treatments" has said something the source text alone does
    not.
    """
    documents = await knowledge_service.list_records(tenant_id=tenant_id)
    source_text = " ".join(
        f"{section.get('heading', '')} {section.get('body', '')}"
        for document in documents
        for section in document.get("sections", [])
    )
    draft = record.get("draft", {}) if isinstance(record.get("draft"), dict) else {}
    offerings = [
        " ".join(str(item.get(key, "")) for key in ("name", "description"))
        for item in record.get("offering_candidates", [])
        if isinstance(item, dict)
    ]
    category_names = [
        str(category["name"])
        for category in await business_service.list_categories(tenant_id=tenant_id)
    ]
    return selling_modes.SourceMaterial(
        source_text=source_text,
        profile=draft,
        offerings=tuple(offerings),
        categories=tuple(category_names),
    )


async def apply_confirmation(
    *,
    tenant_id: UUID,
    business_name: str,
    slug: str,
    profile: dict[str, Any],
    customer_voice: dict[str, Any],
    completed_record: dict[str, Any],
    offering_candidates: list[PendingOffering] | None = None,
    embedder: Embedder | None = None,
) -> None:
    """Persist what confirm() computed in one atomic transaction.

    O-1 captures a business profile, not a priced catalog: onboarding no longer
    writes offerings or pricing_rules, and `payment_processing_mode` keeps its
    schema default until a screen edits it. Priced answers come from the owner's
    uploaded material instead (C-1).

    W-9 writes ``customer_voice`` beside ``profile``: the structured voice the
    customer assistant speaks in, written in the same transaction so a confirmed
    tenant is never live without one. W-10 dropped the free-text
    ``system_prompt``/``tone`` columns this used to set alongside them.
    """
    old_slug: str | None = None
    async with db.tenant_context(tenant_id, "tenant_admin") as conn:
        old_slug = await conn.fetchval("select slug from tenants where id = $1", tenant_id)
        await conn.execute(
            "update tenant_config set config = jsonb_set("
            "jsonb_set(config, '{profile}', $2::jsonb, true), "
            "'{customer_voice}', $3::jsonb, true), "
            "updated_at=now() where tenant_id=$1",
            tenant_id,
            json.dumps(profile),
            json.dumps(customer_voice),
        )
        try:
            await conn.execute(
                "update tenants set business_name=$2, slug=$3 where id=$1",
                tenant_id,
                business_name,
                slug,
            )
        except asyncpg.UniqueViolationError as exc:
            raise PublicSlugTakenError from exc
        await set_onboarding_json(conn, tenant_id, completed_record)
        if offering_candidates:
            if embedder is None:
                raise RuntimeError("an embedder is required to publish offerings")
            await reconcile_offerings_batch(
                conn=conn,
                tenant_id=tenant_id,
                offerings=[item.model_dump() for item in offering_candidates],
                embedder=embedder,
            )
    if old_slug:
        tenant_service.invalidate_slug_cache(old_slug)
    tenant_service.invalidate_slug_cache(slug)


async def publish_reviewed_offerings(
    *, tenant_id: UUID, offerings: list[PendingOffering], embedder: Embedder
) -> None:
    """Publish owner-approved suggestions for an already-live tenant."""
    if not offerings:
        return
    async with db.tenant_context(tenant_id, "tenant_admin") as conn:
        await reconcile_offerings_batch(
            conn=conn,
            tenant_id=tenant_id,
            offerings=[item.model_dump() for item in offerings],
            embedder=embedder,
        )
