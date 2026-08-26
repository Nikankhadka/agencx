"""O-2: SMTP delivery, specifically the credentials path.

The two relays in play need opposite treatment and are the same class: Mailpit
(``make mail``) refuses STARTTLS and AUTH, while every hosted relay requires
both. Whether credentials are configured is the only thing that separates them,
so these tests pin that switch - getting it wrong fails in opposite directions,
and neither direction is visible from a passing local demo.
"""

from __future__ import annotations

import smtplib
from email.message import EmailMessage
from types import TracebackType

import pytest

from app.services import email as email_service
from app.shared.config import get_settings


class _FakeSMTP:
    """Records what a provider does to a connection, in order."""

    instances: list[_FakeSMTP] = []

    def __init__(self, host: str, port: int, timeout: int = 0) -> None:
        self.host = host
        self.port = port
        self.calls: list[str] = []
        self.message: EmailMessage | None = None
        _FakeSMTP.instances.append(self)

    def __enter__(self) -> _FakeSMTP:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        return None

    def starttls(self) -> None:
        self.calls.append("starttls")

    def login(self, user: str, password: str) -> None:
        self.calls.append(f"login:{user}:{password}")

    def send_message(self, message: EmailMessage) -> None:
        self.calls.append("send")
        self.message = message


@pytest.fixture
def fake_smtp(monkeypatch: pytest.MonkeyPatch) -> type[_FakeSMTP]:
    _FakeSMTP.instances = []
    monkeypatch.setattr(smtplib, "SMTP", _FakeSMTP)
    return _FakeSMTP


async def test_credentials_upgrade_the_connection_before_sending(
    fake_smtp: type[_FakeSMTP],
) -> None:
    """Order matters: a hosted relay rejects AUTH on a connection that is still
    in the clear, so STARTTLS has to come first and both before the message."""
    provider = email_service.SmtpEmailProvider(
        "smtp.resend.com", 587, "login@agencx.app", user="resend", password="re_key"
    )

    await provider.send_login_code(email="owner@example.com", code="123456")

    assert fake_smtp.instances[0].calls == ["starttls", "login:resend:re_key", "send"]


async def test_a_relay_without_credentials_is_not_authenticated(
    fake_smtp: type[_FakeSMTP],
) -> None:
    """Mailpit speaks neither, and offering either raises - so the local inbox
    path has to stay a bare send."""
    provider = email_service.SmtpEmailProvider("localhost", 1025, "login@agencx.local")

    await provider.send_login_code(email="owner@example.com", code="123456")

    assert fake_smtp.instances[0].calls == ["send"]


async def test_a_half_configured_relay_does_not_attempt_auth(
    fake_smtp: type[_FakeSMTP],
) -> None:
    """A user with no password cannot authenticate, and calling login() with an
    empty secret asks the relay to reject us. Treat it as unconfigured."""
    provider = email_service.SmtpEmailProvider(
        "localhost", 1025, "login@agencx.local", user="resend"
    )

    await provider.send_login_code(email="owner@example.com", code="123456")

    assert fake_smtp.instances[0].calls == ["send"]


def test_the_provider_is_built_with_the_configured_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The seam is only useful if get_email_provider actually carries the
    credentials through - the deployed stack reads them from env, nowhere else."""
    for key, value in {
        "EMAIL_PROVIDER": "smtp",
        "EMAIL_SMTP_HOST": "smtp.resend.com",
        "EMAIL_SMTP_FROM": "login@agencx.app",
        "EMAIL_SMTP_USER": "resend",
        "EMAIL_SMTP_PASSWORD": "re_key",
    }.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()

    try:
        provider = email_service.get_email_provider()
        assert isinstance(provider, email_service.SmtpEmailProvider)
        assert provider._user == "resend"
        assert provider._password == "re_key"
    finally:
        get_settings.cache_clear()
