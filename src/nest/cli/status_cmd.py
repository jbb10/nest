"""Status command for nest CLI.

Handles the `nest status` command.
"""

from pathlib import Path
from typing import Annotated

import typer

from nest.adapters.file_discovery import FileDiscoveryAdapter
from nest.adapters.filesystem import FileSystemAdapter
from nest.adapters.manifest import ManifestAdapter
from nest.core.exceptions import NestError
from nest.core.project_layout import detect_project
from nest.services.status_service import StatusService
from nest.ui.command import current_output
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
        file_discovery=FileDiscoveryAdapter(),
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

    if not detect_project(project_root).initialized:
        error("No Nest project found. Run `nest init` first.")
        raise typer.Exit(1)

    try:
        ui = current_output()
        ui.stage("Inspecting project status")
        service = create_status_service()
        report = service.get_status(project_root)
        ui.finish()
        display_status(report, console)

    except NestError as e:
        error("Status failed")
        console.print(f"  [dim]Reason: {e}[/dim]")
        raise typer.Exit(1) from None
