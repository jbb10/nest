"""Tests for orphan cleanup service.

Tests the OrphanService orchestration layer.

The new orphan logic:
- A file is an orphan ONLY if it IS in manifest AND source file is missing
- Files NOT in manifest are user-curated and should be preserved
"""

from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from nest.core.models import FileEntry, Manifest
from nest.services.orphan_service import OrphanService


class MockFileSystem:
    """Mock filesystem adapter for testing."""

    def __init__(self) -> None:
        """Initialize mock with tracking lists."""
        self.files: list[Path] = []
        self.deleted_files: list[Path] = []

    def list_files(self, directory: Path) -> list[Path]:
        """Return mock file list."""
        return self.files

    def delete_file(self, path: Path) -> None:
        """Track deleted files."""
        self.deleted_files.append(path)


class MockManifest:
    """Mock manifest adapter for testing."""

    def __init__(self, manifest: Manifest) -> None:
        """Initialize with manifest."""
        self.manifest = manifest
        self.saved = False

    def load(self, project_dir: Path) -> Manifest:
        """Return mock manifest."""
        return self.manifest

    def save(self, project_dir: Path, manifest: Manifest) -> None:
        """Track save calls."""
        self.manifest = manifest
        self.saved = True


class TestOrphanService:
    """Tests for OrphanService class."""

    def test_cleanup_removes_orphans_when_no_clean_false(self, tmp_path: Path) -> None:
        """Verify cleanup removes orphan files when source is missing and no_clean=False."""
        # Arrange
        project_root = tmp_path / "project"
        sources_dir = project_root / "_nest_sources"
        output_dir = project_root / "_nest_context"
        orphan_file = output_dir / "orphan.md"

        mock_fs = MockFileSystem()
        mock_fs.files = [orphan_file]

        # File IS in manifest, but source is missing
        manifest = Manifest(
            nest_version="1.0.0",
            project_name="test",
            files={
                "_nest_sources/orphan.pdf": FileEntry(
                    sha256="abc123",
                    processed_at=datetime.now(),
                    output="orphan.md",
                    status="success",
                )
            },
        )
        mock_manifest = MockManifest(manifest)

        service = OrphanService(mock_fs, mock_manifest, project_root)

        # Act - simulate source file missing
        with patch.object(Path, "exists", return_value=False):
            result = service.cleanup(no_clean=False)

        # Assert
        assert len(result.orphans_detected) == 1
        assert "orphan.md" in result.orphans_detected
        assert len(result.orphans_removed) == 1
        assert "orphan.md" in result.orphans_removed
        assert result.skipped is False
        assert orphan_file in mock_fs.deleted_files

    def test_cleanup_preserves_orphans_when_no_clean_true(self, tmp_path: Path) -> None:
        """Verify cleanup preserves files when no_clean=True."""
        # Arrange
        project_root = tmp_path / "project"
        output_dir = project_root / "_nest_context"
        orphan_file = output_dir / "orphan.md"

        mock_fs = MockFileSystem()
        mock_fs.files = [orphan_file]

        # File IS in manifest but source is missing
        manifest = Manifest(
            nest_version="1.0.0",
            project_name="test",
            files={
                "_nest_sources/orphan.pdf": FileEntry(
                    sha256="abc123",
                    processed_at=datetime.now(),
                    output="orphan.md",
                    status="success",
                )
            },
        )
        mock_manifest = MockManifest(manifest)

        service = OrphanService(mock_fs, mock_manifest, project_root)

        # Act - source file missing
        with patch.object(Path, "exists", return_value=False):
            result = service.cleanup(no_clean=True)

        # Assert
        assert len(result.orphans_detected) == 1
        assert "orphan.md" in result.orphans_detected
        assert len(result.orphans_removed) == 0
        assert result.skipped is True
        assert len(mock_fs.deleted_files) == 0

    def test_cleanup_removes_manifest_entries_for_orphans(self, tmp_path: Path) -> None:
        """Verify cleanup removes manifest entries for orphaned outputs."""
        # Arrange
        project_root = tmp_path / "project"
        output_dir = project_root / "_nest_context"

        orphan_file = output_dir / "orphan.md"
        valid_file = output_dir / "valid.md"

        mock_fs = MockFileSystem()
        mock_fs.files = [orphan_file, valid_file]

        manifest = Manifest(
            nest_version="1.0.0",
            project_name="test",
            files={
                # This entry's source is missing - should be cleaned
                "_nest_sources/orphan.pdf": FileEntry(
                    sha256="abc123",
                    processed_at=datetime.now(),
                    output="orphan.md",
                    status="success",
                ),
                # This entry's source exists - should remain
                "_nest_sources/valid.pdf": FileEntry(
                    sha256="def456",
                    processed_at=datetime.now(),
                    output="valid.md",
                    status="success",
                ),
            },
        )

        mock_manifest = MockManifest(manifest)

        service = OrphanService(mock_fs, mock_manifest, project_root)

        # Act - orphan.pdf missing, valid.pdf exists
        def exists_check(self):
            return "valid.pdf" in str(self)

        with patch.object(Path, "exists", exists_check):
            result = service.cleanup(no_clean=False)

        # Assert - orphan entry removed, valid entry remains
        assert "_nest_sources/orphan.pdf" not in mock_manifest.manifest.files
        assert "_nest_sources/valid.pdf" in mock_manifest.manifest.files
        assert mock_manifest.saved is True
        assert orphan_file in mock_fs.deleted_files

    def test_cleanup_no_orphans(self, tmp_path: Path) -> None:
        """Verify cleanup when no orphans exist (all sources present)."""
        # Arrange
        project_root = tmp_path / "project"
        output_dir = project_root / "_nest_context"
        valid_file = output_dir / "valid.md"

        mock_fs = MockFileSystem()
        mock_fs.files = [valid_file]

        manifest = Manifest(
            nest_version="1.0.0",
            project_name="test",
            files={
                "_nest_sources/source.pdf": FileEntry(
                    sha256="abc123",
                    processed_at=datetime.now(),
                    output="valid.md",
                    status="success",
                )
            },
        )
        mock_manifest = MockManifest(manifest)

        service = OrphanService(mock_fs, mock_manifest, project_root)

        # Act - source file exists
        with patch.object(Path, "exists", return_value=True):
            result = service.cleanup(no_clean=False)

        # Assert
        assert len(result.orphans_detected) == 0
        assert len(result.orphans_removed) == 0
        assert len(mock_fs.deleted_files) == 0

    def test_cleanup_excludes_master_index(self, tmp_path: Path) -> None:
        """Verify 00_MASTER_INDEX.md is never considered orphan."""
        # Arrange
        project_root = tmp_path / "project"
        output_dir = project_root / "_nest_context"
        index_file = output_dir / "00_MASTER_INDEX.md"

        mock_fs = MockFileSystem()
        mock_fs.files = [index_file]

        manifest = Manifest(
            nest_version="1.0.0",
            project_name="test",
            files={},
        )
        mock_manifest = MockManifest(manifest)

        service = OrphanService(mock_fs, mock_manifest, project_root)

        # Act
        result = service.cleanup(no_clean=False)

        # Assert
        assert len(result.orphans_detected) == 0
        assert len(mock_fs.deleted_files) == 0

    def test_user_curated_files_preserved(self, tmp_path: Path) -> None:
        """Verify files NOT in manifest (user-curated) are never removed."""
        # Arrange
        project_root = tmp_path / "project"
        output_dir = project_root / "_nest_context"
        user_file = output_dir / "user-guide.md"

        mock_fs = MockFileSystem()
        mock_fs.files = [user_file]

        # Empty manifest - no tracked files
        manifest = Manifest(
            nest_version="1.0.0",
            project_name="test",
            files={},
        )
        mock_manifest = MockManifest(manifest)

        service = OrphanService(mock_fs, mock_manifest, project_root)

        # Act
        result = service.cleanup(no_clean=False)

        # Assert - user-curated file is NOT an orphan
        assert len(result.orphans_detected) == 0
        assert len(mock_fs.deleted_files) == 0
