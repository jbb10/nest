"""Tests for ManifestService.

Tests manifest tracking and updates during sync operations.
"""

from datetime import datetime, timezone
from pathlib import Path

from nest.core.models import FileEntry, Manifest
from nest.services.manifest_service import ManifestService


class MockManifestAdapter:
    """Mock implementation of ManifestProtocol for testing."""

    def __init__(
        self,
        existing_manifest: Manifest | None = None,
    ) -> None:
        self._manifest = existing_manifest or Manifest(
            nest_version="1.0.0",
            project_name="test-project",
            last_sync=None,
            files={},
        )
        self.save_called = False
        self.saved_manifest: Manifest | None = None

    def exists(self, project_dir: Path) -> bool:
        return True

    def create(self, project_dir: Path, project_name: str) -> Manifest:
        self._manifest.project_name = project_name
        return self._manifest

    def load(self, project_dir: Path) -> Manifest:
        return self._manifest

    def save(self, project_dir: Path, manifest: Manifest) -> None:
        self.save_called = True
        self.saved_manifest = manifest


class TestManifestServiceRecordSuccess:
    """Tests for ManifestService.record_success()."""

    def test_creates_file_entry_with_success_status(self) -> None:
        """AC #1: Creates FileEntry with status='success'."""
        # Arrange
        mock_adapter = MockManifestAdapter()
        service = ManifestService(
            manifest=mock_adapter,
            project_root=Path("/project"),
            raw_inbox=Path("/project/raw_inbox"),
            output_dir=Path("/project/processed_context"),
        )

        # Act
        entry = service.record_success(
            source_path=Path("/project/raw_inbox/doc.pdf"),
            checksum="abc123",
            output_path=Path("/project/processed_context/doc.md"),
        )

        # Assert
        assert entry.status == "success"

    def test_sets_sha256_checksum(self) -> None:
        """AC #1: Entry includes sha256 checksum."""
        # Arrange
        mock_adapter = MockManifestAdapter()
        service = ManifestService(
            manifest=mock_adapter,
            project_root=Path("/project"),
            raw_inbox=Path("/project/raw_inbox"),
            output_dir=Path("/project/processed_context"),
        )

        # Act
        entry = service.record_success(
            source_path=Path("/project/raw_inbox/doc.pdf"),
            checksum="deadbeef123456",
            output_path=Path("/project/processed_context/doc.md"),
        )

        # Assert
        assert entry.sha256 == "deadbeef123456"

    def test_sets_processed_at_timestamp(self) -> None:
        """AC #1: Entry includes processed_at ISO timestamp."""
        # Arrange
        mock_adapter = MockManifestAdapter()
        service = ManifestService(
            manifest=mock_adapter,
            project_root=Path("/project"),
            raw_inbox=Path("/project/raw_inbox"),
            output_dir=Path("/project/processed_context"),
        )
        before = datetime.now(timezone.utc)

        # Act
        entry = service.record_success(
            source_path=Path("/project/raw_inbox/doc.pdf"),
            checksum="abc123",
            output_path=Path("/project/processed_context/doc.md"),
        )
        after = datetime.now(timezone.utc)

        # Assert
        assert before <= entry.processed_at <= after

    def test_sets_relative_output_path(self) -> None:
        """AC #1: Entry includes relative path to processed file."""
        # Arrange
        mock_adapter = MockManifestAdapter()
        service = ManifestService(
            manifest=mock_adapter,
            project_root=Path("/project"),
            raw_inbox=Path("/project/raw_inbox"),
            output_dir=Path("/project/processed_context"),
        )

        # Act
        entry = service.record_success(
            source_path=Path("/project/raw_inbox/contracts/2024/alpha.pdf"),
            checksum="abc123",
            output_path=Path("/project/processed_context/contracts/2024/alpha.md"),
        )

        # Assert
        assert entry.output == "contracts/2024/alpha.md"

    def test_stores_entry_with_correct_manifest_key(self) -> None:
        """Entry is stored with source-relative manifest key."""
        # Arrange
        mock_adapter = MockManifestAdapter()
        service = ManifestService(
            manifest=mock_adapter,
            project_root=Path("/project"),
            raw_inbox=Path("/project/raw_inbox"),
            output_dir=Path("/project/processed_context"),
        )

        # Act
        service.record_success(
            source_path=Path("/project/raw_inbox/contracts/2024/alpha.pdf"),
            checksum="abc123",
            output_path=Path("/project/processed_context/contracts/2024/alpha.md"),
        )

        # Assert - verify pending entry key
        assert "contracts/2024/alpha.pdf" in service._pending_entries


