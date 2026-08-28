"""The tenant slug rule: shape, and the names a tenant may not take.

One module because the rule has three enforcement points that must agree - the
DDL check on ``tenants.slug`` (migration 0003), tenant signup, and platform
provisioning. The last two used to carry their own copy of the regex and of the
validator body; they import from here instead.
"""

from __future__ import annotations

import re
import unicodedata

# Mirrors the DDL check on tenants.slug (database.md section 3) exactly, so a
# bad slug is rejected at the API layer (422) before it can reach the insert.
SLUG_PATTERN = r"^[a-z0-9](-?[a-z0-9])*$"
_SLUG_RE = re.compile(SLUG_PATTERN)

# A tenant is addressed at `/{slug}` (D22), so a slug that matches a route the
# frontend already serves would be shadowed by it - Next resolves static
# segments before the dynamic one, and the tenant would simply be unreachable.
# These are the frontend's top-level routes plus the two names infrastructure
# will always want.
#
# Kept in sync by `frontend/src/lib/reserved-slugs.test.ts`, which reads the
# route directories and fails if one is missing here.
#
# Names starting with `_` (`_next`) need no entry: the pattern above already
# rejects them.
RESERVED_SLUGS = frozenset(
    {
        "admin",
        "api",
        "business",
        "chats",
        "conversations",
        "dashboards",
        "escalations",
        "home",
        "knowledge",
        "login",
        "onboarding",
        "pricing",
        "settings",
        "signup",
        "www",
    }
)


def validate_slug(value: str) -> str:
    """Return ``value`` unchanged, or raise ``ValueError`` describing the break.

    Used as a pydantic ``field_validator`` body, so the message it raises is
    what the caller sees in the 422.
    """
    if not _SLUG_RE.fullmatch(value):
        raise ValueError(f"slug must match {SLUG_PATTERN}")
    if value in RESERVED_SLUGS:
        raise ValueError("that name is reserved; please choose another")
    return value


def suggested_slug(value: str) -> str:
    """Turn a business name into the editable suggestion for its public URL."""
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", normalized.lower()).strip("-")
    return slug[:40].rstrip("-") or "business"
