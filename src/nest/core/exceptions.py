"""Custom exception hierarchy for Nest."""


class NestError(Exception):
    """Base exception for all Nest errors.

    Catch this for general error handling in the application.
    """

    pass


class ProcessingError(NestError):
    """Document processing failed."""

    pass


class ManifestError(NestError):
    """Manifest read/write failed."""

    pass


class ConfigError(NestError):
    """User config invalid."""

    pass


class ModelError(NestError):
    """Docling model issues."""

    pass
