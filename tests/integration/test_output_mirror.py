"""Integration tests for output mirroring with real filesystem.

Tests the full pipeline from source discovery through output mirroring
using temporary directories on the real filesystem.
"""

from pathlib import Path
from unittest.mock import Mock

from nest.adapters.filesystem import FileSystemAdapter
from nest.adapters.protocols import DocumentProcessorProtocol
from nest.core.models import ProcessingResult
from nest.core.paths import mirror_path, relative_to_project
from nest.services.output_service import OutputMirrorService


class TestOutputMirrorIntegration:
    """Integration tests for output mirroring with real filesystem."""

    def test_full_pipeline_creates_mirrored_output(self, tmp_path: Path) -> None:
        """AC #1, #2: Full pipeline creates output at mirrored location."""
        # Arrange - create source directory structure
        raw_inbox = tmp_path / "raw_inbox"
        raw_inbox.mkdir()
        processed_context = tmp_path / "_nest_context"
        # Note: processed_context is NOT pre-created

        # Create nested source structure
        source_dir = raw_inbox / "contracts" / "2024"
        source_dir.mkdir(parents=True)
        source_file = source_dir / "alpha.pdf"
        source_file.write_bytes(b"fake pdf content")

        # Mock processor that writes actual content
        def mock_process(source: Path, output: Path) -> ProcessingResult:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(f"# Converted from {source.name}")
            return ProcessingResult(
                source_path=source,
                status="success",
                output_path=output,
            )

        mock_processor = Mock(spec=DocumentProcessorProtocol)
        mock_processor.process.side_effect = mock_process

        filesystem = FileSystemAdapter()
        service = OutputMirrorService(filesystem, mock_processor)

        # Act
        result = service.process_file(source_file, raw_inbox, processed_context)

        # Assert
        assert result.status == "success"
        expected_output = processed_context / "contracts" / "2024" / "alpha.md"
        assert expected_output.exists()
        assert expected_output.read_text() == "# Converted from alpha.pdf"

    def test_automatic_directory_creation(self, tmp_path: Path) -> None:
        """AC #2: Output directories are created automatically."""
        # Arrange
        raw_inbox = tmp_path / "raw_inbox"
        raw_inbox.mkdir()
        processed_context = tmp_path / "_nest_context"
        # Intentionally NOT creating processed_context or subdirs

        # Create deeply nested source
        deep_dir = raw_inbox / "legal" / "contracts" / "2024" / "q1" / "clients"
        deep_dir.mkdir(parents=True)
        source_file = deep_dir / "agreement.docx"
        source_file.write_bytes(b"fake docx")

        def mock_process(source: Path, output: Path) -> ProcessingResult:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text("# Agreement content")
            return ProcessingResult(
                source_path=source,
                status="success",
                output_path=output,
            )

        mock_processor = Mock(spec=DocumentProcessorProtocol)
        mock_processor.process.side_effect = mock_process

        filesystem = FileSystemAdapter()
        service = OutputMirrorService(filesystem, mock_processor)

        # Act
        result = service.process_file(source_file, raw_inbox, processed_context)

        # Assert
        assert result.status == "success"
        expected_dir = processed_context / "legal" / "contracts" / "2024" / "q1" / "clients"
        assert expected_dir.exists()
        assert (expected_dir / "agreement.md").exists()

    def test_overwrite_modified_files(self, tmp_path: Path) -> None:
        """AC #3: Existing output files are overwritten on re-processing."""
        # Arrange
        raw_inbox = tmp_path / "raw_inbox"
        raw_inbox.mkdir()
        processed_context = tmp_path / "_nest_context"
        processed_context.mkdir()

        source_file = raw_inbox / "document.pdf"
        source_file.write_bytes(b"original content")

        output_file = processed_context / "document.md"
        output_file.write_text("# Original version")

        def mock_process(source: Path, output: Path) -> ProcessingResult:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text("# Updated version")
            return ProcessingResult(
                source_path=source,
                status="success",
                output_path=output,
            )

        mock_processor = Mock(spec=DocumentProcessorProtocol)
        mock_processor.process.side_effect = mock_process

        filesystem = FileSystemAdapter()
        service = OutputMirrorService(filesystem, mock_processor)

        # Act
        result = service.process_file(source_file, raw_inbox, processed_context)

        # Assert
        assert result.status == "success"
        assert output_file.read_text() == "# Updated version"

    def test_file_at_root_level(self, tmp_path: Path) -> None:
        """Edge case: File directly in raw_inbox root."""
        # Arrange
        raw_inbox = tmp_path / "raw_inbox"
        raw_inbox.mkdir()
        processed_context = tmp_path / "_nest_context"

        source_file = raw_inbox / "readme.pdf"
        source_file.write_bytes(b"root file")

        def mock_process(source: Path, output: Path) -> ProcessingResult:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text("# Root readme")
            return ProcessingResult(
                source_path=source,
                status="success",
                output_path=output,
            )

        mock_processor = Mock(spec=DocumentProcessorProtocol)
        mock_processor.process.side_effect = mock_process

        filesystem = FileSystemAdapter()
        service = OutputMirrorService(filesystem, mock_processor)

        # Act
        service.process_file(source_file, raw_inbox, processed_context)

        # Assert
        expected_output = processed_context / "readme.md"
        assert expected_output.exists()

    def test_path_helpers_with_real_paths(self, tmp_path: Path) -> None:
        """AC #4: Path helpers work correctly with real filesystem paths."""
        # Arrange
        raw_inbox = tmp_path / "raw_inbox"
        processed_context = tmp_path / "_nest_context"
        source = raw_inbox / "reports" / "2024" / "q1.xlsx"

        # Act
        output = mirror_path(source, raw_inbox, processed_context)
        relative = relative_to_project(output, tmp_path)

        # Assert
        assert output == processed_context / "reports" / "2024" / "q1.md"
        assert relative == "processed_context/reports/2024/q1.md"
        assert "/" in relative  # Forward slashes for portability

    def test_multiple_files_in_different_directories(self, tmp_path: Path) -> None:
        """Multiple files across different subdirectories."""
        # Arrange
        raw_inbox = tmp_path / "raw_inbox"
        processed_context = tmp_path / "_nest_context"

        files = [
            raw_inbox / "contracts" / "a.pdf",
            raw_inbox / "reports" / "b.xlsx",
            raw_inbox / "presentations" / "2024" / "c.pptx",
            raw_inbox / "d.docx",
        ]

        for f in files:
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_bytes(b"content")

        def mock_process(source: Path, output: Path) -> ProcessingResult:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(f"# {source.stem}")
            return ProcessingResult(
                source_path=source,
                status="success",
                output_path=output,
            )

        mock_processor = Mock(spec=DocumentProcessorProtocol)
        mock_processor.process.side_effect = mock_process

        filesystem = FileSystemAdapter()
        service = OutputMirrorService(filesystem, mock_processor)

        # Act & Assert
        for source in files:
            result = service.process_file(source, raw_inbox, processed_context)
            assert result.status == "success"

        # Verify all outputs exist at correct locations
        assert (processed_context / "contracts" / "a.md").exists()
        assert (processed_context / "reports" / "b.md").exists()
        assert (processed_context / "presentations" / "2024" / "c.md").exists()
        assert (processed_context / "d.md").exists()
