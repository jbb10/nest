"""Main CLI entry point for nest command."""

import os
import sys
from typing import Annotated, NoReturn

import typer

import nest
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


def _version_callback(value: bool) -> None:
    """Print the running Nest version and exit.

    ``nest.__version__`` is the single source of truth: pyproject.toml reads
    it dynamically at build time, so the printed value always matches the
    installed wheel.
    """
    if value:
        typer.echo(nest.__version__)
        raise typer.Exit


@app.callback()
def nest_callback(
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            callback=_version_callback,
            is_eager=True,
            help="Show Nest's version and exit.",
        ),
    ] = False,
) -> None:
    """AI-powered document context tool for projects."""


def _terminate(exit_code: int) -> NoReturn:
    """Flush the output streams and terminate the process immediately.

    The CLI runs Docling's native stack (torch, OpenMP, pdfium), which
    intermittently faults on Windows while CPython joins worker threads and
    runs atexit handlers after the command's work is done (issue #41).
    Terminating directly skips that teardown. Every nest write is
    synchronous, so once the streams are flushed nothing is lost.
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.flush()
        except Exception:
            # A broken pipe must not mask the command's own exit code.
            pass
    os._exit(exit_code)


def _exit_status(code: object) -> int:
    """Map a SystemExit code to a process exit status."""
    if code is None:
        return 0
    return code if isinstance(code, int) else 1


def main() -> None:
    """Entry point for the nest CLI.

    Terminates the process instead of returning, so the console script and
    ``python -m nest.cli.main`` both skip interpreter finalization.
    Unexpected exceptions still propagate for a normal traceback exit.
    """
    try:
        app()
    except SystemExit as exit_signal:
        _terminate(_exit_status(exit_signal.code))
    _terminate(0)


if __name__ == "__main__":
    main()
