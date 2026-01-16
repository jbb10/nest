"""Tests for filesystem adapter.

Tests the FileSystemAdapter implementation including
path computation methods for output mirroring.
"""

from pathlib import Path

from nest.adapters.filesystem import FileSystemAdapter
from nest.adapters.protocols import FileSystemProtocol


class TestFileSystemAdapter:
    """Tests for FileSystemAdapter class."""

    def test_implements_protocol(self) -> None:
        """Verify adapter implements FileSystemProtocol."""
        adapter = FileSystemAdapter()
        assert isinstance(adapter, FileSystemProtocol)

    def test_create_directory(self, tmp_path: Path) -> None:
        """Verify directory creation including parents."""
        adapter = FileSystemAdapter()
        new_dir = tmp_path / "a" / "b" / "c"

        adapter.create_directory(new_dir)

        assert new_dir.exists()
        assert new_dir.is_dir()

    def test_write_text(self, tmp_path: Path) -> None:
        """Verify text file writing."""
        adapter = FileSystemAdapter()
        file_path = tmp_path / "test.txt"

        adapter.write_text(file_path, "Hello, World!")

        assert file_path.read_text() == "Hello, World!"

    def test_read_text(self, tmp_path: Path) -> None:
        """Verify text file reading."""
        adapter = FileSystemAdapter()
        file_path = tmp_path / "test.txt"
        file_path.write_text("Test content")

        result = adapter.read_text(file_path)

        assert result == "Test content"

    def test_exists_returns_true_for_existing(self, tmp_path: Path) -> None:
        """Verify exists returns True for existing paths."""
        adapter = FileSystemAdapter()
        file_path = tmp_path / "exists.txt"
        file_path.write_text("content")

        assert adapter.exists(file_path) is True

    def test_exists_returns_false_for_nonexistent(self, tmp_path: Path) -> None:
        """Verify exists returns False for non-existent paths."""
        adapter = FileSystemAdapter()
        file_path = tmp_path / "does_not_exist.txt"

        assert adapter.exists(file_path) is False

    def test_append_text(self, tmp_path: Path) -> None:
        """Verify text appending to file."""
        adapter = FileSystemAdapter()
        file_path = tmp_path / "append.txt"
        file_path.write_text("Initial")

        adapter.append_text(file_path, " appended")

        assert file_path.read_text() == "Initial appended"

    def test_delete_file_removes_existing_file(self, tmp_path: Path) -> None:
        """Verify delete_file removes an existing file."""
        adapter = FileSystemAdapter()
        file_path = tmp_path / "delete_me.txt"
        file_path.write_text("content")
        assert file_path.exists()

        adapter.delete_file(file_path)

        assert not file_path.exists()

    def test_delete_file_with_missing_file_does_not_error(self, tmp_path: Path) -> None:
        """Verify delete_file handles missing files gracefully."""
        adapter = FileSystemAdapter()
        file_path = tmp_path / "nonexistent.txt"
        assert not file_path.exists()

        # Should not raise - uses missing_ok=True
        adapter.delete_file(file_path)

        assert not file_path.exists()

    def test_list_files_returns_all_files(self, tmp_path: Path) -> None:
        """Verify list_files returns all files in directory tree."""
        adapter = FileSystemAdapter()
        (tmp_path / "file1.txt").write_text("a")
        (tmp_path / "file2.md").write_text("b")
        (tmp_path / "subdir").mkdir()
        (tmp_path / "subdir" / "file3.pdf").write_text("c")

        result = adapter.list_files(tmp_path)

        assert len(result) == 3
        assert tmp_path / "file1.txt" in result
        assert tmp_path / "file2.md" in result
        assert tmp_path / "subdir" / "file3.pdf" in result

    def test_list_files_excludes_hidden_files(self, tmp_path: Path) -> None:
        """Verify list_files excludes hidden files."""
        adapter = FileSystemAdapter()
        (tmp_path / "visible.txt").write_text("a")
        (tmp_path / ".hidden").write_text("b")
        (tmp_path / "subdir").mkdir()
        (tmp_path / "subdir" / ".hidden_nested").write_text("c")

        result = adapter.list_files(tmp_path)

        assert len(result) == 1
        assert tmp_path / "visible.txt" in result

    def test_list_files_excludes_directories(self, tmp_path: Path) -> None:
        """Verify list_files returns only files, not directories."""
        adapter = FileSystemAdapter()
        (tmp_path / "file.txt").write_text("a")
        (tmp_path / "subdir").mkdir()
        (tmp_path / "subdir" / "nested").mkdir()

        result = adapter.list_files(tmp_path)

        assert len(result) == 1
        assert tmp_path / "file.txt" in result

    def test_list_files_returns_sorted_results(self, tmp_path: Path) -> None:
        """Verify list_files returns sorted list."""
        adapter = FileSystemAdapter()
        (tmp_path / "c.txt").write_text("c")
        (tmp_path / "a.txt").write_text("a")
        (tmp_path / "b.txt").write_text("b")

        result = adapter.list_files(tmp_path)

        assert result == sorted(result)

    def test_list_files_empty_directory(self, tmp_path: Path) -> None:
        """Verify list_files returns empty list for empty directory."""
        adapter = FileSystemAdapter()

        result = adapter.list_files(tmp_path)

        assert result == []


