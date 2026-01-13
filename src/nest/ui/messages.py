"""UI message helpers using Rich console.

Provides consistent, colored output for user-facing messages.
NEVER use print() directly - always use these helpers.
"""

from rich.console import Console

# Shared console instance
_console = Console()


def success(message: str) -> None:
    """Print a success message with green checkmark.

    Args:
        message: The message to display.
    """
    _console.print(f"[green]✓[/green] {message}")


def error(message: str) -> None:
    """Print an error message with red X.

    Args:
        message: The message to display.
    """
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
