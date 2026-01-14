"""Docling document processor adapter.

Wraps IBM Docling for converting documents to Markdown.
"""

from pathlib import Path

from docling.datamodel.base_models import InputFormat
from docling.document_converter import DocumentConverter
from docling_core.types.doc.base import ImageRefMode

from nest.core.models import ProcessingResult


class DoclingProcessor:
    """Document processor using IBM Docling for conversion.

    Converts PDF, DOCX, PPTX, XLSX, and HTML files to Markdown.
    Uses TableFormer for accurate table structure extraction.

    IMPORTANT: Output is optimized for LLM consumption - no base64-encoded
    images or binary artifacts are included in the Markdown output.
    """

    SUPPORTED_FORMATS = [
        InputFormat.PDF,
        InputFormat.DOCX,
        InputFormat.PPTX,
        InputFormat.XLSX,
        InputFormat.HTML,
    ]

    def __init__(self) -> None:
        """Initialize Docling converter with optimal settings."""
        self._converter = DocumentConverter(
            allowed_formats=self.SUPPORTED_FORMATS,
        )

    def process(self, source: Path, output: Path) -> ProcessingResult:
        """Convert a document to Markdown.

        Args:
            source: Path to the source document.
            output: Path where Markdown output should be written.

        Returns:
            ProcessingResult indicating success or failure.

        Note:
            Output Markdown excludes base64-encoded images to keep
            content token-efficient for LLM context usage.
        """
        try:
            # Convert document
            result = self._converter.convert(source)

            # Export to Markdown WITHOUT base64 images
            # ImageRefMode.PLACEHOLDER replaces images with [Image: ...] markers
            # This keeps output clean for LLM consumption
            markdown_content = result.document.export_to_markdown(
                image_mode=ImageRefMode.PLACEHOLDER,
            )

            # Ensure output directory exists
            output.parent.mkdir(parents=True, exist_ok=True)

            # Write markdown output
            output.write_text(markdown_content, encoding="utf-8")

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
