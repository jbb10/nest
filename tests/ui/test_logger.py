"""Tests for error logging infrastructure.

Tests for ui/logger.py module - error logging setup and helpers.
"""

from pathlib import Path

import pytest


class TestSetupErrorLogger:
    """Tests for setup_error_logger function."""

    def test_creates_log_file_on_first_write(self, tmp_path: Path) -> None:
        """Test that log file is created when first error is logged."""
        from nest.ui.logger import setup_error_logger

        log_file = tmp_path / ".nest_errors.log"
        logger = setup_error_logger(log_file)

        # Log an error
        logger.error("test error message")

        assert log_file.exists()

    def test_log_format_matches_specification(self, tmp_path: Path) -> None:
        """Test log format: {timestamp} {level} [{service}] {message}."""
        from nest.ui.logger import setup_error_logger

        log_file = tmp_path / ".nest_errors.log"
        logger = setup_error_logger(log_file, service_name="sync")

        logger.error("file.pdf: Error description")

        content = log_file.read_text()
        # Format: 2026-01-12T10:30:00 ERROR [sync] file.pdf: Error description
        assert "ERROR" in content
        assert "[sync]" in content
        assert "file.pdf: Error description" in content
        # Check ISO timestamp format (YYYY-MM-DDTHH:MM:SS)
        assert "T" in content.split()[0]

    def test_log_appends_not_overwrites(self, tmp_path: Path) -> None:
        """Test that subsequent logs append to existing file."""
        from nest.ui.logger import setup_error_logger

        log_file = tmp_path / ".nest_errors.log"

        # First logger session
        logger1 = setup_error_logger(log_file, service_name="sync")
        logger1.error("first error")

        # Second logger session (simulates new run)
        logger2 = setup_error_logger(log_file, service_name="sync")
        logger2.error("second error")

        content = log_file.read_text()
        lines = content.strip().split("\n")

        assert len(lines) == 2
        assert "first error" in lines[0]
        assert "second error" in lines[1]

    def test_default_log_file_path(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that default log file is .nest_errors.log in current directory."""
        from nest.ui.logger import setup_error_logger

        monkeypatch.chdir(tmp_path)
        logger = setup_error_logger()

        logger.error("test")

        assert (tmp_path / ".nest_errors.log").exists()


class TestLogProcessingError:
    """Tests for log_processing_error helper function."""

    def test_logs_with_file_path_and_message(self, tmp_path: Path) -> None:
        """Test that helper logs file path and error message."""
        from nest.ui.logger import log_processing_error, setup_error_logger

        log_file = tmp_path / ".nest_errors.log"
        logger = setup_error_logger(log_file, service_name="sync")

        log_processing_error(logger, Path("contracts/alpha.pdf"), "Password protected")

        content = log_file.read_text()
        assert "alpha.pdf" in content
        assert "Password protected" in content

    def test_logs_multiple_errors_in_sequence(self, tmp_path: Path) -> None:
        """Test that multiple errors are logged correctly."""
        from nest.ui.logger import log_processing_error, setup_error_logger

        log_file = tmp_path / ".nest_errors.log"
        logger = setup_error_logger(log_file, service_name="sync")

        log_processing_error(logger, Path("file1.pdf"), "Error 1")
        log_processing_error(logger, Path("file2.xlsx"), "Error 2")

        content = log_file.read_text()
        lines = content.strip().split("\n")

        assert len(lines) == 2
        assert "file1.pdf" in lines[0]
        assert "file2.xlsx" in lines[1]
