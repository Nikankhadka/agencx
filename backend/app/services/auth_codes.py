"""O-2: the login-code lifecycle - issue and verify 6-digit email codes.

Deterministic by design: no model, no tenant isolation dependency. Only the
sha-256 hash of a code is ever persisted; the raw code is returned to the caller
for delivery. Verification is attempt-bounded, TTL-bounded, and single-use, and
issuance is rate-bounded per address.
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
# Issuance ceiling per address. Same number as MAX_ATTEMPTS deliberately: one
# figure to remember, and both answer the same question - how much abuse one
# email address is allowed to generate before we stop.
ISSUE_WINDOW = timedelta(hours=1)
MAX_CODES_PER_WINDOW = 5


class CodeError(RuntimeError):
    """Issue or verification failed; ``kind`` selects the one-liner the client shows.

    ``invalid`` (wrong code or none outstanding), ``expired``, ``too_many``,
    ``rate_limited`` (too many codes requested for one address).
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

    Succeeds for a duplicate or unknown email so account existence never leaks;
    the only refusal is the rate limit, which is keyed on an address the caller
    already supplied and therefore tells them nothing they did not know. The
    previous outstanding code is superseded by the newest row (verification only
    ever looks at the latest unverified row).

    Raises :class:`CodeError` with kind ``rate_limited`` past the ceiling. This
    endpoint is unauthenticated and, once a real relay is configured, sends mail
    to whatever address it is handed - without a cap it is an open email relay
    that would drain a free tier in a minute and get the account suspended.

    ponytail: per-address only, so rotating addresses walks around it. That
    still bounds what any single mailbox can be made to receive, which is the
    part that gets a sender blacklisted. Per-IP is the upgrade, and needs
    request-context plumbing this layer deliberately has none of.
    """
    code = f"{secrets.randbelow(1_000_000):06d}"
    async with db.tenant_context(None, "service") as conn:
        # Served by auth_codes_email_created_idx (email, created_at desc).
        recent = await conn.fetchval(
            "select count(*) from auth_codes "
            "where email = $1 and created_at > now() - $2::interval",
            email,
            ISSUE_WINDOW,
        )
        if int(recent) >= MAX_CODES_PER_WINDOW:
            raise CodeError("rate_limited")
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
