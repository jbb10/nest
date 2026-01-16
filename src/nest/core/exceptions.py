"""Custom exception hierarchy for Nest."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


class NestError(Exception):
    """Base exception for all Nest errors.

    Catch this for general error handling in the application.
    """

    pass


class ProcessingError(NestError):
    """Document processing failed.

    Attributes:
        source_path: Path to the file that failed processing.
        message: Human-readable error description.
    """

    def __init__(self, message: str, source_path: "Path | None" = None) -> None:
        """Initialize ProcessingError.

        Args:
            message: Human-readable error description.
            source_path: Path to the file that failed processing.
        """
        super().__init__(message)
        self.source_path = source_path
        self.message = message


class ManifestError(NestError):
    """Manifest read/write failed."""

    pass


class ConfigError(NestError):
    """User config invalid."""

    pass


class ModelError(NestError):
    """Docling model issues."""

    pass
