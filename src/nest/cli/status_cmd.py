"""Status command for nest CLI.

Handles the `nest status` command.
"""

from pathlib import Path
from typing import Annotated

import typer

from nest.adapters.filesystem import FileSystemAdapter
from nest.adapters.manifest import ManifestAdapter
from nest.core.exceptions import NestError
from nest.services.status_service import StatusService
from nest.ui.messages import error, get_console
from nest.ui.status_display import display_status


def create_status_service() -> StatusService:
    """Composition root for status service.

    Returns:
        Configured StatusService with real adapters.
    """

    return StatusService(
        filesystem=FileSystemAdapter(),
        manifest=ManifestAdapter(),
    )


def status_command(
    target_dir: Annotated[
        Path | None,
        typer.Option("--dir", "-d", help="Target directory for status operation"),
    ] = None,
) -> None:
    """Show project status.

    Examples:
        nest status
        nest status --dir /path/to/project
    """

    console = get_console()
    project_root = (target_dir or Path.cwd()).resolve()

    # AC4: Outside project
    manifest_adapter = ManifestAdapter()
    if not manifest_adapter.exists(project_root):
        error("No Nest project found. Run `nest init` first.")
        raise typer.Exit(1)

    try:
        service = create_status_service()
        report = service.get_status(project_root)
        display_status(report, console)

    except NestError as e:
        error("Status failed")
        console.print(f"  [dim]Reason: {e}[/dim]")
        raise typer.Exit(1) from None
