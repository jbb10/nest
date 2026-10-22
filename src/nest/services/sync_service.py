from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from nest.core.models import (
    Activity,
    DiscoveryResult,
    DryRunResult,
    FileMetadata,
    SyncResult,
)
from nest.core.paths import (
    CONTEXT_DIR,
    GLOSSARY_FILE,
    INDEX_HINTS_FILE,
    NEST_META_DIR,
    SOURCES_DIR,
)
from nest.services.discovery_service import DiscoveryService
from nest.services.index_service import IndexService, parse_index_descriptions
from nest.services.manifest_service import ManifestService
from nest.services.metadata_service import MetadataExtractorService
from nest.services.orphan_service import OrphanService
from nest.services.output_service import OutputMirrorService
from nest.services.sync_conversion import ConversionPhase
from nest.services.sync_enrichment import EnrichmentPhase
from nest.services.sync_outcomes import OnError, OutcomeRecorder, ProgressCallback, SyncLedger

if TYPE_CHECKING:
    from nest.adapters.docling_processor import DoclingProcessor
    from nest.services.llm_enrichment_service import LLMEnrichmentService
    from nest.services.llm_glossary_service import LLMGlossaryService
    from nest.services.picture_description_service import PictureDescriptionService

logger = logging.getLogger(__name__)

__all__ = ["ProgressCallback", "SyncService"]

LEGACY_GLOSSARY_HINTS_FILE = "00_GLOSSARY_HINTS.yaml"


class SyncService:
    """Runs the document sync pipeline.

    Phases, in order: conversion (with collision resolution and vision),
    manifest commit, orphan cleanup, metadata extraction, LLM enrichment,
    and index generation.
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
        llm_enrichment: LLMEnrichmentService | None = None,
        llm_glossary: LLMGlossaryService | None = None,
        picture_description_service: PictureDescriptionService | None = None,
        vision_docling_processor: DoclingProcessor | None = None,
        image_docling_processor: DoclingProcessor | None = None,
    ) -> None:
        self._discovery = discovery
        self._manifest = manifest
        self._orphan = orphan
        self._index = index
        self._metadata = metadata
        self._project_root = project_root
        self._error_logger = error_logger
        self._context_dir = project_root / CONTEXT_DIR
        self._meta_dir = project_root / NEST_META_DIR
        self._conversion = ConversionPhase(
            output=output,
            sources_dir=project_root / SOURCES_DIR,
            context_dir=self._context_dir,
            picture_description=picture_description_service,
            vision_processor=vision_docling_processor,
            image_processor=image_docling_processor,
        )
        self._enrichment = EnrichmentPhase(
            project_root=project_root,
            context_dir=self._context_dir,
            enrichment=llm_enrichment,
            glossary=llm_glossary,
        )

    @property
    def vision_enabled(self) -> bool:
        """True when image description runs during conversion."""
        return self._conversion.vision_enabled

    def discover(self, force: bool = False) -> DiscoveryResult:
        """Classify source files as new, modified, or unchanged."""
        return self._discovery.discover_changes(self._project_root, force=force)

    def sync(
        self,
        no_clean: bool = False,
        on_error: OnError = "skip",
        dry_run: bool = False,
        force: bool = False,
        progress_callback: ProgressCallback | None = None,
        llm_progress_callback: Callable[[str], None] | None = None,
        changes: DiscoveryResult | None = None,
        activity_callback: Callable[[Activity], None] | None = None,
    ) -> SyncResult | DryRunResult:
        """Execute the sync pipeline.

        Args:
            no_clean: Detect orphans but do not remove them.
            on_error: ``"skip"`` records failures and continues; ``"fail"``
                raises ``ProcessingError`` on the first failed file.
            dry_run: Report what would change without modifying anything.
            force: Reprocess all files and regenerate the glossary input set.
            progress_callback: Called with the file name once per attempted file.
            llm_progress_callback: Called with ``"start"`` when LLM work begins and
                with a summary string when it completes.
            changes: Pre-computed discovery result; discovered when omitted.
            activity_callback: Reports document and finalization stages before blocking work.

        Raises:
            ProcessingError: In ``on_error="fail"`` mode, on the first failed file.
        """
        logger.info("Starting sync process...")
        if changes is None:
            changes = self.discover(force=force)

        if dry_run:
            return DryRunResult(
                new_count=len(changes.new_files),
                modified_count=len(changes.modified_files),
                unchanged_count=len(changes.unchanged_files),
                orphan_count=len(self._orphan.detect_orphans()),
            )

        ledger = SyncLedger(skipped=len(changes.unchanged_files))
        recorder = OutcomeRecorder(
            self._manifest, ledger, on_error, self._error_logger, progress_callback
        )
        self._conversion.run(
            changes.new_files + changes.modified_files,
            recorder,
            ledger,
            activity_callback=activity_callback,
        )

        # Commit before orphan cleanup so the detector sees newly produced outputs.
        if activity_callback is not None:
            activity_callback(Activity(stage="committing"))
        self._manifest.commit()
        if activity_callback is not None:
            activity_callback(Activity(stage="cleanup"))
        orphans = self._orphan.cleanup(no_clean=no_clean)

        if activity_callback is not None:
            activity_callback(Activity(stage="metadata"))
        hints_path = self._meta_dir / INDEX_HINTS_FILE
        hints = self._metadata.load_previous_hints(hints_path)
        old_index = self._index.read_index_content()
        descriptions = parse_index_descriptions(old_index) if old_index else {}
        metadata = self._metadata.extract_all(self._context_dir)
        self._metadata.write_hints(metadata, hints_path)
        self._remove_legacy_glossary_hints()

        self._enrichment.run(
            metadata,
            descriptions,
            hints,
            self._glossary_input(metadata, hints, force),
            ledger,
            llm_progress_callback,
        )

        if activity_callback is not None:
            activity_callback(Activity(stage="indexing"))
        index_content = self._index.generate_content(metadata, descriptions, hints)
        self._index.write_index(index_content)
        logger.info("Master index updated.")

        generated = parse_index_descriptions(index_content)
        return ledger.to_result(
            orphans=orphans,
            user_curated_count=self._orphan.count_user_curated_files(),
            enrichment_needed=sum(1 for d in generated.values() if not d.strip()),
        )

    def _glossary_input(
        self, metadata: list[FileMetadata], old_hints: dict[str, str], force: bool
    ) -> list[Path]:
        """Context files whose content changed since the last sync.

        All files are included when forced, or when the glossary is missing so
        a project synced before an LLM was configured gets backfilled.
        """
        glossary_missing = not (self._meta_dir / GLOSSARY_FILE).exists()
        if force or (metadata and glossary_missing):
            return [self._context_dir / m.path for m in metadata]
        return [
            self._context_dir / m.path for m in metadata if old_hints.get(m.path) != m.content_hash
        ]

    def _remove_legacy_glossary_hints(self) -> None:
        legacy = self._meta_dir / LEGACY_GLOSSARY_HINTS_FILE
        if legacy.exists():
            try:
                legacy.unlink()
            except OSError:
                logger.warning("Failed to delete legacy glossary hints: %s", legacy)