class TestGetRelativePath:
    """Tests for get_relative_path method."""

    def test_computes_relative_path_correctly(self) -> None:
        """Verify relative path computation."""
        adapter = FileSystemAdapter()
        source = Path("/project/raw_inbox/contracts/doc.pdf")
        base = Path("/project/raw_inbox")

        result = adapter.get_relative_path(source, base)

        assert result == Path("contracts/doc.pdf")

    def test_file_at_base_level(self) -> None:
        """File directly at base directory."""
        adapter = FileSystemAdapter()
        source = Path("/project/raw_inbox/doc.pdf")
        base = Path("/project/raw_inbox")

        result = adapter.get_relative_path(source, base)

        assert result == Path("doc.pdf")

    def test_deeply_nested_path(self) -> None:
        """Deeply nested subdirectory structure."""
        adapter = FileSystemAdapter()
        source = Path("/project/raw_inbox/a/b/c/d/file.xlsx")
        base = Path("/project/raw_inbox")

        result = adapter.get_relative_path(source, base)

        assert result == Path("a/b/c/d/file.xlsx")


class TestComputeOutputPath:
    """Tests for compute_output_path method."""

    def test_returns_correct_mirrored_path(self) -> None:
        """AC #1: Verify output path mirrors source structure."""
        adapter = FileSystemAdapter()
        source = Path("/project/raw_inbox/contracts/2024/alpha.pdf")
        raw_dir = Path("/project/raw_inbox")
        output_dir = Path("/project/processed_context")

        result = adapter.compute_output_path(source, raw_dir, output_dir)

        assert result == Path("/project/processed_context/contracts/2024/alpha.md")

    def test_changes_extension_to_md(self) -> None:
        """Verify extension is changed to .md."""
        adapter = FileSystemAdapter()
        source = Path("/project/raw_inbox/report.xlsx")
        raw_dir = Path("/project/raw_inbox")
        output_dir = Path("/project/processed_context")

        result = adapter.compute_output_path(source, raw_dir, output_dir)

        assert result.suffix == ".md"

    def test_file_at_raw_inbox_root(self) -> None:
        """Edge case: file at root of raw_inbox."""
        adapter = FileSystemAdapter()
        source = Path("/project/raw_inbox/document.pdf")
        raw_dir = Path("/project/raw_inbox")
        output_dir = Path("/project/processed_context")

        result = adapter.compute_output_path(source, raw_dir, output_dir)

        assert result == Path("/project/processed_context/document.md")

    def test_preserves_subdirectory_structure(self) -> None:
        """Verify subdirectory structure is preserved in output."""
        adapter = FileSystemAdapter()
        source = Path("/project/raw_inbox/legal/contracts/2024/q1/agreement.docx")
        raw_dir = Path("/project/raw_inbox")
        output_dir = Path("/project/processed_context")

        result = adapter.compute_output_path(source, raw_dir, output_dir)

        expected = Path("/project/processed_context/legal/contracts/2024/q1/agreement.md")
        assert result == expected
