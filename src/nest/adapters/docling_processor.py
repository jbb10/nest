"""Docling document processor adapter.

Wraps IBM Docling for converting documents to Markdown.
"""

from pathlib import Path

from docling.datamodel.base_models import InputFormat
from docling.datamodel.document import ConversionResult
from docling.datamodel.pipeline_options import (
    PdfPipelineOptions,
    TableFormerMode,
    TableStructureOptions,
)
from docling.document_converter import DocumentConverter, PdfFormatOption
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

    def __init__(self, enable_classification: bool = False) -> None:
        """Initialize Docling converter with optimal settings.

        Args:
            enable_classification: When True, enables Docling's local image
                classifier during conversion. Required for the two-pass image
                pipeline (stories 7.2+). Defaults to False for backward
                compatibility.
        """
        self._enable_classification = enable_classification

        # Configure table structure with TableFormer ACCURATE mode and cell matching
        table_structure_options = TableStructureOptions(
            do_cell_matching=True,
            mode=TableFormerMode.ACCURATE,
        )

        if enable_classification:
            # Classification-enabled pipeline: activates local image classifier
            # and image extraction for the two-pass vision LLM pipeline.
            # do_picture_description=False because Pass 2 is handled by
            # PictureDescriptionService (story 7.3) using type-specific prompts.
            pipeline_options = PdfPipelineOptions(
                do_table_structure=True,
                table_structure_options=table_structure_options,
                do_picture_classification=True,
                do_picture_description=False,
                generate_picture_images=True,
                images_scale=2.0,
            )
        else:
            # Standard pipeline: table extraction only, no image processing.
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

    def convert(self, source: Path) -> ConversionResult:
        """Run Pass 1 of the two-pass image pipeline.

        Executes the Docling conversion pipeline (including local image
        classification when ``enable_classification=True``) and returns the
        raw ``ConversionResult`` for the caller to use in Pass 2.

        Pass 2 (description) is performed by ``PictureDescriptionService``
        (story 7.3), which reads ``element.meta.classification.predictions``
        from each ``PictureItem`` and calls the vision LLM with a
        type-specific prompt before exporting the final Markdown.

        Args:
            source: Path to the source document to convert.

        Returns:
            The raw ``ConversionResult`` from Docling. Never returns ``None``;
            exceptions propagate to the caller.
        """
        return self._converter.convert(source)

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
            # Convert document — use self.convert() when classification is
            # enabled so that image metadata is present in the ConversionResult.
            if self._enable_classification:
                result = self.convert(source)
            else:
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
            output.write_text(markdown_content, encoding="utf-8", newline="\n")

            return ProcessingResult(
                source_path=source,
                status="success",
                output_path=output,
            )
        except Exception as e:
            error_msg = str(e)

            return ProcessingResult(
                source_path=source,
                status="failed",
                error=error_msg,
            )
