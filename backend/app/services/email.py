"""O-2: the email-delivery seam.

The code-issuing backend owns delivery, so email is a provider abstraction
selected by env (``EMAIL_PROVIDER``), never a hardcoded vendor. ``console`` is
the default and the local-demo path: it logs the code instead of sending, since
the demo never sends real email. ``smtp`` covers real delivery via a standard
SMTP relay - in production, and locally against Mailpit (``make mail``) when the
code should land in a real inbox. Adding another vendor (e.g. Resend) is one
more subclass.
"""

from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage

from app.shared.config import get_settings

logger = logging.getLogger("app.services.email")


class LoginCodeDeliveryError(RuntimeError):
    """The relay would not take the code. Distinct from a config error.

    A relay that is down is an outage, not a bug in the request - the caller
    turns this into a 502 with copy the owner can act on, rather than letting
    it fall through to the catch-all 500.
    """


class EmailProvider:
    """Sends a login code to ``email``."""

    async def send_login_code(self, *, email: str, code: str) -> None:
        raise NotImplementedError


class ConsoleEmailProvider(EmailProvider):
    """Local dev: log the code rather than sending (no SMTP required)."""

    async def send_login_code(self, *, email: str, code: str) -> None:
        logger.info("login code for %s: %s", email, code)


_last_codes: dict[str, str] = {}


def last_issued_code(email: str) -> str | None:
    return _last_codes.get(email)


class SmtpEmailProvider(EmailProvider):
    """Deliver via an SMTP relay (env: EMAIL_SMTP_*).

    Credentials are optional because the two relays in play want opposite
    things: Mailpit (``make mail``) speaks neither STARTTLS nor AUTH and refuses
    both, while every hosted relay (Resend, Brevo) requires both. Configuring a
    user and password is therefore what selects an authenticated session, rather
    than a second provider class that would differ by six lines.
    """

    def __init__(
        self,
        host: str,
        port: int,
        sender: str,
        *,
        user: str = "",
        password: str = "",
    ) -> None:
        self._host = host
        self._port = port
        self._sender = sender
        self._user = user
        self._password = password

    async def send_login_code(self, *, email: str, code: str) -> None:
        message = EmailMessage()
        message["Subject"] = "Your login code"
        message["From"] = self._sender
        message["To"] = email
        message.set_content(f"Your code is {code}.")
        # smtplib is synchronous; a login-code send is rare and tiny, so the
        # blocking call is acceptable here (run in a thread for real load).
        with smtplib.SMTP(self._host, self._port, timeout=15) as smtp:
            if self._user and self._password:
                smtp.starttls()
                smtp.login(self._user, self._password)
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
            user=settings.email_smtp_user,
            password=settings.email_smtp_password,
        )
    raise RuntimeError(f"unknown EMAIL_PROVIDER {provider!r}; expected console or smtp")


async def send_login_code(*, email: str, code: str) -> None:
    """The one send path: capture the code locally, then deliver it.

    The capture backs the demo's captured-code path and the E2E login flow (the
    dev-login-code endpoint) - the "captured code" of O-2 US-4. It lives here
    rather than in one provider so it survives a switch to a local inbox
    (EMAIL_PROVIDER=smtp against Mailpit), and it is gated to the local
    environment on exactly the same condition as the endpoint that reads it
    (app/features/auth/api.py), so no deployment ever holds a code in memory.
    """
    is_local = get_settings().environment == "local"
    if is_local:
        _last_codes[email] = code
    provider = get_email_provider()
    try:
        await provider.send_login_code(email=email, code=code)
    except (OSError, smtplib.SMTPException) as exc:
        if is_local:
            # EMAIL_PROVIDER=smtp with no relay up. The code is already
            # captured above and served by /api/auth/dev-login-code, so local
            # login carries on the way the console provider would - a missing
            # inbox is a missing inbox, not a broken login.
            logger.warning("login code for %s: %s (delivery failed: %s)", email, code, exc)
            return
        raise LoginCodeDeliveryError(str(exc)) from exc
