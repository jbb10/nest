"""Tests for SyncService orchestration logic."""

from datetime import datetime
from pathlib import Path
from unittest.mock import Mock

import pytest

from nest.core.models import (
    DiscoveredFile,
    DiscoveryResult,
    DryRunResult,
    FileEntry,
    Manifest,
    OrphanCleanupResult,
    ProcessingResult,
)
from nest.services.discovery_service import DiscoveryService
from nest.services.index_service import IndexService
from nest.services.manifest_service import ManifestService
from nest.services.orphan_service import OrphanService
from nest.services.output_service import OutputMirrorService
from nest.services.sync_service import SyncService


@pytest.fixture
def mock_deps():
    """Create mock dependencies for SyncService."""
    orphan_mock = Mock(spec=OrphanService)
    orphan_mock.cleanup.return_value = OrphanCleanupResult(
        orphans_detected=[],
        orphans_removed=[],
        skipped=False,
    )

    return {
        "discovery": Mock(spec=DiscoveryService),
        "output": Mock(spec=OutputMirrorService),
        "manifest": Mock(spec=ManifestService),
        "orphan": orphan_mock,
        "index": Mock(spec=IndexService),
        "project_root": Path("/app"),
    }


def _create_sync_service(deps: dict) -> SyncService:
    """Helper to create SyncService from mock dependencies dict."""
    return SyncService(
        discovery=deps["discovery"],
        output=deps["output"],
        manifest=deps["manifest"],
        orphan=deps["orphan"],
        index=deps["index"],
        project_root=deps["project_root"],
    )


def _empty_discovery_result() -> DiscoveryResult:
    """Return a DiscoveryResult with no files."""
    return DiscoveryResult(new_files=[], modified_files=[], unchanged_files=[])


def _empty_manifest() -> Manifest:
    """Return an empty manifest."""
    return Manifest(nest_version="1.0", project_name="TestProject", files={})


class TestSyncIndexIntegration:
    """Tests for index generation during sync."""

    def test_sync_calls_index_update_with_success_files(self, mock_deps):
        """Index should receive only successful file paths."""
        service = _create_sync_service(mock_deps)

        mock_deps["discovery"].discover_changes.return_value = DiscoveryResult(
            new_files=[DiscoveredFile(path=Path("/app/raw/a.pdf"), checksum="123", status="new")],
            modified_files=[],
            unchanged_files=[],
        )

        mock_deps["output"].process_file.return_value = ProcessingResult(
            source_path=Path("/app/raw/a.pdf"),
            status="success",
            output_path=Path("/app/processed_context/idx/a.md"),
            error=None,
        )

        final_manifest = Manifest(
            nest_version="1.0",
            project_name="Nest",
            files={
                "key_a": FileEntry(
                    sha256="123",
                    processed_at=datetime.now(),
                    output="idx/a.md",
                    status="success",
                    error=None,
                ),
                "key_b": FileEntry(
                    sha256="456",
                    processed_at=datetime.now(),
                    output="",
                    status="failed",
                    error="boom",
                ),
            },
        )

        mock_deps["manifest"].commit.return_value = None
        mock_deps["manifest"].load_current_manifest.return_value = final_manifest

        service.sync()

        mock_deps["index"].update_index.assert_called_once()
        files_arg = mock_deps["index"].update_index.call_args[0][0]
        project_name = mock_deps["index"].update_index.call_args[0][1]

        assert "idx/a.md" in files_arg
        assert "" not in files_arg  # Failed entries have empty output
        assert len(files_arg) == 1
        assert project_name == mock_deps["project_root"].name


