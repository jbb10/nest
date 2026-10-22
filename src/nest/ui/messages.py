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


LLM_DISABLED_NOTE = "disabled (--no-llm)"
LLM_ENABLE_HINT = "run 'nest config llm' or set NEST_LLM_API_KEY"
LLM_NOT_CONFIGURED_NOTE = f"not configured ({LLM_ENABLE_HINT})"
_LLM_ENABLE_SENTENCE = LLM_ENABLE_HINT[0].upper() + LLM_ENABLE_HINT[1:]


def display_path(source: Path, root: Path | None) -> str:
    """Render ``source`` relative to ``root`` when possible, else its file name."""
    if root is not None and source.is_relative_to(root):
        return str(source.relative_to(root))
    return source.name


def print_needs_llm_block(
    console: Console,
    files: Sequence[str],
    *,
    llm_disabled: bool,
    command: str,
) -> None:
    """Call out image files that were not processed because no LLM was available.

    Args:
        console: Console to print to.
        files: Display paths of the affected image files.
        llm_disabled: True when the user passed ``--no-llm``; the guidance then
            says to drop the flag instead of configuring an LLM.
        command: Command to re-run, for example ``"nest sync"``.
    """
    if not files:
        return
    count = len(files)
    if count == 1:
        headline = "1 image file needs an LLM image description and was not processed."
    else:
        headline = f"{count} image files need LLM image descriptions and were not processed."
    if llm_disabled:
        guidance = f"Run '{command}' again without --no-llm."
    else:
        guidance = f"{_LLM_ENABLE_SENTENCE}, then run '{command}' again."
    console.print()
    console.print(f"  [yellow]⚠[/yellow] {headline}")
    for path in files:
        console.print(f"    {path}", markup=False)
    console.print(f"    {guidance}")
