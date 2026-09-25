"""Operator export: everything Agencx holds for one tenant, as JSON on stdout.

This is how a data-portability request is answered (privacy page, T-032; process
in ``docs/agencx/deploy.md``). It is a script rather than an endpoint on purpose:
no route, no auth surface, no decision about who may pull a full PII dump over
HTTP. Connects as the owner like ``app.shared.migrate``, so every query names its
``tenant_id`` instead of leaning on RLS.

Rows are exported verbatim, including the whole ``tenant_config.config``
onboarding record, with two exceptions where a value is replaced by its size:

* ``tenant_assets.bytes`` -> ``bytes_length`` (the cover image; send it as a file)
* ``knowledge_chunks.embedding`` -> ``embedding_dims`` (derived data that would
  dwarf the document; ``tsv``, the search index, is dropped for the same reason)

Login emails live in GoTrue, not in Agencx tables, so they are not in here.

CLI: ``uv run python -m app.shared.export --slug SLUG > export.json``
(``make export SLUG=...``).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime
from typing import Any

import asyncpg

from app.shared.config import get_settings

# Every table that carries a tenant_id. tests/test_operator_export_offboard_db.py fails when a new
# migration adds one that is missing here, so a table can never silently escape
# the export or the offboarding receipt.
TENANT_TABLES: tuple[str, ...] = (
    "tenant_config",
    "users",
    "documents",
    "knowledge_chunks",
    "offerings",
    "offering_categories",
    "offering_category_memberships",
    "pricing_rules",
    "tenant_media",
    "tenant_assets",
    "conversations",
    "messages",
    "tool_calls",
    "escalations",
    "quotes",
    "orders",
    "cost_logs",
    "eval_runs",
)

# The jsonb expression that turns a row (aliased ``t``) into its exported form.
_ROW = {
    "tenant_assets": (
        "to_jsonb(t) - 'bytes' || jsonb_build_object('bytes_length', octet_length(t.bytes))"
    ),
    "knowledge_chunks": (
        "to_jsonb(t) - 'embedding' - 'tsv' "
        "|| jsonb_build_object('embedding_dims', vector_dims(t.embedding))"
    ),
}

NOTES = [
    "tenant_assets.bytes is replaced by bytes_length: the cover image is sent as a file",
    "knowledge_chunks.embedding is replaced by embedding_dims and tsv is dropped: derived data",
    "login emails live in the auth provider, not in Agencx tables, and are not included",
]


async def connect_json(dsn: str | None = None) -> asyncpg.Connection[Any]:
    """An owner connection that hands jsonb back as Python objects."""
    conn = await asyncpg.connect(dsn or get_settings().database_url)
    await conn.set_type_codec("jsonb", encoder=json.dumps, decoder=json.loads, schema="pg_catalog")
    return conn


async def find_tenant(conn: asyncpg.Connection[Any], slug: str) -> dict[str, Any]:
    """The tenant row for ``slug``; a typo is an error, never an empty export."""
    tenant: dict[str, Any] | None = await conn.fetchval(
        "select to_jsonb(t) from tenants t where t.slug = $1", slug
    )
    if tenant is None:
        raise LookupError(f"no tenant with slug {slug!r}")
    return tenant


async def export_tenant(slug: str, dsn: str | None = None) -> dict[str, Any]:
    conn = await connect_json(dsn)
    try:
        tenant = await find_tenant(conn, slug)
        tables: dict[str, list[dict[str, Any]]] = {}
        for table in TENANT_TABLES:
            row = _ROW.get(table, "to_jsonb(t)")
            rows: list[dict[str, Any]] = await conn.fetchval(
                f"select coalesce(jsonb_agg({row}), '[]'::jsonb) "  # noqa: S608
                f"from {table} t where t.tenant_id = $1",
                tenant["id"],
            )
            # Conversations read top to bottom; tables with no created_at keep DB order.
            tables[table] = sorted(rows, key=lambda r: str(r.get("created_at", "")))
        return {
            "exported_at": datetime.now(UTC).isoformat(),
            "tenant": tenant,
            "notes": NOTES,
            "tables": tables,
        }
    finally:
        await conn.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export one tenant's data as JSON.")
    parser.add_argument("--slug", required=True, help="the tenant to export")
    args = parser.parse_args(argv)
    try:
        document = asyncio.run(export_tenant(args.slug))
    except LookupError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(document, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
