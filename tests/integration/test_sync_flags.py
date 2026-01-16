"""Integration tests for sync command flags.

Tests end-to-end behavior of sync with various flag combinations.
"""

from pathlib import Path
from unittest.mock import Mock

import pytest

from nest.core.models import (
    DiscoveredFile,
    DiscoveryResult,
    DryRunResult,
    OrphanCleanupResult,
    ProcessingResult,
)
from nest.services.sync_service import SyncService


class TestSyncDryRunIntegration:
    """Integration tests for --dry-run flag."""

    def test_dry_run_returns_counts_without_processing(self, tmp_path: Path) -> None:
        """Dry run should analyze files but not process them."""
        # Setup mocks
        mock_discovery = Mock()
        mock_output = Mock()
        mock_manifest = Mock()
        mock_orphan = Mock()
        mock_index = Mock()

        mock_discovery.discover_changes.return_value = DiscoveryResult(
            new_files=[
                DiscoveredFile(
                    path=tmp_path / "raw_inbox" / "new.pdf",
                    checksum="111",
                    status="new",
                )
            ],
            modified_files=[
                DiscoveredFile(
                    path=tmp_path / "raw_inbox" / "mod.pdf",
                    checksum="222",
                    status="modified",
                )
            ],
            unchanged_files=[
                DiscoveredFile(
                    path=tmp_path / "raw_inbox" / "same.pdf",
                    checksum="333",
                    status="unchanged",
                )
            ],
        )
        mock_orphan.detect_orphans.return_value = ["orphan.md"]

        service = SyncService(
            discovery=mock_discovery,
            output=mock_output,
            manifest=mock_manifest,
            orphan=mock_orphan,
            index=mock_index,
            project_root=tmp_path,
        )

        result = service.sync(dry_run=True)

        # Verify DryRunResult
        assert isinstance(result, DryRunResult)
        assert result.new_count == 1
        assert result.modified_count == 1
        assert result.unchanged_count == 1
        assert result.orphan_count == 1

        # Verify nothing was actually processed
        mock_output.process_file.assert_not_called()
        mock_manifest.record_success.assert_not_called()
        mock_manifest.record_failure.assert_not_called()
        mock_manifest.commit.assert_not_called()
        mock_orphan.cleanup.assert_not_called()
        mock_index.update_index.assert_not_called()


class TestSyncForceIntegration:
    """Integration tests for --force flag."""

    def test_force_reprocesses_unchanged_files(self, tmp_path: Path) -> None:
        """Force should reprocess files even if unchanged."""
        mock_discovery = Mock()
        mock_output = Mock()
        mock_manifest = Mock()
        mock_orphan = Mock()
        mock_index = Mock()

        # Force mode returns all as modified
        mock_discovery.discover_changes.return_value = DiscoveryResult(
            new_files=[],
            modified_files=[
                DiscoveredFile(
                    path=tmp_path / "raw_inbox" / "file.pdf",
                    checksum="111",
                    status="modified",
                )
            ],
            unchanged_files=[],
        )
        mock_output.process_file.return_value = ProcessingResult(
            source_path=tmp_path / "raw_inbox" / "file.pdf",
            status="success",
            output_path=tmp_path / "processed_context" / "file.md",
        )
        mock_manifest.load_current_manifest.return_value = Mock(files={})
        mock_orphan.cleanup.return_value = OrphanCleanupResult()

        service = SyncService(
            discovery=mock_discovery,
            output=mock_output,
            manifest=mock_manifest,
            orphan=mock_orphan,
            index=mock_index,
            project_root=tmp_path,
        )

        service.sync(force=True)

        # Verify force was passed to discovery
        mock_discovery.discover_changes.assert_called_once()
        call_kwargs = mock_discovery.discover_changes.call_args
        assert call_kwargs[1].get("force") is True

        # Verify file was processed
        mock_output.process_file.assert_called_once()


