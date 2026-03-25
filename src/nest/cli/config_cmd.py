"""Config command for nest CLI.

Handles the `nest config ai` subcommand for AI credential management.
"""

import os
from pathlib import Path
from typing import Annotated

import typer

from nest.services.shell_rc_service import ShellRCService
from nest.ui.messages import error, get_console, info, success, warning

config_app = typer.Typer(help="Commands for managing Nest configuration.")


def _mask_key(key: str) -> str:
    """Mask API key for display, showing last 4 characters.

    Args:
        key: Full API key string.

    Returns:
        Masked key like "••••sk-1234".
    """
    if len(key) <= 4:
        return "••••"
    return "••••" + key[-4:]


def _display_path(path: Path) -> str:
    """Display path with ~ for home directory.

    Args:
        path: Absolute path to display.

    Returns:
        Path string with ~ substituted for home directory.
    """
    home = Path.home()
    try:
        return "~/" + str(path.relative_to(home))
    except ValueError:
        return str(path)


@config_app.command(name="ai")
def ai_command(
    remove: Annotated[
        bool,
        typer.Option(
            "--remove",
            help="Remove Nest AI configuration from shell RC file",
        ),
    ] = False,
) -> None:
    """Configure AI enrichment by writing API credentials to your shell RC file.

    Interactively prompts for API endpoint, model name, and API key,
    then writes them as environment variable exports to your shell RC file
    (e.g., ~/.zshrc, ~/.bashrc, ~/.config/fish/config.fish).

    Use --remove to remove the configuration block.

    Examples:
        nest config ai
        nest config ai --remove
    """
    console = get_console()
    service = ShellRCService()

    # Detect shell and RC file
    shell = service.detect_shell()
    rc_path = service.resolve_rc_path(shell)

    if remove:
        try:
            removed = service.remove_config(rc_path)
        except (PermissionError, OSError) as exc:
            error(f"Cannot update {_display_path(rc_path)}")
            console.print(f"  Reason: {exc}")
            raise typer.Exit(code=1) from exc
        if removed:
            success(f"AI configuration removed from {_display_path(rc_path)}")
        else:
            info(f"No Nest AI configuration found in {_display_path(rc_path)}")
        return

    # Show detected shell info
    console.print(f"  Shell: {shell}")
    console.print(f"  RC file: {_display_path(rc_path)}")
    console.print()

    # Prompt with smart defaults from existing env vars
    current_endpoint = (
        os.environ.get("NEST_BASE_URL")
        or os.environ.get("OPENAI_BASE_URL")
        or "https://api.openai.com/v1"
    )
    current_model = (
        os.environ.get("NEST_TEXT_MODEL") or os.environ.get("OPENAI_MODEL") or "gpt-4o-mini"
    )
    current_key = os.environ.get("NEST_API_KEY") or os.environ.get("OPENAI_API_KEY") or ""

    endpoint = typer.prompt("  API endpoint", default=current_endpoint)
    model = typer.prompt("  Model", default=current_model)

    # Mask default display for API key
    key_display = _mask_key(current_key) if current_key else ""
    if current_key:
        raw_key = typer.prompt(f"  API key [{key_display}]", default="", show_default=False)
        api_key = raw_key if raw_key else current_key
    else:
        api_key = typer.prompt("  API key", hide_input=True)

    # Write config
    try:
        service.write_config(rc_path, endpoint, model, api_key, shell)
    except (PermissionError, OSError) as exc:
        error(f"Cannot write to {_display_path(rc_path)}")
        console.print(f"  Reason: {exc}")
        raise typer.Exit(code=1) from exc

    console.print()
    success(f"Added to {_display_path(rc_path)}")
    warning(f"Run 'source {_display_path(rc_path)}' or open a new terminal to activate.")