class TestSyncEmptyDiscovery:
    """Tests for sync behavior with no files to process."""

    def test_sync_with_no_new_or_modified_files(self, mock_deps):
        """Sync should still commit manifest and update index when no files to process."""
        service = _create_sync_service(mock_deps)

        mock_deps["discovery"].discover_changes.return_value = _empty_discovery_result()
        mock_deps["manifest"].load_current_manifest.return_value = _empty_manifest()

        service.sync()

        # Commit should still be called
        mock_deps["manifest"].commit.assert_called_once()
        # Index should still be updated (empty list)
        mock_deps["index"].update_index.assert_called_once()
        files_arg = mock_deps["index"].update_index.call_args[0][0]
        assert files_arg == []


class TestSyncFailureHandling:
    """Tests for failure path handling in sync."""

    def test_sync_records_failure_when_processing_fails(self, mock_deps):
        """Failed processing should call record_failure with error message."""
        service = _create_sync_service(mock_deps)

        mock_deps["discovery"].discover_changes.return_value = DiscoveryResult(
            new_files=[DiscoveredFile(path=Path("/app/raw/bad.pdf"), checksum="abc", status="new")],
            modified_files=[],
            unchanged_files=[],
        )

        mock_deps["output"].process_file.return_value = ProcessingResult(
            source_path=Path("/app/raw/bad.pdf"),
            status="failed",
            output_path=None,
            error="Password protected",
        )

        mock_deps["manifest"].load_current_manifest.return_value = _empty_manifest()

        service.sync()

        mock_deps["manifest"].record_failure.assert_called_once()
        call_args = mock_deps["manifest"].record_failure.call_args
        assert call_args[0][0] == Path("/app/raw/bad.pdf")
        assert call_args[0][1] == "abc"
        assert call_args[0][2] == "Password protected"

    def test_sync_records_failure_when_error_is_none(self, mock_deps):
        """Failed processing with None error should use 'Unknown error'."""
        service = _create_sync_service(mock_deps)

        mock_deps["discovery"].discover_changes.return_value = DiscoveryResult(
            new_files=[DiscoveredFile(path=Path("/app/raw/bad.pdf"), checksum="abc", status="new")],
            modified_files=[],
            unchanged_files=[],
        )

        mock_deps["output"].process_file.return_value = ProcessingResult(
            source_path=Path("/app/raw/bad.pdf"),
            status="failed",
            output_path=None,
            error=None,  # No error message
        )

        mock_deps["manifest"].load_current_manifest.return_value = _empty_manifest()

        service.sync()

        call_args = mock_deps["manifest"].record_failure.call_args
        assert call_args[0][2] == "Unknown error"

    def test_sync_handles_exception_during_processing(self, mock_deps):
        """Exception during process_file should record failure and continue."""
        service = _create_sync_service(mock_deps)

        mock_deps["discovery"].discover_changes.return_value = DiscoveryResult(
            new_files=[
                DiscoveredFile(path=Path("/app/raw/crash.pdf"), checksum="xyz", status="new"),
                DiscoveredFile(path=Path("/app/raw/ok.pdf"), checksum="def", status="new"),
            ],
            modified_files=[],
            unchanged_files=[],
        )

        # First call raises, second succeeds
        mock_deps["output"].process_file.side_effect = [
            RuntimeError("Unexpected crash"),
            ProcessingResult(
                source_path=Path("/app/raw/ok.pdf"),
                status="success",
                output_path=Path("/app/processed_context/ok.md"),
            ),
        ]

        mock_deps["manifest"].load_current_manifest.return_value = _empty_manifest()

        service.sync()

        # Both files should be processed (no early exit)
        assert mock_deps["output"].process_file.call_count == 2
        # First file should record failure
        assert mock_deps["manifest"].record_failure.call_count == 1
        failure_call = mock_deps["manifest"].record_failure.call_args
        assert "Unexpected crash" in failure_call[0][2]
        # Second file should record success
        assert mock_deps["manifest"].record_success.call_count == 1


