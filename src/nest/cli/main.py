"""Main CLI entry point for nest command."""

import typer

from nest.cli.init_cmd import init_command
from nest.cli.sync_cmd import sync_command

app = typer.Typer()

# Register commands
app.command(name="init")(init_command)
app.command(name="sync")(sync_command)


def main() -> None:
    """Entry point for the nest CLI."""
    app()


if __name__ == "__main__":
    main()
