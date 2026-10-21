"""Unit tests for progress bar helpers.

Tests for SyncProgress class used during sync command.
"""

from io import StringIO

import pytest
from rich.console import Console

from nest.ui.progress import SyncProgress


class TestSyncProgress:
    """Tests for SyncProgress class."""

    @pytest.mark.parametrize("width", [40, 80, 120])
    def test_long_filename_wraps_on_its_own_line(self, width: int) -> None:
        output = StringIO()
        filename = "reports/2024-1015835445 Declaration about access to the parking area [1].pdf"
        console = Console(file=output, width=width, force_terminal=False)
        with SyncProgress(console=console) as progress:
            progress.start(total=77)
            progress.set_activity("Converting document 1 of 77", filename)
        rendered = output.getvalue()
        assert "".join(filename.split()) in "".join(rendered.split())
        assert "File" in rendered
        assert all(len(line) <= width for line in rendered.splitlines())

    def test_setup_does_not_render_an_unknown_count_as_none(self) -> None:
        output = StringIO()
        with SyncProgress(console=Console(file=output)) as progress:
            progress.start(total=None)
            progress.set_activity("Preparing conversion models")
        assert "None" not in output.getvalue()

    def test_completion_does_not_replace_the_current_activity(self) -> None:
        output = StringIO()
        with SyncProgress(console=Console(file=output, width=120)) as progress:
            progress.start(total=2)
            progress.set_activity("Describing images: 2 documents")
            progress.advance("already-complete.pdf")
        assert "already-complete.pdf" not in output.getvalue()
        assert "(1/2)" in output.getvalue()

    def test_activity_is_visible_before_any_file_completes(self) -> None:
        """Ongoing work renders immediately without claiming a completed file."""
        output = StringIO()
        console = Console(file=output, force_terminal=True, width=160, color_system=None)
        with SyncProgress(console=console) as progress:
            progress.start(total=77)
            progress.set_activity("Converting 1/77: report[1].pdf")
            rendered = output.getvalue()
            assert "Converting 1/77: report[1].pdf" in rendered
            assert "(0/77)" in rendered
            assert "(1/77)" not in rendered

    def test_activity_is_logged_without_a_terminal(self) -> None:
        """Piped output includes ongoing activity before the final progress render."""
        output = StringIO()
        console = Console(file=output, force_terminal=False, width=160)
        with SyncProgress(console=console) as progress:
            progress.start(total=2)
            progress.set_activity("Converting 1/2: report.pdf")
            assert "Converting 1/2: report.pdf" in output.getvalue()

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
        progress.set_activity("Converting document 1 of 10", "file.pdf")
        progress.advance("file.pdf")
        progress.finish()
        assert output.getvalue() == ""

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
