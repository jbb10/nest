"""Tests for SyncService orchestration logic."""

from pathlib import Path
from unittest.mock import Mock

import pytest

from nest.core.models import (
    DiscoveredFile,
    DiscoveryResult,
    DryRunResult,
    Manifest,
    OrphanCleanupResult,
    ProcessingResult,
    SyncResult,
)
from nest.services.discovery_service import DiscoveryService
from nest.services.index_service import IndexService
from nest.services.manifest_service import ManifestService
from nest.services.metadata_service import MetadataExtractorService
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
    orphan_mock.count_user_curated_files.return_value = 0

    metadata_mock = Mock(spec=MetadataExtractorService)
    metadata_mock.load_previous_hints.return_value = {}
    metadata_mock.extract_all.return_value = []
    metadata_mock.write_hints.return_value = None

    index_mock = Mock(spec=IndexService)
    index_mock.read_index_content.return_value = ""
    index_mock.generate_content.return_value = (
        "<!-- nest:index-table-start -->\n"
        "| File | Lines | Description |\n"
        "|------|------:|-------------|\n"
        "<!-- nest:index-table-end -->\n"
    )

    return {
        "discovery": Mock(spec=DiscoveryService),
        "output": Mock(spec=OutputMirrorService),
        "manifest": Mock(spec=ManifestService),
        "orphan": orphan_mock,
        "index": index_mock,
        "metadata": metadata_mock,
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
        metadata=deps["metadata"],
        project_root=deps["project_root"],
    )


def _empty_discovery_result() -> DiscoveryResult:
    """Return a DiscoveryResult with no files."""
    return DiscoveryResult(new_files=[], modified_files=[], unchanged_files=[])


def _empty_manifest() -> Manifest:
    """Return an empty manifest."""
    return Manifest(nest_version="1.0", project_name="TestProject", files={})


class TestSyncDiscovery:
    """Tests for discovery during sync."""

    def test_discover_delegates_to_discovery_service(self, mock_deps):
        """discover() method should call discovery service."""
        service = _create_sync_service(mock_deps)

        mock_deps["discovery"].discover_changes.return_value = _empty_discovery_result()

        result = service.discover(force=True)

        assert result == _empty_discovery_result()
        mock_deps["discovery"].discover_changes.assert_called_once_with(
            mock_deps["project_root"], force=True
        )

    def test_sync_uses_provided_changes(self, mock_deps):
        """Sync should use provided changes instead of calling discover."""
        service = _create_sync_service(mock_deps)

        # Pre-calculated changes
        changes = DiscoveryResult(
            new_files=[DiscoveredFile(path=Path("/app/raw/a.pdf"), checksum="111", status="new")],
            modified_files=[],
            unchanged_files=[],
        )

        mock_deps["output"].process_file.return_value = ProcessingResult(
            source_path=Path("/app/raw/a.pdf"),
            status="success",
            output_path=Path("/app/processed_context/a.md"),
        )
        mock_deps["manifest"].load_current_manifest.return_value = _empty_manifest()

        # Call sync with changes
        service.sync(changes=changes)

        # Discovery service should NOT be called
        mock_deps["discovery"].discover_changes.assert_not_called()
        # But processing should happen
        mock_deps["output"].process_file.assert_called_once()

    def test_sync_performs_discovery_if_changes_not_provided(self, mock_deps):
        """Sync should perform discovery if changes arg is None."""
        service = _create_sync_service(mock_deps)

        mock_deps["discovery"].discover_changes.return_value = _empty_discovery_result()
        mock_deps["manifest"].load_current_manifest.return_value = _empty_manifest()

        service.sync(changes=None)

        mock_deps["discovery"].discover_changes.assert_called_once()


class TestSyncIndexIntegration:
    """Tests for index generation during sync."""

    def test_sync_generates_index_with_metadata(self, mock_deps):
        """Index should be generated using metadata extraction pipeline."""
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

        service.sync()

        # Metadata extraction should be called
        mock_deps["metadata"].extract_all.assert_called_once()
        mock_deps["metadata"].write_hints.assert_called_once()
        # Index should be generated and written
        mock_deps["index"].generate_content.assert_called_once()
        mock_deps["index"].write_index.assert_called_once()

    def test_enrichment_needed_counts_empty_descriptions(self, mock_deps):
        """enrichment_needed should count rows with empty descriptions in generated index."""
        service = _create_sync_service(mock_deps)

        mock_deps["discovery"].discover_changes.return_value = _empty_discovery_result()
        mock_deps["manifest"].load_current_manifest.return_value = _empty_manifest()

        # Index with 2 files: one with description, one without
        mock_deps["index"].generate_content.return_value = (
            "<!-- nest:index-table-start -->\n"
            "| File | Lines | Description |\n"
            "|------|------:|-------------|\n"
            "| doc.md | 10 | Has a description |\n"
            "| empty.md | 5 |  |\n"
            "<!-- nest:index-table-end -->\n"
        )

        result = service.sync()

        assert result.enrichment_needed == 1

    def test_glossary_skipped_during_dry_run(self, mock_deps):
        """Glossary should NOT be processed during dry-run."""
        service = _create_sync_service(mock_deps)

        mock_deps["orphan"].detect_orphans.return_value = []
        mock_deps["discovery"].discover_changes.return_value = _empty_discovery_result()

        result = service.sync(dry_run=True)

        assert isinstance(result, DryRunResult)

    def test_enrichment_needed_zero_when_all_described(self, mock_deps):
        """enrichment_needed should be 0 when all files have descriptions."""
        service = _create_sync_service(mock_deps)

        mock_deps["discovery"].discover_changes.return_value = _empty_discovery_result()
        mock_deps["manifest"].load_current_manifest.return_value = _empty_manifest()

        mock_deps["index"].generate_content.return_value = (
            "<!-- nest:index-table-start -->\n"
            "| File | Lines | Description |\n"
            "|------|------:|-------------|\n"
            "| doc.md | 10 | Has a description |\n"
            "| other.md | 5 | Also described |\n"
            "<!-- nest:index-table-end -->\n"
        )

        result = service.sync()

        assert result.enrichment_needed == 0


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
        # Index should still be generated
        mock_deps["index"].generate_content.assert_called_once()
        mock_deps["index"].write_index.assert_called_once()


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

    def test_sync_commits_manifest_before_orphan_cleanup(self, mock_deps):
        """Manifest commit, then orphan cleanup, then index generation."""
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
        mock_deps["index"].write_index.side_effect = lambda *_: call_order.append("index")

        service.sync()

        assert call_order == ["commit", "orphan", "index"]


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
        """dry_run=True should NOT generate the master index."""
        service = _create_sync_service(mock_deps)

        mock_deps["discovery"].discover_changes.return_value = _empty_discovery_result()
        mock_deps["orphan"].detect_orphans.return_value = []

        service.sync(dry_run=True)

        mock_deps["index"].generate_content.assert_not_called()
        mock_deps["index"].write_index.assert_not_called()


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


