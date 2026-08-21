"""Email address extraction and syntax validation.

Login-in-chat (O-2) asks for an email inside a conversation, so what arrives is
whatever the owner typed - "bob@shop.com", "it's bob@shop.com", "mailto:bob@
shop.com.", or junk. The client cannot be the authority on that: it is a chat
composer, not a form field. This module is the one place that turns raw typed
text into either a normalized address or a reason it is not one, so the API can
answer conversationally instead of returning a validation dump.

Scope is deliberately syntax only. Whether an address is *deliverable* is
answered by the login code itself - if the address is wrong, no code arrives,
and the "Wrong email?" affordance is already on screen. No DNS/MX lookup runs
here: it would put a slow, flaky network call in the login path and still not
prove deliverability.

RFC 5322 exotica (quoted local parts, comments, address literals, folding) is
not supported on purpose - no real signup uses it, and accepting it would widen
the surface for no user.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Why not `email-validator`/`EmailStr`: it is a production-image dependency for
# roughly forty lines of well-understood rules, and its headline feature over
# this module (deliverability checks) is exactly the part deliberately excluded
# above. Revisit if internationalized (IDN/unicode) addresses are ever needed -
# that is the case worth a library rather than more regex here.

MAX_LENGTH = 254  # RFC 5321 path limit
MAX_LOCAL = 64
MAX_LABEL = 63

# A candidate token anywhere in the text, so prose around the address is fine.
# The local part is `*`, not `+`, so "@example.com" is still SEEN as an attempt
# at an address and answered with "does not look right" rather than the less
# helpful "could not find an email address in that".
_CANDIDATE_RE = re.compile(r"[^\s<>()\[\],;:\"]*@[^\s<>()\[\],;:\"]+")
# RFC 5322 "atext" plus dot, which covers every address a signup form sees.
_LOCAL_RE = re.compile(r"^[A-Za-z0-9!#$%&'*+/=?^_`{|}~.-]+$")
_LABEL_RE = re.compile(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?$")
_TLD_RE = re.compile(r"^[a-z]{2,}$")

#: Why the text could not be read as an address. ``None`` means it could.
Problem = str  # "missing" | "malformed"


@dataclass(frozen=True)
class EmailCheck:
    """The result of reading raw typed text as an email address."""

    address: str | None
    problem: Problem | None

    @property
    def ok(self) -> bool:
        return self.address is not None


def _strip_decoration(token: str) -> str:
    token = token.strip().strip("<>")
    if token.lower().startswith("mailto:"):
        token = token[len("mailto:") :]
    # Sentence punctuation clings to the end of an address typed in prose.
    return token.rstrip(".,;:!?)'\"")


def _valid_local(local: str) -> bool:
    if not local or len(local) > MAX_LOCAL:
        return False
    if local.startswith(".") or local.endswith(".") or ".." in local:
        return False
    return bool(_LOCAL_RE.fullmatch(local))


def _valid_domain(domain: str) -> bool:
    if not domain or domain.endswith("."):
        return False
    labels = domain.split(".")
    if len(labels) < 2:
        return False
    if any(len(label) > MAX_LABEL or not _LABEL_RE.fullmatch(label) for label in labels):
        return False
    return bool(_TLD_RE.fullmatch(labels[-1]))


def extract(raw: str) -> EmailCheck:
    """Read ``raw`` as an email address.

    Returns the normalized (trimmed, lowercased) address, or the reason it is
    not one: ``"missing"`` when nothing address-shaped is present at all, and
    ``"malformed"`` when something address-shaped is present but does not hold
    up. The two are distinguished because they deserve different answers - one
    asks for an email, the other asks the owner to check the one they gave.

    Lowercasing is applied to the whole address. The local part is technically
    case-sensitive per RFC 5321, but no mail provider in practice treats it so,
    and a stable normalization is what lets the issued code and the verification
    attempt agree on a single key.
    """
    candidates = _CANDIDATE_RE.findall(raw or "")
    if not candidates:
        return EmailCheck(address=None, problem="missing")

    for candidate in candidates:
        token = _strip_decoration(candidate).lower()
        if len(token) > MAX_LENGTH or token.count("@") != 1:
            continue
        local, _, domain = token.partition("@")
        if _valid_local(local) and _valid_domain(domain):
            return EmailCheck(address=token, problem=None)

    return EmailCheck(address=None, problem="malformed")
