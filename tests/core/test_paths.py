"""Tests for core path computation functions.

Tests the pure path manipulation functions used for output mirroring.
"""

from pathlib import Path

from nest.core.paths import (
    ALL_SOURCE_EXTENSIONS,
    CONTEXT_TEXT_EXTENSIONS,
    SUPPORTED_EXTENSIONS,
    is_passthrough_extension,
    mirror_path,
    passthrough_mirror_path,
    relative_to_project,
    source_path_to_manifest_key,
)


class TestContextTextExtensions:
    """Tests for CONTEXT_TEXT_EXTENSIONS constant."""

    def test_contains_all_expected_extensions(self) -> None:
        """AC1: Constant contains all 10 expected text extensions."""
        expected = {
            ".md",
            ".txt",
            ".text",
            ".rst",
            ".csv",
            ".json",
            ".yaml",
            ".yml",
            ".toml",
            ".xml",
        }
        assert set(CONTEXT_TEXT_EXTENSIONS) == expected

    def test_has_exactly_ten_extensions(self) -> None:
        """AC1: Constant has exactly 10 extensions."""
        assert len(CONTEXT_TEXT_EXTENSIONS) == 10

    def test_all_extensions_start_with_dot(self) -> None:
        """All extensions should start with a dot."""
        for ext in CONTEXT_TEXT_EXTENSIONS:
            assert ext.startswith("."), f"Extension {ext!r} missing leading dot"


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


class TestSourcePathToManifestKey:
    """Tests for source_path_to_manifest_key function."""

    def test_returns_forward_slash_path(self) -> None:
        """AC #1: Returns forward-slash separated manifest key."""
        source = Path("/project/raw_inbox/contracts/2024/alpha.pdf")
        raw_inbox = Path("/project/raw_inbox")

        result = source_path_to_manifest_key(source, raw_inbox)

        assert result == "contracts/2024/alpha.pdf"
        assert "\\" not in result  # No backslashes

    def test_nested_subdirectories(self) -> None:
        """Nested subdirectory structure preserved in key."""
        source = Path("/project/raw_inbox/legal/contracts/2024/q1/client-a/agreement.pdf")
        raw_inbox = Path("/project/raw_inbox")

        result = source_path_to_manifest_key(source, raw_inbox)

        assert result == "legal/contracts/2024/q1/client-a/agreement.pdf"

    def test_file_at_raw_inbox_root(self) -> None:
        """File directly at raw_inbox root level (no subdirs)."""
        source = Path("/project/raw_inbox/document.pdf")
        raw_inbox = Path("/project/raw_inbox")

        result = source_path_to_manifest_key(source, raw_inbox)

        assert result == "document.pdf"

    def test_preserves_original_extension(self) -> None:
        """Original file extension is preserved in key."""
        raw_inbox = Path("/project/raw_inbox")

        for ext in [".pdf", ".docx", ".xlsx", ".pptx", ".html"]:
            source = Path(f"/project/raw_inbox/file{ext}")
            result = source_path_to_manifest_key(source, raw_inbox)
            assert result == f"file{ext}"

    def test_handles_spaces_in_filename(self) -> None:
        """Spaces in filename are preserved."""
        source = Path("/project/raw_inbox/My Important Document.pdf")
        raw_inbox = Path("/project/raw_inbox")

        result = source_path_to_manifest_key(source, raw_inbox)

        assert result == "My Important Document.pdf"


