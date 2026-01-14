"""Main CLI entry point for nest command."""
import typer

from nest.cli.init_cmd import init_command

app = typer.Typer()

# Register commands
app.command(name="init")(init_command)


@app.command(name="sync")
def sync_command() -> None:
    """Sync documents from raw_inbox to processed_context.

    TODO: Implement in Story 2.8 (Sync Command CLI Integration).
    """
    from nest.ui.messages import error

    error(
        what="Sync not implemented",
        why="This command is coming in a future release",
        action="Use `nest init` first, then wait for sync support",
    )
    raise typer.Exit(code=1)


def main() -> None:
    """Entry point for the nest CLI."""
    app()


if __name__ == "__main__":
    main()
