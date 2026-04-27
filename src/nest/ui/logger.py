"""Error logging infrastructure for Nest.

Provides file-based error logging for sync operations.
Logs are written to .nest/errors.log in ISO timestamp format.

NEVER use this for user-facing messages - use messages.py Rich helpers.
This module is for diagnostic/error log files only.
"""

import logging
from pathlib import Path

from nest.core.paths import ERROR_LOG_FILENAME, NEST_META_DIR


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


class RichConsoleHandler(logging.Handler):
    """Logging handler that routes ``nest.*`` log records to the Rich console.

    Bridges stdlib ``logging`` to ``ui.messages`` so library code can stay
    UI-agnostic (using ``logger.warning(...)``) while still surfacing
    user-relevant messages during CLI runs.

    Filters:
        - Only records from the ``nest`` namespace are emitted (third-party
          loggers are already silenced in ``cli/main.py``).
        - The ``nest.error_log.*`` namespace is excluded; those records are
          file-only sync error logs (see :func:`setup_error_logger`).

    Routing:
        - ``WARNING`` → :func:`nest.ui.messages.warning`
        - ``ERROR`` / ``CRITICAL`` → :func:`nest.ui.messages.error`
        - Lower levels are ignored.
    """

    def emit(self, record: logging.LogRecord) -> None:
        # Lazy import to avoid a circular import at module load
        # (ui.messages -> rich; logger.py is imported very early).
        from nest.ui.messages import error as ui_error
        from nest.ui.messages import warning as ui_warning

        name = record.name
        if not (name == "nest" or name.startswith("nest.")):
            return
        if name.startswith("nest.error_log."):
            return

        try:
            message = record.getMessage()
        except Exception:  # noqa: BLE001 - never let logging crash the app
            self.handleError(record)
            return

        if record.levelno >= logging.ERROR:
            ui_error(message)
        elif record.levelno >= logging.WARNING:
            ui_warning(message)


def install_rich_console_handler() -> None:
    """Attach :class:`RichConsoleHandler` to the ``nest`` logger once.

    Idempotent: re-invocation will not add duplicate handlers. Intended to
    be called from the CLI entry point so library code (adapters/services)
    can emit user-visible messages via standard ``logger.warning(...)``
    calls without importing UI modules.
    """
    nest_logger = logging.getLogger("nest")
    if nest_logger.level > logging.WARNING or nest_logger.level == logging.NOTSET:
        nest_logger.setLevel(logging.WARNING)

    for existing in nest_logger.handlers:
        if isinstance(existing, RichConsoleHandler):
            return

    nest_logger.addHandler(RichConsoleHandler(level=logging.WARNING))
