"""Tests for IndexService master index generation."""

from pathlib import Path
from unittest.mock import Mock

from nest.adapters.protocols import FileSystemProtocol
from nest.services.index_service import IndexService


class TestGenerateContent:
    """Tests for IndexService.generate_content()."""

    def test_structure_includes_header_and_file_listing(self):
        """Generated content should include project header and file listing."""
        fs = Mock(spec=FileSystemProtocol)
        service = IndexService(filesystem=fs, project_root=Path("/app"))

        files = ["contracts/beta.md", "reports/q3.md", "contracts/alpha.md"]

        content = service.generate_content(files, project_name="Test Project")

        assert "# Nest Project Index: Test Project" in content
        assert "Generated:" in content
        assert "Files: 3" in content
        assert "## File Listing" in content
        assert "contracts/alpha.md" in content
        assert "contracts/beta.md" in content
        assert "reports/q3.md" in content

    def test_files_sorted_alphabetically(self):
        """File listing should be sorted alphabetically."""
        fs = Mock(spec=FileSystemProtocol)
        service = IndexService(filesystem=fs, project_root=Path("/app"))

        files = ["z.md", "a.md", "m.md"]

        content = service.generate_content(files, project_name="Sort Test")

        parts = content.split("## File Listing")
        listing = parts[1].strip().splitlines()
        file_lines = [line for line in listing if line.strip()]

        assert file_lines[0] == "a.md"
        assert file_lines[1] == "m.md"
        assert file_lines[2] == "z.md"

    def test_empty_list_produces_zero_count(self):
        """Empty file list should show Files: 0."""
        fs = Mock(spec=FileSystemProtocol)
        service = IndexService(filesystem=fs, project_root=Path("/app"))

        content = service.generate_content([], project_name="Empty")

        assert "Files: 0" in content

    def test_content_ends_with_newline(self):
        """Generated content should end with a newline."""
        fs = Mock(spec=FileSystemProtocol)
        service = IndexService(filesystem=fs, project_root=Path("/app"))

        content = service.generate_content(["file.md"], project_name="Test")

        assert content.endswith("\n")

    def test_timestamp_is_iso_format(self):
        """Generated timestamp should be ISO 8601 format with seconds precision."""
        fs = Mock(spec=FileSystemProtocol)
        service = IndexService(filesystem=fs, project_root=Path("/app"))

        content = service.generate_content(["file.md"], project_name="Test")

        # ISO format includes T and timezone info
        # Example: 2026-01-15T10:30:00+00:00
        import re

        iso_pattern = r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}"
        assert re.search(iso_pattern, content), f"No ISO timestamp in: {content}"


class TestWriteIndex:
    """Tests for IndexService.write_index()."""

    def test_writes_to_processed_context_directory(self):
        """Index should be written to processed_context/00_MASTER_INDEX.md."""
        fs = Mock(spec=FileSystemProtocol)
        fs.exists.return_value = True
        service = IndexService(filesystem=fs, project_root=Path("/app"))

        service.write_index("test content")

        expected_path = Path("/app/processed_context/00_MASTER_INDEX.md")
        fs.write_text.assert_called_once_with(expected_path, "test content")

    def test_creates_directory_if_not_exists(self):
        """Should create processed_context directory if it doesn't exist."""
        fs = Mock(spec=FileSystemProtocol)
        fs.exists.return_value = False
        service = IndexService(filesystem=fs, project_root=Path("/app"))

        service.write_index("test content")

        fs.create_directory.assert_called_once_with(Path("/app/processed_context"))
        fs.write_text.assert_called_once()

    def test_skips_directory_creation_if_exists(self):
        """Should not create directory if it already exists."""
        fs = Mock(spec=FileSystemProtocol)
        fs.exists.return_value = True
        service = IndexService(filesystem=fs, project_root=Path("/app"))

        service.write_index("test content")

        fs.create_directory.assert_not_called()


class TestUpdateIndex:
    """Tests for IndexService.update_index() end-to-end."""

    def test_writes_to_correct_file(self):
        """update_index should write formatted content to correct path."""
        fs = Mock(spec=FileSystemProtocol)
        fs.exists.return_value = True
        service = IndexService(filesystem=fs, project_root=Path("/app"))

        service.update_index(["doc.md"], project_name="TestNested")

        expected_path = Path("/app/processed_context/00_MASTER_INDEX.md")
        fs.write_text.assert_called_once()
        args, _ = fs.write_text.call_args
        assert args[0] == expected_path
        assert "# Nest Project Index: TestNested" in args[1]
        assert "doc.md" in args[1]

    def test_handles_empty_list(self):
        """update_index with empty list should write index with zero files."""
        fs = Mock(spec=FileSystemProtocol)
        fs.exists.return_value = True
        service = IndexService(filesystem=fs, project_root=Path("/app"))

        service.update_index([], project_name="Empty Project")

        fs.write_text.assert_called_once()
        args, _ = fs.write_text.call_args
        assert "Files: 0" in args[1]


class TestIndexAccuracy:
    """Tests for AC3: Index accuracy when files are removed."""

    def test_index_only_contains_provided_files(self):
        """Index should only contain files passed to generate_content."""
        fs = Mock(spec=FileSystemProtocol)
        service = IndexService(filesystem=fs, project_root=Path("/app"))

        # Simulate files after removal - only file_b remains
        current_files = ["file_b.md"]

        content = service.generate_content(current_files, project_name="Test")

        assert "file_b.md" in content
        assert "file_a.md" not in content
        assert "file_c.md" not in content

    def test_regenerate_excludes_removed_files(self):
        """When a file is removed from manifest, index should not contain it."""
        fs = Mock(spec=FileSystemProtocol)
        fs.exists.return_value = True
        service = IndexService(filesystem=fs, project_root=Path("/app"))

        # First generation with 3 files
        files_v1 = ["a.md", "b.md", "c.md"]
        content_v1 = service.generate_content(files_v1, project_name="Test")
        assert "a.md" in content_v1
        assert "b.md" in content_v1
        assert "c.md" in content_v1
        assert "Files: 3" in content_v1

        # Second generation with b.md removed
        files_v2 = ["a.md", "c.md"]
        content_v2 = service.generate_content(files_v2, project_name="Test")
        assert "a.md" in content_v2
        assert "b.md" not in content_v2
        assert "c.md" in content_v2
        assert "Files: 2" in content_v2
