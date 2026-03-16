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
