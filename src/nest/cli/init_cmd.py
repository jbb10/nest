"""Init command for nest CLI.

Handles the `nest init "Project Name"` command.
"""

from pathlib import Path
from typing import Annotated

import typer

from nest.adapters.docling_downloader import DoclingModelDownloader
from nest.adapters.filesystem import FileSystemAdapter
from nest.adapters.manifest import ManifestAdapter
from nest.agents.vscode_writer import VSCodeAgentWriter
from nest.core.exceptions import NestError
from nest.services.init_service import InitService
from nest.ui.messages import error, get_console, success


def create_init_service() -> InitService:
    """Composition root for init service.

    Returns:
        Configured InitService with real adapters.
    """
    filesystem = FileSystemAdapter()
    return InitService(
        filesystem=filesystem,
        manifest=ManifestAdapter(),
        agent_writer=VSCodeAgentWriter(filesystem=filesystem),
        model_downloader=DoclingModelDownloader(),
    )


def init_command(
    project_name: Annotated[
        str, typer.Argument(help="The project/client name (e.g., 'Nike')")
    ],
    target_dir: Annotated[
        Path | None,
        typer.Option("--dir", "-d", help="Target directory for project initialization"),
    ] = None,
) -> None:
    """Initialize a new Nest project.

    Creates the required directory structure and manifest file
    for processing documents with nest sync.

    Example:
        nest init "Nike"
    """
    console = get_console()
    resolved_dir = (target_dir or Path.cwd()).resolve()

    try:
        service = create_init_service()
        service.execute(project_name, resolved_dir)

        success(f'Project "{project_name}" initialized!')
        console.print()
        console.print("[bold]Next steps:[/bold]")
        console.print("  1. Drop your documents into raw_inbox/")
        console.print("  2. Run [cyan]nest sync[/cyan] to process them")
        console.print("  3. Open VS Code and use @nest in Copilot Chat")
        console.print()
        console.print("[dim]Supported formats: PDF, DOCX, PPTX, XLSX, HTML[/dim]")

    except NestError as e:
        error(str(e))
        if "already exists" in str(e):
            console.print("  [dim]Use `nest sync` to process documents instead.[/dim]")
        raise typer.Exit(1) from None