class TestAllSourceExtensions:
    """Tests for ALL_SOURCE_EXTENSIONS constant."""

    def test_contains_all_supported_extensions(self) -> None:
        """AC1: ALL_SOURCE_EXTENSIONS includes all Docling-convertible extensions."""
        for ext in SUPPORTED_EXTENSIONS:
            assert ext in ALL_SOURCE_EXTENSIONS, f"Missing Docling extension: {ext}"

    def test_contains_all_context_text_extensions(self) -> None:
        """AC1: ALL_SOURCE_EXTENSIONS includes all passthrough text extensions."""
        for ext in CONTEXT_TEXT_EXTENSIONS:
            assert ext in ALL_SOURCE_EXTENSIONS, f"Missing text extension: {ext}"

    def test_is_deduplicated(self) -> None:
        """ALL_SOURCE_EXTENSIONS has no duplicate entries."""
        assert len(ALL_SOURCE_EXTENSIONS) == len(set(ALL_SOURCE_EXTENSIONS))

    def test_is_sorted(self) -> None:
        """ALL_SOURCE_EXTENSIONS is sorted."""
        assert ALL_SOURCE_EXTENSIONS == sorted(ALL_SOURCE_EXTENSIONS)

    def test_union_count(self) -> None:
        """ALL_SOURCE_EXTENSIONS has the expected number of entries."""
        expected = sorted(set(SUPPORTED_EXTENSIONS + CONTEXT_TEXT_EXTENSIONS))
        assert ALL_SOURCE_EXTENSIONS == expected


class TestIsPassthroughExtension:
    """Tests for is_passthrough_extension function."""

    def test_returns_true_for_text_extensions(self) -> None:
        """AC1: Text extensions are passthrough."""
        for ext in CONTEXT_TEXT_EXTENSIONS:
            assert is_passthrough_extension(ext) is True, f"Expected True for {ext}"

    def test_returns_false_for_docling_extensions(self) -> None:
        """Docling-convertible extensions are NOT passthrough."""
        for ext in SUPPORTED_EXTENSIONS:
            assert is_passthrough_extension(ext) is False, f"Expected False for {ext}"

    def test_case_insensitive(self) -> None:
        """Extension matching is case-insensitive."""
        assert is_passthrough_extension(".TXT") is True
        assert is_passthrough_extension(".Yaml") is True
        assert is_passthrough_extension(".PDF") is False

    def test_returns_false_for_unknown_extension(self) -> None:
        """Unknown extensions are not passthrough."""
        assert is_passthrough_extension(".png") is False
        assert is_passthrough_extension(".zip") is False


class TestPassthroughMirrorPath:
    """Tests for passthrough_mirror_path function."""

    def test_preserves_original_extension(self) -> None:
        """AC2: Passthrough mirror preserves original file extension."""
        source = Path("/project/_nest_sources/notes.txt")
        source_root = Path("/project/_nest_sources")
        target_root = Path("/project/_nest_context")

        result = passthrough_mirror_path(source, source_root, target_root)

        assert result == Path("/project/_nest_context/notes.txt")
        assert result.suffix == ".txt"

    def test_preserves_subdirectory_structure(self) -> None:
        """AC3: Subdirectory structure is preserved."""
        source = Path("/project/_nest_sources/team/meeting-notes.md")
        source_root = Path("/project/_nest_sources")
        target_root = Path("/project/_nest_context")

        result = passthrough_mirror_path(source, source_root, target_root)

        assert result == Path("/project/_nest_context/team/meeting-notes.md")

    def test_file_at_root_level(self) -> None:
        """File directly in source root."""
        source = Path("/project/_nest_sources/readme.md")
        source_root = Path("/project/_nest_sources")
        target_root = Path("/project/_nest_context")

        result = passthrough_mirror_path(source, source_root, target_root)

        assert result == Path("/project/_nest_context/readme.md")

    def test_deeply_nested_path(self) -> None:
        """Deeply nested paths are handled correctly."""
        source = Path("/project/_nest_sources/a/b/c/d/config.yaml")
        source_root = Path("/project/_nest_sources")
        target_root = Path("/project/_nest_context")

        result = passthrough_mirror_path(source, source_root, target_root)

        assert result == Path("/project/_nest_context/a/b/c/d/config.yaml")

    def test_various_text_extensions(self) -> None:
        """All text extensions preserve their suffix."""
        source_root = Path("/project/_nest_sources")
        target_root = Path("/project/_nest_context")

        for ext in CONTEXT_TEXT_EXTENSIONS:
            source = Path(f"/project/_nest_sources/file{ext}")
            result = passthrough_mirror_path(source, source_root, target_root)
            assert result.suffix == ext, f"Failed for {ext}"
