"""Tests for error logging infrastructure.

Tests for ui/logger.py module - error logging setup and helpers.
"""

from pathlib import Path

import pytest


class TestSetupErrorLogger:
    """Tests for setup_error_logger function."""

    def test_logger_uses_non_legacy_namespace(self, tmp_path: Path) -> None:
        """Logger name should not use the legacy nest.errors namespace."""
        from nest.ui.logger import setup_error_logger

        log_file = tmp_path / ".nest" / "errors.log"
        log_file.parent.mkdir(parents=True, exist_ok=True)
        logger = setup_error_logger(log_file, service_name="sync")

        assert logger.logger.name.startswith("nest.error_log.sync.")
        assert "nest.errors" not in logger.logger.name

    def test_logger_disables_propagation(self, tmp_path: Path) -> None:
        """Logger should not propagate to parent handlers."""
        from nest.ui.logger import setup_error_logger

        log_file = tmp_path / ".nest" / "errors.log"
        log_file.parent.mkdir(parents=True, exist_ok=True)
        logger = setup_error_logger(log_file, service_name="sync")

        assert logger.logger.propagate is False

    def test_creates_log_file_on_first_write(self, tmp_path: Path) -> None:
        """Test that log file is created when first error is logged."""
        from nest.ui.logger import setup_error_logger

        log_file = tmp_path / ".nest" / "errors.log"
        log_file.parent.mkdir(parents=True, exist_ok=True)
        logger = setup_error_logger(log_file)

        # Log an error
        logger.error("test error message")

        assert log_file.exists()

    def test_log_format_matches_specification(self, tmp_path: Path) -> None:
        """Test log format: {timestamp} {level} [{service}] {message}."""
        from nest.ui.logger import setup_error_logger

        log_file = tmp_path / ".nest" / "errors.log"
        log_file.parent.mkdir(parents=True, exist_ok=True)
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

        log_file = tmp_path / ".nest" / "errors.log"
        log_file.parent.mkdir(parents=True, exist_ok=True)

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
        """Test that default log file is .nest/errors.log in current directory."""
        from nest.ui.logger import setup_error_logger

        monkeypatch.chdir(tmp_path)
        # Ensure .nest/ exists in cwd for default path
        (tmp_path / ".nest").mkdir(parents=True, exist_ok=True)
        logger = setup_error_logger()

        logger.error("test")

        assert (tmp_path / ".nest" / "errors.log").exists()


class TestLogProcessingError:
    """Tests for log_processing_error helper function."""

    def test_logs_with_file_path_and_message(self, tmp_path: Path) -> None:
        """Test that helper logs file path and error message."""
        from nest.ui.logger import log_processing_error, setup_error_logger

        log_file = tmp_path / ".nest" / "errors.log"
        log_file.parent.mkdir(parents=True, exist_ok=True)
        logger = setup_error_logger(log_file, service_name="sync")

        log_processing_error(logger, Path("contracts/alpha.pdf"), "Password protected")

        content = log_file.read_text()
        assert "alpha.pdf" in content
        assert "Password protected" in content

    def test_logs_multiple_errors_in_sequence(self, tmp_path: Path) -> None:
        """Test that multiple errors are logged correctly."""
        from nest.ui.logger import log_processing_error, setup_error_logger

        log_file = tmp_path / ".nest" / "errors.log"
        log_file.parent.mkdir(parents=True, exist_ok=True)
        logger = setup_error_logger(log_file, service_name="sync")

        log_processing_error(logger, Path("file1.pdf"), "Error 1")
        log_processing_error(logger, Path("file2.xlsx"), "Error 2")

        content = log_file.read_text()
        lines = content.strip().split("\n")

        assert len(lines) == 2
        assert "file1.pdf" in lines[0]
        assert "file2.xlsx" in lines[1]


class TestRichConsoleHandler:
    """Tests for RichConsoleHandler and install_rich_console_handler."""

    def _reset_nest_logger(self) -> None:
        import logging

        nest_logger = logging.getLogger("nest")
        nest_logger.handlers.clear()
        nest_logger.setLevel(logging.NOTSET)

    def test_warning_routed_to_ui_warning(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A WARNING from nest.* should be forwarded to ui.messages.warning."""
        import logging

        from nest.ui import messages
        from nest.ui.logger import install_rich_console_handler

        self._reset_nest_logger()

        captured: list[str] = []
        monkeypatch.setattr(messages, "warning", lambda msg: captured.append(msg))

        install_rich_console_handler()

        logging.getLogger("nest.adapters.file_discovery").warning(
            "Skipping broken symlink: %s", "/tmp/foo"
        )

        assert captured == ["Skipping broken symlink: /tmp/foo"]
        self._reset_nest_logger()

    def test_error_routed_to_ui_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """An ERROR from nest.* should be forwarded to ui.messages.error."""
        import logging

        from nest.ui import messages
        from nest.ui.logger import install_rich_console_handler

        self._reset_nest_logger()

        captured: list[str] = []
        monkeypatch.setattr(messages, "error", lambda msg: captured.append(msg))

        install_rich_console_handler()

        logging.getLogger("nest.services.sync_service").error("boom")

        assert captured == ["boom"]
        self._reset_nest_logger()

    def test_third_party_records_are_ignored(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Records from non-nest namespaces must not reach the UI."""
        import logging

        from nest.ui import messages
        from nest.ui.logger import install_rich_console_handler

        self._reset_nest_logger()

        warned: list[str] = []
        monkeypatch.setattr(messages, "warning", lambda msg: warned.append(msg))

        install_rich_console_handler()

        # Attach the same handler instance to a third-party logger to prove
        # the namespace filter (not just propagation) blocks the record.
        from nest.ui.logger import RichConsoleHandler

        for h in logging.getLogger("nest").handlers:
            if isinstance(h, RichConsoleHandler):
                logging.getLogger("docling").addHandler(h)
                logging.getLogger("docling").warning("noisy")
                logging.getLogger("docling").removeHandler(h)
                break

        assert warned == []
        self._reset_nest_logger()

    def test_error_log_namespace_is_excluded(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Records from nest.error_log.* (file-only sync errors) must be skipped."""
        from nest.ui import messages
        from nest.ui.logger import install_rich_console_handler, setup_error_logger

        self._reset_nest_logger()

        captured: list[str] = []
        monkeypatch.setattr(messages, "error", lambda msg: captured.append(msg))

        install_rich_console_handler()

        log_file = tmp_path / "errors.log"
        err_logger = setup_error_logger(log_file, service_name="sync")
        err_logger.error("file.pdf: failure")

        assert captured == []
        self._reset_nest_logger()

    def test_install_is_idempotent(self) -> None:
        """Calling install twice must not add duplicate handlers."""
        import logging

        from nest.ui.logger import RichConsoleHandler, install_rich_console_handler

        self._reset_nest_logger()

        install_rich_console_handler()
        install_rich_console_handler()

        handlers = [
            h for h in logging.getLogger("nest").handlers if isinstance(h, RichConsoleHandler)
        ]
        assert len(handlers) == 1
        self._reset_nest_logger()
