"""Tests for output mirror service.

Tests the OutputMirrorService which orchestrates directory-preserving
document processing, routing files by extension.
"""

from pathlib import Path
from unittest.mock import Mock

from nest.adapters.protocols import DocumentProcessorProtocol, FileSystemProtocol
from nest.core.models import ProcessingResult
from nest.services.output_service import OutputMirrorService


class TestOutputMirrorService:
    """Tests for OutputMirrorService class."""

    def test_process_file_computes_correct_output_path(self) -> None:
        """AC #1: Verify output path mirrors source structure."""
        # Arrange
        mock_fs = Mock(spec=FileSystemProtocol)
        mock_fs.compute_output_path.return_value = Path("/out/sub/file.md")

        mock_processor = Mock(spec=DocumentProcessorProtocol)
        mock_processor.process.return_value = ProcessingResult(
            source_path=Path("/in/sub/file.pdf"),
            status="success",
            output_path=Path("/out/sub/file.md"),
        )

        service = OutputMirrorService(mock_fs, mock_processor)

        # Act
        service.process_file(
            source=Path("/in/sub/file.pdf"),
            raw_dir=Path("/in"),
            output_dir=Path("/out"),
        )

        # Assert
        mock_fs.compute_output_path.assert_called_once_with(
            Path("/in/sub/file.pdf"),
            Path("/in"),
            Path("/out"),
        )

    def test_process_file_calls_processor_with_correct_paths(self) -> None:
        """Verify processor receives source and computed output path."""
        # Arrange
        mock_fs = Mock(spec=FileSystemProtocol)
        mock_fs.compute_output_path.return_value = Path("/out/contracts/alpha.md")

        mock_processor = Mock(spec=DocumentProcessorProtocol)
        mock_processor.process.return_value = ProcessingResult(
            source_path=Path("/in/contracts/alpha.pdf"),
            status="success",
            output_path=Path("/out/contracts/alpha.md"),
        )

        service = OutputMirrorService(mock_fs, mock_processor)

        # Act
        service.process_file(
            source=Path("/in/contracts/alpha.pdf"),
            raw_dir=Path("/in"),
            output_dir=Path("/out"),
        )

        # Assert
        mock_processor.process.assert_called_once_with(
            Path("/in/contracts/alpha.pdf"),
            Path("/out/contracts/alpha.md"),
        )

    def test_process_file_returns_processor_result(self) -> None:
        """Verify service returns the ProcessingResult from processor."""
        # Arrange
        mock_fs = Mock(spec=FileSystemProtocol)
        mock_fs.compute_output_path.return_value = Path("/out/doc.md")

        expected_result = ProcessingResult(
            source_path=Path("/in/doc.pdf"),
            status="success",
            output_path=Path("/out/doc.md"),
        )
        mock_processor = Mock(spec=DocumentProcessorProtocol)
        mock_processor.process.return_value = expected_result

        service = OutputMirrorService(mock_fs, mock_processor)

        # Act
        result = service.process_file(
            source=Path("/in/doc.pdf"),
            raw_dir=Path("/in"),
            output_dir=Path("/out"),
        )

        # Assert
        assert result is expected_result
        assert result.status == "success"

    def test_process_file_handles_failed_processing(self) -> None:
        """Verify failed processing results are passed through."""
        # Arrange
        mock_fs = Mock(spec=FileSystemProtocol)
        mock_fs.compute_output_path.return_value = Path("/out/corrupt.md")

        failed_result = ProcessingResult(
            source_path=Path("/in/corrupt.pdf"),
            status="failed",
            output_path=None,
            error="Password protected",
        )
        mock_processor = Mock(spec=DocumentProcessorProtocol)
        mock_processor.process.return_value = failed_result

        service = OutputMirrorService(mock_fs, mock_processor)

        # Act
        result = service.process_file(
            source=Path("/in/corrupt.pdf"),
            raw_dir=Path("/in"),
            output_dir=Path("/out"),
        )

        # Assert
        assert result.status == "failed"
        assert result.error == "Password protected"

    def test_process_file_with_deeply_nested_source(self) -> None:
        """Verify deeply nested paths are handled correctly."""
        # Arrange
        mock_fs = Mock(spec=FileSystemProtocol)
        deep_output = Path("/out/a/b/c/d/file.md")
        mock_fs.compute_output_path.return_value = deep_output

        mock_processor = Mock(spec=DocumentProcessorProtocol)
        mock_processor.process.return_value = ProcessingResult(
            source_path=Path("/in/a/b/c/d/file.pdf"),
            status="success",
            output_path=deep_output,
        )

        service = OutputMirrorService(mock_fs, mock_processor)

        # Act
        result = service.process_file(
            source=Path("/in/a/b/c/d/file.pdf"),
            raw_dir=Path("/in"),
            output_dir=Path("/out"),
        )

        # Assert
        assert result.output_path == deep_output

    def test_process_file_overwrites_existing_output(self) -> None:
        """AC #3: Verify existing files are overwritten (processor behavior)."""
        # Arrange
        mock_fs = Mock(spec=FileSystemProtocol)
        mock_fs.compute_output_path.return_value = Path("/out/modified.md")

        # Processor returns success - indicating file was written (overwritten)
        mock_processor = Mock(spec=DocumentProcessorProtocol)
        mock_processor.process.return_value = ProcessingResult(
            source_path=Path("/in/modified.pdf"),
            status="success",
            output_path=Path("/out/modified.md"),
        )

        service = OutputMirrorService(mock_fs, mock_processor)

        # Act - simulate re-processing after modification
        result = service.process_file(
            source=Path("/in/modified.pdf"),
            raw_dir=Path("/in"),
            output_dir=Path("/out"),
        )

        # Assert - processor was called (would overwrite existing file)
        mock_processor.process.assert_called_once()
        assert result.status == "success"


