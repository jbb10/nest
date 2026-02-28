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
from nest.services.glossary_hints_service import GlossaryHintsService
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

    from nest.core.models import GlossaryHints

    glossary_mock = Mock(spec=GlossaryHintsService)
    glossary_mock.load_previous_hints.return_value = None
    glossary_mock.extract_all.return_value = GlossaryHints(terms=[])
    glossary_mock.merge_with_previous.return_value = GlossaryHints(terms=[])
    glossary_mock.write_hints.return_value = None

    return {
        "discovery": Mock(spec=DiscoveryService),
        "output": Mock(spec=OutputMirrorService),
        "manifest": Mock(spec=ManifestService),
        "orphan": orphan_mock,
        "index": index_mock,
        "metadata": metadata_mock,
        "glossary": glossary_mock,
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
        glossary=deps["glossary"],
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

    def test_glossary_terms_discovered_in_sync_result(self, mock_deps):
        """glossary_terms_discovered should reflect merged glossary term count."""
        from nest.core.models import CandidateTerm, GlossaryHints

        service = _create_sync_service(mock_deps)

        mock_deps["discovery"].discover_changes.return_value = _empty_discovery_result()
        mock_deps["manifest"].load_current_manifest.return_value = _empty_manifest()

        mock_deps["glossary"].merge_with_previous.return_value = GlossaryHints(
            terms=[
                CandidateTerm(
                    term="PDC",
                    category="abbreviation",
                    occurrences=5,
                    source_files=["doc.md"],
                    context_snippets=["The PDC board"],
                ),
                CandidateTerm(
                    term="SME",
                    category="abbreviation",
                    occurrences=3,
                    source_files=["doc.md"],
                    context_snippets=["SME review"],
                ),
            ]
        )

        result = service.sync()

        assert result.glossary_terms_discovered == 2

    def test_glossary_service_called_during_sync(self, mock_deps):
        """GlossaryHintsService should be called during normal sync."""
        service = _create_sync_service(mock_deps)

        mock_deps["discovery"].discover_changes.return_value = _empty_discovery_result()
        mock_deps["manifest"].load_current_manifest.return_value = _empty_manifest()

        service.sync()

        mock_deps["glossary"].load_previous_hints.assert_called_once()
        mock_deps["glossary"].extract_all.assert_called_once()
        mock_deps["glossary"].merge_with_previous.assert_called_once()
        mock_deps["glossary"].write_hints.assert_called_once()

    def test_glossary_skipped_during_dry_run(self, mock_deps):
        """Glossary hints should NOT be processed during dry-run."""
        service = _create_sync_service(mock_deps)

        mock_deps["orphan"].detect_orphans.return_value = []
        mock_deps["discovery"].discover_changes.return_value = _empty_discovery_result()

        service.sync(dry_run=True)

        mock_deps["glossary"].load_previous_hints.assert_not_called()
        mock_deps["glossary"].extract_all.assert_not_called()
        mock_deps["glossary"].write_hints.assert_not_called()

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