class TestSyncOnErrorIntegration:
    """Integration tests for --on-error flag."""

    def test_skip_mode_continues_after_error(self, tmp_path: Path) -> None:
        """Skip mode should continue processing after failures."""
        mock_discovery = Mock()
        mock_output = Mock()
        mock_manifest = Mock()
        mock_orphan = Mock()
        mock_index = Mock()

        mock_discovery.discover_changes.return_value = DiscoveryResult(
            new_files=[
                DiscoveredFile(
                    path=tmp_path / "raw_inbox" / "fail.pdf",
                    checksum="111",
                    status="new",
                ),
                DiscoveredFile(
                    path=tmp_path / "raw_inbox" / "ok.pdf",
                    checksum="222",
                    status="new",
                ),
            ],
            modified_files=[],
            unchanged_files=[],
        )

        # First file fails, second succeeds
        mock_output.process_file.side_effect = [
            ProcessingResult(
                source_path=tmp_path / "raw_inbox" / "fail.pdf",
                status="failed",
                error="Corrupted",
            ),
            ProcessingResult(
                source_path=tmp_path / "raw_inbox" / "ok.pdf",
                status="success",
                output_path=tmp_path / "processed_context" / "ok.md",
            ),
        ]
        mock_manifest.load_current_manifest.return_value = Mock(files={})
        mock_orphan.cleanup.return_value = OrphanCleanupResult()

        service = SyncService(
            discovery=mock_discovery,
            output=mock_output,
            manifest=mock_manifest,
            orphan=mock_orphan,
            index=mock_index,
            project_root=tmp_path,
        )

        # Should not raise
        service.sync(on_error="skip")

        # Both files should have been attempted
        assert mock_output.process_file.call_count == 2
        # Both success and failure recorded
        mock_manifest.record_success.assert_called_once()
        mock_manifest.record_failure.assert_called_once()

    def test_fail_mode_aborts_on_first_error(self, tmp_path: Path) -> None:
        """Fail mode should abort immediately on first failure."""
        from nest.core.exceptions import ProcessingError

        mock_discovery = Mock()
        mock_output = Mock()
        mock_manifest = Mock()
        mock_orphan = Mock()
        mock_index = Mock()

        mock_discovery.discover_changes.return_value = DiscoveryResult(
            new_files=[
                DiscoveredFile(
                    path=tmp_path / "raw_inbox" / "fail.pdf",
                    checksum="111",
                    status="new",
                ),
                DiscoveredFile(
                    path=tmp_path / "raw_inbox" / "ok.pdf",
                    checksum="222",
                    status="new",
                ),
            ],
            modified_files=[],
            unchanged_files=[],
        )

        mock_output.process_file.return_value = ProcessingResult(
            source_path=tmp_path / "raw_inbox" / "fail.pdf",
            status="failed",
            error="Corrupted",
        )

        service = SyncService(
            discovery=mock_discovery,
            output=mock_output,
            manifest=mock_manifest,
            orphan=mock_orphan,
            index=mock_index,
            project_root=tmp_path,
        )

        with pytest.raises(ProcessingError):
            service.sync(on_error="fail")

        # Only first file should have been attempted
        assert mock_output.process_file.call_count == 1


class TestSyncFlagCombinations:
    """Tests for combining multiple flags."""

    def test_force_and_dry_run(self, tmp_path: Path) -> None:
        """--force --dry-run should show all files as modified."""
        mock_discovery = Mock()
        mock_output = Mock()
        mock_manifest = Mock()
        mock_orphan = Mock()
        mock_index = Mock()

        # Force returns everything as modified
        mock_discovery.discover_changes.return_value = DiscoveryResult(
            new_files=[],
            modified_files=[
                DiscoveredFile(
                    path=tmp_path / "raw_inbox" / "a.pdf",
                    checksum="111",
                    status="modified",
                ),
                DiscoveredFile(
                    path=tmp_path / "raw_inbox" / "b.pdf",
                    checksum="222",
                    status="modified",
                ),
            ],
            unchanged_files=[],
        )
        mock_orphan.detect_orphans.return_value = []

        service = SyncService(
            discovery=mock_discovery,
            output=mock_output,
            manifest=mock_manifest,
            orphan=mock_orphan,
            index=mock_index,
            project_root=tmp_path,
        )

        result = service.sync(force=True, dry_run=True)

        assert isinstance(result, DryRunResult)
        assert result.modified_count == 2
        assert result.unchanged_count == 0

        # Verify force was passed
        call_kwargs = mock_discovery.discover_changes.call_args
        assert call_kwargs[1].get("force") is True

    def test_no_clean_and_dry_run(self, tmp_path: Path) -> None:
        """--no-clean --dry-run should work (dry-run takes precedence)."""
        mock_discovery = Mock()
        mock_output = Mock()
        mock_manifest = Mock()
        mock_orphan = Mock()
        mock_index = Mock()

        mock_discovery.discover_changes.return_value = DiscoveryResult(
            new_files=[],
            modified_files=[],
            unchanged_files=[],
        )
        mock_orphan.detect_orphans.return_value = ["orphan.md"]

        service = SyncService(
            discovery=mock_discovery,
            output=mock_output,
            manifest=mock_manifest,
            orphan=mock_orphan,
            index=mock_index,
            project_root=tmp_path,
        )

        result = service.sync(no_clean=True, dry_run=True)

        assert isinstance(result, DryRunResult)
        assert result.orphan_count == 1
        # Cleanup should not be called (dry-run)
        mock_orphan.cleanup.assert_not_called()
