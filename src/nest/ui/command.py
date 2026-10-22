"""Shared command output lifecycle for every Nest CLI command."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar, Token
from pathlib import Path
from types import TracebackType
from typing import Any

import click
from rich.console import Console
from typer.core import TyperCommand

from nest.core.models import Activity
from nest.ui.logger import ConsoleDiagnostics
from nest.ui.progress import SyncProgress

_current: ContextVar[CommandUI | None] = ContextVar("nest_command_output", default=None)


class CommandUI:
    """Own progress, diagnostic policy, and cleanup for one complete command."""

    def __init__(self, name: str, console: Console, verbose: bool = False) -> None:
        self.name = name
        self.console = console
        self.verbose = verbose
        self.root = Path.cwd()
        self._progress = SyncProgress(console=console)
        self._diagnostics = ConsoleDiagnostics(console, verbose, self._download_activity)
        self._token: Token[CommandUI | None] | None = None
        self._total: int | None = None
        self._stage = "Preparing"
        self._file = ""

    @property
    def has_warnings(self) -> bool:
        return bool(self._diagnostics.issues)

    def __enter__(self) -> CommandUI:
        self._token = _current.set(self)
        if self.name != "llm":
            self.stage(f"Preparing {self.name}")
        try:
            self._diagnostics.__enter__()
        except BaseException:
            self.pause()
            _current.reset(self._token)
            raise
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.pause()
        self._diagnostics.__exit__(exc_type, exc_value, traceback)
        self._diagnostics.print_summary(self.root)
        if self._token is not None:
            _current.reset(self._token)

    def start(self, total: int) -> None:
        self._total = total
        self._progress.start(total)

    def advance(self, name: str) -> None:
        self._progress.advance(name)

    def stage(self, label: str) -> None:
        self._diagnostics.source = None
        self._stage, self._file = label, ""
        self._progress.start(total=None)
        self._progress.set_activity(label)

    def activity(self, activity: Activity) -> None:
        document_stage = _document_stage(activity)
        if document_stage is not None:
            source = activity.files[0]
            self._diagnostics.source = source
            self._stage = document_stage
            self._file = (
                str(source.relative_to(self.root))
                if source.is_relative_to(self.root)
                else str(source)
            )
            self._progress.start(self._total)
            self._progress.set_activity(self._stage, self._file)
        elif activity.stage == "describing":
            noun = "document" if len(activity.files) == 1 else "documents"
            self.stage(f"Describing images: {len(activity.files)} {noun}")
        elif activity.stage == "downloading":
            self.stage("Downloading conversion models")
        else:
            labels = {
                "preparing": "Preparing conversion models",
                "committing": "Saving document outcomes",
                "cleanup": "Checking orphaned outputs",
                "metadata": "Reading document metadata",
                "indexing": "Updating the project index",
                "scaffolding": "Creating project structure",
                "agents": "Generating agent files",
            }
            self.stage(labels[activity.stage])

    def pause(self) -> None:
        self._progress.finish()

    def finish(self, failed: bool = False) -> None:
        label = (
            "Failed" if failed else "Completed with warnings" if self.has_warnings else "Complete"
        )
        self._progress.set_activity(label)
        self.pause()

    def _download_activity(self, label: str | None) -> None:
        self._progress.set_activity(label or self._stage, self._file)


def _document_stage(activity: Activity) -> str | None:
    """Progress label for a stage that works on one document, else None."""
    if activity.stage == "converting":
        return f"Converting document {activity.current} of {activity.total}"
    if activity.stage == "transcribing":
        return f"Transcribing document {activity.current} of {activity.total}"
    if activity.stage == "writing":
        return "Writing document"
    return None


def current_output() -> CommandUI:
    """Return the output session established by the CLI command lifecycle."""
    output = _current.get()
    if output is None:
        raise RuntimeError("No active Nest command output session")
    return output


@contextmanager
def command_activity(label: str, console: Console) -> Generator[None, None, None]:
    """Show one blocking operation without leaving a spinner over the next prompt."""
    output = _current.get()
    if output is None:
        with CommandUI("operation", console) as standalone:
            standalone.stage(label)
            yield
        return
    output.stage(label)
    try:
        yield
    finally:
        output.pause()


def finish_output(failed: bool = False) -> bool:
    """Finish live output before a result message, returning whether warnings occurred."""
    output = _current.get()
    if output is None:
        return False
    output.finish(failed=failed)
    return output.has_warnings


def _verbose_option(ctx: click.Context, parameter: click.Parameter, value: bool) -> bool:
    ctx.meta["nest_verbose"] = value
    return value


class NestCommand(TyperCommand):
    """Apply the shared output policy to commands, including nested configuration commands."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        if not any(parameter.name == "verbose" for parameter in self.params):
            self.params.append(
                click.Option(
                    ["--verbose", "-v"],
                    is_flag=True,
                    expose_value=False,
                    callback=_verbose_option,
                    help="Show detailed diagnostics",
                )
            )

    def invoke(self, ctx: click.Context) -> Any:
        from nest.ui.messages import get_console

        verbose = bool(ctx.params.get("verbose", ctx.meta.get("nest_verbose", False)))
        with CommandUI(self.name or "command", get_console(), verbose):
            return super().invoke(ctx)
