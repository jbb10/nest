"""Tests for IndexService master index generation."""

from pathlib import Path
from unittest.mock import Mock

from nest.adapters.protocols import FileSystemProtocol
from nest.core.models import FileMetadata
from nest.services.index_service import IndexService, parse_index_descriptions


def _make_metadata(path: str, lines: int = 10, content_hash: str = "abc123") -> FileMetadata:
    """Helper to create FileMetadata with defaults."""
    return FileMetadata(
        path=path,
        content_hash=content_hash,
        lines=lines,
        headings=[],
        first_paragraph="",
        table_columns=[],
    )


class TestGenerateContent:
    """Tests for IndexService.generate_content() with table format."""

    def test_structure_includes_header_and_table(self):
        """Generated content should include project header and table format."""
        fs = Mock(spec=FileSystemProtocol)
        service = IndexService(filesystem=fs, project_root=Path("/app"))

        files = [
            _make_metadata("contracts/beta.md", lines=50),
            _make_metadata("reports/q3.md", lines=200),
            _make_metadata("contracts/alpha.md", lines=100),
        ]

        content = service.generate_content(
            files, old_descriptions={}, old_hints={}, project_name="Test Project"
        )

        assert "# Nest Project Index: Test Project" in content
        assert "Generated:" in content
        assert "Files: 3" in content
        assert "## File Listing" in content
        assert "| File | Lines | Description |" in content
        assert "|------|------:|-------------|" in content
        assert "contracts/alpha.md" in content
        assert "contracts/beta.md" in content
        assert "reports/q3.md" in content

    def test_table_start_end_markers_present(self):
        """Table should have nest:index-table-start/end markers."""
        fs = Mock(spec=FileSystemProtocol)
        service = IndexService(filesystem=fs, project_root=Path("/app"))

        files = [_make_metadata("doc.md")]
        content = service.generate_content(
            files, old_descriptions={}, old_hints={}, project_name="Test"
        )

        assert "<!-- nest:index-table-start -->" in content
        assert "<!-- nest:index-table-end -->" in content

    def test_lines_column_populated_with_correct_counts(self):
        """Lines column should show accurate line counts."""
        fs = Mock(spec=FileSystemProtocol)
        service = IndexService(filesystem=fs, project_root=Path("/app"))

        files = [_make_metadata("doc.md", lines=284)]
        content = service.generate_content(
            files, old_descriptions={}, old_hints={}, project_name="Test"
        )

        assert "| doc.md | 284 |" in content

    def test_files_sorted_alphabetically(self):
        """File listing should be sorted alphabetically."""
        fs = Mock(spec=FileSystemProtocol)
        service = IndexService(filesystem=fs, project_root=Path("/app"))

        files = [
            _make_metadata("z.md"),
            _make_metadata("a.md"),
            _make_metadata("m.md"),
        ]

        content = service.generate_content(
            files, old_descriptions={}, old_hints={}, project_name="Sort Test"
        )

        idx_a = content.index("a.md")
        idx_m = content.index("m.md")
        idx_z = content.index("z.md")
        assert idx_a < idx_m < idx_z

    def test_empty_list_produces_zero_count(self):
        """Empty file list should show Files: 0."""
        fs = Mock(spec=FileSystemProtocol)
        service = IndexService(filesystem=fs, project_root=Path("/app"))

        content = service.generate_content(
            [], old_descriptions={}, old_hints={}, project_name="Empty"
        )

        assert "Files: 0" in content

    def test_content_ends_with_newline(self):
        """Generated content should end with a newline."""
        fs = Mock(spec=FileSystemProtocol)
        service = IndexService(filesystem=fs, project_root=Path("/app"))

        content = service.generate_content(
            [_make_metadata("file.md")],
            old_descriptions={},
            old_hints={},
            project_name="Test",
        )

        assert content.endswith("\n")

    def test_timestamp_is_iso_format(self):
        """Generated timestamp should be ISO 8601 format with seconds precision."""
        import re

        fs = Mock(spec=FileSystemProtocol)
        service = IndexService(filesystem=fs, project_root=Path("/app"))

        content = service.generate_content(
            [_make_metadata("file.md")],
            old_descriptions={},
            old_hints={},
            project_name="Test",
        )

        iso_pattern = r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}"
        assert re.search(iso_pattern, content), f"No ISO timestamp in: {content}"

    def test_description_empty_for_new_files(self):
        """New files (not in old_hints) should have empty Description."""
        fs = Mock(spec=FileSystemProtocol)
        service = IndexService(filesystem=fs, project_root=Path("/app"))

        files = [_make_metadata("new.md", content_hash="newhash")]
        content = service.generate_content(
            files, old_descriptions={}, old_hints={}, project_name="Test"
        )

        assert "| new.md | 10 |  |" in content

    def test_description_preserved_when_content_hash_unchanged(self):
        """Description should be preserved when content_hash matches old hints."""
        fs = Mock(spec=FileSystemProtocol)
        service = IndexService(filesystem=fs, project_root=Path("/app"))

        files = [_make_metadata("doc.md", lines=50, content_hash="samehash")]
        content = service.generate_content(
            files,
            old_descriptions={"doc.md": "An important document"},
            old_hints={"doc.md": "samehash"},
            project_name="Test",
        )

        assert "| doc.md | 50 | An important document |" in content

    def test_description_cleared_when_content_hash_changed(self):
        """Description should be cleared when content_hash differs from old hints."""
        fs = Mock(spec=FileSystemProtocol)
        service = IndexService(filesystem=fs, project_root=Path("/app"))

        files = [_make_metadata("doc.md", lines=60, content_hash="newhash")]
        content = service.generate_content(
            files,
            old_descriptions={"doc.md": "Old description"},
            old_hints={"doc.md": "oldhash"},
            project_name="Test",
        )

        assert "| doc.md | 60 |  |" in content

    def test_index_only_contains_provided_files(self):
        """Index should only contain files passed to generate_content."""
        fs = Mock(spec=FileSystemProtocol)
        service = IndexService(filesystem=fs, project_root=Path("/app"))

        current_files = [_make_metadata("file_b.md")]
        content = service.generate_content(
            current_files, old_descriptions={}, old_hints={}, project_name="Test"
        )

        assert "file_b.md" in content
        assert "file_a.md" not in content
        assert "file_c.md" not in content


