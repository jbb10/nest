"""Shared test utilities."""

import re

# Rich/Typer emits ANSI escape sequences in help output.  Strip them before
# asserting flag names so tests work reliably on CI and locally.
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")


def strip_ansi(output: str) -> str:
    """Remove ANSI escape sequences from a string.

    Args:
        output: String potentially containing ANSI escape codes.

    Returns:
        Clean string with all ANSI sequences removed.
    """
    return _ANSI_RE.sub("", output)