"""Output mirror service for directory-preserving document processing.

Orchestrates document processing while maintaining source
directory structure in the output. Routes files by extension:
passthrough text files are copied as-is, Docling-convertible
files go through document conversion.
"""

from pathlib import Path

from nest.adapters.protocols import DocumentProcessorProtocol, FileSystemProtocol
from nest.core.models import ProcessingResult
from nest.core.paths import is_passthrough_extension, passthrough_mirror_path


class OutputMirrorService:
    """Service for processing files with directory mirroring.

    Orchestrates document processing while maintaining source
    directory structure in the output. Routes files by extension:
    - Passthrough text files (.md, .txt, .yaml, etc.) are copied as-is
    - Docling-convertible files (.pdf, .docx, etc.) go through document conversion
    """

    def __init__(
        self,
        filesystem: FileSystemProtocol,
        processor: DocumentProcessorProtocol,
        passthrough_processor: DocumentProcessorProtocol | None = None,
    ) -> None:
        """Initialize with required adapters.

        Args:
            filesystem: Adapter for filesystem operations.
            processor: Adapter for document conversion (Docling).
            passthrough_processor: Adapter for passthrough file copying.
                If None, passthrough files will fail with an error.
        """
        self._filesystem = filesystem
        self._processor = processor
        self._passthrough = passthrough_processor

    def process_file(
        self,
        source: Path,
        raw_dir: Path,
        output_dir: Path,
    ) -> ProcessingResult:
        """Process a single file with directory mirroring.

        Routes by extension: passthrough text files are copied as-is,
        Docling-convertible files go through document conversion.

        Args:
            source: Path to source document.
            raw_dir: Root of sources directory.
            output_dir: Root of context directory.

        Returns:
            ProcessingResult from the appropriate processor.
        """
        if is_passthrough_extension(source.suffix):
            # Passthrough: copy with original extension
            output_path = passthrough_mirror_path(source, raw_dir, output_dir)
            if self._passthrough is None:
                return ProcessingResult(
                    source_path=source,
                    status="failed",
                    error="Passthrough processor not configured",
                )
            return self._passthrough.process(source, output_path)
        else:
            # Docling conversion: change suffix to .md
            output_path = self._filesystem.compute_output_path(source, raw_dir, output_dir)
            return self._processor.process(source, output_path)

    def compute_docling_output_path(
        self,
        source: Path,
        raw_dir: Path,
        output_dir: Path,
    ) -> Path:
        """Compute the output path for a Docling-converted file.

        Delegates to the filesystem adapter, mirroring directory structure
        and replacing the source suffix with .md.

        Args:
            source: Path to source document.
            raw_dir: Root of sources directory.
            output_dir: Root of context directory.

        Returns:
            Path where the converted Markdown file would be written.
        """
        return self._filesystem.compute_output_path(source, raw_dir, output_dir)