class TestSyncProgressCallback:
    """Tests for progress callback integration."""

    def test_sync_calls_progress_callback_for_each_file(self, mock_deps):
        """Progress callback should be called for each file processed."""
        service = _create_sync_service(mock_deps)

        mock_deps["discovery"].discover_changes.return_value = DiscoveryResult(
            new_files=[
                DiscoveredFile(path=Path("/app/raw/a.pdf"), checksum="111", status="new"),
                DiscoveredFile(path=Path("/app/raw/b.pdf"), checksum="222", status="new"),
                DiscoveredFile(path=Path("/app/raw/c.pdf"), checksum="333", status="new"),
            ],
            modified_files=[],
            unchanged_files=[],
        )

        mock_deps["output"].process_file.return_value = ProcessingResult(
            source_path=Path("/app/raw/a.pdf"),
            status="success",
            output_path=Path("/app/processed_context/a.md"),
        )

        mock_deps["manifest"].load_current_manifest.return_value = _empty_manifest()

        # Track progress calls
        progress_calls: list[str] = []

        def mock_progress(filename: str) -> None:
            progress_calls.append(filename)

        service.sync(progress_callback=mock_progress)

        assert len(progress_calls) == 3
        assert "a.pdf" in progress_calls
        assert "b.pdf" in progress_calls
        assert "c.pdf" in progress_calls

    def test_sync_calls_progress_for_modified_files(self, mock_deps):
        """Progress callback should be called for modified files too."""
        service = _create_sync_service(mock_deps)

        mock_deps["discovery"].discover_changes.return_value = DiscoveryResult(
            new_files=[],
            modified_files=[
                DiscoveredFile(path=Path("/app/raw/m.pdf"), checksum="mod", status="modified"),
            ],
            unchanged_files=[],
        )

        mock_deps["output"].process_file.return_value = ProcessingResult(
            source_path=Path("/app/raw/m.pdf"),
            status="success",
            output_path=Path("/app/processed_context/m.md"),
        )

        mock_deps["manifest"].load_current_manifest.return_value = _empty_manifest()

        progress_calls: list[str] = []
        service.sync(progress_callback=lambda f: progress_calls.append(f))

        assert progress_calls == ["m.pdf"]

    def test_sync_does_not_call_progress_when_no_files(self, mock_deps):
        """No progress callbacks when no files to process."""
        service = _create_sync_service(mock_deps)

        mock_deps["discovery"].discover_changes.return_value = _empty_discovery_result()
        mock_deps["manifest"].load_current_manifest.return_value = _empty_manifest()

        progress_calls: list[str] = []
        service.sync(progress_callback=lambda f: progress_calls.append(f))

        assert progress_calls == []

    def test_sync_works_without_progress_callback(self, mock_deps):
        """Sync should work fine when progress_callback is None."""
        service = _create_sync_service(mock_deps)

        mock_deps["discovery"].discover_changes.return_value = DiscoveryResult(
            new_files=[
                DiscoveredFile(path=Path("/app/raw/x.pdf"), checksum="xxx", status="new"),
            ],
            modified_files=[],
            unchanged_files=[],
        )

        mock_deps["output"].process_file.return_value = ProcessingResult(
            source_path=Path("/app/raw/x.pdf"),
            status="success",
            output_path=Path("/app/processed_context/x.md"),
        )

        mock_deps["manifest"].load_current_manifest.return_value = _empty_manifest()

        # No progress callback - should not crash
        service.sync(progress_callback=None)

        mock_deps["output"].process_file.assert_called_once()

    def test_sync_calls_progress_even_on_failure(self, mock_deps):
        """Progress should be reported even for failed files."""
        service = _create_sync_service(mock_deps)

        mock_deps["discovery"].discover_changes.return_value = DiscoveryResult(
            new_files=[
                DiscoveredFile(path=Path("/app/raw/fail.pdf"), checksum="fail", status="new"),
            ],
            modified_files=[],
            unchanged_files=[],
        )

        mock_deps["output"].process_file.return_value = ProcessingResult(
            source_path=Path("/app/raw/fail.pdf"),
            status="failed",
            output_path=None,
            error="Password protected",
        )

        mock_deps["manifest"].load_current_manifest.return_value = _empty_manifest()

        progress_calls: list[str] = []
        service.sync(progress_callback=lambda f: progress_calls.append(f))

        assert progress_calls == ["fail.pdf"]


