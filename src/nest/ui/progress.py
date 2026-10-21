"""Rich progress bar helpers for sync operations.

Provides SyncProgress class for displaying file processing progress.
"""

from __future__ import annotations

from types import TracebackType
from typing import TYPE_CHECKING

from rich.console import Console, Group
from rich.live import Live
from rich.progress import (
    BarColumn,
    Progress,
    ProgressColumn,
    SpinnerColumn,
    Task,
    TaskID,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table
from rich.text import Text

if TYPE_CHECKING:
    pass


class _CompletedFilesColumn(ProgressColumn):
    def render(self, task: Task) -> Text:
        if task.total is None:
            return Text("")
        return Text(f"({int(task.completed)}/{int(task.total)})")


class SyncProgress:
    """Rich progress bar for sync file processing.

    Wraps Rich Progress with a sync-specific format:
    [████████████--------] 60% (30/50) processing contract.pdf

    Methods:
        start(total): Initialize progress with total file count.
        advance(current_file): Update progress after processing a file.
        finish(): Complete the progress bar.

    Can be used as a context manager:
        with SyncProgress(console=console) as progress:
            progress.start(total=50)
            for file in files:
                process(file)
                progress.advance(file.name)
    """

    def __init__(
        self,
        console: Console | None = None,
        disabled: bool = False,
    ) -> None:
        """Initialize SyncProgress.

        Args:
            console: Rich console for output. Uses default if None.
            disabled: If True, disables progress display (quiet mode).
        """
        self._console = console
        self._disabled = disabled
        self._progress: Progress | None = None
        self._task_id: TaskID | None = None
        self._live: Live | None = None
        self._activity = ""
        self._current_file = ""

    def __enter__(self) -> SyncProgress:
        """Enter context manager."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Exit context manager, ensuring progress is finished."""
        self.finish()

    def start(self, total: int | None) -> None:
        """Start the progress bar with a total count.

        Args:
            total: Total number of files to process.
        """
        if self._progress is not None and self._task_id is not None:
            self._progress.tasks[self._task_id].total = total
            self._set_columns(total)
            self._refresh()
            return
        self._progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(bar_width=None),
            TaskProgressColumn(),
            _CompletedFilesColumn(),
            TimeElapsedColumn(),
            console=self._console,
            disable=self._disabled,
            auto_refresh=False,
        )
        self._task_id = self._progress.add_task(
            "Processing",
            total=total,
        )
        self._set_columns(total)
        if not self._disabled:
            self._live = Live(
                self._render(), console=self._progress.console, vertical_overflow="visible"
            )
            self._live.start()

    def _set_columns(self, total: int | None) -> None:
        assert self._progress is not None
        self._progress.columns = (
            (SpinnerColumn(), TextColumn("Working"), TimeElapsedColumn())
            if total is None
            else (
                SpinnerColumn(),
                TextColumn("Documents"),
                BarColumn(bar_width=None),
                TaskProgressColumn(),
                _CompletedFilesColumn(),
                TimeElapsedColumn(),
            )
        )

    def set_activity(self, activity: str, current_file: str = "") -> None:
        """Show ongoing work without incrementing the completed-file count."""
        if self._progress is None or self._task_id is None:
            return
        self._activity = activity
        self._current_file = current_file
        self._refresh()
        if not self._disabled and not self._progress.console.is_terminal:
            message = f"{activity}\n  {current_file}" if current_file else activity
            self._progress.console.print(Text(message))

    def _render(self) -> Group:
        assert self._progress is not None
        details = Table.grid(padding=(0, 2), expand=True)
        details.add_column(width=8, no_wrap=True)
        details.add_column(ratio=1, overflow="fold")
        if self._activity:
            details.add_row("Stage", Text(self._activity))
        if self._current_file:
            details.add_row("File", Text(self._current_file, style="cyan", overflow="fold"))
        return Group(self._progress, details)

    def _refresh(self) -> None:
        if self._live is not None:
            self._live.update(self._render(), refresh=True)

    def advance(self, current_file: str) -> None:
        """Advance progress by one and update current file display.

        Args:
            current_file: Name of the file just processed.
        """
        if self._progress is None or self._task_id is None:
            return

        self._progress.update(
            self._task_id,
            advance=1,
        )
        if not self._activity:
            self._current_file = current_file
        self._refresh()

    def finish(self) -> None:
        """Complete and stop the progress bar."""
        if self._progress is not None:
            if self._live is not None:
                self._live.stop()
                self._live = None
            self._progress = None
            self._task_id = None
