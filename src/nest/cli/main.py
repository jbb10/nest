"""Main CLI entry point for nest command."""

import typer

from nest.cli.config_cmd import config_app
from nest.cli.convert_cmd import convert_command
from nest.cli.doctor_cmd import doctor_command
from nest.cli.init_cmd import init_command
from nest.cli.status_cmd import status_command
from nest.cli.sync_cmd import sync_command
from nest.cli.update_cmd import update_command
from nest.ui.command import NestCommand

app = typer.Typer(pretty_exceptions_show_locals=False)

# Register commands
app.command(name="init", cls=NestCommand)(init_command)
app.command(name="sync", cls=NestCommand)(sync_command)
app.command(name="convert", cls=NestCommand)(convert_command)
app.command(name="status", cls=NestCommand)(status_command)
app.command(name="doctor", cls=NestCommand)(doctor_command)
app.command(name="update", cls=NestCommand)(update_command)
app.add_typer(config_app, name="config")


def main() -> None:
    """Entry point for the nest CLI."""
    app()


if __name__ == "__main__":
    main()