class TestSyncOutputPathNone:
    """Tests for defensive check when success status has None output_path."""

    def test_sync_records_failure_when_success_but_output_path_none(self, mock_deps):
        """Success status with None output_path should record failure."""
        service = _create_sync_service(mock_deps)

        mock_deps["discovery"].discover_changes.return_value = DiscoveryResult(
            new_files=[
                DiscoveredFile(path=Path("/app/raw/weird.pdf"), checksum="999", status="new")
            ],
            modified_files=[],
            unchanged_files=[],
        )

        # Malformed result: success but no output_path
        mock_deps["output"].process_file.return_value = ProcessingResult(
            source_path=Path("/app/raw/weird.pdf"),
            status="success",
            output_path=None,  # Bug in processor
            error=None,
        )

        mock_deps["manifest"].load_current_manifest.return_value = _empty_manifest()

        service.sync()

        mock_deps["manifest"].record_failure.assert_called_once()
        call_args = mock_deps["manifest"].record_failure.call_args
        assert "output_path missing" in call_args[0][2]
        # record_success should NOT be called
        mock_deps["manifest"].record_success.assert_not_called()


class TestSyncManifestCommit:
    """Tests for manifest commit behavior."""

    def test_sync_commits_manifest_before_index_update(self, mock_deps):
        """Orphan cleanup, then manifest commit, then index update."""
        service = _create_sync_service(mock_deps)
        call_order = []

        mock_deps["discovery"].discover_changes.return_value = _empty_discovery_result()
        mock_deps["orphan"].cleanup.side_effect = lambda no_clean: (
            call_order.append("orphan"),
            OrphanCleanupResult(),
        )[1]
        mock_deps["manifest"].commit.side_effect = lambda: call_order.append("commit")
        mock_deps["manifest"].load_current_manifest.side_effect = lambda: (
            call_order.append("load"),
            _empty_manifest(),
        )[1]
        mock_deps["index"].update_index.side_effect = lambda *_: call_order.append("index")

        service.sync()

        assert call_order == ["orphan", "commit", "load", "index"]


