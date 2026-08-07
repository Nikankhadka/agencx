"""Fail-fast configuration guard, run once at app startup.

The migration runner already refuses the ``change-me`` DB password, and the
auth layer rejects an empty JWT secret on the first request - but nothing
stopped a misconfigured API from *booting* and only 500ing later. This guard
closes that gap: outside local/CI, placeholder or empty secrets abort startup
loudly instead of lying dormant until the first authed request.
"""

from __future__ import annotations

from app.shared.config import Settings

# Environments where placeholder secrets are expected and fine.
_DEV_ENVIRONMENTS = frozenset({"local", "ci", "test"})

# The placeholder the migration runner and Terraform both use; never valid live.
_PLACEHOLDER_DB_PASSWORD = "change-me"


class ConfigError(RuntimeError):
    """A production deployment is running with placeholder/empty secrets."""


def check_startup_config(settings: Settings) -> None:
    """Raise :class:`ConfigError` if a real deployment is missing required
    secrets. A no-op in local/CI, where defaults are expected."""
    if settings.environment.lower() in _DEV_ENVIRONMENTS:
        return

    missing: list[str] = []
    if not settings.supabase_jwt_secret:
        missing.append("SUPABASE_JWT_SECRET is empty")
    db_password = settings.wren_app_db_password
    if not db_password or db_password == _PLACEHOLDER_DB_PASSWORD:
        missing.append("WREN_APP_DB_PASSWORD is unset or still the 'change-me' placeholder")

    if missing:
        raise ConfigError(
            f"refusing to start in environment={settings.environment!r} with "
            f"insecure configuration: {'; '.join(missing)}"
        )
