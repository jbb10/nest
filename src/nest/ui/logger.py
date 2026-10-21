"""Logging infrastructure for Nest.

- ``setup_error_logger`` / ``log_processing_error``: file-based error logging
  for sync operations, written to .nest/errors.log in ISO timestamp format.
  NEVER use these for user-facing messages - use messages.py Rich helpers.
- ``ConsoleDiagnostics``: scoped dependency output and document quality warnings.
"""

from __future__ import annotations

import logging
import os
import re
import sys
import warnings
from collections.abc import Callable
from contextlib import ExitStack
from functools import partial
from pathlib import Path
from types import TracebackType
from typing import IO

from rich.console import Console
from rich.text import Text

from nest.core.paths import ERROR_LOG_FILENAME, NEST_META_DIR


class ConsoleDiagnostics(logging.Handler):
    """Own dependency output for one CLI run, restoring global state on exit.

    Routine diagnostics are available only in verbose mode. Other warnings
    are deduplicated by source document for the completion summary.
    """

    def __init__(
        self,
        console: Console,
        verbose: bool = False,
        download_activity: Callable[[str | None], None] | None = None,
    ) -> None:
        super().__init__()
        self.setFormatter(logging.Formatter("%(levelname)s [%(name)s] %(message)s"))
        self.console = console
        self.verbose = verbose
        self.source: Path | None = None
        self.issues: dict[Path | None, set[str]] = {}
        self._download_activity = download_activity
        self._stack = ExitStack()
        self._rapidocr_configured = False
        self._secrets = [
            value
            for name, value in os.environ.items()
            if len(value) >= 8
            and any(part in name.upper() for part in ("API_KEY", "TOKEN", "PASSWORD", "SECRET"))
        ]

    def __enter__(self) -> ConsoleDiagnostics:
        try:
            root = logging.getLogger()
            self._route(root)
            for name in (
                "RapidOCR",
                "transformers",
                "torch.distributed.elastic.multiprocessing.redirects",
            ):
                logger = logging.getLogger(name)
                logger.addFilter(self._intercept)
                self._stack.callback(logger.removeFilter, self._intercept)
                self._route(logger)

            self._stack.enter_context(warnings.catch_warnings())
            warnings.simplefilter("always", UserWarning)
            warnings.simplefilter("always", RuntimeWarning)
            previous_showwarning = warnings.showwarning
            warnings.showwarning = self._show_warning
            self._stack.callback(setattr, warnings, "showwarning", previous_showwarning)

            self._configure_library_output()
            for name in ("docling", "docling_core", "httpx", "openai", "nest"):
                self._route(logging.getLogger(name))
            return self
        except BaseException:
            self._stack.close()
            raise

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self._stack.close()

    def _route(self, logger: logging.Logger) -> None:
        self._stack.callback(setattr, logger, "handlers", logger.handlers[:])
        self._stack.callback(logger.setLevel, logger.level)
        self._stack.callback(setattr, logger, "propagate", logger.propagate)
        logger.handlers = [self]
        logger.setLevel(
            logging.INFO if self.verbose or logger.name == "RapidOCR" else logging.WARNING
        )
        logger.propagate = False

    def _configure_library_output(self) -> None:
        """Disable library bars, including RapidOCR's unconfigurable local tqdm alias."""
        if self.verbose:
            return
        for name, value in (
            ("HF_HUB_DISABLE_PROGRESS_BARS", "1"),
            ("TQDM_DISABLE", "1"),
            ("TRANSFORMERS_VERBOSITY", "error"),
        ):
            previous = os.environ.get(name)
            if previous is None:
                self._stack.callback(os.environ.pop, name, None)
            else:
                self._stack.callback(os.environ.__setitem__, name, previous)
            os.environ[name] = value
        if "transformers.utils.logging" in sys.modules:
            from huggingface_hub.utils.tqdm import (
                are_progress_bars_disabled,
                disable_progress_bars,
                enable_progress_bars,
            )
            from transformers.utils import logging as transformers_logging

            hub_was_disabled = are_progress_bars_disabled()
            self._stack.callback(
                disable_progress_bars if hub_was_disabled else enable_progress_bars
            )
            if transformers_logging.is_progress_bar_enabled():
                transformers_logging.disable_progress_bar()
                self._stack.callback(transformers_logging.enable_progress_bar)
            disable_progress_bars()
        self._configure_rapidocr()

    def _configure_rapidocr(self) -> None:
        module = sys.modules.get("rapidocr.utils.download_file")
        if self.verbose or self._rapidocr_configured or module is None:
            return
        original_tqdm = module.__dict__["tqdm"]
        module.__dict__["tqdm"] = partial(original_tqdm, disable=True)
        self._stack.callback(setattr, module, "tqdm", original_tqdm)
        self._rapidocr_configured = True

    def _intercept(self, record: logging.LogRecord) -> bool:
        self._configure_rapidocr()
        self.handle(record)
        return False

    def emit(self, record: logging.LogRecord) -> None:
        if record.name.startswith("nest.error_log."):
            return
        message = record.getMessage()
        if self._download_activity is not None and record.name == "RapidOCR":
            if message.startswith("Initiating download:"):
                self._download_activity("Downloading OCR models")
            elif message.startswith("Successfully saved to:") or record.levelno >= logging.ERROR:
                self._download_activity(None)

        if self.verbose:
            self.console.print(Text(self._redact(self.format(record))), style="dim")
        if record.levelno >= logging.WARNING:
            source = record.__dict__.get("source_path")
            self._record_issue(message, Path(source) if isinstance(source, (str, Path)) else None)

    def _show_warning(
        self,
        message: Warning | str,
        category: type[Warning],
        filename: str,
        lineno: int,
        file: IO[str] | None = None,
        line: str | None = None,
    ) -> None:
        if self.verbose:
            self.console.print(
                Text(
                    self._redact(warnings.formatwarning(message, category, filename, lineno, line))
                )
            )
        self._record_issue(str(message))

    def _redact(self, message: str) -> str:
        for secret in self._secrets:
            message = message.replace(secret, "[redacted]")
        return re.sub(r"(?i)(bearer\s+)[A-Za-z0-9._~+/=-]+", r"\1[redacted]", message)

    def _record_issue(self, message: str, source: Path | None = None) -> None:
        if message.startswith(
            (
                "Using a slow image processor as `use_fast` is unset",
                "Using padding='same' with even kernel lengths and odd dilation",
                "NOTE: Redirects are currently not supported in Windows or MacOs.",
                "NOTE: Redirects are currently not supported in MacOs.",
            )
        ) or message in (
            "The text detection result is empty",
            "The identified content is empty.",
        ):
            return
        if "pdf cells matched neither a row nor a column band" in message:
            message = "Table extraction dropped some content; review the Markdown tables."
        elif message.startswith("Table cell bbox coordinate") and "clamping" in message:
            message = "Table geometry was adjusted; review the Markdown tables."
        elif message.startswith("Provenance bbox coordinate") and "clamping" in message:
            message = "Document geometry was adjusted; review the extracted content."
        elif message.startswith("Skipping malformed picture shape: no embedded image"):
            message = (
                "A picture without embedded image data was skipped; review the source document."
            )
        self.issues.setdefault(source or self.source, set()).add(self._redact(message))

    def print_summary(self, root: Path) -> None:
        """Display actionable diagnostics grouped by document, without raw log prefixes."""
        if not self.issues:
            return
        self.console.print("\nReview recommended:", style="yellow")
        for source, messages in self.issues.items():
            label = (
                str(source.relative_to(root) if source.is_relative_to(root) else source)
                if source is not None
                else "Command"
            )
            self.console.print(Text(f"  {label}"))
            for message in sorted(messages):
                self.console.print(Text(f"    {message}"))


