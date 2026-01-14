"""Tests for error logging configuration."""

from pathlib import Path

import pytest

from nest.core.logging import log_processing_error, setup_error_logger


class TestSetupErrorLogger:
    """Tests for setup_error_logger function."""

    def test_creates_log_directory(self, tmp_path: Path) -> None:
        """Test that setup creates log directory if needed."""
        log_file = tmp_path / "nested" / "deep" / ".nest_errors.log"

        logger = setup_error_logger(log_file)

        assert log_file.parent.exists()

    def test_returns_logger_instance(self, tmp_path: Path) -> None:
        """Test that setup returns a logger."""
        import logging

        log_file = tmp_path / ".nest_errors.log"

        logger = setup_error_logger(log_file)

        assert isinstance(logger, logging.Logger)
        assert logger.name == "nest.errors"

    def test_logger_has_file_handler(self, tmp_path: Path) -> None:
        """Test that logger is configured with file handler."""
        import logging

        log_file = tmp_path / ".nest_errors.log"

        # Clear any existing handlers first
        logger = logging.getLogger("nest.errors")
        logger.handlers.clear()

        logger = setup_error_logger(log_file)

        assert len(logger.handlers) == 1
        assert isinstance(logger.handlers[0], logging.FileHandler)


class TestLogProcessingError:
    """Tests for log_processing_error function."""

    def test_writes_error_to_log_file(self, tmp_path: Path) -> None:
        """Test that error is written to the log file."""
        import logging

        # Clear existing handlers
        logger = logging.getLogger("nest.errors")
        logger.handlers.clear()

        log_file = tmp_path / ".nest_errors.log"
        file_path = Path("/some/path/document.pdf")

        log_processing_error(
            log_file=log_file,
            context="sync",
            file_path=file_path,
            error="File is password protected",
        )

        # Force flush
        for handler in logger.handlers:
            handler.flush()

        assert log_file.exists()
        content = log_file.read_text()
        assert "ERROR" in content
        assert "[sync]" in content
        assert "document.pdf" in content
        assert "File is password protected" in content

    def test_log_format_includes_timestamp(self, tmp_path: Path) -> None:
        """Test that log entries include timestamp."""
        import logging
        import re

        # Clear existing handlers
        logger = logging.getLogger("nest.errors")
        logger.handlers.clear()

        log_file = tmp_path / ".nest_errors.log"

        log_processing_error(
            log_file=log_file,
            context="doctor",
            file_path=Path("/test.pdf"),
            error="Test error",
        )

        for handler in logger.handlers:
            handler.flush()

        content = log_file.read_text()
        # Check for ISO timestamp format: YYYY-MM-DDTHH:MM:SS
        timestamp_pattern = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")
        assert timestamp_pattern.search(content)

    def test_multiple_errors_append(self, tmp_path: Path) -> None:
        """Test that multiple errors are appended to the same file."""
        import logging

        # Clear existing handlers
        logger = logging.getLogger("nest.errors")
        logger.handlers.clear()

        log_file = tmp_path / ".nest_errors.log"

        log_processing_error(
            log_file=log_file,
            context="sync",
            file_path=Path("/first.pdf"),
            error="First error",
        )
        log_processing_error(
            log_file=log_file,
            context="sync",
            file_path=Path("/second.pdf"),
            error="Second error",
        )

        for handler in logger.handlers:
            handler.flush()

        content = log_file.read_text()
        assert "First error" in content
        assert "Second error" in content
        lines = content.strip().split("\n")
        assert len(lines) == 2