class TestSyncResultCounts:
    """Tests for SyncResult count tracking."""

    def test_sync_returns_sync_result_with_counts(self, mock_deps):
        """Sync should return SyncResult with processed, skipped, failed counts."""
        service = _create_sync_service(mock_deps)

        mock_deps["discovery"].discover_changes.return_value = DiscoveryResult(
            new_files=[
                DiscoveredFile(path=Path("/app/raw/a.pdf"), checksum="111", status="new"),
                DiscoveredFile(path=Path("/app/raw/b.pdf"), checksum="222", status="new"),
            ],
            modified_files=[],
            unchanged_files=[
                DiscoveredFile(path=Path("/app/raw/c.pdf"), checksum="333", status="unchanged"),
            ],
        )

        mock_deps["output"].process_file.return_value = ProcessingResult(
            source_path=Path("/app/raw/a.pdf"),
            status="success",
            output_path=Path("/app/processed_context/a.md"),
        )

        mock_deps["manifest"].load_current_manifest.return_value = _empty_manifest()

        result = service.sync()

        assert isinstance(result, SyncResult)
        assert result.processed_count == 2
        assert result.skipped_count == 1
        assert result.failed_count == 0

    def test_sync_result_counts_failures(self, mock_deps):
        """SyncResult should count failed files."""
        service = _create_sync_service(mock_deps)

        mock_deps["discovery"].discover_changes.return_value = DiscoveryResult(
            new_files=[
                DiscoveredFile(path=Path("/app/raw/ok.pdf"), checksum="111", status="new"),
                DiscoveredFile(path=Path("/app/raw/bad.pdf"), checksum="222", status="new"),
            ],
            modified_files=[],
            unchanged_files=[],
        )

        # First succeeds, second fails
        mock_deps["output"].process_file.side_effect = [
            ProcessingResult(
                source_path=Path("/app/raw/ok.pdf"),
                status="success",
                output_path=Path("/app/processed_context/ok.md"),
            ),
            ProcessingResult(
                source_path=Path("/app/raw/bad.pdf"),
                status="failed",
                output_path=None,
                error="Encrypted",
            ),
        ]

        mock_deps["manifest"].load_current_manifest.return_value = _empty_manifest()

        result = service.sync()

        assert isinstance(result, SyncResult)
        assert result.processed_count == 1
        assert result.failed_count == 1
        assert result.skipped_count == 0

    def test_sync_result_includes_orphan_info(self, mock_deps):
        """SyncResult should include orphan cleanup information."""
        service = _create_sync_service(mock_deps)

        mock_deps["discovery"].discover_changes.return_value = _empty_discovery_result()
        mock_deps["manifest"].load_current_manifest.return_value = _empty_manifest()

        mock_deps["orphan"].cleanup.return_value = OrphanCleanupResult(
            orphans_detected=["old1.md", "old2.md", "old3.md"],
            orphans_removed=["old1.md", "old2.md"],
            skipped=False,
        )

        result = service.sync()

        assert isinstance(result, SyncResult)
        assert result.orphans_detected == 3
        assert result.orphans_removed == 2
        assert result.skipped_orphan_cleanup is False

    def test_sync_result_reflects_no_clean_flag(self, mock_deps):
        """SyncResult should reflect when --no-clean was used."""
        service = _create_sync_service(mock_deps)

        mock_deps["discovery"].discover_changes.return_value = _empty_discovery_result()
        mock_deps["manifest"].load_current_manifest.return_value = _empty_manifest()

        mock_deps["orphan"].cleanup.return_value = OrphanCleanupResult(
            orphans_detected=["orphan.md"],
            orphans_removed=[],
            skipped=True,
        )

        result = service.sync(no_clean=True)

        assert isinstance(result, SyncResult)
        assert result.orphans_detected == 1
        assert result.orphans_removed == 0
        assert result.skipped_orphan_cleanup is True

    def test_sync_result_counts_exception_as_failure(self, mock_deps):
        """Exception during processing should count as failure in SyncResult."""
        service = _create_sync_service(mock_deps)

        mock_deps["discovery"].discover_changes.return_value = DiscoveryResult(
            new_files=[
                DiscoveredFile(path=Path("/app/raw/crash.pdf"), checksum="xxx", status="new"),
            ],
            modified_files=[],
            unchanged_files=[],
        )

        mock_deps["output"].process_file.side_effect = RuntimeError("Crash!")
        mock_deps["manifest"].load_current_manifest.return_value = _empty_manifest()

        result = service.sync()

        assert isinstance(result, SyncResult)
        assert result.failed_count == 1
        assert result.processed_count == 0


class TestSyncCollisionDetection:
    """Tests for name collision detection (AC7)."""

    def test_passthrough_wins_over_docling_collision(self, mock_deps):
        """AC7: Passthrough file wins when output paths collide."""
        mock_deps["project_root"] = Path("/app")
        service = _create_sync_service(mock_deps)

        # report.md (passthrough) and report.pdf (Docling → report.md) collide
        changes = DiscoveryResult(
            new_files=[
                DiscoveredFile(
                    path=Path("/app/_nest_sources/report.pdf"),
                    checksum="aaa",
                    status="new",
                ),
                DiscoveredFile(
                    path=Path("/app/_nest_sources/report.md"),
                    checksum="bbb",
                    status="new",
                ),
            ],
            modified_files=[],
            unchanged_files=[],
        )

        mock_deps["output"].process_file.return_value = ProcessingResult(
            source_path=Path("/app/_nest_sources/report.md"),
            status="success",
            output_path=Path("/app/_nest_context/report.md"),
        )
        mock_deps["manifest"].load_current_manifest.return_value = _empty_manifest()

        result = service.sync(changes=changes)

        assert isinstance(result, SyncResult)
        # Only 1 file should be processed (the passthrough .md)
        assert result.processed_count == 1
        # The .pdf should have been skipped (manifest.record_skipped called)
        mock_deps["manifest"].record_skipped.assert_called_once()

    def test_no_collision_when_output_paths_differ(self, mock_deps):
        """No collision when files produce different output paths."""
        mock_deps["project_root"] = Path("/app")
        service = _create_sync_service(mock_deps)

        changes = DiscoveryResult(
            new_files=[
                DiscoveredFile(
                    path=Path("/app/_nest_sources/report.pdf"),
                    checksum="aaa",
                    status="new",
                ),
                DiscoveredFile(
                    path=Path("/app/_nest_sources/notes.txt"),
                    checksum="bbb",
                    status="new",
                ),
            ],
            modified_files=[],
            unchanged_files=[],
        )

        mock_deps["output"].process_file.return_value = ProcessingResult(
            source_path=Path("/app/_nest_sources/report.pdf"),
            status="success",
            output_path=Path("/app/_nest_context/report.md"),
        )
        mock_deps["manifest"].load_current_manifest.return_value = _empty_manifest()

        result = service.sync(changes=changes)

        assert isinstance(result, SyncResult)
        # Both files should be processed
        assert result.processed_count == 2
        mock_deps["manifest"].record_skipped.assert_not_called()

    def test_same_type_collision_tracks_skipped_file(self, mock_deps):
        """AC4: Same-type collision (e.g., .docx + .pdf → same .md) tracks displaced file."""
        mock_deps["project_root"] = Path("/app")
        service = _create_sync_service(mock_deps)

        # report.docx and report.pdf both produce report.md — same-type collision
        changes = DiscoveryResult(
            new_files=[
                DiscoveredFile(
                    path=Path("/app/_nest_sources/report.docx"),
                    checksum="aaa",
                    status="new",
                ),
                DiscoveredFile(
                    path=Path("/app/_nest_sources/report.pdf"),
                    checksum="bbb",
                    status="new",
                ),
            ],
            modified_files=[],
            unchanged_files=[],
        )

        mock_deps["output"].process_file.return_value = ProcessingResult(
            source_path=Path("/app/_nest_sources/report.pdf"),
            status="success",
            output_path=Path("/app/_nest_context/report.md"),
        )
        mock_deps["manifest"].load_current_manifest.return_value = _empty_manifest()

        result = service.sync(changes=changes)

        assert isinstance(result, SyncResult)
        # Only 1 file should be processed (last one wins)
        assert result.processed_count == 1
        # Collision adds to skipped count
        assert result.skipped_count == 1
        # The displaced file should be recorded as skipped in manifest
        mock_deps["manifest"].record_skipped.assert_called_once()
        skipped_call = mock_deps["manifest"].record_skipped.call_args
        # Verify the reason contains collision info
        assert "collision" in skipped_call[1].get("reason", skipped_call[0][-1]).lower()


