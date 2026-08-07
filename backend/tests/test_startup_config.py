"""The fail-fast startup guard (app/core/startup.py).

A real deployment must not boot with placeholder/empty secrets and only 500 on
the first authed request - it should refuse to start.
"""

from __future__ import annotations

import pytest

from app.shared.config import Settings
from app.shared.startup import ConfigError, check_startup_config


def _settings(**overrides: object) -> Settings:
    base: dict[str, object] = {
        "environment": "production",
        "supabase_jwt_secret": "a-real-secret",
        "wren_app_db_password": "a-real-password",
    }
    base.update(overrides)
    return Settings(**base)  # type: ignore[arg-type]


def test_local_environment_tolerates_placeholder_secrets() -> None:
    # The default dev posture: empty/placeholder secrets are expected and fine.
    check_startup_config(
        _settings(
            environment="local",
            supabase_jwt_secret="",
            wren_app_db_password="change-me",
        )
    )


def test_ci_environment_is_also_exempt() -> None:
    check_startup_config(_settings(environment="ci", supabase_jwt_secret=""))


def test_production_rejects_empty_jwt_secret() -> None:
    with pytest.raises(ConfigError, match="SUPABASE_JWT_SECRET"):
        check_startup_config(_settings(supabase_jwt_secret=""))


def test_production_rejects_placeholder_db_password() -> None:
    with pytest.raises(ConfigError, match="WREN_APP_DB_PASSWORD"):
        check_startup_config(_settings(wren_app_db_password="change-me"))


def test_production_with_real_secrets_passes() -> None:
    check_startup_config(_settings())
