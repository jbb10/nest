"""Output mirror service for directory-preserving document processing.

Orchestrates document processing while maintaining source
directory structure in the output.
"""

from pathlib import Path

from nest.adapters.protocols import DocumentProcessorProtocol, FileSystemProtocol
from nest.core.models import ProcessingResult


class OutputMirrorService:
    """Service for processing files with directory mirroring.

    Orchestrates document processing while maintaining source
    directory structure in the output. Delegates path computation
    to the filesystem adapter and document conversion to the processor.
    """

    def __init__(
        self,
        filesystem: FileSystemProtocol,
        processor: DocumentProcessorProtocol,
    ) -> None:
        """Initialize with required adapters.

        Args:
            filesystem: Adapter for filesystem operations.
            processor: Adapter for document conversion.
        """
        self._filesystem = filesystem
        self._processor = processor

    def process_file(
        self,
        source: Path,
        raw_dir: Path,
        output_dir: Path,
    ) -> ProcessingResult:
        """Process a single file with directory mirroring.

        Computes the mirrored output path, ensures parent directories
        exist, and delegates to the document processor.

        Args:
            source: Path to source document.
            raw_dir: Root of sources directory.
            output_dir: Root of context directory.

        Returns:
            ProcessingResult from the document processor.
        """
        # Compute mirrored output path
        output_path = self._filesystem.compute_output_path(source, raw_dir, output_dir)

        # Process document (processor handles dir creation)
        return self._processor.process(source, output_path)
