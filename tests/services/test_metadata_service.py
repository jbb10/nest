"""Tests for MetadataExtractorService."""

from pathlib import Path
from unittest.mock import Mock

import yaml

from nest.adapters.protocols import FileSystemProtocol
from nest.core.models import FileMetadata, HeadingInfo
from nest.services.metadata_service import (
    MetadataExtractorService,
    _compute_content_hash,
    _extract_csv_columns,
    _extract_first_paragraph,
    _extract_headings,
)


class TestExtractHeadings:
    """Tests for Markdown heading extraction."""

    def test_extracts_multiple_heading_levels(self):
        """Should extract h1, h2, h3 headings."""
        content = "# Title\n\nParagraph\n\n## Section\n\n### Subsection\n"
        result = _extract_headings(content)

        assert len(result) == 3
        assert result[0] == HeadingInfo(level=1, text="Title")
        assert result[1] == HeadingInfo(level=2, text="Section")
        assert result[2] == HeadingInfo(level=3, text="Subsection")

    def test_returns_empty_for_no_headings(self):
        """Should return empty list for content without headings."""
        content = "Just plain text\nAnother line\n"
        result = _extract_headings(content)
        assert result == []

    def test_strips_heading_text(self):
        """Should strip whitespace from heading text."""
        content = "# Title with trailing space   \n"
        result = _extract_headings(content)
        assert result[0].text == "Title with trailing space"

    def test_ignores_non_heading_hash_lines(self):
        """Lines starting with # but not followed by space are not headings."""
        content = "#notaheading\n## Real heading\n"
        result = _extract_headings(content)
        assert len(result) == 1
        assert result[0].text == "Real heading"


class TestExtractFirstParagraph:
    """Tests for first paragraph extraction."""

    def test_markdown_skips_headings(self):
        """First paragraph of Markdown should skip heading lines."""
        content = "# Title\n\nThis is the first paragraph.\nSecond line.\n"
        result = _extract_first_paragraph(content, is_markdown=True)
        assert result == "This is the first paragraph."

    def test_non_markdown_takes_first_line(self):
        """Non-Markdown first paragraph is just the first non-empty line."""
        content = "First line of text file\nSecond line\n"
        result = _extract_first_paragraph(content, is_markdown=False)
        assert result == "First line of text file"

    def test_truncates_to_200_chars(self):
        """Should truncate to 200 characters."""
        long_line = "x" * 300
        result = _extract_first_paragraph(long_line, is_markdown=False)
        assert len(result) == 200

    def test_empty_content_returns_empty_string(self):
        """Empty content should return empty string."""
        result = _extract_first_paragraph("", is_markdown=True)
        assert result == ""

    def test_whitespace_only_returns_empty(self):
        """Content with only whitespace should return empty string."""
        result = _extract_first_paragraph("   \n\n   \n", is_markdown=True)
        assert result == ""

    def test_skips_empty_lines_in_markdown(self):
        """Should skip empty lines before finding first paragraph."""
        content = "# Title\n\n\n\nActual paragraph\n"
        result = _extract_first_paragraph(content, is_markdown=True)
        assert result == "Actual paragraph"


class TestExtractCsvColumns:
    """Tests for CSV column header extraction."""

    def test_extracts_comma_separated_headers(self):
        """Should extract CSV header columns."""
        content = "Name,Age,City\nJohn,30,NYC\n"
        result = _extract_csv_columns(content)
        assert result == ["Name", "Age", "City"]

    def test_strips_quotes_from_headers(self):
        """Should strip quotes from CSV headers."""
        content = '"Item","Quantity","Price"\n1,2,3\n'
        result = _extract_csv_columns(content)
        assert result == ["Item", "Quantity", "Price"]

    def test_empty_content_returns_empty_list(self):
        """Empty content should return empty list."""
        result = _extract_csv_columns("")
        assert result == []


class TestComputeContentHash:
    """Tests for content hash computation."""

    def test_deterministic_same_input(self):
        """Same input should produce same hash."""
        headings = [HeadingInfo(level=1, text="Title")]
        hash1 = _compute_content_hash(headings, "paragraph", 10)
        hash2 = _compute_content_hash(headings, "paragraph", 10)
        assert hash1 == hash2

    def test_hash_length_is_16(self):
        """Hash should be 16 hex characters."""
        result = _compute_content_hash([], "", 0)
        assert len(result) == 16

    def test_hash_changes_when_headings_change(self):
        """Hash should change when headings differ."""
        h1 = _compute_content_hash([HeadingInfo(level=1, text="Old")], "", 10)
        h2 = _compute_content_hash([HeadingInfo(level=1, text="New")], "", 10)
        assert h1 != h2

    def test_hash_changes_when_paragraph_changes(self):
        """Hash should change when first paragraph differs."""
        h1 = _compute_content_hash([], "old text", 10)
        h2 = _compute_content_hash([], "new text", 10)
        assert h1 != h2

    def test_hash_changes_when_lines_change(self):
        """Hash should change when line count differs."""
        h1 = _compute_content_hash([], "", 10)
        h2 = _compute_content_hash([], "", 20)
        assert h1 != h2


