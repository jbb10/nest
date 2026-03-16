from __future__ import annotations

import logging
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from nest.core.exceptions import ProcessingError
from nest.core.models import DiscoveredFile, DiscoveryResult, DryRunResult, SyncResult
from nest.core.paths import (
    CONTEXT_DIR,
    GLOSSARY_FILE,
    INDEX_HINTS_FILE,
    NEST_META_DIR,
    SOURCES_DIR,
    is_passthrough_extension,
)
from nest.services.discovery_service import DiscoveryService
from nest.services.index_service import IndexService, parse_index_descriptions
from nest.services.manifest_service import ManifestService
from nest.services.metadata_service import MetadataExtractorService
from nest.services.orphan_service import OrphanService
from nest.services.output_service import OutputMirrorService
from nest.ui.logger import log_processing_error

if TYPE_CHECKING:
    from nest.core.models import AIEnrichmentResult, AIGlossaryResult
    from nest.services.ai_enrichment_service import AIEnrichmentService
    from nest.services.ai_glossary_service import AIGlossaryService

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
        metadata: MetadataExtractorService,
        project_root: Path,
        error_logger: logging.Logger | logging.LoggerAdapter[logging.Logger] | None = None,
        ai_enrichment: AIEnrichmentService | None = None,
        ai_glossary: AIGlossaryService | None = None,
    ) -> None:
        """Initialize SyncService.

        Args:
            discovery: Service for file discovery.
            output: Service for document processing and output mirroring.
            manifest: Service for manifest tracking.
            orphan: Service for orphan file cleanup.
            index: Service for master index generation.
            metadata: Service for metadata extraction and hints.
            project_root: Root directory of the project.
            error_logger: Logger for writing errors to .nest/errors.log (AC5).
            ai_enrichment: Optional AI enrichment service for generating descriptions.
            ai_glossary: Optional AI glossary service for generating glossary definitions.
        """
        self._discovery = discovery
        self._output = output
        self._manifest = manifest
        self._orphan = orphan
        self._index = index
        self._metadata = metadata
        self._project_root = project_root
        self._error_logger = error_logger
        self._ai_enrichment = ai_enrichment
        self._ai_glossary = ai_glossary

    def discover(self, force: bool = False) -> DiscoveryResult:
        """Run file discovery.

        Args:
            force: If True, reprocess all files regardless of checksum.

        Returns:
            DiscoveryResult containing new, modified, and unchanged files.
        """
        return self._discovery.discover_changes(self._project_root, force=force)

    def sync(
        self,
        no_clean: bool = False,
        on_error: Literal["skip", "fail"] = "skip",
        dry_run: bool = False,
        force: bool = False,
        progress_callback: ProgressCallback | None = None,
        ai_progress_callback: Callable[[str], None] | None = None,
        changes: DiscoveryResult | None = None,
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
            ai_progress_callback: Optional callback for AI phase progress. Receives
                ``"start"`` when the AI phase begins and a summary string
                (e.g., ``"4 descriptions, 3 glossary terms"``) when it completes.
            changes: Optional pre-calculated discovery result. If None, discovery is performed.

        Returns:
            SyncResult for normal sync, DryRunResult for dry run.

        Raises:
            ProcessingError: If on_error="fail" and a file fails processing.
        """
        logger.info("Starting sync process...")

        # 1. Discovery
        if changes is None:
            changes = self.discover(force=force)

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

        # 2. Processing Loop
        raw_inbox = self._project_root / SOURCES_DIR
        output_dir = self._project_root / CONTEXT_DIR

        # Pre-scan for name collisions between passthrough and Docling files
        files_to_process, collision_skipped = self._resolve_collisions(files_to_process, raw_inbox)

        # Record collision-skipped files in manifest
        for skipped_file in collision_skipped:
            self._manifest.record_skipped(
                skipped_file.path,
                skipped_file.checksum,
                skipped_file.collision_reason or "Output path collision with passthrough file",
            )
            skipped_count += 1

        if files_to_process:
            logger.info("Processing %d files...", len(files_to_process))

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
                    # Log to .nest/errors.log (AC5)
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
                # Log to .nest/errors.log (AC5)
                if self._error_logger:
                    log_processing_error(self._error_logger, file_info.path, error_msg)
                if on_error == "fail":
                    raise

        # 3. Commit Manifest (before orphan cleanup so orphan detector knows about new files)
        self._manifest.commit()

        # 4. Orphan Cleanup (after manifest commit)
        orphan_result = self._orphan.cleanup(no_clean=no_clean)

        # 5. Load old hints
        context_dir = self._project_root / CONTEXT_DIR
        meta_dir = self._project_root / NEST_META_DIR
        hints_path = meta_dir / INDEX_HINTS_FILE
        old_hints = self._metadata.load_previous_hints(hints_path)

        # 6. Load old index and parse descriptions
        old_descriptions: dict[str, str] = {}
        old_index_content = self._index.read_index_content()
        if old_index_content:
            old_descriptions = parse_index_descriptions(old_index_content)

        # 7. Extract metadata for all context files
        new_metadata = self._metadata.extract_all(context_dir)

        # 8. Write new hints file
        self._metadata.write_hints(new_metadata, hints_path)

        # 9. Determine changed context files for glossary
        changed_context_files: list[Path] = []
        for file_meta in new_metadata:
            old_hash = old_hints.get(file_meta.path)
            if old_hash is None or old_hash != file_meta.content_hash:
                changed_context_files.append(context_dir / file_meta.path)

        # 10. Legacy hints cleanup — delete 00_GLOSSARY_HINTS.yaml if it exists
        legacy_hints_path = meta_dir / "00_GLOSSARY_HINTS.yaml"
        if legacy_hints_path.exists():
            try:
                legacy_hints_path.unlink()
            except OSError:
                logger.warning("Failed to delete legacy glossary hints: %s", legacy_hints_path)

        # Parallel AI execution (after glossary hints, before index generation)
        ai_prompt_tokens = 0
        ai_completion_tokens = 0
        ai_files_enriched = 0
        ai_glossary_terms_added = 0
        ai_glossary_prompt_tokens = 0
        ai_glossary_completion_tokens = 0

        has_enrichment_work = self._ai_enrichment is not None
        has_glossary_work = self._ai_glossary is not None and len(changed_context_files) > 0

        # Signal AI phase start
        if ai_progress_callback is not None and (has_enrichment_work or has_glossary_work):
            ai_progress_callback("start")

        if has_enrichment_work and has_glossary_work:
            # Both tasks have work — run in parallel
            with ThreadPoolExecutor(max_workers=2) as executor:
                enrichment_future = executor.submit(
                    self._ai_enrichment.enrich,  # type: ignore[union-attr]
                    new_metadata,
                    old_descriptions,
                    old_hints,
                )
                glossary_future = executor.submit(
                    self._run_glossary,
                    changed_context_files,
                    context_dir,
                )
                # Collect results (exceptions caught per-task)
                ai_result = self._collect_enrichment_result(enrichment_future)
                glossary_result = self._collect_glossary_result(glossary_future)
        elif has_enrichment_work:
            # Only enrichment — run directly (no thread overhead)
            try:
                ai_result = self._ai_enrichment.enrich(  # type: ignore[union-attr]
                    new_metadata,
                    old_descriptions,
                    old_hints,
                )
            except Exception:
                logger.exception("AI enrichment failed during sequential execution")
                ai_result = None
            glossary_result = None
        elif has_glossary_work:
            # Only glossary — run directly
            ai_result = None
            try:
                glossary_result = self._run_glossary(changed_context_files, context_dir)
            except Exception:
                logger.exception("AI glossary generation failed during sequential execution")
                glossary_result = None
        else:
            ai_result = None
            glossary_result = None

        # Apply enrichment results
        if ai_result is not None:
            old_descriptions.update(ai_result.descriptions)
            for file_meta in new_metadata:
                if file_meta.path in ai_result.descriptions:
                    old_hints[file_meta.path] = file_meta.content_hash
            ai_prompt_tokens = ai_result.prompt_tokens
            ai_completion_tokens = ai_result.completion_tokens
            ai_files_enriched = ai_result.files_enriched

        # Apply glossary results
        if glossary_result is not None:
            ai_glossary_terms_added = glossary_result.terms_added
            ai_glossary_prompt_tokens = glossary_result.prompt_tokens
            ai_glossary_completion_tokens = glossary_result.completion_tokens

        # Signal AI phase completion
        if ai_progress_callback is not None and (has_enrichment_work or has_glossary_work):
            parts: list[str] = []
            if ai_files_enriched > 0:
                parts.append(f"{ai_files_enriched} descriptions")
            if ai_glossary_terms_added > 0:
                parts.append(f"{ai_glossary_terms_added} glossary terms")
            summary = ", ".join(parts) if parts else "cached"
            ai_progress_callback(summary)

        # 14. Generate index (table format, with description carry-forward)
        project_name = self._project_root.name
        index_content = self._index.generate_content(
            new_metadata, old_descriptions, old_hints, project_name
        )

        # 15. Write new index
        self._index.write_index(index_content)
        logger.info("Master index updated.")

        # 16. Count empty descriptions in generated index
        generated_descriptions = parse_index_descriptions(index_content)
        enrichment_needed = sum(1 for desc in generated_descriptions.values() if not desc.strip())

        # Count user-curated files
        user_curated_count = self._orphan.count_user_curated_files()

        return SyncResult(
            processed_count=processed_count,
            skipped_count=skipped_count,
            failed_count=failed_count,
            orphans_removed=len(orphan_result.orphans_removed),
            orphans_detected=len(orphan_result.orphans_detected),
            skipped_orphan_cleanup=orphan_result.skipped,
            user_curated_count=user_curated_count,
            enrichment_needed=enrichment_needed,
            ai_prompt_tokens=ai_prompt_tokens,
            ai_completion_tokens=ai_completion_tokens,
            ai_files_enriched=ai_files_enriched,
            ai_glossary_terms_added=ai_glossary_terms_added,
            ai_glossary_prompt_tokens=ai_glossary_prompt_tokens,
            ai_glossary_completion_tokens=ai_glossary_completion_tokens,
        )

    def _run_glossary(self, changed_files: list[Path], context_dir: Path) -> AIGlossaryResult:
        """Run AI glossary generation.

        Extracted to a method for ThreadPoolExecutor.submit() compatibility.

        Args:
            changed_files: List of changed/new file paths.
            context_dir: Path to _nest_context directory.

        Returns:
            AIGlossaryResult with counts and token usage.
        """
        glossary_file_path = context_dir / GLOSSARY_FILE
        project_context = self._load_project_context(context_dir)
        return self._ai_glossary.generate(  # type: ignore[union-attr]
            changed_files,
            context_dir,
            glossary_file_path,
            project_context,
        )

    def _load_project_context(self, context_dir: Path) -> str | None:
        """Load optional project context text for glossary prompting."""
        candidates = [
            self._project_root / "_bmad-output" / "project-context.md",
            self._project_root / "docs" / "project-context.md",
            context_dir / "project-context.md",
        ]
        for path in candidates:
            try:
                if path.exists():
                    text = path.read_text(encoding="utf-8").strip()
                    if text:
                        return text
            except OSError:
                continue
        return None

    def _collect_enrichment_result(
        self, future: Future[AIEnrichmentResult]
    ) -> AIEnrichmentResult | None:
        """Safely collect enrichment result from a future.

        Args:
            future: Future from ThreadPoolExecutor.

        Returns:
            AIEnrichmentResult or None if the task raised an exception.
        """
        try:
            return future.result()
        except Exception:
            logger.exception("AI enrichment failed during parallel execution")
            return None

    def _collect_glossary_result(self, future: Future[AIGlossaryResult]) -> AIGlossaryResult | None:
        """Safely collect glossary result from a future.

        Args:
            future: Future from ThreadPoolExecutor.

        Returns:
            AIGlossaryResult or None if the task raised an exception.
        """
        try:
            return future.result()
        except Exception:
            logger.exception("AI glossary generation failed during parallel execution")
            return None

    def _resolve_collisions(
        self,
        files: list[DiscoveredFile],
        raw_inbox: Path,
    ) -> tuple[list[DiscoveredFile], list[DiscoveredFile]]:
        """Pre-scan files for output path collisions.

        When a passthrough text file and a Docling-convertible file would
        produce the same output path (e.g., report.md from both report.md
        source and report.pdf conversion), the passthrough file wins.

        Args:
            files: List of files to process.
            raw_inbox: Root of sources directory.

        Returns:
            Tuple of (files_to_process, collision_skipped_files).
        """
        # Build output path map: output_relative -> (file, is_passthrough)
        output_map: dict[str, tuple[DiscoveredFile, bool]] = {}
        collision_skipped: list[DiscoveredFile] = []

        for file_info in files:
            is_pt = is_passthrough_extension(file_info.path.suffix)

            try:
                relative = file_info.path.relative_to(raw_inbox)
            except ValueError:
                # File not under raw_inbox — can't determine output path for collision check
                # Add to output map with a unique key to avoid dropping it
                unique_key = file_info.path.as_posix()
                output_map[unique_key] = (file_info, is_pt)
                continue

            if is_pt:
                # Passthrough files keep their extension
                output_key = relative.as_posix()
            else:
                # Docling files get .md extension
                output_key = relative.with_suffix(".md").as_posix()

            if output_key in output_map:
                existing_file, existing_is_pt = output_map[output_key]
                if is_pt and not existing_is_pt:
                    # Passthrough wins over Docling — skip the existing Docling file
                    reason = (
                        f"Skipping Docling conversion of {existing_file.path.name} "
                        f"— output path {output_key} conflicts with passthrough "
                        f"source file {file_info.path.name}"
                    )
                    logger.warning(reason)
                    existing_file.collision_reason = reason
                    collision_skipped.append(existing_file)
                    output_map[output_key] = (file_info, is_pt)
                elif not is_pt and existing_is_pt:
                    # Passthrough already registered, skip the Docling file
                    reason = (
                        f"Skipping Docling conversion of {file_info.path.name} "
                        f"— output path {output_key} conflicts with passthrough "
                        f"source file {existing_file.path.name}"
                    )
                    logger.warning(reason)
                    file_info.collision_reason = reason
                    collision_skipped.append(file_info)
                else:
                    # Both same type — last one wins (unlikely but possible,
                    # e.g., report.pdf + report.docx both → report.md)
                    existing_file, _ = output_map[output_key]
                    reason = (
                        f"Output path collision: {existing_file.path.name} and "
                        f"{file_info.path.name} both produce {output_key} "
                        f"— keeping {file_info.path.name}"
                    )
                    logger.warning(reason)
                    existing_file.collision_reason = reason
                    collision_skipped.append(existing_file)
                    output_map[output_key] = (file_info, is_pt)
            else:
                output_map[output_key] = (file_info, is_pt)

        files_to_process = [f for f, _ in output_map.values()]
        return files_to_process, collision_skipped
