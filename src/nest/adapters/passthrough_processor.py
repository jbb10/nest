"""Passthrough file processor for text files.

Copies text files without conversion, preserving original content and extension.
Implements DocumentProcessorProtocol for seamless integration with the sync pipeline.
"""

import shutil
from pathlib import Path

from nest.core.models import ProcessingResult


class PassthroughProcessor:
    """Copies text files without conversion, preserving original content and extension.

    Used for text files in _nest_sources/ that don't need Docling conversion
    (e.g., .md, .txt, .yaml, .csv, .json).
    """

    def process(self, source: Path, output: Path) -> ProcessingResult:
        """Copy source file to output location.

        Creates parent directories as needed and copies the file content
        preserving the original extension.

        Args:
            source: Path to the source text file.
            output: Path where the file should be copied.

        Returns:
            ProcessingResult indicating success or failure.
        """
        try:
            output.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, output)
            return ProcessingResult(
                source_path=source,
                status="success",
                output_path=output,
            )
        except Exception as e:
            return ProcessingResult(
                source_path=source,
                status="failed",
                error=str(e),
            )
