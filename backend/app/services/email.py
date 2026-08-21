"""O-2: the email-delivery seam.

The code-issuing backend owns delivery, so email is a provider abstraction
selected by env (``EMAIL_PROVIDER``), never a hardcoded vendor. ``console`` is
the default and the local-demo path: it logs the code instead of sending, since
the demo never sends real email. ``smtp`` covers real delivery via a standard
SMTP relay. Adding another vendor (e.g. Resend) is one more subclass.
"""

from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage

from app.shared.config import get_settings

logger = logging.getLogger("app.services.email")


class EmailProvider:
    """Sends a login code to ``email``."""

    async def send_login_code(self, *, email: str, code: str) -> None:
        raise NotImplementedError


class ConsoleEmailProvider(EmailProvider):
    """Local dev: log the code rather than sending (no SMTP in the demo).

    The last-issued code per email is also kept in memory so the local demo and
    E2E can retrieve it (the dev-login-code endpoint) - the "captured code" path
    from O-2 US-4. Never populated in production (EMAIL_PROVIDER=smtp).
    """

    async def send_login_code(self, *, email: str, code: str) -> None:
        _last_codes[email] = code
        logger.info("login code for %s: %s", email, code)


_last_codes: dict[str, str] = {}


def last_issued_code(email: str) -> str | None:
    return _last_codes.get(email)


class SmtpEmailProvider(EmailProvider):
    """Deliver via an SMTP relay (env: EMAIL_SMTP_*)."""

    def __init__(self, host: str, port: int, sender: str):
        self._host = host
        self._port = port
        self._sender = sender

    async def send_login_code(self, *, email: str, code: str) -> None:
        message = EmailMessage()
        message["Subject"] = "Your login code"
        message["From"] = self._sender
        message["To"] = email
        message.set_content(f"Your code is {code}.")
        # smtplib is synchronous; a login-code send is rare and tiny, so the
        # blocking call is acceptable here (run in a thread for real load).
        with smtplib.SMTP(self._host, self._port, timeout=15) as smtp:
            smtp.send_message(message)


def get_email_provider() -> EmailProvider:
    settings = get_settings()
    provider = settings.email_provider
    if provider == "console":
        return ConsoleEmailProvider()
    if provider == "smtp":
        if not settings.email_smtp_host or not settings.email_smtp_from:
            raise RuntimeError("EMAIL_PROVIDER=smtp requires EMAIL_SMTP_HOST and EMAIL_SMTP_FROM")
        return SmtpEmailProvider(
            settings.email_smtp_host,
            settings.email_smtp_port,
            settings.email_smtp_from,
        )
    raise RuntimeError(f"unknown EMAIL_PROVIDER {provider!r}; expected console or smtp")