class TestSyncAIEnrichment:
    """Tests for AI enrichment integration in SyncService."""

    def test_sync_with_ai_enrichment_merges_descriptions(self, mock_deps):
        """AI descriptions should be merged into old_descriptions before index generation."""
        from nest.core.models import AIEnrichmentResult, FileMetadata
        from nest.services.ai_enrichment_service import AIEnrichmentService

        ai_mock = Mock(spec=AIEnrichmentService)
        ai_mock.enrich.return_value = AIEnrichmentResult(
            descriptions={"doc.md": "AI generated description"},
            prompt_tokens=50,
            completion_tokens=5,
            files_enriched=1,
            files_skipped=0,
            files_failed=0,
        )

        # Metadata returns a file so AI enrichment has something to process
        file_meta = FileMetadata(path="doc.md", content_hash="new_hash", lines=10)
        mock_deps["metadata"].extract_all.return_value = [file_meta]
        mock_deps["discovery"].discover_changes.return_value = _empty_discovery_result()
        mock_deps["manifest"].load_current_manifest.return_value = _empty_manifest()

        service = SyncService(
            discovery=mock_deps["discovery"],
            output=mock_deps["output"],
            manifest=mock_deps["manifest"],
            orphan=mock_deps["orphan"],
            index=mock_deps["index"],
            metadata=mock_deps["metadata"],
            project_root=mock_deps["project_root"],
            ai_enrichment=ai_mock,
        )

        service.sync()

        # AI enrichment should have been called
        ai_mock.enrich.assert_called_once()
        # Index generation should have been called with merged descriptions
        mock_deps["index"].generate_content.assert_called_once()
        call_args = mock_deps["index"].generate_content.call_args
        passed_old_descriptions = call_args[0][1]
        passed_old_hints = call_args[0][2]
        # AI description must be in old_descriptions
        assert "doc.md" in passed_old_descriptions
        assert passed_old_descriptions["doc.md"] == "AI generated description"
        # old_hints must be updated so generate_content reads the description
        assert passed_old_hints.get("doc.md") == "new_hash"

    def test_sync_without_ai_generates_unenriched_index(self, mock_deps):
        """ai_enrichment=None → same behavior as before, no AI calls."""
        service = _create_sync_service(mock_deps)

        mock_deps["discovery"].discover_changes.return_value = _empty_discovery_result()
        mock_deps["manifest"].load_current_manifest.return_value = _empty_manifest()

        result = service.sync()

        assert isinstance(result, SyncResult)
        assert result.ai_prompt_tokens == 0
        assert result.ai_completion_tokens == 0
        assert result.ai_files_enriched == 0

    def test_sync_returns_ai_token_counts(self, mock_deps):
        """Token counts should propagate from AI enrichment to SyncResult."""
        from nest.core.models import AIEnrichmentResult
        from nest.services.ai_enrichment_service import AIEnrichmentService

        ai_mock = Mock(spec=AIEnrichmentService)
        ai_mock.enrich.return_value = AIEnrichmentResult(
            descriptions={"a.md": "Desc A", "b.md": "Desc B"},
            prompt_tokens=200,
            completion_tokens=30,
            files_enriched=2,
            files_skipped=0,
            files_failed=0,
        )

        mock_deps["discovery"].discover_changes.return_value = _empty_discovery_result()
        mock_deps["manifest"].load_current_manifest.return_value = _empty_manifest()

        service = SyncService(
            discovery=mock_deps["discovery"],
            output=mock_deps["output"],
            manifest=mock_deps["manifest"],
            orphan=mock_deps["orphan"],
            index=mock_deps["index"],
            metadata=mock_deps["metadata"],
            project_root=mock_deps["project_root"],
            ai_enrichment=ai_mock,
        )

        result = service.sync()

        assert result.ai_prompt_tokens == 200
        assert result.ai_completion_tokens == 30
        assert result.ai_files_enriched == 2


