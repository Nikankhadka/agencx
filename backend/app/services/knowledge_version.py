"""P-4: the tenant's knowledge version - one derived timestamp, no new table.

The context package (P-3) is cached in-process keyed by ``(tenant_id,
knowledge_version)``; this is the half that makes the key safe. The version is
derived, never written: the max of the tenant's document timestamps and its
config row's ``updated_at``. Both are already trigger- or default-maintained, so
there is no new write path to drift and nothing to backfill.

What bumps it: an upload, a re-ingest (migration 0018's touch trigger), a
document delete, a profile/system-prompt/brand write (``tenant_config`` has had
a touch trigger since 0003). What does not: reading, chatting, or anything a
customer does.

Deterministic - no model, no LLM import. The caller owns the connection (and so
the ``tenant_context``): opening one here would nest it, which costs a second
pooled connection per call (see app/shared/db.py).
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from app.shared.db import AppConnection

# A tenant with no documents and (impossibly) no config row still needs a
# comparable version rather than None, so every lookup path is the same shape.
EPOCH_SQL = "'epoch'::timestamptz"

_VERSION_SQL = f"""
select greatest(
  coalesce((select max(updated_at) from documents where tenant_id = $1), {EPOCH_SQL}),
  coalesce((select updated_at from tenant_config where tenant_id = $1), {EPOCH_SQL}),
  coalesce((select max(updated_at) from catalog_items where tenant_id = $1), {EPOCH_SQL})
)
"""


async def knowledge_version(conn: AppConnection, tenant_id: UUID) -> datetime:
    """The tenant's current knowledge version.

    One indexed query (``documents`` is indexed by tenant, ``tenant_config`` is
    keyed by it), so a package lookup can afford to check it on every turn. The
    value is a timestamp - it carries no tenant content, so it is safe to use as
    a cache key and to log.
    """
    version: datetime = await conn.fetchval(_VERSION_SQL, tenant_id)
    return version
