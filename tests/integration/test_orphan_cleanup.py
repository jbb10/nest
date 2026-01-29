"""Integration tests for orphan cleanup functionality.

Tests the full orphan cleanup flow with MANIFEST-AWARE orphan detection.
Orphans are files that ARE in manifest but whose source file no longer exists.
User-curated files (not in manifest) are NEVER orphans and are preserved.
"""

from datetime import datetime
from pathlib import Path

from nest.adapters.filesystem import FileSystemAdapter
from nest.adapters.manifest import ManifestAdapter
from nest.core.models import FileEntry, Manifest
from nest.core.paths import SOURCES_DIR, CONTEXT_DIR
from nest.services.orphan_service import OrphanService


class TestOrphanCleanupIntegration:
    """Integration tests for manifest-aware orphan cleanup."""

    def test_orphan_cleanup_removes_stale_files(self, tmp_path: Path) -> None:
        """Verify orphans are detected and removed when source is deleted.
        
        Orphan = file IN manifest whose source no longer exists.
        """
        # Setup project structure
        project_root = tmp_path / "project"
        sources_dir = project_root / SOURCES_DIR
        output_dir = project_root / CONTEXT_DIR
        sources_dir.mkdir(parents=True)
        output_dir.mkdir(parents=True)

        # Create manifest with processed file (source was deleted)
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

        # Write output file (source was deleted - making this an orphan)
        orphan_file = output_dir / "report.md"
        orphan_file.write_text("# Old Report\n\nThis file is now an orphan.")

        # NOTE: Source file (report.pdf) does NOT exist - this makes it an orphan

        # Save manifest
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
        sources_dir = project_root / SOURCES_DIR
        output_dir = project_root / CONTEXT_DIR
        sources_dir.mkdir(parents=True)
        output_dir.mkdir(parents=True)

        # File in manifest but source deleted = orphan
        manifest = Manifest(
            nest_version="1.0.0",
            project_name="test",
            files={
                "orphan.pdf": FileEntry(
                    sha256="abc123",
                    processed_at=datetime.now(),
                    output="orphan.md",
                    status="success",
                )
            },
        )

        orphan_file = output_dir / "orphan.md"
        orphan_file.write_text("# Orphan")
        # NOTE: orphan.pdf source does NOT exist

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
        sources_dir = project_root / SOURCES_DIR
        output_dir = project_root / CONTEXT_DIR
        sources_dir.mkdir(parents=True)
        output_dir.mkdir(parents=True)

        manifest = Manifest(
            nest_version="1.0.0",
            project_name="test",
            files={},  # Empty manifest
        )

        # Create index file (user-curated, not in manifest)
        index_file = output_dir / "00_MASTER_INDEX.md"
        index_file.write_text("# Master Index\n\nThis should never be removed.")

        adapter = ManifestAdapter()
        adapter.save(project_root, manifest)

        # Run cleanup
        fs = FileSystemAdapter()
        orphan_service = OrphanService(fs, adapter, project_root)

        result = orphan_service.cleanup(no_clean=False)

        # Verify index was not detected as orphan (not in manifest)
        assert len(result.orphans_detected) == 0
        assert index_file.exists()

    def test_orphan_cleanup_with_nested_directories(self, tmp_path: Path) -> None:
        """Verify orphan detection works in subdirectories."""
        # Setup
        project_root = tmp_path / "project"
        sources_dir = project_root / SOURCES_DIR
        output_dir = project_root / CONTEXT_DIR
        contracts_dir = output_dir / "contracts" / "2024"
        sources_dir.mkdir(parents=True)
        contracts_dir.mkdir(parents=True)

        # File in manifest with nested output, source deleted = orphan
        manifest = Manifest(
            nest_version="1.0.0",
            project_name="test",
            files={
                "contracts/2024/agreement.pdf": FileEntry(
                    sha256="abc123",
                    processed_at=datetime.now(),
                    output="contracts/2024/agreement.md",
                    status="success",
                )
            },
        )

        # Create nested orphan (source doesn't exist)
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

    def test_orphan_cleanup_preserves_user_curated_files(self, tmp_path: Path) -> None:
        """Verify user-curated files (not in manifest) are never orphans."""
        # Setup
        project_root = tmp_path / "project"
        sources_dir = project_root / SOURCES_DIR
        output_dir = project_root / CONTEXT_DIR
        sources_dir.mkdir(parents=True)
        output_dir.mkdir(parents=True)

        # Empty manifest - no tracked files
        manifest = Manifest(
            nest_version="1.0.0",
            project_name="test",
            files={},
        )

        # Create user-curated file (NOT in manifest)
        user_file = output_dir / "my_notes.md"
        user_file.write_text("# My Custom Notes\n\nUser-created content.")

        adapter = ManifestAdapter()
        adapter.save(project_root, manifest)

        # Run cleanup
        fs = FileSystemAdapter()
        orphan_service = OrphanService(fs, adapter, project_root)

        result = orphan_service.cleanup(no_clean=False)

        # Verify user file was NOT detected as orphan
        assert len(result.orphans_detected) == 0
        assert user_file.exists()

    def test_orphan_cleanup_with_existing_source_not_orphan(self, tmp_path: Path) -> None:
        """Verify files with existing sources are NOT orphans."""
        # Setup
        project_root = tmp_path / "project"
        sources_dir = project_root / SOURCES_DIR
        output_dir = project_root / CONTEXT_DIR
        sources_dir.mkdir(parents=True)
        output_dir.mkdir(parents=True)

        # Create source file (exists)
        source_file = sources_dir / "report.pdf"
        source_file.write_bytes(b"PDF content")

        # File in manifest with existing source = NOT orphan
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

        # Create output file
        output_file = output_dir / "report.md"
        output_file.write_text("# Report")

        adapter = ManifestAdapter()
        adapter.save(project_root, manifest)

        # Run cleanup
        fs = FileSystemAdapter()
        orphan_service = OrphanService(fs, adapter, project_root)

        result = orphan_service.cleanup(no_clean=False)

        # Verify no orphans detected (source exists)
        assert len(result.orphans_detected) == 0
        assert output_file.exists()
