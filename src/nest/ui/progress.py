"""Rich progress bar helpers for sync operations.

Provides SyncProgress class for displaying file processing progress.
"""

from __future__ import annotations

from types import TracebackType
from typing import TYPE_CHECKING

from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    TaskID,
    TaskProgressColumn,
    TextColumn,
)

if TYPE_CHECKING:
    pass


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

    def start(self, total: int) -> None:
        """Start the progress bar with a total count.

        Args:
            total: Total number of files to process.
        """
        self._progress = Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TextColumn("({task.completed}/{task.total})"),
            TextColumn("[cyan]{task.fields[current_file]}[/cyan]"),
            console=self._console,
            disable=self._disabled,
        )
        self._progress.start()
        self._task_id = self._progress.add_task(
            "Processing",
            total=total,
            current_file="",
        )

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
            current_file=current_file,
        )

    def finish(self) -> None:
        """Complete and stop the progress bar."""
        if self._progress is not None:
            self._progress.stop()
            self._progress = None
            self._task_id = None
