"""Tests for orphan detection logic.

Tests the OrphanDetector class for identifying orphaned output files.
"""

from pathlib import Path

from nest.core.orphan_detector import OrphanDetector


class TestOrphanDetector:
    """Tests for OrphanDetector class."""

    def test_detects_orphan_when_file_not_in_manifest(self) -> None:
        """Verify orphan detection when file exists but not in manifest."""
        detector = OrphanDetector()
        output_dir = Path("/project/processed_context")
        output_files = [
            Path("/project/processed_context/valid.md"),
            Path("/project/processed_context/orphan.md"),
        ]
        manifest_outputs = {"valid.md"}

        orphans = detector.detect(output_files, manifest_outputs, output_dir)

        assert len(orphans) == 1
        assert Path("/project/processed_context/orphan.md") in orphans

    def test_no_orphans_when_all_files_in_manifest(self) -> None:
        """Verify no orphans detected when all files in manifest."""
        detector = OrphanDetector()
        output_dir = Path("/project/processed_context")
        output_files = [
            Path("/project/processed_context/file1.md"),
            Path("/project/processed_context/file2.md"),
        ]
        manifest_outputs = {"file1.md", "file2.md"}

        orphans = detector.detect(output_files, manifest_outputs, output_dir)

        assert len(orphans) == 0

    def test_excludes_master_index_from_orphans(self) -> None:
        """Verify 00_MASTER_INDEX.md is never considered an orphan."""
        detector = OrphanDetector()
        output_dir = Path("/project/processed_context")
        output_files = [
            Path("/project/processed_context/00_MASTER_INDEX.md"),
        ]
        manifest_outputs = set()  # Empty manifest

        orphans = detector.detect(output_files, manifest_outputs, output_dir)

        assert len(orphans) == 0

    def test_handles_nested_orphans(self) -> None:
        """Verify detection works for files in subdirectories."""
        detector = OrphanDetector()
        output_dir = Path("/project/processed_context")
        output_files = [
            Path("/project/processed_context/contracts/2024/orphan.md"),
        ]
        manifest_outputs = set()

        orphans = detector.detect(output_files, manifest_outputs, output_dir)

        assert len(orphans) == 1
        assert Path("/project/processed_context/contracts/2024/orphan.md") in orphans

    def test_empty_output_directory(self) -> None:
        """Verify handles empty output directory."""
        detector = OrphanDetector()
        output_dir = Path("/project/processed_context")
        output_files: list[Path] = []
        manifest_outputs = {"file.md"}

        orphans = detector.detect(output_files, manifest_outputs, output_dir)

        assert len(orphans) == 0

    def test_multiple_orphans(self) -> None:
        """Verify detection of multiple orphan files."""
        detector = OrphanDetector()
        output_dir = Path("/project/processed_context")
        output_files = [
            Path("/project/processed_context/valid.md"),
            Path("/project/processed_context/orphan1.md"),
            Path("/project/processed_context/orphan2.md"),
            Path("/project/processed_context/subdir/orphan3.md"),
        ]
        manifest_outputs = {"valid.md"}

        orphans = detector.detect(output_files, manifest_outputs, output_dir)

        assert len(orphans) == 3
        assert Path("/project/processed_context/orphan1.md") in orphans
        assert Path("/project/processed_context/orphan2.md") in orphans
        assert Path("/project/processed_context/subdir/orphan3.md") in orphans
