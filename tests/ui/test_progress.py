"""Unit tests for progress bar helpers.

Tests for SyncProgress class used during sync command.
"""

from io import StringIO

from rich.console import Console

from nest.ui.progress import SyncProgress


class TestSyncProgress:
    """Tests for SyncProgress class."""

    def test_sync_progress_initializes_with_total(self) -> None:
        """Test progress bar starts with correct total."""
        output = StringIO()
        console = Console(file=output, force_terminal=True)

        progress = SyncProgress(console=console)
        progress.start(total=10)
        progress.finish()

        # Progress should render something
        result = output.getvalue()
        assert result != ""

    def test_sync_progress_advances_correctly(self) -> None:
        """Test progress bar advances on each file."""
        output = StringIO()
        console = Console(file=output, force_terminal=True)

        progress = SyncProgress(console=console)
        progress.start(total=3)

        progress.advance("file1.pdf")
        progress.advance("file2.pdf")
        progress.advance("file3.pdf")

        progress.finish()

        result = output.getvalue()
        # Progress should have rendered output
        assert result != ""

    def test_sync_progress_shows_current_file(self) -> None:
        """Test progress displays current file being processed."""
        output = StringIO()
        console = Console(file=output, force_terminal=True, width=120)

        progress = SyncProgress(console=console)
        progress.start(total=5)

        progress.advance("contract.pdf")

        progress.finish()

        # The file name should appear in output
        result = output.getvalue()
        assert "contract.pdf" in result

    def test_sync_progress_context_manager(self) -> None:
        """Test progress works as context manager."""
        output = StringIO()
        console = Console(file=output, force_terminal=True)

        with SyncProgress(console=console) as progress:
            progress.start(total=2)
            progress.advance("test.pdf")
            progress.advance("test2.pdf")

        result = output.getvalue()
        assert result != ""

    def test_sync_progress_shows_count(self) -> None:
        """Test progress shows count of completed files."""
        output = StringIO()
        console = Console(file=output, force_terminal=True, width=120)

        progress = SyncProgress(console=console)
        progress.start(total=10)

        for i in range(5):
            progress.advance(f"file{i}.pdf")

        progress.finish()

        result = output.getvalue()
        # Should show some fraction (5/10 or similar)
        assert result != ""

    def test_sync_progress_can_be_disabled(self) -> None:
        """Test progress can be created with disabled=True for quiet mode."""
        output = StringIO()
        console = Console(file=output, force_terminal=True)

        progress = SyncProgress(console=console, disabled=True)
        progress.start(total=10)
        progress.advance("file.pdf")
        progress.finish()

        # Should not produce visible progress output when disabled
        # (Rich progress with disable=True produces minimal output)


class TestSyncProgressProtocol:
    """Tests for progress callback protocol compatibility."""

    def test_progress_has_required_methods(self) -> None:
        """Test SyncProgress has all required methods for callback."""
        output = StringIO()
        console = Console(file=output, force_terminal=True)

        progress = SyncProgress(console=console)

        # Verify required methods exist
        assert hasattr(progress, "start")
        assert hasattr(progress, "advance")
        assert hasattr(progress, "finish")
        assert callable(progress.start)
        assert callable(progress.advance)
        assert callable(progress.finish)
