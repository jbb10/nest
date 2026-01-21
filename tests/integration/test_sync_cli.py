"""Integration tests for sync CLI with progress and summary.

Tests end-to-end behavior of the sync command with Rich progress display
and enhanced summary output.
"""

import json
from pathlib import Path

from typer.testing import CliRunner

from nest.cli.main import app

runner = CliRunner()


class TestSyncCLIIntegration:
    """Integration tests for sync CLI command."""

    def test_sync_displays_summary_on_completion(self, tmp_path: Path) -> None:
        """Sync should display summary with counts on completion."""
        # Setup minimal project
        manifest = {
            "nest_version": "1.0.0",
            "project_name": "Test",
            "files": {},
        }
        manifest_path = tmp_path / ".nest_manifest.json"
        manifest_path.write_text(json.dumps(manifest))

        # Create raw_inbox and processed_context
        (tmp_path / "raw_inbox").mkdir()
        (tmp_path  "_nest_context").mkdir()

        result = runner.invoke(app, ["sync", "--dir", str(tmp_path)])

        # Should show sync complete summary
        assert result.exit_code == 0
        assert "Sync complete" in result.output
        assert "Processed:" in result.output
        assert "Skipped:" in result.output
        assert "Orphans:" in result.output
        assert "Index updated:" in result.output

    def test_sync_summary_shows_all_counts(self, tmp_path: Path) -> None:
        """Sync summary should display processed, skipped, failed counts."""
        # Setup project
        manifest = {
            "nest_version": "1.0.0",
            "project_name": "Test",
            "files": {},
        }
        manifest_path = tmp_path / ".nest_manifest.json"
        manifest_path.write_text(json.dumps(manifest))

        (tmp_path / "raw_inbox").mkdir()
        (tmp_path  "_nest_context").mkdir()

        result = runner.invoke(app, ["sync", "--dir", str(tmp_path)])

        assert result.exit_code == 0
        # All count lines should be present
        assert "Processed:" in result.output
        assert "Skipped:" in result.output
        assert "Failed:" in result.output
        assert "Orphans:" in result.output

    def test_sync_dry_run_shows_preview(self, tmp_path: Path) -> None:
        """Dry run should show preview without processing."""
        # Setup project
        manifest = {
            "nest_version": "1.0.0",
            "project_name": "Test",
            "files": {},
        }
        manifest_path = tmp_path / ".nest_manifest.json"
        manifest_path.write_text(json.dumps(manifest))

        (tmp_path / "raw_inbox").mkdir()
        (tmp_path  "_nest_context").mkdir()

        result = runner.invoke(app, ["sync", "--dry-run", "--dir", str(tmp_path)])

        assert result.exit_code == 0
        assert "Dry Run Preview" in result.output
        assert "Would process:" in result.output
        assert "Would skip:" in result.output
        assert "Would remove:" in result.output

    def test_sync_no_project_shows_error_with_action(self, tmp_path: Path) -> None:
        """Sync without manifest should show error with instructions."""
        result = runner.invoke(app, ["sync", "--dir", str(tmp_path)])

        assert result.exit_code == 1
        assert "No Nest project found" in result.output
        assert "nest init" in result.output


class TestSyncProgressIntegration:
    """Integration tests for sync progress bar."""

    def test_sync_does_not_crash_with_progress(self, tmp_path: Path) -> None:
        """Sync with progress bar should complete without errors."""
        # Setup project
        manifest = {
            "nest_version": "1.0.0",
            "project_name": "Test",
            "files": {},
        }
        manifest_path = tmp_path / ".nest_manifest.json"
        manifest_path.write_text(json.dumps(manifest))

        (tmp_path / "raw_inbox").mkdir()
        (tmp_path  "_nest_context").mkdir()

        result = runner.invoke(app, ["sync", "--dir", str(tmp_path)])

        # Should complete without crash
        assert result.exit_code == 0
        assert "Sync complete" in result.output