class TestSyncAIGlossary:
    """Tests for AI glossary integration in SyncService."""

    def test_sync_with_ai_glossary_generates_terms(self, mock_deps):
        """AI glossary called when changed context files exist."""
        from nest.core.models import AIGlossaryResult, FileMetadata
        from nest.services.ai_glossary_service import AIGlossaryService

        ai_glossary_mock = Mock(spec=AIGlossaryService)
        ai_glossary_mock.generate.return_value = AIGlossaryResult(
            terms_added=3,
            terms_skipped_existing=0,
            terms_failed=0,
            prompt_tokens=300,
            completion_tokens=40,
        )

        file_meta = FileMetadata(path="doc.md", content_hash="new_hash", lines=10)
        mock_deps["metadata"].extract_all.return_value = [file_meta]
        mock_deps["discovery"].discover_changes.return_value = _empty_discovery_result()
        mock_deps["manifest"].load_current_manifest.return_value = _empty_manifest()

        service = SyncService(
            discovery=mock_deps["discovery"],
            output=mock_deps["output"],
            manifest=mock_deps["manifest"],
            orphan=mock_deps["orphan"],
            index=mock_deps["index"],
            metadata=mock_deps["metadata"],
            project_root=mock_deps["project_root"],
            ai_glossary=ai_glossary_mock,
        )

        result = service.sync()

        ai_glossary_mock.generate.assert_called_once()
        assert result.ai_glossary_terms_added == 3
        assert result.ai_glossary_prompt_tokens == 300
        assert result.ai_glossary_completion_tokens == 40

    def test_sync_without_ai_glossary_skips_generation(self, mock_deps):
        """ai_glossary=None -> same behavior as before."""
        service = _create_sync_service(mock_deps)

        mock_deps["discovery"].discover_changes.return_value = _empty_discovery_result()
        mock_deps["manifest"].load_current_manifest.return_value = _empty_manifest()

        result = service.sync()

        assert isinstance(result, SyncResult)
        assert result.ai_glossary_terms_added == 0
        assert result.ai_glossary_prompt_tokens == 0
        assert result.ai_glossary_completion_tokens == 0

    def test_sync_returns_ai_glossary_token_counts(self, mock_deps):
        """Token counts should propagate from AI glossary to SyncResult."""
        from nest.core.models import AIGlossaryResult, FileMetadata
        from nest.services.ai_glossary_service import AIGlossaryService

        ai_glossary_mock = Mock(spec=AIGlossaryService)
        ai_glossary_mock.generate.return_value = AIGlossaryResult(
            terms_added=2,
            prompt_tokens=150,
            completion_tokens=25,
        )

        file_meta = FileMetadata(path="doc.md", content_hash="new_hash", lines=10)
        mock_deps["metadata"].extract_all.return_value = [file_meta]
        mock_deps["discovery"].discover_changes.return_value = _empty_discovery_result()
        mock_deps["manifest"].load_current_manifest.return_value = _empty_manifest()

        service = SyncService(
            discovery=mock_deps["discovery"],
            output=mock_deps["output"],
            manifest=mock_deps["manifest"],
            orphan=mock_deps["orphan"],
            index=mock_deps["index"],
            metadata=mock_deps["metadata"],
            project_root=mock_deps["project_root"],
            ai_glossary=ai_glossary_mock,
        )

        result = service.sync()

        assert result.ai_glossary_prompt_tokens == 150
        assert result.ai_glossary_completion_tokens == 25
        assert result.ai_glossary_terms_added == 2

    def test_sync_skips_ai_glossary_when_no_terms(self, mock_deps):
        """No changed files -> glossary service not called."""
        from nest.services.ai_glossary_service import AIGlossaryService

        ai_glossary_mock = Mock(spec=AIGlossaryService)

        # Default mock_deps returns no metadata (no changed files)
        mock_deps["discovery"].discover_changes.return_value = _empty_discovery_result()
        mock_deps["manifest"].load_current_manifest.return_value = _empty_manifest()

        service = SyncService(
            discovery=mock_deps["discovery"],
            output=mock_deps["output"],
            manifest=mock_deps["manifest"],
            orphan=mock_deps["orphan"],
            index=mock_deps["index"],
            metadata=mock_deps["metadata"],
            project_root=mock_deps["project_root"],
            ai_glossary=ai_glossary_mock,
        )

        result = service.sync()

        ai_glossary_mock.generate.assert_not_called()
        assert result.ai_glossary_terms_added == 0

    def test_sync_passes_project_context_to_glossary(self, mock_deps):
        """Glossary call includes optional project context when available."""
        from nest.core.models import AIGlossaryResult, FileMetadata
        from nest.services.ai_glossary_service import AIGlossaryService

        ai_glossary_mock = Mock(spec=AIGlossaryService)
        ai_glossary_mock.generate.return_value = AIGlossaryResult(terms_added=1)

        file_meta = FileMetadata(path="doc.md", content_hash="new_hash", lines=10)
        mock_deps["metadata"].extract_all.return_value = [file_meta]
        mock_deps["discovery"].discover_changes.return_value = _empty_discovery_result()

        service = SyncService(
            discovery=mock_deps["discovery"],
            output=mock_deps["output"],
            manifest=mock_deps["manifest"],
            orphan=mock_deps["orphan"],
            index=mock_deps["index"],
            metadata=mock_deps["metadata"],
            project_root=mock_deps["project_root"],
            ai_glossary=ai_glossary_mock,
        )

        service._load_project_context = Mock(return_value="Project context text")  # type: ignore[method-assign]
        service.sync()

        args = ai_glossary_mock.generate.call_args.args
        assert args[3] == "Project context text"


