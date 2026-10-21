"""UI message helpers using Rich console.

Provides consistent, colored output for user-facing messages.
NEVER use print() directly - always use these helpers.
"""

from collections.abc import Sequence
from pathlib import Path

from rich.console import Console

# Shared console instance
_console = Console()


def success(message: str) -> None:
    """Print a success message with green checkmark.

    Args:
        message: The message to display.
    """
    from nest.ui.command import finish_output

    if finish_output():
        _console.print(f"[yellow]✓[/yellow] {message} (with warnings)")
    else:
        _console.print(f"[green]✓[/green] {message}")


def error(message: str) -> None:
    """Print an error message with red X.

    Args:
        message: The message to display.
    """
    from nest.ui.command import finish_output

    finish_output(failed=True)
    _console.print(f"[red]✗[/red] {message}")


def warning(message: str) -> None:
    """Print a warning message with yellow warning symbol.

    Args:
        message: The message to display.
    """
    _console.print(f"[yellow]⚠[/yellow] {message}")


def info(message: str) -> None:
    """Print an info message with blue bullet.

    Args:
        message: The message to display.
    """
    _console.print(f"[blue]•[/blue] {message}")


def get_console() -> Console:
    """Get the shared console instance for advanced output.

    Returns:
        The shared Rich Console instance.
    """
    return _console


AI_DISABLED_NOTE = "disabled (--no-ai)"
AI_ENABLE_HINT = "run 'nest config ai' or set NEST_AI_API_KEY"
AI_NOT_CONFIGURED_NOTE = f"not configured ({AI_ENABLE_HINT})"
_AI_ENABLE_SENTENCE = AI_ENABLE_HINT[0].upper() + AI_ENABLE_HINT[1:]


def display_path(source: Path, root: Path | None) -> str:
    """Render ``source`` relative to ``root`` when possible, else its file name."""
    if root is not None and source.is_relative_to(root):
        return str(source.relative_to(root))
    return source.name


def print_needs_ai_block(
    console: Console,
    files: Sequence[str],
    *,
    ai_disabled: bool,
    command: str,
) -> None:
    """Call out image files that were not processed because AI was unavailable.

    Args:
        console: Console to print to.
        files: Display paths of the affected image files.
        ai_disabled: True when the user passed ``--no-ai``; the guidance then
            says to drop the flag instead of configuring AI.
        command: Command to re-run, for example ``"nest sync"``.
    """
    if not files:
        return
    count = len(files)
    if count == 1:
        headline = "1 image file needs an AI image description and was not processed."
    else:
        headline = f"{count} image files need AI image descriptions and were not processed."
    if ai_disabled:
        guidance = f"Run '{command}' again without --no-ai."
    else:
        guidance = f"{_AI_ENABLE_SENTENCE}, then run '{command}' again."
    console.print()
    console.print(f"  [yellow]⚠[/yellow] {headline}")
    for path in files:
        console.print(f"    {path}", markup=False)
    console.print(f"    {guidance}")
