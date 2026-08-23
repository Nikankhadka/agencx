"""Eval-suite helpers shared by every metric module."""

from __future__ import annotations

import subprocess


def git_sha() -> str:
    """The short SHA an eval run is recorded against, or "" when unknowable.

    Two ways it is unknowable, both legitimate and neither a failure: the
    working tree is not a git repository (`check=False` already covers that),
    and `git` is not installed at all. The second one is the deployed shape -
    the production image and the `test` stage built from it carry no git and no
    `.git/` - so an eval run there records an empty SHA rather than crashing on
    exec.
    """
    try:
        result = subprocess.run(  # noqa: S603 - fixed args, no shell, dev-tool only
            ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=False
        )
    except (FileNotFoundError, OSError):
        return ""
    return result.stdout.strip()
