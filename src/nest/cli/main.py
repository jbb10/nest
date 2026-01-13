"""Main CLI entry point for nest command."""
from pathlib import Path
from typing import Annotated

import typer

from nest.adapters.filesystem import FileSystemAdapter
from nest.adapters.manifest import ManifestAdapter
from nest.agents.vscode_writer import VSCodeAgentWriter
from nest.services.init_service import InitService
from nest.ui.messages import error, success

app = typer.Typer()


@app.command("init")
def init_command(
    project_name: Annotated[
        str,
        typer.Argument(help="Human-readable project name (e.g., 'Nike')"),
    ],
) -> None:
    """Initialize a new Nest project.

    Creates directory structure, manifest, and agent file.
    """
    try:
        # Composition root - wire dependencies
        filesystem = FileSystemAdapter()
        manifest = ManifestAdapter()
        agent_writer = VSCodeAgentWriter(filesystem=filesystem)

        service = InitService(
            filesystem=filesystem,
            manifest=manifest,
            agent_writer=agent_writer,
        )

        # Execute initialization
        target_dir = Path.cwd()
        service.execute(project_name, target_dir)

        # Success message
        success(f"Nest project '{project_name}' initialized")
        typer.echo("")
        typer.echo("Next steps:")
        typer.echo("  1. Add documents to raw_inbox/")
        typer.echo("  2. Run 'nest sync' to process documents")
        typer.echo("  3. Use @nest in VS Code Copilot Chat to query documents")

    except Exception as e:
        error(str(e))
        raise typer.Exit(1) from e


def main() -> None:
    """Entry point for the nest CLI."""
    app()


if __name__ == "__main__":
    main()