def setup_error_logger(
    log_file: Path | None = None,
    service_name: str = "nest",
) -> logging.LoggerAdapter[logging.Logger]:
    """Setup file logger for error tracking.

    Creates or appends to an error log file with ISO timestamp format.
    Each call creates a new logger instance with its own file handler.

    Args:
        log_file: Path to the log file. Defaults to .nest/errors.log in cwd.
        service_name: Service name to include in log entries (e.g., "sync").

    Returns:
        Configured logger instance for error logging.
    """
    if log_file is None:
        log_file = Path(NEST_META_DIR) / ERROR_LOG_FILENAME

    # Use a dedicated namespace outside the legacy error-logger hierarchy.
    logger_name = f"nest.error_log.{service_name}.{id(log_file)}"
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.ERROR)
    logger.propagate = False

    # Clear any existing handlers to prevent duplicates
    if logger.hasHandlers():
        logger.handlers.clear()

    # Create file handler that appends
    handler = logging.FileHandler(log_file, mode="a", encoding="utf-8")
    handler.setLevel(logging.ERROR)

    # Format: 2026-01-12T10:30:00 ERROR [sync] message
    formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)s [%(service)s] %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    # Store service name for use in log entries
    # Pyright strict requires typed generic for LoggerAdapter
    adapter = logging.LoggerAdapter(logger, {"service": service_name})

    return adapter


def log_processing_error(
    logger: logging.Logger | logging.LoggerAdapter[logging.Logger],
    file_path: Path,
    error: str,
) -> None:
    """Log a processing error with standard format.

    Logs an error for a specific file with the error description.

    Args:
        logger: Logger instance from setup_error_logger.
        file_path: Path to the file that failed processing.
        error: Error message describing the failure.
    """
    logger.error("%s: %s", file_path.name, error)
