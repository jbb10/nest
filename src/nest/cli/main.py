"""Main CLI entry point for nest command."""

import logging

import typer

from nest.cli.config_cmd import config_app
from nest.cli.doctor_cmd import doctor_command
from nest.cli.init_cmd import init_command
from nest.cli.status_cmd import status_command
from nest.cli.sync_cmd import sync_command
from nest.cli.update_cmd import update_command
from nest.ui.logger import install_rich_console_handler

app = typer.Typer()

# Register commands
app.command(name="init")(init_command)
app.command(name="sync")(sync_command)
app.command(name="status")(status_command)
app.command(name="doctor")(doctor_command)
app.command(name="update")(update_command)
app.add_typer(config_app, name="config")


def _suppress_third_party_loggers() -> None:
    """Silence noisy third-party loggers that pollute console output.

    Docling internally calls logging.basicConfig(level=INFO) which causes
    its pipeline internals, httpx HTTP traces, and openai SDK logs to
    flood stderr.  We pre-configure the root logger at WARNING and
    explicitly silence the noisiest namespaces at ERROR so their
    non-actionable warnings (msword list items, slow tokenizer, etc.)
    do not reach the user.
    """
    logging.basicConfig(level=logging.WARNING, force=True)
    for name in ("docling", "httpx", "openai", "PIL", "transformers", "urllib3"):
        logging.getLogger(name).setLevel(logging.ERROR)


def main() -> None:
    """Entry point for the nest CLI."""
    _suppress_third_party_loggers()
    install_rich_console_handler()
    app()


if __name__ == "__main__":
    main()