class TestSyncOnErrorMode:
    """Tests for on_error flag behavior (skip vs fail)."""

    def test_skip_mode_continues_after_processing_failure(self, mock_deps):
        """on_error=skip should continue processing remaining files after failure."""
        service = _create_sync_service(mock_deps)

        mock_deps["discovery"].discover_changes.return_value = DiscoveryResult(
            new_files=[
                DiscoveredFile(path=Path("/app/raw/fail.pdf"), checksum="111", status="new"),
                DiscoveredFile(path=Path("/app/raw/ok.pdf"), checksum="222", status="new"),
            ],
            modified_files=[],
            unchanged_files=[],
        )

        # First file fails, second succeeds
        mock_deps["output"].process_file.side_effect = [
            ProcessingResult(
                source_path=Path("/app/raw/fail.pdf"),
                status="failed",
                output_path=None,
                error="Corrupted file",
            ),
            ProcessingResult(
                source_path=Path("/app/raw/ok.pdf"),
                status="success",
                output_path=Path("/app/processed_context/ok.md"),
            ),
        ]

        mock_deps["manifest"].load_current_manifest.return_value = _empty_manifest()

        # Default is on_error="skip"
        service.sync(on_error="skip")

        # Both files should be attempted
        assert mock_deps["output"].process_file.call_count == 2
        # Success should be recorded
        mock_deps["manifest"].record_success.assert_called_once()
        # Failure should be recorded
        mock_deps["manifest"].record_failure.assert_called_once()

    def test_fail_mode_aborts_on_first_failure(self, mock_deps):
        """on_error=fail should raise immediately on first failure."""
        from nest.core.exceptions import ProcessingError

        service = _create_sync_service(mock_deps)

        mock_deps["discovery"].discover_changes.return_value = DiscoveryResult(
            new_files=[
                DiscoveredFile(path=Path("/app/raw/fail.pdf"), checksum="111", status="new"),
                DiscoveredFile(path=Path("/app/raw/ok.pdf"), checksum="222", status="new"),
            ],
            modified_files=[],
            unchanged_files=[],
        )

        mock_deps["output"].process_file.return_value = ProcessingResult(
            source_path=Path("/app/raw/fail.pdf"),
            status="failed",
            output_path=None,
            error="Corrupted file",
        )

        with pytest.raises(ProcessingError) as exc_info:
            service.sync(on_error="fail")

        # Should abort after first file
        assert mock_deps["output"].process_file.call_count == 1
        assert "fail.pdf" in str(exc_info.value)

    def test_fail_mode_raises_on_exception(self, mock_deps):
        """on_error=fail should re-raise exceptions immediately."""
        service = _create_sync_service(mock_deps)

        mock_deps["discovery"].discover_changes.return_value = DiscoveryResult(
            new_files=[
                DiscoveredFile(path=Path("/app/raw/crash.pdf"), checksum="111", status="new"),
                DiscoveredFile(path=Path("/app/raw/ok.pdf"), checksum="222", status="new"),
            ],
            modified_files=[],
            unchanged_files=[],
        )

        mock_deps["output"].process_file.side_effect = RuntimeError("Unexpected crash")

        with pytest.raises(RuntimeError, match="Unexpected crash"):
            service.sync(on_error="fail")

        # Should abort after first exception
        assert mock_deps["output"].process_file.call_count == 1

    def test_skip_mode_is_default(self, mock_deps):
        """Default on_error should be skip (continue after failures)."""
        service = _create_sync_service(mock_deps)

        mock_deps["discovery"].discover_changes.return_value = DiscoveryResult(
            new_files=[
                DiscoveredFile(path=Path("/app/raw/fail.pdf"), checksum="111", status="new"),
                DiscoveredFile(path=Path("/app/raw/ok.pdf"), checksum="222", status="new"),
            ],
            modified_files=[],
            unchanged_files=[],
        )

        mock_deps["output"].process_file.side_effect = [
            RuntimeError("First fails"),
            ProcessingResult(
                source_path=Path("/app/raw/ok.pdf"),
                status="success",
                output_path=Path("/app/processed_context/ok.md"),
            ),
        ]

        mock_deps["manifest"].load_current_manifest.return_value = _empty_manifest()

        # No on_error argument - should use default (skip)
        service.sync()

        # Both files should be attempted
        assert mock_deps["output"].process_file.call_count == 2