class TestWriteIndex:
    """Tests for IndexService.write_index()."""

    def test_writes_to_meta_directory(self):
        """Index should be written to .nest/00_MASTER_INDEX.md."""
        fs = Mock(spec=FileSystemProtocol)
        fs.exists.return_value = True
        service = IndexService(filesystem=fs, project_root=Path("/app"))

        service.write_index("test content")

        expected_path = Path("/app/.nest/00_MASTER_INDEX.md")
        fs.write_text.assert_called_once_with(expected_path, "test content")

    def test_creates_directory_if_not_exists(self):
        """Should create .nest/ directory if it doesn't exist."""
        fs = Mock(spec=FileSystemProtocol)
        fs.exists.return_value = False
        service = IndexService(filesystem=fs, project_root=Path("/app"))

        service.write_index("test content")

        fs.create_directory.assert_called_once_with(Path("/app/.nest"))
        fs.write_text.assert_called_once()

    def test_skips_directory_creation_if_exists(self):
        """Should not create directory if it already exists."""
        fs = Mock(spec=FileSystemProtocol)
        fs.exists.return_value = True
        service = IndexService(filesystem=fs, project_root=Path("/app"))

        service.write_index("test content")

        fs.create_directory.assert_not_called()


class TestReadIndexContent:
    """Tests for IndexService.read_index_content()."""

    def test_returns_content_when_file_exists(self):
        """Should return file content when index exists."""
        fs = Mock(spec=FileSystemProtocol)
        fs.exists.return_value = True
        fs.read_text.return_value = "# Index content"
        service = IndexService(filesystem=fs, project_root=Path("/app"))

        result = service.read_index_content()

        assert result == "# Index content"
        fs.read_text.assert_called_once_with(Path("/app/.nest/00_MASTER_INDEX.md"))

    def test_returns_empty_string_when_file_missing(self):
        """Should return empty string when index doesn't exist."""
        fs = Mock(spec=FileSystemProtocol)
        fs.exists.return_value = False
        service = IndexService(filesystem=fs, project_root=Path("/app"))

        result = service.read_index_content()

        assert result == ""
        fs.read_text.assert_not_called()

    def test_returns_empty_string_on_os_error(self):
        """Should return empty string when read fails."""
        fs = Mock(spec=FileSystemProtocol)
        fs.exists.return_value = True
        fs.read_text.side_effect = OSError("Permission denied")
        service = IndexService(filesystem=fs, project_root=Path("/app"))

        result = service.read_index_content()

        assert result == ""


class TestParseIndexDescriptions:
    """Tests for parse_index_descriptions()."""

    def test_parses_valid_table(self):
        """Should extract file→description from a valid table."""
        content = (
            "# Index\n\n"
            "<!-- nest:index-table-start -->\n"
            "| File | Lines | Description |\n"
            "|------|------:|-------------|\n"
            "| doc.md | 100 | An important doc |\n"
            "| notes.txt | 42 |  |\n"
            "<!-- nest:index-table-end -->\n"
        )
        result = parse_index_descriptions(content)
        assert result == {"doc.md": "An important doc", "notes.txt": ""}

    def test_returns_empty_with_missing_markers(self):
        """Should return empty dict if markers are missing (first run)."""
        content = "# Index\n\nSome content\n"
        result = parse_index_descriptions(content)
        assert result == {}

    def test_returns_empty_with_empty_table(self):
        """Should return empty dict for table with no data rows."""
        content = (
            "<!-- nest:index-table-start -->\n"
            "| File | Lines | Description |\n"
            "|------|------:|-------------|\n"
            "<!-- nest:index-table-end -->\n"
        )
        result = parse_index_descriptions(content)
        assert result == {}

    def test_handles_pipe_characters_in_descriptions(self):
        """Should handle descriptions containing pipe characters."""
        content = (
            "<!-- nest:index-table-start -->\n"
            "| File | Lines | Description |\n"
            "|------|------:|-------------|\n"
            "| doc.md | 100 | Input | output mapping |\n"
            "<!-- nest:index-table-end -->\n"
        )
        result = parse_index_descriptions(content)
        assert result["doc.md"] == "Input | output mapping"

    def test_handles_malformed_rows(self):
        """Should skip rows with insufficient parts."""
        content = (
            "<!-- nest:index-table-start -->\n"
            "| File | Lines | Description |\n"
            "|------|------:|-------------|\n"
            "bad row\n"
            "| doc.md | 100 | Good |\n"
            "<!-- nest:index-table-end -->\n"
        )
        result = parse_index_descriptions(content)
        assert result == {"doc.md": "Good"}

    def test_hints_file_excluded_from_index(self):
        """00_INDEX_HINTS.yaml should not appear in generated index content."""
        fs = Mock(spec=FileSystemProtocol)
        service = IndexService(filesystem=fs, project_root=Path("/app"))

        files = [_make_metadata("doc.md")]
        content = service.generate_content(
            files, old_descriptions={}, old_hints={}, project_name="Test"
        )
        assert "00_INDEX_HINTS.yaml" not in content
