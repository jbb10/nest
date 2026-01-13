"""Main CLI entry point for nest command."""
import typer

from nest.cli.init_cmd import init_command

app = typer.Typer()

# Register commands
app.command(name="init")(init_command)


@app.command(name="_placeholder")
def _placeholder_command() -> None:  # pyright: ignore[reportUnusedFunction]
    """Temporary placeholder to prevent single-command promotion.

    TODO: Remove when implementing nest sync (Story 2.x).
    This exists because Typer promotes single-command apps to root level,
    which would change `nest init Nike` to `nest Nike`.
    """
    raise typer.Exit(code=0)


def main() -> None:
    """Entry point for the nest CLI."""
    app()


if __name__ == "__main__":
    main()