class TestOutputMirrorServicePassthrough:
    """Tests for passthrough routing in OutputMirrorService."""

    def test_routes_txt_to_passthrough_processor(self) -> None:
        """AC2: .txt files are routed to passthrough processor."""
        mock_fs = Mock(spec=FileSystemProtocol)
        mock_docling = Mock(spec=DocumentProcessorProtocol)
        mock_passthrough = Mock(spec=DocumentProcessorProtocol)
        mock_passthrough.process.return_value = ProcessingResult(
            source_path=Path("/in/notes.txt"),
            status="success",
            output_path=Path("/out/notes.txt"),
        )

        service = OutputMirrorService(mock_fs, mock_docling, mock_passthrough)

        result = service.process_file(
            source=Path("/in/notes.txt"),
            raw_dir=Path("/in"),
            output_dir=Path("/out"),
        )

        assert result.status == "success"
        assert result.output_path == Path("/out/notes.txt")
        mock_passthrough.process.assert_called_once()
        mock_docling.process.assert_not_called()
        mock_fs.compute_output_path.assert_not_called()

    def test_routes_yaml_to_passthrough_processor(self) -> None:
        """AC2: .yaml files are routed to passthrough processor."""
        mock_fs = Mock(spec=FileSystemProtocol)
        mock_docling = Mock(spec=DocumentProcessorProtocol)
        mock_passthrough = Mock(spec=DocumentProcessorProtocol)
        mock_passthrough.process.return_value = ProcessingResult(
            source_path=Path("/in/config.yaml"),
            status="success",
            output_path=Path("/in/config.yaml"),
        )

        service = OutputMirrorService(mock_fs, mock_docling, mock_passthrough)

        service.process_file(
            source=Path("/in/config.yaml"),
            raw_dir=Path("/in"),
            output_dir=Path("/out"),
        )

        mock_passthrough.process.assert_called_once()
        mock_docling.process.assert_not_called()

    def test_routes_md_to_passthrough_processor(self) -> None:
        """AC2: .md files are routed to passthrough processor."""
        mock_fs = Mock(spec=FileSystemProtocol)
        mock_docling = Mock(spec=DocumentProcessorProtocol)
        mock_passthrough = Mock(spec=DocumentProcessorProtocol)
        mock_passthrough.process.return_value = ProcessingResult(
            source_path=Path("/in/readme.md"),
            status="success",
            output_path=Path("/out/readme.md"),
        )

        service = OutputMirrorService(mock_fs, mock_docling, mock_passthrough)

        service.process_file(
            source=Path("/in/readme.md"),
            raw_dir=Path("/in"),
            output_dir=Path("/out"),
        )

        mock_passthrough.process.assert_called_once()
        mock_docling.process.assert_not_called()

    def test_routes_pdf_to_docling_processor(self) -> None:
        """AC2: .pdf files are routed to Docling processor."""
        mock_fs = Mock(spec=FileSystemProtocol)
        mock_fs.compute_output_path.return_value = Path("/out/report.md")
        mock_docling = Mock(spec=DocumentProcessorProtocol)
        mock_docling.process.return_value = ProcessingResult(
            source_path=Path("/in/report.pdf"),
            status="success",
            output_path=Path("/out/report.md"),
        )
        mock_passthrough = Mock(spec=DocumentProcessorProtocol)

        service = OutputMirrorService(mock_fs, mock_docling, mock_passthrough)

        result = service.process_file(
            source=Path("/in/report.pdf"),
            raw_dir=Path("/in"),
            output_dir=Path("/out"),
        )

        assert result.status == "success"
        mock_docling.process.assert_called_once()
        mock_passthrough.process.assert_not_called()
        mock_fs.compute_output_path.assert_called_once()

    def test_passthrough_preserves_subdirectory(self) -> None:
        """AC3: Passthrough preserves subdirectory structure."""
        mock_fs = Mock(spec=FileSystemProtocol)
        mock_docling = Mock(spec=DocumentProcessorProtocol)
        mock_passthrough = Mock(spec=DocumentProcessorProtocol)
        mock_passthrough.process.return_value = ProcessingResult(
            source_path=Path("/in/team/notes.txt"),
            status="success",
            output_path=Path("/out/team/notes.txt"),
        )

        service = OutputMirrorService(mock_fs, mock_docling, mock_passthrough)

        service.process_file(
            source=Path("/in/team/notes.txt"),
            raw_dir=Path("/in"),
            output_dir=Path("/out"),
        )

        # Verify passthrough was called with correct output path
        call_args = mock_passthrough.process.call_args
        assert call_args[0][1] == Path("/out/team/notes.txt")

    def test_no_passthrough_processor_returns_failure(self) -> None:
        """Missing passthrough processor returns failure for text files."""
        mock_fs = Mock(spec=FileSystemProtocol)
        mock_docling = Mock(spec=DocumentProcessorProtocol)

        service = OutputMirrorService(mock_fs, mock_docling, passthrough_processor=None)

        result = service.process_file(
            source=Path("/in/notes.txt"),
            raw_dir=Path("/in"),
            output_dir=Path("/out"),
        )

        assert result.status == "failed"
        assert "not configured" in result.error
