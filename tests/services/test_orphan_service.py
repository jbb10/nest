"""Tests for orphan cleanup service.

Tests the OrphanService orchestration layer.
"""

from pathlib import Path

import pytest

from nest.core.models import FileEntry, Manifest, OrphanCleanupResult
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
        """Verify cleanup removes orphan files when no_clean=False."""
        # Arrange
        project_root = tmp_path / "project"
        output_dir = project_root / "processed_context"
        orphan_file = output_dir / "orphan.md"

        mock_fs = MockFileSystem()
        mock_fs.files = [orphan_file]

        manifest = Manifest(
            nest_version="1.0.0",
            project_name="test",
            files={},  # Empty - all files are orphans
        )
        mock_manifest = MockManifest(manifest)

        service = OrphanService(mock_fs, mock_manifest, project_root)

        # Act
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
        output_dir = project_root / "processed_context"
        orphan_file = output_dir / "orphan.md"

        mock_fs = MockFileSystem()
        mock_fs.files = [orphan_file]

        manifest = Manifest(
            nest_version="1.0.0",
            project_name="test",
            files={},
        )
        mock_manifest = MockManifest(manifest)

        service = OrphanService(mock_fs, mock_manifest, project_root)

        # Act
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
        output_dir = project_root / "processed_context"
        
        # Orphan file exists (perhaps from old failed processing or manually created)
        orphan_file = output_dir / "orphan.md"
        
        # Valid successful file
        valid_file = output_dir / "valid.md"

        mock_fs = MockFileSystem()
        mock_fs.files = [orphan_file, valid_file]

        from datetime import datetime

        manifest = Manifest(
            nest_version="1.0.0",
            project_name="test",
            files={
                # This entry failed, but file still exists - should be cleaned
                "failed_source.pdf": FileEntry(
                    sha256="abc123",
                    processed_at=datetime.now(),
                    output="orphan.md",
                    status="failed",  # Failed status means not in manifest_outputs
                ),
                # This is successful and should remain
                "active_source.pdf": FileEntry(
                    sha256="def456",
                    processed_at=datetime.now(),
                    output="valid.md",
                    status="success",
                ),
            },
        )
        
        mock_manifest = MockManifest(manifest)

        service = OrphanService(mock_fs, mock_manifest, project_root)

        # Act
        result = service.cleanup(no_clean=False)

        # Assert - failed entry's orphan output removed, entry also removed
        assert "failed_source.pdf" not in mock_manifest.manifest.files
        assert "active_source.pdf" in mock_manifest.manifest.files
        assert mock_manifest.saved is True
        assert orphan_file in mock_fs.deleted_files

    def test_cleanup_no_orphans(self, tmp_path: Path) -> None:
        """Verify cleanup when no orphans exist."""
        # Arrange
        project_root = tmp_path / "project"
        output_dir = project_root / "processed_context"
        valid_file = output_dir / "valid.md"

        mock_fs = MockFileSystem()
        mock_fs.files = [valid_file]

        from datetime import datetime

        manifest = Manifest(
            nest_version="1.0.0",
            project_name="test",
            files={
                "source.pdf": FileEntry(
                    sha256="abc123",
                    processed_at=datetime.now(),
                    output="valid.md",
                    status="success",
                )
            },
        )
        mock_manifest = MockManifest(manifest)

        service = OrphanService(mock_fs, mock_manifest, project_root)

        # Act
        result = service.cleanup(no_clean=False)

        # Assert
        assert len(result.orphans_detected) == 0
        assert len(result.orphans_removed) == 0
        assert len(mock_fs.deleted_files) == 0

    def test_cleanup_excludes_master_index(self, tmp_path: Path) -> None:
        """Verify 00_MASTER_INDEX.md is never considered orphan."""
        # Arrange
        project_root = tmp_path / "project"
        output_dir = project_root / "processed_context"
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
