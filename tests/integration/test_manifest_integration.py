"""Integration tests for manifest tracking.

Tests the full pipeline: process file → manifest updated → re-process → entry updated.
"""

from datetime import datetime, timezone
from pathlib import Path

from nest.adapters.manifest import ManifestAdapter
from nest.services.manifest_service import ManifestService


class TestManifestIntegration:
    """Integration tests for manifest tracking with real filesystem."""

    def test_process_file_updates_manifest(self, tmp_path: Path) -> None:
        """Process file → check manifest updated with correct entry."""
        # Arrange - create project structure
        project_root = tmp_path
        raw_inbox = project_root / "raw_inbox"
        processed = project_root / "processed_context"
        raw_inbox.mkdir()
        processed.mkdir()

        # Create initial manifest
        adapter = ManifestAdapter()
        adapter.create(project_root, "test-project")

        service = ManifestService(
            manifest=adapter,
            project_root=project_root,
        )

        # Simulate processing a file
        source = raw_inbox / "contracts" / "alpha.pdf"
        source.parent.mkdir(parents=True)
        source.write_bytes(b"PDF content")

        output = processed / "contracts" / "alpha.md"
        output.parent.mkdir(parents=True)
        output.write_text("# Alpha Contract\n\nContent here.")

        # Act
        service.record_success(
            source_path=source,
            checksum="abc123def456",
            output_path=output,
        )
        service.commit()

        # Assert - reload manifest and verify
        manifest = adapter.load(project_root)
        assert "contracts/alpha.pdf" in manifest.files

        entry = manifest.files["contracts/alpha.pdf"]
        assert entry.status == "success"
        assert entry.sha256 == "abc123def456"
        assert entry.output == "contracts/alpha.md"
        assert entry.processed_at is not None

    def test_fail_processing_records_failure(self, tmp_path: Path) -> None:
        """Fail processing → check manifest records failure entry."""
        # Arrange
        project_root = tmp_path
        raw_inbox = project_root / "raw_inbox"
        raw_inbox.mkdir()
        (project_root / "processed_context").mkdir()

        adapter = ManifestAdapter()
        adapter.create(project_root, "test-project")

        service = ManifestService(
            manifest=adapter,
            project_root=project_root,
        )

        source = raw_inbox / "encrypted.pdf"
        source.write_bytes(b"Encrypted PDF")

        # Act
        service.record_failure(
            source_path=source,
            checksum="encrypted123",
            error="Password protected file",
        )
        service.commit()

        # Assert
        manifest = adapter.load(project_root)
        assert "encrypted.pdf" in manifest.files

        entry = manifest.files["encrypted.pdf"]
        assert entry.status == "failed"
        assert entry.error == "Password protected file"
        assert entry.output == ""

    def test_reprocess_updates_existing_entry(self, tmp_path: Path) -> None:
        """Re-process → check manifest entry updated (not duplicated)."""
        # Arrange
        project_root = tmp_path
        raw_inbox = project_root / "raw_inbox"
        processed = project_root / "processed_context"
        raw_inbox.mkdir()
        processed.mkdir()

        adapter = ManifestAdapter()
        adapter.create(project_root, "test-project")

        service = ManifestService(
            manifest=adapter,
            project_root=project_root,
        )

        source = raw_inbox / "doc.pdf"
        source.write_bytes(b"Original content")
        output = processed / "doc.md"
        output.write_text("# Document")

        # First processing
        service.record_success(
            source_path=source,
            checksum="original_checksum",
            output_path=output,
        )
        service.commit()

        # Simulate file modification and re-processing
        source.write_bytes(b"Modified content")

        service2 = ManifestService(
            manifest=adapter,
            project_root=project_root,
        )
        service2.record_success(
            source_path=source,
            checksum="new_checksum",
            output_path=output,
        )
        service2.commit()

        # Assert - only one entry, with updated checksum
        manifest = adapter.load(project_root)
        assert len(manifest.files) == 1
        assert "doc.pdf" in manifest.files
        assert manifest.files["doc.pdf"].sha256 == "new_checksum"

    def test_manifest_last_sync_and_version_updated(self, tmp_path: Path) -> None:
        """Verify last_sync and nest_version are updated on commit."""
        # Arrange
        project_root = tmp_path
        raw_inbox = project_root / "raw_inbox"
        processed = project_root / "processed_context"
        raw_inbox.mkdir()
        processed.mkdir()

        adapter = ManifestAdapter()
        initial_manifest = adapter.create(project_root, "test-project")
        assert initial_manifest.last_sync is None

        service = ManifestService(
            manifest=adapter,
            project_root=project_root,
        )

        before = datetime.now(timezone.utc)

        # Act
        service.commit()

        after = datetime.now(timezone.utc)

        # Assert
        manifest = adapter.load(project_root)
        assert manifest.last_sync is not None
        assert before <= manifest.last_sync <= after

        from nest import __version__

        assert manifest.nest_version == __version__

    def test_multiple_files_in_single_commit(self, tmp_path: Path) -> None:
        """Multiple files recorded and committed together."""
        # Arrange
        project_root = tmp_path
        raw_inbox = project_root / "raw_inbox"
        processed = project_root / "processed_context"
        raw_inbox.mkdir()
        processed.mkdir()

        adapter = ManifestAdapter()
        adapter.create(project_root, "test-project")

        service = ManifestService(
            manifest=adapter,
            project_root=project_root,
        )

        # Create multiple files
        files = [
            ("doc1.pdf", "hash1", "doc1.md"),
            ("doc2.pdf", "hash2", "doc2.md"),
            ("subdir/doc3.pdf", "hash3", "subdir/doc3.md"),
        ]

        for source_rel, checksum, output_rel in files:
            source = raw_inbox / source_rel
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_bytes(b"content")

            output = processed / output_rel
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text("# Content")

            service.record_success(
                source_path=source,
                checksum=checksum,
                output_path=output,
            )

        # Act
        service.commit()

        # Assert
        manifest = adapter.load(project_root)
        assert len(manifest.files) == 3
        assert manifest.files["doc1.pdf"].sha256 == "hash1"
        assert manifest.files["doc2.pdf"].sha256 == "hash2"
        assert manifest.files["subdir/doc3.pdf"].sha256 == "hash3"