class TestManifestServiceRecordFailure:
    """Tests for ManifestService.record_failure()."""

    def test_creates_file_entry_with_failed_status(self) -> None:
        """AC #2: Creates FileEntry with status='failed'."""
        # Arrange
        mock_adapter = MockManifestAdapter()
        service = ManifestService(
            manifest=mock_adapter,
            project_root=Path("/project"),
            raw_inbox=Path("/project/raw_inbox"),
            output_dir=Path("/project/processed_context"),
        )

        # Act
        entry = service.record_failure(
            source_path=Path("/project/raw_inbox/doc.pdf"),
            checksum="abc123",
            error="Password protected",
        )

        # Assert
        assert entry.status == "failed"

    def test_includes_error_message(self) -> None:
        """AC #2: Entry includes error description message."""
        # Arrange
        mock_adapter = MockManifestAdapter()
        service = ManifestService(
            manifest=mock_adapter,
            project_root=Path("/project"),
            raw_inbox=Path("/project/raw_inbox"),
            output_dir=Path("/project/processed_context"),
        )

        # Act
        entry = service.record_failure(
            source_path=Path("/project/raw_inbox/doc.pdf"),
            checksum="abc123",
            error="File is password protected",
        )

        # Assert
        assert entry.error == "File is password protected"

    def test_sets_empty_output_path(self) -> None:
        """AC #2: Failed entries have empty output path."""
        # Arrange
        mock_adapter = MockManifestAdapter()
        service = ManifestService(
            manifest=mock_adapter,
            project_root=Path("/project"),
            raw_inbox=Path("/project/raw_inbox"),
            output_dir=Path("/project/processed_context"),
        )

        # Act
        entry = service.record_failure(
            source_path=Path("/project/raw_inbox/doc.pdf"),
            checksum="abc123",
            error="Some error",
        )

        # Assert
        assert entry.output == ""

    def test_sets_sha256_and_processed_at(self) -> None:
        """Failed entries still include checksum and timestamp."""
        # Arrange
        mock_adapter = MockManifestAdapter()
        service = ManifestService(
            manifest=mock_adapter,
            project_root=Path("/project"),
            raw_inbox=Path("/project/raw_inbox"),
            output_dir=Path("/project/processed_context"),
        )

        # Act
        entry = service.record_failure(
            source_path=Path("/project/raw_inbox/doc.pdf"),
            checksum="checksum123",
            error="Error message",
        )

        # Assert
        assert entry.sha256 == "checksum123"
        assert entry.processed_at is not None


class TestManifestServiceCommit:
    """Tests for ManifestService.commit()."""

    def test_merges_pending_entries_into_manifest(self) -> None:
        """AC #3: Pending entries are merged into manifest.files."""
        # Arrange
        mock_adapter = MockManifestAdapter()
        service = ManifestService(
            manifest=mock_adapter,
            project_root=Path("/project"),
            raw_inbox=Path("/project/raw_inbox"),
            output_dir=Path("/project/processed_context"),
        )
        service.record_success(
            source_path=Path("/project/raw_inbox/doc.pdf"),
            checksum="abc123",
            output_path=Path("/project/processed_context/doc.md"),
        )

        # Act
        service.commit()

        # Assert
        assert mock_adapter.save_called
        assert "doc.pdf" in mock_adapter.saved_manifest.files

    def test_updates_last_sync_timestamp(self) -> None:
        """AC #3: last_sync timestamp is updated."""
        # Arrange
        mock_adapter = MockManifestAdapter()
        service = ManifestService(
            manifest=mock_adapter,
            project_root=Path("/project"),
            raw_inbox=Path("/project/raw_inbox"),
            output_dir=Path("/project/processed_context"),
        )
        before = datetime.now(timezone.utc)

        # Act
        service.commit()
        after = datetime.now(timezone.utc)

        # Assert
        saved = mock_adapter.saved_manifest
        assert saved.last_sync is not None
        assert before <= saved.last_sync <= after

    def test_updates_nest_version(self) -> None:
        """AC #3: nest_version reflects current version."""
        # Arrange
        mock_adapter = MockManifestAdapter()
        service = ManifestService(
            manifest=mock_adapter,
            project_root=Path("/project"),
            raw_inbox=Path("/project/raw_inbox"),
            output_dir=Path("/project/processed_context"),
        )

        # Act
        service.commit()

        # Assert
        from nest import __version__

        assert mock_adapter.saved_manifest.nest_version == __version__

    def test_clears_pending_entries_after_commit(self) -> None:
        """Pending entries are cleared after commit."""
        # Arrange
        mock_adapter = MockManifestAdapter()
        service = ManifestService(
            manifest=mock_adapter,
            project_root=Path("/project"),
            raw_inbox=Path("/project/raw_inbox"),
            output_dir=Path("/project/processed_context"),
        )
        service.record_success(
            source_path=Path("/project/raw_inbox/doc.pdf"),
            checksum="abc123",
            output_path=Path("/project/processed_context/doc.md"),
        )

        # Act
        service.commit()

        # Assert
        assert len(service._pending_entries) == 0

    def test_preserves_existing_manifest_entries(self) -> None:
        """Existing manifest entries are preserved when adding new ones."""
        # Arrange
        existing_entry = FileEntry(
            sha256="existing123",
            processed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            output="existing.md",
            status="success",
        )
        existing_manifest = Manifest(
            nest_version="0.9.0",
            project_name="test",
            last_sync=None,
            files={"existing.pdf": existing_entry},
        )
        mock_adapter = MockManifestAdapter(existing_manifest=existing_manifest)
        service = ManifestService(
            manifest=mock_adapter,
            project_root=Path("/project"),
            raw_inbox=Path("/project/raw_inbox"),
            output_dir=Path("/project/processed_context"),
        )
        service.record_success(
            source_path=Path("/project/raw_inbox/new.pdf"),
            checksum="new123",
            output_path=Path("/project/processed_context/new.md"),
        )

        # Act
        service.commit()

        # Assert
        saved_files = mock_adapter.saved_manifest.files
        assert "existing.pdf" in saved_files
        assert "new.pdf" in saved_files

    def test_creates_manifest_if_missing(self) -> None:
        """Creates a new manifest if not found during commit."""
        # Arrange
        mock_adapter = MockManifestAdapter()
        # Mock exists() to return False
        mock_adapter.exists = lambda _: False

        service = ManifestService(
            manifest=mock_adapter,
            project_root=Path("/project"),
            raw_inbox=Path("/project/raw_inbox"),
            output_dir=Path("/project/processed_context"),
        )

        # Act
        service.commit()

        # Assert
        assert mock_adapter.save_called
        assert mock_adapter.saved_manifest.project_name == "project"