class TestExtractFileMetadata:
    """Tests for MetadataExtractorService.extract_file_metadata()."""

    def test_markdown_file_extracts_headings(self):
        """Should extract headings from .md files."""
        fs = Mock(spec=FileSystemProtocol)
        fs.read_text.return_value = "# Title\n\nSome content\n\n## Section\n"
        service = MetadataExtractorService(filesystem=fs, project_root=Path("/app"))

        result = service.extract_file_metadata(
            Path("/app/_nest_context/doc.md"), Path("/app/_nest_context")
        )

        assert result.path == "doc.md"
        assert len(result.headings) == 2
        assert result.headings[0].text == "Title"
        assert result.lines == 5

    def test_txt_file_no_headings(self):
        """Non-Markdown files should have empty headings."""
        fs = Mock(spec=FileSystemProtocol)
        fs.read_text.return_value = "First line\nSecond line\n"
        service = MetadataExtractorService(filesystem=fs, project_root=Path("/app"))

        result = service.extract_file_metadata(
            Path("/app/_nest_context/notes.txt"), Path("/app/_nest_context")
        )

        assert result.headings == []
        assert result.first_paragraph == "First line"
        assert result.lines == 2

    def test_csv_file_extracts_columns(self):
        """CSV files should extract table columns."""
        fs = Mock(spec=FileSystemProtocol)
        fs.read_text.return_value = "Name,Age,City\nJohn,30,NYC\n"
        service = MetadataExtractorService(filesystem=fs, project_root=Path("/app"))

        result = service.extract_file_metadata(
            Path("/app/_nest_context/data.csv"), Path("/app/_nest_context")
        )

        assert result.table_columns == ["Name", "Age", "City"]

    def test_zero_byte_file(self):
        """Zero-byte file should return lines=0 with deterministic hash."""
        fs = Mock(spec=FileSystemProtocol)
        fs.read_text.return_value = ""
        service = MetadataExtractorService(filesystem=fs, project_root=Path("/app"))

        result = service.extract_file_metadata(
            Path("/app/_nest_context/empty.md"), Path("/app/_nest_context")
        )

        assert result.lines == 0
        assert result.headings == []
        assert result.first_paragraph == ""
        assert len(result.content_hash) == 16

    def test_unreadable_file_returns_minimal_metadata(self):
        """Unreadable file should return minimal metadata, not crash."""
        fs = Mock(spec=FileSystemProtocol)
        fs.read_text.side_effect = PermissionError("Permission denied")
        service = MetadataExtractorService(filesystem=fs, project_root=Path("/app"))

        result = service.extract_file_metadata(
            Path("/app/_nest_context/locked.md"), Path("/app/_nest_context")
        )

        assert result.lines == 0
        assert result.headings == []
        assert result.path == "locked.md"

    def test_encoding_error_returns_minimal_metadata(self):
        """File with encoding error should return minimal metadata, not crash."""
        fs = Mock(spec=FileSystemProtocol)
        fs.read_text.side_effect = UnicodeDecodeError("utf-8", b"", 0, 1, "bad")
        service = MetadataExtractorService(filesystem=fs, project_root=Path("/app"))

        result = service.extract_file_metadata(
            Path("/app/_nest_context/binary.md"), Path("/app/_nest_context")
        )

        assert result.lines == 0

    def test_line_count_crlf(self):
        """Line count should handle CRLF line endings correctly."""
        fs = Mock(spec=FileSystemProtocol)
        fs.read_text.return_value = "line1\r\nline2\r\nline3\r\n"
        service = MetadataExtractorService(filesystem=fs, project_root=Path("/app"))

        result = service.extract_file_metadata(
            Path("/app/_nest_context/win.md"), Path("/app/_nest_context")
        )

        assert result.lines == 3


