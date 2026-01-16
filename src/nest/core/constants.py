"""Core constants for the Nest application.

This module contains application-wide constants that define
supported file types, default paths, and other configuration values.
"""

# Supported document file extensions for processing
# These are the file types that Docling can convert to Markdown
SUPPORTED_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".pdf",
        ".docx",
        ".pptx",
        ".xlsx",
        ".html",
    }
)