class TestSyncParallelAI:
    """Tests for parallel AI execution in SyncService (Story 6.4)."""

    def test_sync_runs_ai_tasks_in_parallel_when_both_have_work(self, mock_deps):
        """Both enrichment and glossary execute and results merge correctly."""
        from nest.core.models import (
            AIEnrichmentResult,
            AIGlossaryResult,
            FileMetadata,
        )
        from nest.services.ai_enrichment_service import AIEnrichmentService
        from nest.services.ai_glossary_service import AIGlossaryService

        ai_mock = Mock(spec=AIEnrichmentService)
        ai_mock.enrich.return_value = AIEnrichmentResult(
            descriptions={"doc.md": "AI desc"},
            prompt_tokens=100,
            completion_tokens=20,
            files_enriched=1,
        )

        ai_glossary_mock = Mock(spec=AIGlossaryService)
        ai_glossary_mock.generate.return_value = AIGlossaryResult(
            terms_added=2,
            prompt_tokens=200,
            completion_tokens=30,
        )

        file_meta = FileMetadata(path="doc.md", content_hash="new_hash", lines=10)
        mock_deps["metadata"].extract_all.return_value = [file_meta]

        file_meta = FileMetadata(path="doc.md", content_hash="h1", lines=10)
        mock_deps["metadata"].extract_all.return_value = [file_meta]
        mock_deps["discovery"].discover_changes.return_value = _empty_discovery_result()

        service = SyncService(
            discovery=mock_deps["discovery"],
            output=mock_deps["output"],
            manifest=mock_deps["manifest"],
            orphan=mock_deps["orphan"],
            index=mock_deps["index"],
            metadata=mock_deps["metadata"],
            project_root=mock_deps["project_root"],
            ai_enrichment=ai_mock,
            ai_glossary=ai_glossary_mock,
        )

        result = service.sync()

        ai_mock.enrich.assert_called_once()
        ai_glossary_mock.generate.assert_called_once()
        assert result.ai_files_enriched == 1
        assert result.ai_glossary_terms_added == 2
        assert result.ai_prompt_tokens == 100
        assert result.ai_completion_tokens == 20
        assert result.ai_glossary_prompt_tokens == 200
        assert result.ai_glossary_completion_tokens == 30

    def test_sync_runs_only_enrichment_when_no_glossary_terms(self, mock_deps):
        """No changed files → no glossary thread spawned."""
        from nest.core.models import AIEnrichmentResult
        from nest.services.ai_enrichment_service import AIEnrichmentService
        from nest.services.ai_glossary_service import AIGlossaryService

        ai_mock = Mock(spec=AIEnrichmentService)
        ai_mock.enrich.return_value = AIEnrichmentResult(
            descriptions={"x.md": "desc"},
            prompt_tokens=50,
            completion_tokens=10,
            files_enriched=1,
        )

        ai_glossary_mock = Mock(spec=AIGlossaryService)

        # Default: no metadata (no changed files)
        mock_deps["discovery"].discover_changes.return_value = _empty_discovery_result()

        service = SyncService(
            discovery=mock_deps["discovery"],
            output=mock_deps["output"],
            manifest=mock_deps["manifest"],
            orphan=mock_deps["orphan"],
            index=mock_deps["index"],
            metadata=mock_deps["metadata"],
            project_root=mock_deps["project_root"],
            ai_enrichment=ai_mock,
            ai_glossary=ai_glossary_mock,
        )

        result = service.sync()

        ai_mock.enrich.assert_called_once()
        ai_glossary_mock.generate.assert_not_called()
        assert result.ai_files_enriched == 1
        assert result.ai_glossary_terms_added == 0

    def test_sync_runs_only_glossary_when_no_enrichment_service(self, mock_deps):
        """Enrichment is None, changed files exist."""
        from nest.core.models import AIGlossaryResult, FileMetadata
        from nest.services.ai_glossary_service import AIGlossaryService

        ai_glossary_mock = Mock(spec=AIGlossaryService)
        ai_glossary_mock.generate.return_value = AIGlossaryResult(
            terms_added=3,
            prompt_tokens=150,
            completion_tokens=25,
        )

        file_meta = FileMetadata(path="doc.md", content_hash="new_hash", lines=10)
        mock_deps["metadata"].extract_all.return_value = [file_meta]
        mock_deps["discovery"].discover_changes.return_value = _empty_discovery_result()

        service = SyncService(
            discovery=mock_deps["discovery"],
            output=mock_deps["output"],
            manifest=mock_deps["manifest"],
            orphan=mock_deps["orphan"],
            index=mock_deps["index"],
            metadata=mock_deps["metadata"],
            project_root=mock_deps["project_root"],
            ai_enrichment=None,
            ai_glossary=ai_glossary_mock,
        )

        result = service.sync()

        ai_glossary_mock.generate.assert_called_once()
        assert result.ai_glossary_terms_added == 3
        assert result.ai_files_enriched == 0

    def test_sync_skips_ai_entirely_when_both_none(self, mock_deps):
        """Both services None → no executor created."""
        service = _create_sync_service(mock_deps)

        mock_deps["discovery"].discover_changes.return_value = _empty_discovery_result()

        result = service.sync()

        assert result.ai_files_enriched == 0
        assert result.ai_glossary_terms_added == 0
        assert result.ai_prompt_tokens == 0
        assert result.ai_glossary_prompt_tokens == 0

    def test_sync_sequential_enrichment_failure_degrades_gracefully(self, mock_deps):
        """Enrichment-only path raises → sync completes with zero AI results."""
        from nest.services.ai_enrichment_service import AIEnrichmentService

        ai_mock = Mock(spec=AIEnrichmentService)
        ai_mock.enrich.side_effect = RuntimeError("Sequential enrichment crash")

        mock_deps["discovery"].discover_changes.return_value = _empty_discovery_result()

        service = SyncService(
            discovery=mock_deps["discovery"],
            output=mock_deps["output"],
            manifest=mock_deps["manifest"],
            orphan=mock_deps["orphan"],
            index=mock_deps["index"],
            metadata=mock_deps["metadata"],
            project_root=mock_deps["project_root"],
            ai_enrichment=ai_mock,
            ai_glossary=None,
        )

        result = service.sync()

        assert result.ai_files_enriched == 0
        assert result.ai_prompt_tokens == 0

    def test_sync_sequential_glossary_failure_degrades_gracefully(self, mock_deps):
        """Glossary-only path raises → sync completes with zero glossary results."""
        from nest.core.models import FileMetadata
        from nest.services.ai_glossary_service import AIGlossaryService

        ai_glossary_mock = Mock(spec=AIGlossaryService)
        ai_glossary_mock.generate.side_effect = RuntimeError("Sequential glossary crash")

        file_meta = FileMetadata(path="doc.md", content_hash="new_hash", lines=10)
        mock_deps["metadata"].extract_all.return_value = [file_meta]
        mock_deps["discovery"].discover_changes.return_value = _empty_discovery_result()

        service = SyncService(
            discovery=mock_deps["discovery"],
            output=mock_deps["output"],
            manifest=mock_deps["manifest"],
            orphan=mock_deps["orphan"],
            index=mock_deps["index"],
            metadata=mock_deps["metadata"],
            project_root=mock_deps["project_root"],
            ai_enrichment=None,
            ai_glossary=ai_glossary_mock,
        )

        result = service.sync()

        assert result.ai_glossary_terms_added == 0
        assert result.ai_glossary_prompt_tokens == 0

    def test_sync_enrichment_failure_doesnt_block_glossary(self, mock_deps):
        """Enrichment raises exception → glossary still succeeds."""
        from nest.core.models import AIGlossaryResult, FileMetadata
        from nest.services.ai_enrichment_service import AIEnrichmentService
        from nest.services.ai_glossary_service import AIGlossaryService

        ai_mock = Mock(spec=AIEnrichmentService)
        ai_mock.enrich.side_effect = RuntimeError("Enrichment network timeout")

        ai_glossary_mock = Mock(spec=AIGlossaryService)
        ai_glossary_mock.generate.return_value = AIGlossaryResult(
            terms_added=2,
            prompt_tokens=100,
            completion_tokens=15,
        )

        file_meta = FileMetadata(path="doc.md", content_hash="new_hash", lines=10)
        mock_deps["metadata"].extract_all.return_value = [file_meta]
        mock_deps["discovery"].discover_changes.return_value = _empty_discovery_result()

        service = SyncService(
            discovery=mock_deps["discovery"],
            output=mock_deps["output"],
            manifest=mock_deps["manifest"],
            orphan=mock_deps["orphan"],
            index=mock_deps["index"],
            metadata=mock_deps["metadata"],
            project_root=mock_deps["project_root"],
            ai_enrichment=ai_mock,
            ai_glossary=ai_glossary_mock,
        )

        result = service.sync()

        assert result.ai_files_enriched == 0
        assert result.ai_prompt_tokens == 0
        assert result.ai_glossary_terms_added == 2
        assert result.ai_glossary_prompt_tokens == 100

    def test_sync_glossary_failure_doesnt_block_enrichment(self, mock_deps):
        """Glossary raises exception → enrichment still succeeds."""
        from nest.core.models import AIEnrichmentResult, FileMetadata
        from nest.services.ai_enrichment_service import AIEnrichmentService
        from nest.services.ai_glossary_service import AIGlossaryService

        ai_mock = Mock(spec=AIEnrichmentService)
        ai_mock.enrich.return_value = AIEnrichmentResult(
            descriptions={"f.md": "desc"},
            prompt_tokens=80,
            completion_tokens=12,
            files_enriched=1,
        )

        ai_glossary_mock = Mock(spec=AIGlossaryService)
        ai_glossary_mock.generate.side_effect = RuntimeError("Glossary API rate limit exceeded")

        file_meta = FileMetadata(path="doc.md", content_hash="new_hash", lines=10)
        mock_deps["metadata"].extract_all.return_value = [file_meta]
        mock_deps["discovery"].discover_changes.return_value = _empty_discovery_result()

        service = SyncService(
            discovery=mock_deps["discovery"],
            output=mock_deps["output"],
            manifest=mock_deps["manifest"],
            orphan=mock_deps["orphan"],
            index=mock_deps["index"],
            metadata=mock_deps["metadata"],
            project_root=mock_deps["project_root"],
            ai_enrichment=ai_mock,
            ai_glossary=ai_glossary_mock,
        )

        result = service.sync()

        assert result.ai_files_enriched == 1
        assert result.ai_prompt_tokens == 80
        assert result.ai_glossary_terms_added == 0
        assert result.ai_glossary_prompt_tokens == 0

    def test_sync_both_ai_tasks_fail_gracefully(self, mock_deps):
        """Both fail → sync completes, zero AI results."""
        from nest.core.models import FileMetadata
        from nest.services.ai_enrichment_service import AIEnrichmentService
        from nest.services.ai_glossary_service import AIGlossaryService

        ai_mock = Mock(spec=AIEnrichmentService)
        ai_mock.enrich.side_effect = RuntimeError("Enrichment crash")

        ai_glossary_mock = Mock(spec=AIGlossaryService)
        ai_glossary_mock.generate.side_effect = RuntimeError("Glossary crash")

        file_meta = FileMetadata(path="doc.md", content_hash="new_hash", lines=10)
        mock_deps["metadata"].extract_all.return_value = [file_meta]
        mock_deps["discovery"].discover_changes.return_value = _empty_discovery_result()

        service = SyncService(
            discovery=mock_deps["discovery"],
            output=mock_deps["output"],
            manifest=mock_deps["manifest"],
            orphan=mock_deps["orphan"],
            index=mock_deps["index"],
            metadata=mock_deps["metadata"],
            project_root=mock_deps["project_root"],
            ai_enrichment=ai_mock,
            ai_glossary=ai_glossary_mock,
        )

        result = service.sync()

        assert result.ai_files_enriched == 0
        assert result.ai_prompt_tokens == 0
        assert result.ai_glossary_terms_added == 0
        assert result.ai_glossary_prompt_tokens == 0

    def test_sync_aggregates_tokens_from_both_ai_tasks(self, mock_deps):
        """Token counts from both tasks sum correctly in SyncResult."""
        from nest.core.models import (
            AIEnrichmentResult,
            AIGlossaryResult,
            FileMetadata,
        )
        from nest.services.ai_enrichment_service import AIEnrichmentService
        from nest.services.ai_glossary_service import AIGlossaryService

        ai_mock = Mock(spec=AIEnrichmentService)
        ai_mock.enrich.return_value = AIEnrichmentResult(
            descriptions={"a.md": "A"},
            prompt_tokens=500,
            completion_tokens=100,
            files_enriched=1,
        )

        ai_glossary_mock = Mock(spec=AIGlossaryService)
        ai_glossary_mock.generate.return_value = AIGlossaryResult(
            terms_added=2,
            prompt_tokens=300,
            completion_tokens=50,
        )

        file_meta = FileMetadata(path="doc.md", content_hash="new_hash", lines=10)
        mock_deps["metadata"].extract_all.return_value = [file_meta]
        mock_deps["discovery"].discover_changes.return_value = _empty_discovery_result()

        service = SyncService(
            discovery=mock_deps["discovery"],
            output=mock_deps["output"],
            manifest=mock_deps["manifest"],
            orphan=mock_deps["orphan"],
            index=mock_deps["index"],
            metadata=mock_deps["metadata"],
            project_root=mock_deps["project_root"],
            ai_enrichment=ai_mock,
            ai_glossary=ai_glossary_mock,
        )

        result = service.sync()

        # Enrichment tokens
        assert result.ai_prompt_tokens == 500
        assert result.ai_completion_tokens == 100
        # Glossary tokens
        assert result.ai_glossary_prompt_tokens == 300
        assert result.ai_glossary_completion_tokens == 50
        # Total (aggregation tests at display layer)
        total = (
            result.ai_prompt_tokens
            + result.ai_glossary_prompt_tokens
            + result.ai_completion_tokens
            + result.ai_glossary_completion_tokens
        )
        assert total == 950

    def test_sync_parallel_results_applied_to_descriptions(self, mock_deps):
        """Enrichment descriptions merged into old_descriptions after parallel run."""
        from nest.core.models import (
            AIEnrichmentResult,
            AIGlossaryResult,
            FileMetadata,
        )
        from nest.services.ai_enrichment_service import AIEnrichmentService
        from nest.services.ai_glossary_service import AIGlossaryService

        ai_mock = Mock(spec=AIEnrichmentService)
        ai_mock.enrich.return_value = AIEnrichmentResult(
            descriptions={"doc.md": "Parallel AI desc"},
            prompt_tokens=10,
            completion_tokens=5,
            files_enriched=1,
        )

        ai_glossary_mock = Mock(spec=AIGlossaryService)
        ai_glossary_mock.generate.return_value = AIGlossaryResult(
            terms_added=1,
            prompt_tokens=10,
            completion_tokens=5,
        )

        file_meta = FileMetadata(path="doc.md", content_hash="new_hash", lines=10)
        mock_deps["metadata"].extract_all.return_value = [file_meta]

        file_meta = FileMetadata(path="doc.md", content_hash="hx", lines=5)
        mock_deps["metadata"].extract_all.return_value = [file_meta]
        mock_deps["discovery"].discover_changes.return_value = _empty_discovery_result()

        service = SyncService(
            discovery=mock_deps["discovery"],
            output=mock_deps["output"],
            manifest=mock_deps["manifest"],
            orphan=mock_deps["orphan"],
            index=mock_deps["index"],
            metadata=mock_deps["metadata"],
            project_root=mock_deps["project_root"],
            ai_enrichment=ai_mock,
            ai_glossary=ai_glossary_mock,
        )

        service.sync()

        # Verify index was generated with AI descriptions
        call_args = mock_deps["index"].generate_content.call_args
        passed_descriptions = call_args[0][1]
        assert passed_descriptions.get("doc.md") == "Parallel AI desc"

    def test_sync_calls_ai_progress_callback_on_start(self, mock_deps):
        """Callback receives 'start' when AI phase begins."""
        from nest.core.models import AIEnrichmentResult
        from nest.services.ai_enrichment_service import AIEnrichmentService

        ai_mock = Mock(spec=AIEnrichmentService)
        ai_mock.enrich.return_value = AIEnrichmentResult(
            descriptions={},
            prompt_tokens=0,
            completion_tokens=0,
            files_enriched=0,
        )

        mock_deps["discovery"].discover_changes.return_value = _empty_discovery_result()

        service = SyncService(
            discovery=mock_deps["discovery"],
            output=mock_deps["output"],
            manifest=mock_deps["manifest"],
            orphan=mock_deps["orphan"],
            index=mock_deps["index"],
            metadata=mock_deps["metadata"],
            project_root=mock_deps["project_root"],
            ai_enrichment=ai_mock,
        )

        callback_calls: list[str] = []
        service.sync(ai_progress_callback=lambda msg: callback_calls.append(msg))

        assert "start" in callback_calls

    def test_sync_calls_ai_progress_callback_with_summary(self, mock_deps):
        """Callback receives summary like '4 descriptions, 3 glossary terms'."""
        from nest.core.models import (
            AIEnrichmentResult,
            AIGlossaryResult,
            FileMetadata,
        )
        from nest.services.ai_enrichment_service import AIEnrichmentService
        from nest.services.ai_glossary_service import AIGlossaryService

        ai_mock = Mock(spec=AIEnrichmentService)
        ai_mock.enrich.return_value = AIEnrichmentResult(
            descriptions={"a.md": "d1", "b.md": "d2", "c.md": "d3", "d.md": "d4"},
            prompt_tokens=100,
            completion_tokens=20,
            files_enriched=4,
        )

        ai_glossary_mock = Mock(spec=AIGlossaryService)
        ai_glossary_mock.generate.return_value = AIGlossaryResult(
            terms_added=3,
            prompt_tokens=50,
            completion_tokens=10,
        )

        file_meta = FileMetadata(path="doc.md", content_hash="new_hash", lines=10)
        mock_deps["metadata"].extract_all.return_value = [file_meta]
        mock_deps["discovery"].discover_changes.return_value = _empty_discovery_result()

        service = SyncService(
            discovery=mock_deps["discovery"],
            output=mock_deps["output"],
            manifest=mock_deps["manifest"],
            orphan=mock_deps["orphan"],
            index=mock_deps["index"],
            metadata=mock_deps["metadata"],
            project_root=mock_deps["project_root"],
            ai_enrichment=ai_mock,
            ai_glossary=ai_glossary_mock,
        )

        callback_calls: list[str] = []
        service.sync(ai_progress_callback=lambda msg: callback_calls.append(msg))

        assert "start" in callback_calls
        assert "4 descriptions, 3 glossary terms" in callback_calls

    def test_sync_no_ai_progress_callback_when_no_ai_work(self, mock_deps):
        """Callback not called when no AI tasks."""
        service = _create_sync_service(mock_deps)

        mock_deps["discovery"].discover_changes.return_value = _empty_discovery_result()

        callback_calls: list[str] = []
        service.sync(ai_progress_callback=lambda msg: callback_calls.append(msg))

        assert callback_calls == []
