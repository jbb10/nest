"""Tests for file change detector."""

from pathlib import Path

from nest.core.change_detector import FileChangeDetector


class TestFileChangeDetector:
    """Tests for FileChangeDetector class."""

    def test_classifies_new_file_when_not_in_manifest(self) -> None:
        """Verify file not in manifest is classified as 'new'."""
        # Arrange
        manifest_files: dict[str, str] = {}  # Empty manifest
        detector = FileChangeDetector(manifest_files)

        # Act
        result = detector.classify(Path("raw_inbox/document.pdf"), "abc123hash")

        # Assert
        assert result == "new"

    def test_classifies_modified_when_checksum_differs(self) -> None:
        """Verify file with different checksum is classified as 'modified'."""
        # Arrange
        manifest_files = {"raw_inbox/document.pdf": "old_hash_value"}
        detector = FileChangeDetector(manifest_files)

        # Act
        result = detector.classify(Path("raw_inbox/document.pdf"), "new_hash_value")

        # Assert
        assert result == "modified"

    def test_classifies_unchanged_when_checksum_matches(self) -> None:
        """Verify file with matching checksum is classified as 'unchanged'."""
        # Arrange
        same_hash = "abc123hashvalue"
        manifest_files = {"raw_inbox/document.pdf": same_hash}
        detector = FileChangeDetector(manifest_files)

        # Act
        result = detector.classify(Path("raw_inbox/document.pdf"), same_hash)

        # Assert
        assert result == "unchanged"

    def test_uses_relative_path_for_lookup(self) -> None:
        """Verify detector converts to relative path for manifest lookup."""
        # Arrange - manifest uses relative paths
        manifest_files = {"raw_inbox/contracts/alpha.pdf": "hash123"}
        detector = FileChangeDetector(manifest_files)

        # Act - classify with relative path
        result = detector.classify(Path("raw_inbox/contracts/alpha.pdf"), "hash123")

        # Assert
        assert result == "unchanged"

    def test_handles_nested_paths(self) -> None:
        """Verify deeply nested paths are handled correctly."""
        # Arrange
        manifest_files = {"raw_inbox/2024/q1/reports/summary.pdf": "hash_value"}
        detector = FileChangeDetector(manifest_files)

        # Act - Same checksum should be unchanged
        result = detector.classify(Path("raw_inbox/2024/q1/reports/summary.pdf"), "hash_value")

        # Assert
        assert result == "unchanged"

    def test_handles_empty_manifest(self) -> None:
        """Verify all files are 'new' with empty manifest."""
        # Arrange
        detector = FileChangeDetector({})

        # Act
        result = detector.classify(Path("raw_inbox/doc.pdf"), "any_hash")

        # Assert
        assert result == "new"

    def test_path_comparison_uses_forward_slashes(self) -> None:
        """Verify path normalization uses forward slashes consistently."""
        # Arrange - Manifest uses forward slashes
        manifest_files = {"raw_inbox/sub/doc.pdf": "hash123"}
        detector = FileChangeDetector(manifest_files)

        # Act - Path with forward slashes
        result = detector.classify(Path("raw_inbox/sub/doc.pdf"), "hash123")

        # Assert
        assert result == "unchanged"

    def test_different_file_names_are_independent(self) -> None:
        """Verify files with similar names are tracked separately."""
        # Arrange
        manifest_files = {
            "raw_inbox/report.pdf": "hash_a",
            "raw_inbox/report_v2.pdf": "hash_b",
        }
        detector = FileChangeDetector(manifest_files)

        # Act & Assert - Each file has its own checksum
        assert detector.classify(Path("raw_inbox/report.pdf"), "hash_a") == "unchanged"
        assert detector.classify(Path("raw_inbox/report_v2.pdf"), "hash_b") == "unchanged"
        assert detector.classify(Path("raw_inbox/report.pdf"), "hash_b") == "modified"
        assert detector.classify(Path("raw_inbox/report_new.pdf"), "hash_c") == "new"

    def test_raises_error_for_absolute_path(self) -> None:
        """Verify ValueError is raised if path is absolute."""
        import pytest

        # Arrange
        detector = FileChangeDetector({})
        abs_path = Path("/absolute/path/doc.pdf")

        # Act & Assert
        with pytest.raises(ValueError, match="Path must be relative"):
            detector.classify(abs_path, "hash")
