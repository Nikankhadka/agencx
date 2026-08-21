"""O-2: the login-code lifecycle - issue and verify 6-digit email codes.

Deterministic by design: no model, no tenant isolation dependency. Only the
sha-256 hash of a code is ever persisted; the raw code is returned to the caller
for delivery. Verification is attempt-bounded, TTL-bounded, and single-use.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

from app.shared import db

CODE_TTL = timedelta(minutes=10)
MAX_ATTEMPTS = 5


class CodeError(RuntimeError):
    """Verification failed; ``kind`` selects the calm one-liner the client shows.

    ``invalid`` (wrong code or none outstanding), ``expired``, ``too_many``.
    """

    def __init__(self, kind: str):
        self.kind = kind
        super().__init__(kind)


def _hash(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


def _digest_matches(stored: str, code: str) -> bool:
    return hmac.compare_digest(stored, _hash(code))


async def issue_code(*, email: str, tenant_id: UUID | None = None) -> str:
    """Issue a fresh 6-digit code for ``email`` and return the raw code.

    Always succeeds (even for a duplicate/unknown email) so account existence
    never leaks. The previous outstanding code for the email is superseded by
    the newest row (verification only ever looks at the latest unverified row).
    """
    code = f"{secrets.randbelow(1_000_000):06d}"
    async with db.tenant_context(None, "service") as conn:
        await conn.execute(
            "insert into auth_codes (tenant_id, email, code_hash, expires_at) "
            "values ($1, $2, $3, now() + $4::interval)",
            tenant_id,
            email,
            _hash(code),
            CODE_TTL,
        )
    return code


async def verify_code(*, email: str, code: str) -> None:
    """Verify ``code`` against the latest outstanding code for ``email``.

    Raises :class:`CodeError` with a ``kind`` of ``invalid`` | ``expired`` |
    ``too_many``. A successful match marks the row verified (single-use).
    """
    async with db.tenant_context(None, "service") as conn:
        row = await conn.fetchrow(
            "select id, code_hash, expires_at, attempts from auth_codes "
            "where email = $1 and verified_at is null "
            "order by created_at desc limit 1",
            email,
        )
    if row is None:
        raise CodeError("invalid")
    if datetime.now(UTC) > row["expires_at"]:
        raise CodeError("expired")
    if row["attempts"] >= MAX_ATTEMPTS:
        raise CodeError("too_many")
    if not _digest_matches(row["code_hash"], code):
        async with db.tenant_context(None, "service") as conn:
            await conn.execute(
                "update auth_codes set attempts = attempts + 1 where id = $1", row["id"]
            )
        raise CodeError("invalid")
    async with db.tenant_context(None, "service") as conn:
        await conn.execute("update auth_codes set verified_at = now() where id = $1", row["id"])
