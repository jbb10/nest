"""Tests for error logging infrastructure.

Tests for ui/logger.py module - error logging setup and helpers.
"""

import logging
import warnings
from io import StringIO
from pathlib import Path

import pytest
from rich.console import Console

from nest.ui.logger import ConsoleDiagnostics


class TestConsoleDiagnostics:
    """Dependency diagnostics follow the same scoped policy in every output channel."""

    @pytest.mark.parametrize("verbose", [False, True])
    def test_secrets_are_redacted_in_diagnostics(
        self, monkeypatch: pytest.MonkeyPatch, verbose: bool
    ) -> None:
        secret = "sample-secret-for-diagnostic-test"
        monkeypatch.setenv("NEST_AI_API_KEY", secret)
        output = StringIO()
        with ConsoleDiagnostics(Console(file=output, width=160), verbose=verbose) as diagnostics:
            logging.getLogger("httpx").warning(
                "Request failed with %s and Bearer another-token", secret
            )
            diagnostics.print_summary(Path.cwd())
        assert secret not in output.getvalue()
        assert "another-token" not in output.getvalue()
        assert "[redacted]" in output.getvalue()

    def test_library_progress_settings_are_restored(self) -> None:
        from huggingface_hub.utils.tqdm import (
            are_progress_bars_disabled,
            disable_progress_bars,
            enable_progress_bars,
        )
        from rapidocr.utils import download_file
        from transformers.utils import logging as transformers_logging

        original_factory = download_file.__dict__["tqdm"]
        original_transformers = transformers_logging.is_progress_bar_enabled()
        original_hub = are_progress_bars_disabled()
        try:
            transformers_logging.disable_progress_bar()
            enable_progress_bars()
            with ConsoleDiagnostics(Console(file=StringIO())):
                assert are_progress_bars_disabled()
                with download_file.__dict__["tqdm"](total=1) as progress:
                    assert progress.disable

            assert not transformers_logging.is_progress_bar_enabled()
            assert not are_progress_bars_disabled()
            assert download_file.__dict__["tqdm"] is original_factory
        finally:
            if original_transformers:
                transformers_logging.enable_progress_bar()
            else:
                transformers_logging.disable_progress_bar()
            if original_hub:
                disable_progress_bars()
            else:
                enable_progress_bars()

    def test_unrecognized_errors_remain_visible(self) -> None:
        output = StringIO()
        with ConsoleDiagnostics(Console(file=output, width=160)) as diagnostics:
            logging.getLogger("RapidOCR").error("Unable to decode page image")
            diagnostics.print_summary(Path.cwd())
        assert "Unable to decode page image" in output.getvalue()

    def test_quiet_output_keeps_document_quality_warnings(self, tmp_path: Path) -> None:
        output = StringIO()
        console = Console(file=output, width=160)
        with ConsoleDiagnostics(console) as diagnostics:
            diagnostics.source = tmp_path / "budget[1].pdf"
            logging.getLogger("RapidOCR").info("Using engine_name: torch")
            logging.getLogger("RapidOCR").warning("The text detection result is empty")
            warnings.warn(
                "Using padding='same' with even kernel lengths and odd dilation",
                UserWarning,
                stacklevel=2,
            )
            for _ in range(2):
                logging.getLogger("MatchingPostProcessor").warning(
                    "47 of 966 pdf cells matched neither a row nor a column band and were dropped"
                )
            warnings.warn("Unexpected extraction warning", UserWarning, stacklevel=2)
            diagnostics.print_summary(tmp_path)

        rendered = output.getvalue()
        assert "engine_name" not in rendered
        assert "text detection" not in rendered
        assert "padding=" not in rendered
        assert "budget[1].pdf" in rendered
        assert rendered.count("Table extraction dropped some content") == 1
        assert "Unexpected extraction warning" in rendered

    def test_verbose_output_includes_logs_and_python_warnings(self) -> None:
        output = StringIO()
        with ConsoleDiagnostics(Console(file=output, width=160), verbose=True):
            logging.getLogger("RapidOCR").info("Using engine_name: torch")
            logging.getLogger("nest.services.sync_conversion").info("Processing 4 files")
            logging.getLogger("RapidOCR").warning("The text detection result is empty")
            warnings.warn(
                "Using padding='same' with even kernel lengths and odd dilation",
                UserWarning,
                stacklevel=2,
            )

        rendered = output.getvalue()
        assert "INFO [RapidOCR] Using engine_name: torch" in rendered
        assert "Processing 4 files" in rendered
        assert "The text detection result is empty" in rendered
        assert "UserWarning:" in rendered

    def test_configuration_is_restored_after_failure(self) -> None:
        root = logging.getLogger()
        rapidocr = logging.getLogger("RapidOCR")
        root_state = (root.level, root.handlers[:], root.propagate)
        rapidocr_state = (rapidocr.level, rapidocr.handlers[:], rapidocr.propagate)
        original_showwarning = warnings.showwarning

        with pytest.raises(RuntimeError, match="conversion failed"):
            with ConsoleDiagnostics(Console(file=StringIO())):
                raise RuntimeError("conversion failed")

        assert (root.level, root.handlers, root.propagate) == root_state
        assert (rapidocr.level, rapidocr.handlers, rapidocr.propagate) == rapidocr_state
        assert warnings.showwarning is original_showwarning

    def test_downloads_have_a_user_facing_activity_without_urls(self) -> None:
        output = StringIO()
        activities: list[str | None] = []
        with ConsoleDiagnostics(Console(file=output), download_activity=activities.append):
            logging.getLogger("RapidOCR").info("Initiating download: https://example.test/model")
            logging.getLogger("RapidOCR").info("Successfully saved to: /tmp/model")

        assert activities == ["Downloading OCR models", None]
        assert output.getvalue() == ""


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


def test_file_only_error_logger_does_not_duplicate_console_output(tmp_path: Path) -> None:
    from nest.ui.logger import setup_error_logger

    stream = StringIO()
    log_file = tmp_path / "errors.log"
    with ConsoleDiagnostics(Console(file=stream)) as diagnostics:
        setup_error_logger(log_file, service_name="sync").error("file.pdf: failure")
        diagnostics.print_summary(tmp_path)
    assert stream.getvalue() == ""
    assert "file.pdf: failure" in log_file.read_text()