class TestSyncDryRunMode:
    """Tests for dry-run flag behavior."""

    def test_dry_run_returns_dry_run_result(self, mock_deps):
        """dry_run=True should return DryRunResult instead of OrphanCleanupResult."""
        service = _create_sync_service(mock_deps)

        mock_deps["discovery"].discover_changes.return_value = DiscoveryResult(
            new_files=[
                DiscoveredFile(path=Path("/app/raw/new.pdf"), checksum="111", status="new"),
            ],
            modified_files=[
                DiscoveredFile(path=Path("/app/raw/mod.pdf"), checksum="222", status="modified"),
            ],
            unchanged_files=[
                DiscoveredFile(path=Path("/app/raw/same.pdf"), checksum="333", status="unchanged"),
            ],
        )

        mock_deps["orphan"].detect_orphans.return_value = ["orphan1.md", "orphan2.md"]

        result = service.sync(dry_run=True)

        assert isinstance(result, DryRunResult)
        assert result.new_count == 1
        assert result.modified_count == 1
        assert result.unchanged_count == 1
        assert result.orphan_count == 2

    def test_dry_run_does_not_process_files(self, mock_deps):
        """dry_run=True should NOT call process_file."""
        service = _create_sync_service(mock_deps)

        mock_deps["discovery"].discover_changes.return_value = DiscoveryResult(
            new_files=[
                DiscoveredFile(path=Path("/app/raw/new.pdf"), checksum="111", status="new"),
            ],
            modified_files=[],
            unchanged_files=[],
        )

        mock_deps["orphan"].detect_orphans.return_value = []

        service.sync(dry_run=True)

        # No files should be processed
        mock_deps["output"].process_file.assert_not_called()

    def test_dry_run_does_not_modify_manifest(self, mock_deps):
        """dry_run=True should NOT modify or commit manifest."""
        service = _create_sync_service(mock_deps)

        mock_deps["discovery"].discover_changes.return_value = DiscoveryResult(
            new_files=[
                DiscoveredFile(path=Path("/app/raw/new.pdf"), checksum="111", status="new"),
            ],
            modified_files=[],
            unchanged_files=[],
        )

        mock_deps["orphan"].detect_orphans.return_value = []

        service.sync(dry_run=True)

        # Manifest should not be modified
        mock_deps["manifest"].record_success.assert_not_called()
        mock_deps["manifest"].record_failure.assert_not_called()
        mock_deps["manifest"].commit.assert_not_called()

    def test_dry_run_does_not_remove_orphans(self, mock_deps):
        """dry_run=True should detect orphans but NOT remove them."""
        service = _create_sync_service(mock_deps)

        mock_deps["discovery"].discover_changes.return_value = _empty_discovery_result()
        mock_deps["orphan"].detect_orphans.return_value = ["orphan.md"]

        service.sync(dry_run=True)

        # Orphan cleanup should not be called
        mock_deps["orphan"].cleanup.assert_not_called()
        # But detect_orphans should be called
        mock_deps["orphan"].detect_orphans.assert_called_once()

    def test_dry_run_does_not_update_index(self, mock_deps):
        """dry_run=True should NOT update the master index."""
        service = _create_sync_service(mock_deps)

        mock_deps["discovery"].discover_changes.return_value = _empty_discovery_result()
        mock_deps["orphan"].detect_orphans.return_value = []

        service.sync(dry_run=True)

        mock_deps["index"].update_index.assert_not_called()


class TestSyncForceMode:
    """Tests for force flag behavior."""

    def test_force_mode_processes_all_files(self, mock_deps):
        """force=True should process all files including unchanged."""
        service = _create_sync_service(mock_deps)

        # Force mode passes force=True to discovery, which returns files as modified
        mock_deps["discovery"].discover_changes.return_value = DiscoveryResult(
            new_files=[],
            modified_files=[
                DiscoveredFile(path=Path("/app/raw/same.pdf"), checksum="111", status="modified"),
            ],
            unchanged_files=[],
        )

        mock_deps["output"].process_file.return_value = ProcessingResult(
            source_path=Path("/app/raw/same.pdf"),
            status="success",
            output_path=Path("/app/processed_context/same.md"),
        )

        mock_deps["manifest"].load_current_manifest.return_value = _empty_manifest()

        service.sync(force=True)

        # Discovery should be called with force=True
        mock_deps["discovery"].discover_changes.assert_called_once()
        call_kwargs = mock_deps["discovery"].discover_changes.call_args
        assert call_kwargs[1].get("force") is True

        # File should be processed
        mock_deps["output"].process_file.assert_called_once()

    def test_force_mode_with_dry_run_shows_all_as_modified(self, mock_deps):
        """force=True with dry_run=True should count all files as modified."""
        service = _create_sync_service(mock_deps)

        # Force discovery returns all as modified
        mock_deps["discovery"].discover_changes.return_value = DiscoveryResult(
            new_files=[],
            modified_files=[
                DiscoveredFile(path=Path("/app/raw/a.pdf"), checksum="111", status="modified"),
                DiscoveredFile(path=Path("/app/raw/b.pdf"), checksum="222", status="modified"),
            ],
            unchanged_files=[],
        )

        mock_deps["orphan"].detect_orphans.return_value = []

        result = service.sync(force=True, dry_run=True)

        assert isinstance(result, DryRunResult)
        assert result.modified_count == 2
        assert result.unchanged_count == 0

        # Discovery should be called with force=True
        call_kwargs = mock_deps["discovery"].discover_changes.call_args
        assert call_kwargs[1].get("force") is True
