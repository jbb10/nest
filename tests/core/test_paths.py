"""Tests for core path computation functions.

Tests the pure path manipulation functions used for output mirroring.
"""

from pathlib import Path

from nest.core.paths import mirror_path, relative_to_project


class TestMirrorPath:
    """Tests for mirror_path function."""

    def test_preserves_subdirectory_structure(self) -> None:
        """AC #1: Source subdirectory structure is preserved in output."""
        source = Path("/project/raw_inbox/contracts/2024/alpha.pdf")
        source_root = Path("/project/raw_inbox")
        target_root = Path("/project/processed_context")

        result = mirror_path(source, source_root, target_root)

        assert result == Path("/project/processed_context/contracts/2024/alpha.md")

    def test_changes_extension_to_md(self) -> None:
        """AC #1: Output extension is changed to .md."""
        source = Path("/project/raw_inbox/report.xlsx")
        source_root = Path("/project/raw_inbox")
        target_root = Path("/project/processed_context")

        result = mirror_path(source, source_root, target_root)

        assert result.suffix == ".md"
        assert result.name == "report.md"

    def test_file_at_root_level_no_subdirs(self) -> None:
        """Edge case: File directly in raw_inbox with no subdirectories."""
        source = Path("/project/raw_inbox/document.pdf")
        source_root = Path("/project/raw_inbox")
        target_root = Path("/project/processed_context")

        result = mirror_path(source, source_root, target_root)

        assert result == Path("/project/processed_context/document.md")

    def test_deeply_nested_paths(self) -> None:
        """Edge case: File in deeply nested subdirectory (3+ levels)."""
        source = Path("/project/raw_inbox/legal/contracts/2024/q1/client-a/agreement.docx")
        source_root = Path("/project/raw_inbox")
        target_root = Path("/project/processed_context")

        result = mirror_path(source, source_root, target_root)

        expected = Path("/project/processed_context/legal/contracts/2024/q1/client-a/agreement.md")
        assert result == expected

    def test_custom_suffix(self) -> None:
        """Custom suffix parameter is respected."""
        source = Path("/project/raw_inbox/doc.pdf")
        source_root = Path("/project/raw_inbox")
        target_root = Path("/project/output")

        result = mirror_path(source, source_root, target_root, new_suffix=".txt")

        assert result == Path("/project/output/doc.txt")

    def test_preserves_filename_stem(self) -> None:
        """Original filename (without extension) is preserved."""
        source = Path("/project/raw_inbox/My Important Document.pdf")
        source_root = Path("/project/raw_inbox")
        target_root = Path("/project/processed_context")

        result = mirror_path(source, source_root, target_root)

        assert result.stem == "My Important Document"
        assert result.name == "My Important Document.md"

    def test_different_source_extensions(self) -> None:
        """Various source extensions all become .md."""
        source_root = Path("/project/raw_inbox")
        target_root = Path("/project/processed_context")

        extensions = [".pdf", ".docx", ".pptx", ".xlsx", ".html"]

        for ext in extensions:
            source = Path(f"/project/raw_inbox/file{ext}")
            result = mirror_path(source, source_root, target_root)
            assert result.suffix == ".md", f"Failed for {ext}"


class TestRelativeToProject:
    """Tests for relative_to_project function."""

    def test_returns_portable_string_path(self) -> None:
        """AC #4: Returns portable relative path string."""
        path = Path("/project/processed_context/contracts/alpha.md")
        project_root = Path("/project")

        result = relative_to_project(path, project_root)

        assert result == "processed_context/contracts/alpha.md"

    def test_uses_forward_slashes(self) -> None:
        """Paths use forward slashes for cross-platform portability."""
        path = Path("/project/a/b/c/file.md")
        project_root = Path("/project")

        result = relative_to_project(path, project_root)

        assert "/" in result or result.count("/") == 0  # No backslashes
        assert "\\" not in result
        assert result == "a/b/c/file.md"

    def test_file_at_project_root(self) -> None:
        """File directly at project root level."""
        path = Path("/project/manifest.json")
        project_root = Path("/project")

        result = relative_to_project(path, project_root)

        assert result == "manifest.json"

    def test_deeply_nested_output(self) -> None:
        """Deeply nested output path."""
        path = Path("/project/processed_context/legal/2024/q1/report.md")
        project_root = Path("/project")

        result = relative_to_project(path, project_root)

        assert result == "processed_context/legal/2024/q1/report.md"
