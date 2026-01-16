"""Error logging configuration for Nest.

Provides logging utilities for file processing errors that are written
to .nest_errors.log for diagnostics. User-facing messages should use
Rich console output (nest.ui.messages), not this logger.
"""

import logging
from pathlib import Path


def setup_error_logger(log_file: Path) -> logging.Logger:
    """Configure error logger for .nest_errors.log.

    Creates or retrieves a logger that writes processing errors to a file.
    Uses a custom format including context and file path.

    Args:
        log_file: Path to the error log file.

    Returns:
        Configured logger instance.
    """
    logger = logging.getLogger("nest.errors")
    logger.setLevel(logging.WARNING)

    # Avoid adding duplicate handlers
    if not logger.handlers:
        # Ensure log directory exists
        log_file.parent.mkdir(parents=True, exist_ok=True)

        handler = logging.FileHandler(log_file)
        handler.setLevel(logging.WARNING)

        # Format: {timestamp} {level} [{context}] {file}: {message}
        formatter = logging.Formatter(
            fmt="%(asctime)s %(levelname)s [%(context)s] %(file_path)s: %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger


def log_processing_error(log_file: Path, context: str, file_path: Path, error: str) -> None:
    """Log a processing error to the error log file.

    Args:
        log_file: Path to the error log file.
        context: Context identifier (e.g., "sync", "doctor").
        file_path: Path to the file that failed.
        error: Error message describing the failure.
    """
    logger = setup_error_logger(log_file)
    logger.error(
        error,
        extra={"context": context, "file_path": str(file_path)},
    )
