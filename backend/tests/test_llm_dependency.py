"""get_llm_provider wiring: LLM_PROVIDER / LLM_FALLBACK_PROVIDER select the
vendor behavior for each failover position, purely by env.

The provider class itself is tested elsewhere (test_llm_zai.py,
test_llm_provider_retry.py); this file pins the factory's routing: one
universal OpenAICompatProvider, with the 'zai' role distinguished only by the
quirks the factory applies (json_object extract mode, thinking disabled, Z.ai
base URL default).
"""

from __future__ import annotations

from typing import Any

import pytest

from app.core.config import Settings
from app.llm import dependency
from app.llm.failover import FailoverProvider
from app.llm.openai_compat import OpenAICompatProvider
from app.llm.provider import LLMProvider

_THINKING_OFF = {"thinking": {"type": "disabled"}}


def _wired(monkeypatch: pytest.MonkeyPatch, **settings_kwargs: Any) -> LLMProvider:
    # The wiring tests must not read backend/.env (real keys, real models) -
    # each call passes every LLM_* field explicitly, including empty values
    # where the test intends "unset" (init kwargs beat dotenv values).
    monkeypatch.setattr(dependency, "get_settings", lambda: Settings(**settings_kwargs))
    return dependency.get_llm_provider()


def test_zai_primary_with_openai_compat_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = _wired(
        monkeypatch,
        llm_provider="zai",
        llm_api_key="k",
        llm_model="glm-4.7-flash",
        llm_fallback_provider="openai_compat",
        llm_fallback_base_url="https://openrouter.example.test/v1",
        llm_fallback_api_key="k2",
        llm_fallback_model="google/gemma-4-26b-a4b-it:free",
    )
    assert isinstance(provider, FailoverProvider)
    primary = provider._primary
    assert isinstance(primary, OpenAICompatProvider)
    assert primary._model == "glm-4.7-flash"
    assert primary._json_object_extract is True
    assert primary._extra_body == _THINKING_OFF
    fallback = provider._fallback
    assert isinstance(fallback, OpenAICompatProvider)
    assert fallback._model == "google/gemma-4-26b-a4b-it:free"
    assert fallback._json_object_extract is False
    assert fallback._extra_body == {}
    assert str(fallback._client.base_url).startswith("https://openrouter.example.test")
    assert provider.supports_tools is True


def test_openai_compat_primary_with_default_zai_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The pre-existing pairing must keep wiring exactly as before; an empty
    fallback base URL defaults to the Z.ai endpoint."""
    provider = _wired(
        monkeypatch,
        llm_provider="openai_compat",
        llm_base_url="https://openrouter.example.test/v1",
        llm_api_key="k",
        llm_model="google/gemma-4-26b-a4b-it:free",
        llm_fallback_api_key="k2",
        llm_fallback_model="glm-4.7-flash",
        llm_fallback_provider="zai",
        llm_fallback_base_url="",
    )
    assert isinstance(provider, FailoverProvider)
    assert isinstance(provider._primary, OpenAICompatProvider)
    fallback = provider._fallback
    assert isinstance(fallback, OpenAICompatProvider)
    assert fallback._model == "glm-4.7-flash"
    assert fallback._json_object_extract is True
    assert fallback._extra_body == _THINKING_OFF
    assert str(fallback._client.base_url).endswith("api.z.ai/api/paas/v4/")


def test_no_fallback_configuration_returns_the_plain_primary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = _wired(
        monkeypatch,
        llm_provider="openai_compat",
        llm_base_url="https://openrouter.example.test/v1",
        llm_api_key="k",
        llm_model="m",
        llm_fallback_api_key="",
        llm_fallback_model="",
        llm_fallback_base_url="",
    )
    assert isinstance(provider, OpenAICompatProvider)
    assert not isinstance(provider, FailoverProvider)
