"""Tests for discovery service."""

from datetime import datetime
from pathlib import Path
from unittest.mock import Mock

from nest.adapters.protocols import FileDiscoveryProtocol, ManifestProtocol
from nest.core.models import DiscoveryResult, FileEntry, Manifest
from nest.services.discovery_service import DiscoveryService


class TestDiscoveryService:
    """Tests for DiscoveryService class."""

    def test_discovers_new_files_not_in_manifest(self, tmp_path: Path) -> None:
        """Verify files not in manifest are classified as 'new'."""
        # Arrange
        raw_inbox = tmp_path / "raw_inbox"
        raw_inbox.mkdir()
        pdf_file = raw_inbox / "document.pdf"
        pdf_file.write_bytes(b"pdf content")

        # Mock file discovery
        mock_discovery = Mock(spec=FileDiscoveryProtocol)
        mock_discovery.discover.return_value = [pdf_file]

        # Mock manifest - empty files dict
        mock_manifest = Mock(spec=ManifestProtocol)
        mock_manifest.load.return_value = Manifest(
            nest_version="0.1.0",
            project_name="test",
            files={},
        )

        service = DiscoveryService(
            file_discovery=mock_discovery,
            manifest=mock_manifest,
        )

        # Act
        result = service.discover_changes(tmp_path)

        # Assert
        assert len(result.new_files) == 1
        assert len(result.modified_files) == 0
        assert len(result.unchanged_files) == 0
        assert result.new_files[0].path == pdf_file
        assert result.new_files[0].status == "new"

    def test_discovers_modified_files_with_different_checksum(
        self, tmp_path: Path
    ) -> None:
        """Verify files with different checksums are classified as 'modified'."""
        # Arrange
        raw_inbox = tmp_path / "raw_inbox"
        raw_inbox.mkdir()
        pdf_file = raw_inbox / "document.pdf"
        pdf_file.write_bytes(b"updated content")

        mock_discovery = Mock(spec=FileDiscoveryProtocol)
        mock_discovery.discover.return_value = [pdf_file]

        # Mock manifest with old checksum
        mock_manifest = Mock(spec=ManifestProtocol)
        mock_manifest.load.return_value = Manifest(
            nest_version="0.1.0",
            project_name="test",
            files={
                "raw_inbox/document.pdf": FileEntry(
                    sha256="old_different_checksum",
                    processed_at=datetime.now(),
                    output="processed_context/document.md",
                    status="success",
                )
            },
        )

        service = DiscoveryService(
            file_discovery=mock_discovery,
            manifest=mock_manifest,
        )

        # Act
        result = service.discover_changes(tmp_path)

        # Assert
        assert len(result.new_files) == 0
        assert len(result.modified_files) == 1
        assert len(result.unchanged_files) == 0
        assert result.modified_files[0].status == "modified"

    def test_discovers_unchanged_files_with_matching_checksum(
        self, tmp_path: Path
    ) -> None:
        """Verify files with matching checksums are classified as 'unchanged'."""
        # Arrange
        import hashlib

        raw_inbox = tmp_path / "raw_inbox"
        raw_inbox.mkdir()
        content = b"same content"
        pdf_file = raw_inbox / "document.pdf"
        pdf_file.write_bytes(content)
        same_checksum = hashlib.sha256(content).hexdigest()

        mock_discovery = Mock(spec=FileDiscoveryProtocol)
        mock_discovery.discover.return_value = [pdf_file]

        mock_manifest = Mock(spec=ManifestProtocol)
        mock_manifest.load.return_value = Manifest(
            nest_version="0.1.0",
            project_name="test",
            files={
                "raw_inbox/document.pdf": FileEntry(
                    sha256=same_checksum,
                    processed_at=datetime.now(),
                    output="processed_context/document.md",
                    status="success",
                )
            },
        )

        service = DiscoveryService(
            file_discovery=mock_discovery,
            manifest=mock_manifest,
        )

        # Act
        result = service.discover_changes(tmp_path)

        # Assert
        assert len(result.new_files) == 0
        assert len(result.modified_files) == 0
        assert len(result.unchanged_files) == 1
        assert result.unchanged_files[0].status == "unchanged"

    def test_returns_discovery_result_with_correct_counts(self, tmp_path: Path) -> None:
        """Verify pending_count and total_count properties work correctly."""
        # Arrange
        import hashlib

        raw_inbox = tmp_path / "raw_inbox"
        raw_inbox.mkdir()

        # Create 3 files: 1 new, 1 modified, 1 unchanged
        new_file = raw_inbox / "new.pdf"
        new_file.write_bytes(b"new content")

        modified_file = raw_inbox / "modified.pdf"
        modified_file.write_bytes(b"modified content")

        unchanged_content = b"unchanged content"
        unchanged_file = raw_inbox / "unchanged.pdf"
        unchanged_file.write_bytes(unchanged_content)
        unchanged_hash = hashlib.sha256(unchanged_content).hexdigest()

        mock_discovery = Mock(spec=FileDiscoveryProtocol)
        mock_discovery.discover.return_value = [new_file, modified_file, unchanged_file]

        mock_manifest = Mock(spec=ManifestProtocol)
        mock_manifest.load.return_value = Manifest(
            nest_version="0.1.0",
            project_name="test",
            files={
                "raw_inbox/modified.pdf": FileEntry(
                    sha256="old_hash",
                    processed_at=datetime.now(),
                    output="processed_context/modified.md",
                    status="success",
                ),
                "raw_inbox/unchanged.pdf": FileEntry(
                    sha256=unchanged_hash,
                    processed_at=datetime.now(),
                    output="processed_context/unchanged.md",
                    status="success",
                ),
            },
        )

        service = DiscoveryService(
            file_discovery=mock_discovery,
            manifest=mock_manifest,
        )

        # Act
        result = service.discover_changes(tmp_path)

        # Assert
        assert result.pending_count == 2  # new + modified
        assert result.total_count == 3

    def test_calls_file_discovery_with_correct_parameters(self, tmp_path: Path) -> None:
        """Verify file discovery is called with raw_inbox and supported extensions."""
        # Arrange
        raw_inbox = tmp_path / "raw_inbox"
        raw_inbox.mkdir()

        mock_discovery = Mock(spec=FileDiscoveryProtocol)
        mock_discovery.discover.return_value = []

        mock_manifest = Mock(spec=ManifestProtocol)
        mock_manifest.load.return_value = Manifest(
            nest_version="0.1.0",
            project_name="test",
            files={},
        )

        service = DiscoveryService(
            file_discovery=mock_discovery,
            manifest=mock_manifest,
        )

        # Act
        service.discover_changes(tmp_path)

        # Assert
        mock_discovery.discover.assert_called_once()
        call_args = mock_discovery.discover.call_args
        assert call_args[0][0] == raw_inbox  # First positional arg is directory
        # Second arg should be set of supported extensions
        extensions = call_args[0][1]
        assert ".pdf" in extensions
        assert ".docx" in extensions
        assert ".pptx" in extensions
        assert ".xlsx" in extensions
        assert ".html" in extensions

    def test_handles_empty_raw_inbox(self, tmp_path: Path) -> None:
        """Verify empty raw_inbox returns empty discovery result."""
        # Arrange
        raw_inbox = tmp_path / "raw_inbox"
        raw_inbox.mkdir()

        mock_discovery = Mock(spec=FileDiscoveryProtocol)
        mock_discovery.discover.return_value = []

        mock_manifest = Mock(spec=ManifestProtocol)
        mock_manifest.load.return_value = Manifest(
            nest_version="0.1.0",
            project_name="test",
            files={},
        )

        service = DiscoveryService(
            file_discovery=mock_discovery,
            manifest=mock_manifest,
        )

        # Act
        result = service.discover_changes(tmp_path)

        # Assert
        assert result.pending_count == 0
        assert result.total_count == 0
        assert isinstance(result, DiscoveryResult)

    def test_loads_manifest_from_project_directory(self, tmp_path: Path) -> None:
        """Verify manifest is loaded from the project directory."""
        # Arrange
        raw_inbox = tmp_path / "raw_inbox"
        raw_inbox.mkdir()

        mock_discovery = Mock(spec=FileDiscoveryProtocol)
        mock_discovery.discover.return_value = []

        mock_manifest = Mock(spec=ManifestProtocol)
        mock_manifest.load.return_value = Manifest(
            nest_version="0.1.0",
            project_name="test",
            files={},
        )

        service = DiscoveryService(
            file_discovery=mock_discovery,
            manifest=mock_manifest,
        )

        # Act
        service.discover_changes(tmp_path)

        # Assert
        mock_manifest.load.assert_called_once_with(tmp_path)
