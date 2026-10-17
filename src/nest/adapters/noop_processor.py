"""Fallback document processor for when Docling is not installed.

Implements DocumentProcessorProtocol so CLI composition roots can wire a
processor unconditionally and let every file fail with a clear reason.
"""

from pathlib import Path

from nest.core.models import ProcessingResult


class NoOpProcessor:
    """Fallback processor when docling is missing."""

    def process(self, source: Path, output: Path) -> ProcessingResult:
        """Fail all processing."""
        return ProcessingResult(
            source_path=source,
            status="failed",
            error="Docling is not installed",
        )
