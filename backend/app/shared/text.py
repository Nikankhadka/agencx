"""Small text normalizations shared by every surface that speaks to a user."""

from __future__ import annotations

import re

# conventions.md 1 bans the em dash repo-wide, and the W-9 reproduction showed a
# prompt rule alone does not hold it: three live drives out of three produced
# "Got it-open Monday" style dashes. Normalizing deterministically in the output
# path is what makes the rule true. Server-authored strings are already written
# with a plain dash, so this only ever touches model prose.
# The pattern names the character by code point: conventions.md 1 bans the
# literal from this repo's source, and this file is not the exception.
_EM_DASH = re.compile(r"\s*\u2014\s*")

# The customer chat surface never shows citation syntax. Models are prompted to
# cite as bare ``[1]`` but also see the catalog as ``[catalog_id=<uuid>]``
# (services/context_package.py), and conflate the two into forms like
# ``[1, 295feb16-a7f3-49e7-b771-e3b18fa0e76f]`` or ``[<uuid>]``. A prompt rule
# alone does not hold this (the W-9 em-dash reproduction showed the same for
# another instruction), so the strip is deterministic and lives at the chat
# boundary (features/chat/controller.py) rather than at each producer - the
# graph's own draft keeps its markers for Inspection and the citation evals.
_UUID = r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
# A citation token is a bracket index (1-3 digits, so a bracketed year like
# [2024] survives), a uuid, or an id-prefixed uuid the model copied.
_CITATION_TOKEN = rf"(?:catalog[\s_-]*)?id[ \t]*[=:][ \t]*{_UUID}|{_UUID}|\d{{1,3}}"
_CITATION_SEPARATOR = r"(?:[ \t]*[,;][ \t]*|[ \t]+)"
_CITATION_MARKER = re.compile(
    rf"[ \t]*\[[ \t]*(?:{_CITATION_TOKEN})(?:{_CITATION_SEPARATOR}(?:{_CITATION_TOKEN}))*[ \t]*\]",
    re.IGNORECASE,
)
_SPACE_BEFORE_PUNCTUATION = re.compile(r"[ \t]+([.,;:!?)\]])")
_MULTI_SPACE = re.compile(r"[ \t]{2,}")


def plain_dashes(text: str) -> str:
    """Replace every em dash, and the spacing around it, with a plain dash."""
    return _EM_DASH.sub(" - ", text)


def strip_citation_markers(text: str) -> str:
    """Remove citation syntax from text a customer is about to read or store.

    Handles the malformed forms a model produces by mixing bracket-citation
    numbers with catalog ids: ``[1]``, ``[1, <uuid>]``, ``[<uuid>]``,
    ``[catalog_id=<uuid>]``, ``[1, 2]``. Non-marker brackets (``[GF]``,
    ``[2024-01-01]``, ``[1999]``) are left alone. The whitespace a removed
    marker leaves behind is tidied so a stripped sentence still reads
    naturally. Idempotent.
    """
    without_markers = _CITATION_MARKER.sub("", text)
    if without_markers == text:
        # Nothing was a marker: leave the text byte-identical rather than
        # tidying whitespace the author actually wrote.
        return text
    tidied = _SPACE_BEFORE_PUNCTUATION.sub(r"\1", without_markers)
    return _MULTI_SPACE.sub(" ", tidied).strip()
