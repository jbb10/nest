"""Tests for file discovery adapter."""

from pathlib import Path

from nest.adapters.file_discovery import FileDiscoveryAdapter
from nest.adapters.protocols import FileDiscoveryProtocol


class TestFileDiscoveryAdapter:
    """Tests for FileDiscoveryAdapter class."""

    def test_implements_protocol(self) -> None:
        """Verify adapter implements FileDiscoveryProtocol."""
        adapter = FileDiscoveryAdapter()
        assert isinstance(adapter, FileDiscoveryProtocol)

    def test_discovers_supported_files_recursively(self, tmp_path: Path) -> None:
        """Verify recursive discovery finds files in subdirectories."""
        # Arrange
        (tmp_path / "doc1.pdf").write_bytes(b"pdf content")
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        (subdir / "doc2.pdf").write_bytes(b"nested pdf")
        (subdir / "deep" / "nested").mkdir(parents=True)
        (subdir / "deep" / "nested" / "doc3.pdf").write_bytes(b"deep pdf")

        adapter = FileDiscoveryAdapter()

        # Act
        result = adapter.discover(tmp_path, {".pdf"})

        # Assert
        assert len(result) == 3
        assert all(p.suffix == ".pdf" for p in result)

    def test_filters_by_extension(self, tmp_path: Path) -> None:
        """Verify only specified extensions are included."""
        # Arrange
        (tmp_path / "document.pdf").write_bytes(b"pdf")
        (tmp_path / "spreadsheet.xlsx").write_bytes(b"xlsx")
        (tmp_path / "readme.txt").write_bytes(b"text")
        (tmp_path / "image.jpg").write_bytes(b"image")

        adapter = FileDiscoveryAdapter()

        # Act
        result = adapter.discover(tmp_path, {".pdf", ".xlsx"})

        # Assert
        assert len(result) == 2
        suffixes = {p.suffix for p in result}
        assert suffixes == {".pdf", ".xlsx"}

    def test_extension_matching_is_case_insensitive(self, tmp_path: Path) -> None:
        """Verify .PDF and .pdf both match when searching for .pdf."""
        # Arrange
        (tmp_path / "lower.pdf").write_bytes(b"pdf")
        (tmp_path / "upper.PDF").write_bytes(b"pdf")
        (tmp_path / "mixed.PdF").write_bytes(b"pdf")

        adapter = FileDiscoveryAdapter()

        # Act
        result = adapter.discover(tmp_path, {".pdf"})

        # Assert
        assert len(result) == 3

    def test_ignores_hidden_files(self, tmp_path: Path) -> None:
        """Verify files starting with . are excluded."""
        # Arrange
        (tmp_path / "visible.pdf").write_bytes(b"pdf")
        (tmp_path / ".hidden.pdf").write_bytes(b"hidden pdf")

        adapter = FileDiscoveryAdapter()

        # Act
        result = adapter.discover(tmp_path, {".pdf"})

        # Assert
        assert len(result) == 1
        assert result[0].name == "visible.pdf"

    def test_ignores_hidden_directories(self, tmp_path: Path) -> None:
        """Verify directories starting with . are excluded."""
        # Arrange
        (tmp_path / "visible.pdf").write_bytes(b"pdf")
        hidden_dir = tmp_path / ".hidden"
        hidden_dir.mkdir()
        (hidden_dir / "secret.pdf").write_bytes(b"secret pdf")

        adapter = FileDiscoveryAdapter()

        # Act
        result = adapter.discover(tmp_path, {".pdf"})

        # Assert
        assert len(result) == 1
        assert result[0].name == "visible.pdf"

    def test_returns_sorted_list(self, tmp_path: Path) -> None:
        """Verify results are sorted for deterministic ordering."""
        # Arrange
        (tmp_path / "zebra.pdf").write_bytes(b"z")
        (tmp_path / "alpha.pdf").write_bytes(b"a")
        (tmp_path / "middle.pdf").write_bytes(b"m")

        adapter = FileDiscoveryAdapter()

        # Act
        result = adapter.discover(tmp_path, {".pdf"})

        # Assert
        assert result == sorted(result)
        assert result[0].name == "alpha.pdf"
        assert result[-1].name == "zebra.pdf"

    def test_returns_absolute_paths(self, tmp_path: Path) -> None:
        """Verify all returned paths are absolute."""
        # Arrange
        (tmp_path / "doc.pdf").write_bytes(b"pdf")

        adapter = FileDiscoveryAdapter()

        # Act
        result = adapter.discover(tmp_path, {".pdf"})

        # Assert
        assert len(result) == 1
        assert result[0].is_absolute()

    def test_handles_empty_directory(self, tmp_path: Path) -> None:
        """Verify empty directories return empty list."""
        # Arrange
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        adapter = FileDiscoveryAdapter()

        # Act
        result = adapter.discover(empty_dir, {".pdf"})

        # Assert
        assert result == []

    def test_handles_no_matching_extensions(self, tmp_path: Path) -> None:
        """Verify no matches when extensions don't match."""
        # Arrange
        (tmp_path / "document.txt").write_bytes(b"text")
        (tmp_path / "image.jpg").write_bytes(b"image")

        adapter = FileDiscoveryAdapter()

        # Act
        result = adapter.discover(tmp_path, {".pdf", ".docx"})

        # Assert
        assert result == []

    def test_discovers_all_supported_extensions(self, tmp_path: Path) -> None:
        """Verify all supported document types are discovered."""
        # Arrange
        (tmp_path / "doc.pdf").write_bytes(b"pdf")
        (tmp_path / "doc.docx").write_bytes(b"docx")
        (tmp_path / "doc.pptx").write_bytes(b"pptx")
        (tmp_path / "doc.xlsx").write_bytes(b"xlsx")
        (tmp_path / "doc.html").write_bytes(b"html")
        (tmp_path / "doc.txt").write_bytes(b"txt - unsupported")

        adapter = FileDiscoveryAdapter()
        extensions = {".pdf", ".docx", ".pptx", ".xlsx", ".html"}

        # Act
        result = adapter.discover(tmp_path, extensions)

        # Assert
        assert len(result) == 5
        suffixes = {p.suffix.lower() for p in result}
        assert suffixes == extensions
