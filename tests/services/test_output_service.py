"""Tests for output mirror service.

Tests the OutputMirrorService which orchestrates directory-preserving
document processing.
"""

from pathlib import Path
from unittest.mock import Mock

import pytest

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
        result = service.process_file(
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
