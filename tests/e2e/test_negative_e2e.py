"""E2E tests for negative/error paths.

Tests various invalid states and commands to verify proper error handling.
"""

import shutil
from pathlib import Path

import pytest

from .conftest import run_cli, skip_without_docling


@pytest.mark.e2e
class TestNegativePathsE2E:
    """E2E tests for error handling and invalid states."""

    def test_sync_without_init(self, fresh_temp_dir: Path):
        """Test that sync without init fails with helpful error.

        AC6: nest sync without init → exit 1, error message
        """
        # Act
        result = run_cli(["sync"], cwd=fresh_temp_dir)

        # Assert
        assert result.exit_code == 1, f"Expected exit 1, got {result.exit_code}"
        # Should mention init or project not found
        output = result.stdout + result.stderr
        assert (
            "init" in output.lower() or "not found" in output.lower() or "no nest" in output.lower()
        ), f"Expected error about missing project: {output}"

    def test_init_existing_project(self, fresh_temp_dir: Path):
        """Test that init fails if project already exists.

        AC6: nest init where project exists → exit 1, error message
        """
        # Arrange - first init
        result1 = run_cli(["init"], cwd=fresh_temp_dir)
        assert result1.exit_code == 0

        # Act - second init
        result2 = run_cli(["init"], cwd=fresh_temp_dir)

        # Assert
        assert result2.exit_code == 1, f"Expected exit 1, got {result2.exit_code}"
        output = result2.stdout + result2.stderr
        assert "exists" in output.lower() or "already" in output.lower(), (
            f"Expected error about existing project: {output}"
        )

    def test_init_rejects_positional_argument(self, fresh_temp_dir: Path):
        """Test that init rejects unexpected positional arguments.

        AC6: nest init <name> → exit 2, error about unexpected argument
        """
        result = run_cli(["init", "SomeName"], cwd=fresh_temp_dir)

        assert result.exit_code == 2, (
            f"Expected exit code 2 for unexpected arg, got {result.exit_code}"
        )

    def test_sync_empty_inbox(self, fresh_temp_dir: Path):
        """Test that sync with empty inbox succeeds with informative message.

        AC6: Empty inbox → exit 0, no files message
        """
        # Arrange - init project but don't add any files
        result = run_cli(["init"], cwd=fresh_temp_dir)
        assert result.exit_code == 0

        # Act
        result = run_cli(["sync"], cwd=fresh_temp_dir)

        # Assert
        assert result.exit_code == 0, f"Expected exit 0, got {result.exit_code}: {result.stderr}"
        output = result.stdout + result.stderr
        # Should indicate no files to process
        assert "0" in output or "no file" in output.lower() or "nothing" in output.lower(), (
            f"Expected message about no files: {output}"
        )


@pytest.mark.e2e
@skip_without_docling
class TestNegativePathsWithDocling:
    """E2E tests that require Docling for processing."""

    def test_sync_continues_after_corrupt_file_but_exits_nonzero(self, fresh_temp_dir: Path):
        """A failed document does not stop other documents but makes the command fail."""
        fixtures_dir = Path(__file__).parent / "fixtures"

        # Arrange - init project
        result = run_cli(["init"], cwd=fresh_temp_dir)
        assert result.exit_code == 0

        # Add corrupt.pdf and a valid file
        raw_inbox = fresh_temp_dir / "_nest_sources"
        shutil.copy(fixtures_dir / "corrupt.pdf", raw_inbox / "corrupt.pdf")
        shutil.copy(fixtures_dir / "summary.docx", raw_inbox / "valid.docx")

        # Act
        result = run_cli(["sync"], cwd=fresh_temp_dir)

        # Assert
        assert result.exit_code == 1, (
            f"Expected exit 1 with a failed document, got {result.exit_code}: {result.stderr}"
        )
        assert "Failed:    1" in result.stdout
        assert "Sync finished with failures" in result.stdout

        # Valid doc should be processed
        processed = fresh_temp_dir / "_nest_context"
        assert (processed / "valid.md").exists(), "Valid doc should be processed"

        # Error log should exist
        error_log = fresh_temp_dir / ".nest" / "errors.log"
        assert error_log.exists(), "Error log should exist for skipped file"

    def test_sync_fail_mode_aborts(self, fresh_temp_dir: Path):
        """Test that --on-error=fail aborts on first error.

        AC6: Corrupt PDF with --on-error=fail → exit 1, abort
        """
        fixtures_dir = Path(__file__).parent / "fixtures"

        # Arrange - init project
        result = run_cli(["init"], cwd=fresh_temp_dir)
        assert result.exit_code == 0

        # Add corrupt.pdf
        raw_inbox = fresh_temp_dir / "_nest_sources"
        shutil.copy(fixtures_dir / "corrupt.pdf", raw_inbox / "corrupt.pdf")

        # Act - sync with fail mode
        result = run_cli(["sync", "--on-error", "fail"], cwd=fresh_temp_dir)

        # Assert
        assert result.exit_code == 1, f"Expected exit 1 with fail mode, got {result.exit_code}"

    def test_sync_ignores_unsupported_file_types(self, fresh_temp_dir: Path):
        """Test that unsupported file types are ignored without error.

        AC6: Unsupported file type → ignored, no error
        Note: Text files (.txt, .md, .yaml, etc.) are passthrough-copied and
        raster images are converted, so only truly unsupported types such as
        .zip are ignored.
        """
        # Arrange - init project
        result = run_cli(["init"], cwd=fresh_temp_dir)
        assert result.exit_code == 0

        # Add a .zip file (unsupported binary format)
        raw_inbox = fresh_temp_dir / "_nest_sources"
        zip_file = raw_inbox / "archive.zip"
        zip_file.write_bytes(b"PK\x03\x04" + b"\x00" * 100)

        # Act
        result = run_cli(["sync"], cwd=fresh_temp_dir)

        # Assert
        assert result.exit_code == 0, f"Expected exit 0, got {result.exit_code}: {result.stderr}"

        # .zip should NOT be in output
        processed = fresh_temp_dir / "_nest_context"
        assert not (processed / "archive.zip").exists(), ".zip file should be ignored"
        assert not (processed / "archive.md").exists(), ".zip file should be ignored"