class TestExtractAll:
    """Tests for MetadataExtractorService.extract_all()."""

    def test_excludes_master_index_and_hints(self):
        """Should exclude 00_MASTER_INDEX.md, 00_INDEX_HINTS.yaml, and 00_GLOSSARY_HINTS.yaml."""
        fs = Mock(spec=FileSystemProtocol)
        fs.list_files.return_value = [
            Path("/app/_nest_context/doc.md"),
            Path("/app/_nest_context/00_MASTER_INDEX.md"),
            Path("/app/_nest_context/00_INDEX_HINTS.yaml"),
            Path("/app/_nest_context/00_GLOSSARY_HINTS.yaml"),
        ]
        fs.read_text.return_value = "content\n"
        service = MetadataExtractorService(filesystem=fs, project_root=Path("/app"))

        results = service.extract_all(Path("/app/_nest_context"))

        assert len(results) == 1
        assert results[0].path == "doc.md"

    def test_glossary_md_included_in_index(self):
        """glossary.md should NOT be excluded — it's user-facing content."""
        fs = Mock(spec=FileSystemProtocol)
        fs.list_files.return_value = [
            Path("/app/_nest_context/glossary.md"),
            Path("/app/_nest_context/00_GLOSSARY_HINTS.yaml"),
        ]
        fs.read_text.return_value = "# Glossary\n"
        service = MetadataExtractorService(filesystem=fs, project_root=Path("/app"))

        results = service.extract_all(Path("/app/_nest_context"))

        paths = [r.path for r in results]
        assert "glossary.md" in paths

    def test_filters_to_supported_extensions(self):
        """Should only process files with supported text extensions."""
        fs = Mock(spec=FileSystemProtocol)
        fs.list_files.return_value = [
            Path("/app/_nest_context/doc.md"),
            Path("/app/_nest_context/image.png"),
            Path("/app/_nest_context/data.csv"),
        ]
        fs.read_text.return_value = "content\n"
        service = MetadataExtractorService(filesystem=fs, project_root=Path("/app"))

        results = service.extract_all(Path("/app/_nest_context"))

        paths = [r.path for r in results]
        assert "doc.md" in paths
        assert "data.csv" in paths
        assert "image.png" not in paths


class TestLoadPreviousHints:
    """Tests for loading previous hints file."""

    def test_returns_empty_if_file_missing(self):
        """Should return empty dict if hints file doesn't exist."""
        fs = Mock(spec=FileSystemProtocol)
        fs.exists.return_value = False
        service = MetadataExtractorService(filesystem=fs, project_root=Path("/app"))

        result = service.load_previous_hints(Path("/app/.nest/00_INDEX_HINTS.yaml"))
        assert result == {}

    def test_parses_valid_hints_file(self):
        """Should parse valid YAML hints file and return path→hash dict."""
        fs = Mock(spec=FileSystemProtocol)
        fs.exists.return_value = True
        hints_data = {
            "files": [
                {"path": "doc.md", "content_hash": "abc123"},
                {"path": "notes.txt", "content_hash": "def456"},
            ]
        }
        fs.read_text.return_value = yaml.safe_dump(hints_data)
        service = MetadataExtractorService(filesystem=fs, project_root=Path("/app"))

        result = service.load_previous_hints(Path("/app/.nest/00_INDEX_HINTS.yaml"))
        assert result == {"doc.md": "abc123", "notes.txt": "def456"}

    def test_corrupt_yaml_returns_empty(self):
        """Should return empty dict for corrupt YAML, not crash."""
        fs = Mock(spec=FileSystemProtocol)
        fs.exists.return_value = True
        fs.read_text.return_value = "{{invalid yaml: ["
        service = MetadataExtractorService(filesystem=fs, project_root=Path("/app"))

        result = service.load_previous_hints(Path("/app/.nest/00_INDEX_HINTS.yaml"))
        assert result == {}

    def test_invalid_structure_returns_empty(self):
        """Should return empty dict for valid YAML with wrong structure."""
        fs = Mock(spec=FileSystemProtocol)
        fs.exists.return_value = True
        fs.read_text.return_value = "just_a_string"
        service = MetadataExtractorService(filesystem=fs, project_root=Path("/app"))

        result = service.load_previous_hints(Path("/app/.nest/00_INDEX_HINTS.yaml"))
        assert result == {}


class TestWriteHints:
    """Tests for writing hints file."""

    def test_writes_valid_yaml_with_header(self):
        """Should write YAML with auto-generated header comment."""
        fs = Mock(spec=FileSystemProtocol)
        fs.exists.return_value = True
        service = MetadataExtractorService(filesystem=fs, project_root=Path("/app"))

        metadata = [
            FileMetadata(
                path="doc.md",
                content_hash="abc123",
                lines=42,
                headings=[HeadingInfo(level=1, text="Title")],
                first_paragraph="First paragraph text",
                table_columns=[],
            )
        ]

        service.write_hints(metadata, Path("/app/.nest/00_INDEX_HINTS.yaml"))

        fs.write_text.assert_called_once()
        written_content = fs.write_text.call_args[0][1]
        assert "Auto-generated by nest sync" in written_content

        # Parse the YAML (skip comment line)
        parsed = yaml.safe_load(written_content)
        assert len(parsed["files"]) == 1
        assert parsed["files"][0]["path"] == "doc.md"
        assert parsed["files"][0]["content_hash"] == "abc123"
        assert parsed["files"][0]["lines"] == 42

    def test_creates_parent_directory_if_missing(self):
        """Should create parent directory if it doesn't exist."""
        fs = Mock(spec=FileSystemProtocol)
        fs.exists.return_value = False
        service = MetadataExtractorService(filesystem=fs, project_root=Path("/app"))

        service.write_hints([], Path("/app/.nest/00_INDEX_HINTS.yaml"))

        fs.create_directory.assert_called_once_with(Path("/app/.nest"))
