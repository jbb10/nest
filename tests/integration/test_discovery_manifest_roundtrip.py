"""Integration tests for manifest key roundtrip.

Verifies that keys written by ManifestService.record_success() are correctly
looked up by DiscoveryService.discover_changes(). This catches key format
drift between the two services (e.g., the path prefix mismatch bug where
manifest stored 'reports/file.pdf' but discovery looked up
'_nest_sources/reports/file.pdf').

These tests use the real ManifestAdapter and FileDiscoveryAdapter — no mocks —
and do NOT require Docling models, so they run in every CI environment.
"""

import hashlib
from pathlib import Path

from nest.adapters.file_discovery import FileDiscoveryAdapter
from nest.adapters.manifest import ManifestAdapter
from nest.services.discovery_service import DiscoveryService
from nest.services.manifest_service import ManifestService


class TestDiscoveryManifestKeyRoundtrip:
    """Verify manifest keys written by ManifestService match DiscoveryService lookups."""

    def _setup_project(self, tmp_path: Path) -> tuple[Path, Path, Path]:
        """Create a realistic project structure.

        Returns:
            Tuple of (project_root, sources_dir, output_dir).
        """
        project_root = tmp_path
        sources_dir = project_root / "_nest_sources"
        output_dir = project_root / "_nest_context"
        sources_dir.mkdir()
        output_dir.mkdir()
        return project_root, sources_dir, output_dir

    def test_unchanged_files_detected_after_manifest_write(self, tmp_path: Path) -> None:
        """Files recorded in manifest should be classified as 'unchanged' on next discovery.

        This is the core regression test for the key format mismatch bug.
        """
        project_root, sources_dir, output_dir = self._setup_project(tmp_path)

        # Create source files in nested structure (matches real usage)
        reports_dir = sources_dir / "reports"
        reports_dir.mkdir()
        content = b"Quarterly earnings report PDF content"
        source_file = reports_dir / "quarterly.pdf"
        source_file.write_bytes(content)
        checksum = hashlib.sha256(content).hexdigest()

        # Create corresponding output file
        output_file = output_dir / "reports" / "quarterly.md"
        output_file.parent.mkdir(parents=True)
        output_file.write_text("# Quarterly Report\n\nConverted content.")

        # Step 1: Record the file via ManifestService (simulates first sync)
        manifest_adapter = ManifestAdapter()
        manifest_adapter.create(project_root, "test-project")

        manifest_svc = ManifestService(
            manifest=manifest_adapter,
            project_root=project_root,
            raw_inbox=sources_dir,
            output_dir=output_dir,
        )
        manifest_svc.record_success(
            source_path=source_file,
            checksum=checksum,
            output_path=output_file,
        )
        manifest_svc.commit()

        # Step 2: Run discovery (simulates second sync)
        discovery_svc = DiscoveryService(
            file_discovery=FileDiscoveryAdapter(),
            manifest=manifest_adapter,
        )
        result = discovery_svc.discover_changes(project_root)

        # Assert: file must be classified as unchanged, not new
        assert len(result.unchanged_files) == 1, (
            f"Expected 1 unchanged file, got {len(result.unchanged_files)} unchanged, "
            f"{len(result.new_files)} new, {len(result.modified_files)} modified"
        )
        assert len(result.new_files) == 0
        assert len(result.modified_files) == 0
        assert result.unchanged_files[0].status == "unchanged"

    def test_modified_files_detected_after_content_change(self, tmp_path: Path) -> None:
        """Files with changed content should be classified as 'modified'."""
        project_root, sources_dir, output_dir = self._setup_project(tmp_path)

        # Create and record original file
        source_file = sources_dir / "document.pdf"
        original_content = b"Original document content"
        source_file.write_bytes(original_content)
        original_checksum = hashlib.sha256(original_content).hexdigest()

        output_file = output_dir / "document.md"
        output_file.write_text("# Original\n\nContent.")

        manifest_adapter = ManifestAdapter()
        manifest_adapter.create(project_root, "test-project")

        manifest_svc = ManifestService(
            manifest=manifest_adapter,
            project_root=project_root,
            raw_inbox=sources_dir,
            output_dir=output_dir,
        )
        manifest_svc.record_success(
            source_path=source_file,
            checksum=original_checksum,
            output_path=output_file,
        )
        manifest_svc.commit()

        # Modify the source file
        updated_content = b"Updated document content with new data"
        source_file.write_bytes(updated_content)

        # Run discovery — should detect modification
        discovery_svc = DiscoveryService(
            file_discovery=FileDiscoveryAdapter(),
            manifest=manifest_adapter,
        )
        result = discovery_svc.discover_changes(project_root)

        assert len(result.modified_files) == 1
        assert len(result.new_files) == 0
        assert len(result.unchanged_files) == 0
        assert result.modified_files[0].status == "modified"

    def test_new_files_detected_without_manifest_entry(self, tmp_path: Path) -> None:
        """Files not in manifest should be classified as 'new'."""
        project_root, sources_dir, output_dir = self._setup_project(tmp_path)

        # Record one file in manifest
        existing_file = sources_dir / "existing.pdf"
        existing_content = b"Existing content"
        existing_file.write_bytes(existing_content)
        existing_checksum = hashlib.sha256(existing_content).hexdigest()

        output_file = output_dir / "existing.md"
        output_file.write_text("# Existing")

        manifest_adapter = ManifestAdapter()
        manifest_adapter.create(project_root, "test-project")

        manifest_svc = ManifestService(
            manifest=manifest_adapter,
            project_root=project_root,
            raw_inbox=sources_dir,
            output_dir=output_dir,
        )
        manifest_svc.record_success(
            source_path=existing_file,
            checksum=existing_checksum,
            output_path=output_file,
        )
        manifest_svc.commit()

        # Add a new file NOT in manifest
        new_file = sources_dir / "brand_new.pdf"
        new_file.write_bytes(b"Brand new document")

        # Run discovery
        discovery_svc = DiscoveryService(
            file_discovery=FileDiscoveryAdapter(),
            manifest=manifest_adapter,
        )
        result = discovery_svc.discover_changes(project_root)

        assert len(result.new_files) == 1
        assert len(result.unchanged_files) == 1
        assert len(result.modified_files) == 0
        assert result.new_files[0].path.name == "brand_new.pdf"
        assert result.unchanged_files[0].path.name == "existing.pdf"

    def test_nested_directory_keys_match(self, tmp_path: Path) -> None:
        """Keys for deeply nested files must match between write and read."""
        project_root, sources_dir, output_dir = self._setup_project(tmp_path)

        # Create file in nested structure
        nested_dir = sources_dir / "contracts" / "2026" / "q1"
        nested_dir.mkdir(parents=True)
        content = b"Deeply nested contract"
        source_file = nested_dir / "alpha.pdf"
        source_file.write_bytes(content)
        checksum = hashlib.sha256(content).hexdigest()

        output_file = output_dir / "contracts" / "2026" / "q1" / "alpha.md"
        output_file.parent.mkdir(parents=True)
        output_file.write_text("# Alpha Contract")

        manifest_adapter = ManifestAdapter()
        manifest_adapter.create(project_root, "test-project")

        manifest_svc = ManifestService(
            manifest=manifest_adapter,
            project_root=project_root,
            raw_inbox=sources_dir,
            output_dir=output_dir,
        )
        manifest_svc.record_success(
            source_path=source_file,
            checksum=checksum,
            output_path=output_file,
        )
        manifest_svc.commit()

        # Verify the manifest key format
        manifest = manifest_adapter.load(project_root)
        assert "contracts/2026/q1/alpha.pdf" in manifest.files

        # Run discovery — must find as unchanged
        discovery_svc = DiscoveryService(
            file_discovery=FileDiscoveryAdapter(),
            manifest=manifest_adapter,
        )
        result = discovery_svc.discover_changes(project_root)

        assert len(result.unchanged_files) == 1
        assert len(result.new_files) == 0

    def test_force_mode_classifies_existing_as_modified(self, tmp_path: Path) -> None:
        """Force mode should classify manifest-tracked files as 'modified', not 'new'."""
        project_root, sources_dir, output_dir = self._setup_project(tmp_path)

        source_file = sources_dir / "report.pdf"
        content = b"Report content"
        source_file.write_bytes(content)
        checksum = hashlib.sha256(content).hexdigest()

        output_file = output_dir / "report.md"
        output_file.write_text("# Report")

        manifest_adapter = ManifestAdapter()
        manifest_adapter.create(project_root, "test-project")

        manifest_svc = ManifestService(
            manifest=manifest_adapter,
            project_root=project_root,
            raw_inbox=sources_dir,
            output_dir=output_dir,
        )
        manifest_svc.record_success(
            source_path=source_file,
            checksum=checksum,
            output_path=output_file,
        )
        manifest_svc.commit()

        # Run discovery with force=True
        discovery_svc = DiscoveryService(
            file_discovery=FileDiscoveryAdapter(),
            manifest=manifest_adapter,
        )
        result = discovery_svc.discover_changes(project_root, force=True)

        # Force mode: existing files → modified (not new)
        assert len(result.modified_files) == 1, (
            f"Expected 1 modified, got {len(result.modified_files)} modified, "
            f"{len(result.new_files)} new"
        )
        assert len(result.new_files) == 0
        assert result.modified_files[0].status == "modified"
