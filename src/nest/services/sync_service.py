import logging
from collections.abc import Callable
from pathlib import Path
from typing import Literal

from nest.core.exceptions import ProcessingError
from nest.core.models import DryRunResult, SyncResult
from nest.services.discovery_service import DiscoveryService
from nest.services.index_service import IndexService
from nest.services.manifest_service import ManifestService
from nest.services.orphan_service import OrphanService
from nest.services.output_service import OutputMirrorService
from nest.ui.logger import log_processing_error

logger = logging.getLogger(__name__)

# Type alias for progress callback function
ProgressCallback = Callable[[str], None]


class SyncService:
    """Orchestrator for the document sync process.

    Coordinates discovery, processing, manifest updates, orphan cleanup, and index generation.
    """

    def __init__(
        self,
        discovery: DiscoveryService,
        output: OutputMirrorService,
        manifest: ManifestService,
        orphan: OrphanService,
        index: IndexService,
        project_root: Path,
        error_logger: logging.Logger | logging.LoggerAdapter | None = None,  # type: ignore[type-arg]
    ) -> None:
        """Initialize SyncService.

        Args:
            discovery: Service for file discovery.
            output: Service for document processing and output mirroring.
            manifest: Service for manifest tracking.
            orphan: Service for orphan file cleanup.
            index: Service for master index generation.
            project_root: Root directory of the project.
            error_logger: Logger for writing errors to .nest_errors.log (AC5).
        """
        self._discovery = discovery
        self._output = output
        self._manifest = manifest
        self._orphan = orphan
        self._index = index
        self._project_root = project_root
        self._error_logger = error_logger

    def sync(
        self,
        no_clean: bool = False,
        on_error: Literal["skip", "fail"] = "skip",
        dry_run: bool = False,
        force: bool = False,
        progress_callback: ProgressCallback | None = None,
    ) -> SyncResult | DryRunResult:
        """Execute the sync process.

        Args:
            no_clean: If True, detect but don't remove orphan files.
            on_error: Error handling strategy:
                - "skip" (default): Log error, skip file, continue processing.
                - "fail": Raise exception immediately on first failure.
            dry_run: If True, analyze files but don't process/modify anything.
            force: If True, reprocess all files regardless of checksum.
            progress_callback: Optional callback called with filename after each file.

        Returns:
            SyncResult for normal sync, DryRunResult for dry run.

        Raises:
            ProcessingError: If on_error="fail" and a file fails processing.
        """
        logger.info("Starting sync process...")

        # 1. Discovery
        changes = self._discovery.discover_changes(self._project_root, force=force)

        # Dry run mode - analyze only, no modifications
        if dry_run:
            orphans = self._orphan.detect_orphans()
            return DryRunResult(
                new_count=len(changes.new_files),
                modified_count=len(changes.modified_files),
                unchanged_count=len(changes.unchanged_files),
                orphan_count=len(orphans),
            )

        files_to_process = changes.new_files + changes.modified_files
        skipped_count = len(changes.unchanged_files)
        processed_count = 0
        failed_count = 0

        if files_to_process:
            logger.info("Processing %d files...", len(files_to_process))

        # 2. Processing Loop
        raw_inbox = self._project_root / "raw_inbox"
        output_dir = self._project_root / "processed_context"

        for file_info in files_to_process:
            try:
                result = self._output.process_file(file_info.path, raw_inbox, output_dir)

                # Report progress after processing each file
                if progress_callback is not None:
                    progress_callback(file_info.path.name)

                if result.status == "success":
                    if result.output_path is None:
                        # Defensive check - should not happen for success status
                        logger.error(
                            "Processing succeeded but output_path is None: %s",
                            file_info.path,
                        )
                        self._manifest.record_failure(
                            file_info.path,
                            file_info.checksum,
                            "Internal error: output_path missing",
                        )
                        failed_count += 1
                    else:
                        self._manifest.record_success(
                            file_info.path,
                            file_info.checksum,
                            result.output_path,
                        )
                        processed_count += 1
                elif result.status == "failed":
                    error_msg = result.error or "Unknown error"
                    self._manifest.record_failure(
                        file_info.path,
                        file_info.checksum,
                        error_msg,
                    )
                    failed_count += 1
                    # Log to .nest_errors.log (AC5)
                    if self._error_logger:
                        log_processing_error(self._error_logger, file_info.path, error_msg)
                    if on_error == "fail":
                        raise ProcessingError(
                            f"Processing failed for {file_info.path.name}: {error_msg}",
                            source_path=file_info.path,
                        )
                else:
                    self._manifest.record_failure(
                        file_info.path,
                        file_info.checksum,
                        result.error or "Unknown error",
                    )
                    failed_count += 1

            except ProcessingError:
                # Re-raise ProcessingError (from fail mode) without catching
                raise
            except Exception as e:
                logger.exception("Unexpected error processing %s", file_info.path)
                error_msg = str(e)
                self._manifest.record_failure(file_info.path, file_info.checksum, error_msg)
                failed_count += 1
                # Log to .nest_errors.log (AC5)
                if self._error_logger:
                    log_processing_error(self._error_logger, file_info.path, error_msg)
                if on_error == "fail":
                    raise

        # 3. Orphan Cleanup (after processing, before manifest commit)
        orphan_result = self._orphan.cleanup(no_clean=no_clean)

        # 4. Commit Manifest (includes any orphan removals from step 3)
        self._manifest.commit()

        # 5. Update Index
        current_manifest = self._manifest.load_current_manifest()
        success_files: list[str] = []
        for entry in current_manifest.files.values():
            if entry.status == "success":
                success_files.append(entry.output)

        # Use project directory name as project name
        project_name = self._project_root.name

        self._index.update_index(success_files, project_name)
        logger.info("Master index updated.")

        return SyncResult(
            processed_count=processed_count,
            skipped_count=skipped_count,
            failed_count=failed_count,
            orphans_removed=len(orphan_result.orphans_removed),
            orphans_detected=len(orphan_result.orphans_detected),
            skipped_orphan_cleanup=orphan_result.skipped,
        )
