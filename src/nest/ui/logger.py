"""Error logging infrastructure for Nest.

Provides file-based error logging for sync operations.
Logs are written to .nest_errors.log in ISO timestamp format.

NEVER use this for user-facing messages - use messages.py Rich helpers.
This module is for diagnostic/error log files only.
"""

import logging
from pathlib import Path


def setup_error_logger(
    log_file: Path | None = None,
    service_name: str = "nest",
) -> logging.Logger:
    """Setup file logger for error tracking.

    Creates or appends to an error log file with ISO timestamp format.
    Each call creates a new logger instance with its own file handler.

    Args:
        log_file: Path to the log file. Defaults to .nest_errors.log in cwd.
        service_name: Service name to include in log entries (e.g., "sync").

    Returns:
        Configured logger instance for error logging.
    """
    if log_file is None:
        log_file = Path(".nest_errors.log")

    # Create unique logger name to avoid handler accumulation
    logger_name = f"nest.errors.{service_name}.{id(log_file)}"
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.ERROR)

    # Clear any existing handlers to prevent duplicates
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
    logger = logging.LoggerAdapter(logger, {"service": service_name})

    return logger  # type: ignore[return-value]


def log_processing_error(
    logger: logging.Logger | logging.LoggerAdapter,  # type: ignore[type-arg]
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
