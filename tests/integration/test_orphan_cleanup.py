"""Integration tests for orphan cleanup functionality.

Tests the full orphan cleanup flow from file deletion detection to removal.
"""

from datetime import datetime
from pathlib import Path

from nest.adapters.filesystem import FileSystemAdapter
from nest.adapters.manifest import ManifestAdapter
from nest.core.models import FileEntry, Manifest
from nest.services.orphan_service import OrphanService


class TestOrphanCleanupIntegration:
    """Integration tests for orphan cleanup."""

    def test_orphan_cleanup_removes_stale_files(self, tmp_path: Path) -> None:
        """Verify orphans are detected and removed when source deleted."""
        # Setup project structure
        project_root = tmp_path / "project"
        raw_inbox = project_root / "raw_inbox"
        output_dir = project_root  "_nest_context"
        raw_inbox.mkdir(parents=True)
        output_dir.mkdir(parents=True)

        # Create manifest with processed file
        manifest_path = project_root / ".nest_manifest.json"
        manifest = Manifest(
            nest_version="1.0.0",
            project_name="test",
            files={
                "report.pdf": FileEntry(
                    sha256="abc123",
                    processed_at=datetime.now(),
                    output="report.md",
                    status="success",
                )
            },
        )

        # Write orphan file (source was deleted)
        orphan_file = output_dir / "report.md"
        orphan_file.write_text("# Old Report\n\nThis file is now an orphan.")

        # Simulate source deletion: remove the source from manifest
        # (in real scenario, discovery would detect this)
        manifest.files = {}  # Source deleted, manifest updated

        # Save empty manifest
        adapter = ManifestAdapter()
        adapter.save(project_root, manifest)

        # Run orphan cleanup
        fs = FileSystemAdapter()
        orphan_service = OrphanService(fs, adapter, project_root)

        result = orphan_service.cleanup(no_clean=False)

        # Verify orphan was detected and removed
        assert len(result.orphans_detected) == 1
        assert "report.md" in result.orphans_detected
        assert len(result.orphans_removed) == 1
        assert "report.md" in result.orphans_removed
        assert not orphan_file.exists()

    def test_orphan_cleanup_with_no_clean_flag(self, tmp_path: Path) -> None:
        """Verify --no-clean preserves orphan files."""
        # Setup
        project_root = tmp_path / "project"
        output_dir = project_root  "_nest_context"
        output_dir.mkdir(parents=True)

        manifest = Manifest(
            nest_version="1.0.0",
            project_name="test",
            files={},  # Empty - all files are orphans
        )

        orphan_file = output_dir / "orphan.md"
        orphan_file.write_text("# Orphan")

        adapter = ManifestAdapter()
        adapter.save(project_root, manifest)

        # Run with no_clean=True
        fs = FileSystemAdapter()
        orphan_service = OrphanService(fs, adapter, project_root)

        result = orphan_service.cleanup(no_clean=True)

        # Verify orphan detected but not removed
        assert len(result.orphans_detected) == 1
        assert len(result.orphans_removed) == 0
        assert result.skipped is True
        assert orphan_file.exists()

    def test_orphan_cleanup_preserves_master_index(self, tmp_path: Path) -> None:
        """Verify 00_MASTER_INDEX.md is never removed."""
        # Setup
        project_root = tmp_path / "project"
        output_dir = project_root  "_nest_context"
        output_dir.mkdir(parents=True)

        manifest = Manifest(
            nest_version="1.0.0",
            project_name="test",
            files={},  # Empty manifest
        )

        # Create index file
        index_file = output_dir / "00_MASTER_INDEX.md"
        index_file.write_text("# Master Index\n\nThis should never be removed.")

        adapter = ManifestAdapter()
        adapter.save(project_root, manifest)

        # Run cleanup
        fs = FileSystemAdapter()
        orphan_service = OrphanService(fs, adapter, project_root)

        result = orphan_service.cleanup(no_clean=False)

        # Verify index was not detected as orphan
        assert len(result.orphans_detected) == 0
        assert index_file.exists()

    def test_orphan_cleanup_with_nested_directories(self, tmp_path: Path) -> None:
        """Verify orphan detection works in subdirectories."""
        # Setup
        project_root = tmp_path / "project"
        output_dir = project_root  "_nest_context"
        contracts_dir = output_dir / "contracts" / "2024"
        contracts_dir.mkdir(parents=True)

        manifest = Manifest(
            nest_version="1.0.0",
            project_name="test",
            files={},
        )

        # Create nested orphan
        orphan = contracts_dir / "agreement.md"
        orphan.write_text("# Agreement")

        adapter = ManifestAdapter()
        adapter.save(project_root, manifest)

        # Run cleanup
        fs = FileSystemAdapter()
        orphan_service = OrphanService(fs, adapter, project_root)

        result = orphan_service.cleanup(no_clean=False)

        # Verify nested orphan detected and removed
        assert len(result.orphans_detected) == 1
        assert "contracts/2024/agreement.md" in result.orphans_detected
        assert not orphan.exists()
