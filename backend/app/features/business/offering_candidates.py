"""The equality key every offering boundary is decided on.

This module used to also derive offering candidates from saved knowledge, by
splitting each line of two fixed headings ("What we offer", "Prices") at its
first monetary figure. W-6 replaced that: a real owner document is prose, and
cutting a sentence at its first "$" produced names like "Bowl is" and "Pocket
both run" and never a description. The whole-document extraction that replaced
it lives in ``app.features.knowledge.offering_extraction``.

What stays here is ``normalize_name``, which is not part of that parse - it is
the shared definition of when two offerings are the same offering, used by the
onboarding record, the confirm-time write path and the new extraction alike.
"""

from __future__ import annotations

import re
import unicodedata


def normalize_name(value: str) -> str:
    """Return the equality key used for every offering boundary."""
    normalized = unicodedata.normalize("NFKC", value).strip().casefold()
    normalized = "".join(
        " " if unicodedata.category(char).startswith("P") else char for char in normalized
    )
    return re.sub(r"\s+", " ", normalized).strip()
