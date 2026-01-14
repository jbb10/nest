"""Docling document processor adapter.

Wraps IBM Docling for converting documents to Markdown.
"""

from pathlib import Path

from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import (
    PdfPipelineOptions,
    TableFormerMode,
    TableStructureOptions,
)
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling_core.types.doc.base import ImageRefMode

from nest.core.logging import log_processing_error
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

    # Default error log file path (can be overridden)
    DEFAULT_ERROR_LOG = Path(".nest_errors.log")

    def __init__(self, error_log: Path | None = None) -> None:
        """Initialize Docling converter with optimal settings.

        Args:
            error_log: Path to the error log file. Defaults to .nest_errors.log
                       in the current working directory.
        """
        self._error_log = error_log or self.DEFAULT_ERROR_LOG

        # Configure table structure with TableFormer ACCURATE mode and cell matching
        table_structure_options = TableStructureOptions(
            do_cell_matching=True,
            mode=TableFormerMode.ACCURATE,
        )

        # Configure PDF pipeline with TableFormer for accurate table extraction
        pipeline_options = PdfPipelineOptions(
            do_table_structure=True,
            table_structure_options=table_structure_options,
        )

        self._converter = DocumentConverter(
            allowed_formats=self.SUPPORTED_FORMATS,
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options),
            },
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
            error_msg = str(e)
            # Log the error to .nest_errors.log
            log_processing_error(
                log_file=self._error_log,
                context="sync",
                file_path=source,
                error=error_msg,
            )
            return ProcessingResult(
                source_path=source,
                status="failed",
                error=error_msg,
            )
