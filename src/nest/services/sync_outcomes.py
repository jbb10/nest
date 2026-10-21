"""Per-file outcome recording for the sync pipeline.

Every file a sync attempts ends in exactly one outcome: processed, skipped,
or failed. ``OutcomeRecorder`` is the single place that turns an outcome into
its side effects (manifest entry, counters, error log, progress, fail-mode
abort). ``SyncLedger`` accumulates what the phases produce and renders the
final ``SyncResult``.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from nest.core.exceptions import ProcessingError
from nest.core.models import (
    AIEnrichmentResult,
    AIGlossaryResult,
    DiscoveredFile,
    OrphanCleanupResult,
    PictureDescriptionResult,
    ProcessingResult,
    SyncResult,
)
from nest.ui.logger import log_processing_error

if TYPE_CHECKING:
    from nest.services.manifest_service import ManifestService

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[str], None]
OnError = Literal["skip", "fail"]


@dataclass
class SyncLedger:
    """Accumulates counts and phase results over one sync run."""

    processed: int = 0
    skipped: int = 0
    failed: int = 0
    vision: list[PictureDescriptionResult] = field(default_factory=lambda: [])
    enrichment: AIEnrichmentResult | None = None
    glossary: AIGlossaryResult | None = None
    skip_reasons: list[tuple[Path, str]] = field(default_factory=lambda: [])
    failure_reasons: list[tuple[Path, str]] = field(default_factory=lambda: [])

    def to_result(
        self,
        orphans: OrphanCleanupResult,
        user_curated_count: int,
        enrichment_needed: int,
    ) -> SyncResult:
        enrichment = self.enrichment or AIEnrichmentResult()
        glossary = self.glossary or AIGlossaryResult()
        return SyncResult(
            processed_count=self.processed,
            skipped_count=self.skipped,
            failed_count=self.failed,
            orphans_removed=len(orphans.orphans_removed),
            orphans_detected=len(orphans.orphans_detected),
            skipped_orphan_cleanup=orphans.skipped,
            user_curated_count=user_curated_count,
            enrichment_needed=enrichment_needed,
            ai_prompt_tokens=enrichment.prompt_tokens,
            ai_completion_tokens=enrichment.completion_tokens,
            ai_files_enriched=enrichment.files_enriched,
            ai_glossary_terms_added=glossary.terms_added,
            ai_glossary_prompt_tokens=glossary.prompt_tokens,
            ai_glossary_completion_tokens=glossary.completion_tokens,
            vision_prompt_tokens=sum(v.prompt_tokens for v in self.vision),
            vision_completion_tokens=sum(v.completion_tokens for v in self.vision),
            images_described=sum(v.images_described for v in self.vision),
            images_mermaid=sum(v.images_mermaid for v in self.vision),
            images_skipped=sum(v.images_skipped for v in self.vision),
            images_failed=sum(v.images_failed for v in self.vision),
            failure_reasons={str(path): reason for path, reason in self.failure_reasons},
        )


class OutcomeRecorder:
    """Applies the side effects of a single file outcome.

    Each call records the manifest entry (when a manifest is configured),
    updates the ledger, and advances progress exactly once. In
    ``on_error="fail"`` mode, ``failed`` raises ``ProcessingError`` after
    recording. Manifest-free runs (``manifest=None``) still count every
    outcome and collect skip/failure reasons on the ledger.
    """

    def __init__(
        self,
        manifest: ManifestService | None,
        ledger: SyncLedger,
        on_error: OnError,
        error_logger: logging.Logger | logging.LoggerAdapter[logging.Logger] | None,
        progress_callback: ProgressCallback | None,
    ) -> None:
        self._manifest = manifest
        self._ledger = ledger
        self._on_error = on_error
        self._error_logger = error_logger
        self._progress = progress_callback

    def processed(self, file: DiscoveredFile, output_path: Path) -> None:
        if self._manifest is not None:
            self._manifest.record_success(file.path, file.checksum, output_path)
        self._ledger.processed += 1
        self._advance(file)

    def skipped(self, file: DiscoveredFile, reason: str) -> None:
        if self._manifest is not None:
            self._manifest.record_skipped(file.path, file.checksum, reason)
        self._ledger.skipped += 1
        self._ledger.skip_reasons.append((file.path, reason))
        self._advance(file)

    def failed(self, file: DiscoveredFile, error: str, cause: BaseException | None = None) -> None:
        if cause is not None:
            logger.error(
                "Unexpected error processing %s",
                file.path,
                exc_info=cause,
                extra={"source_path": str(file.path)},
            )
        if self._manifest is not None:
            self._manifest.record_failure(file.path, file.checksum, error)
        self._ledger.failed += 1
        self._ledger.failure_reasons.append((file.path, error))
        if self._error_logger:
            log_processing_error(self._error_logger, file.path, error)
        self._advance(file)
        if self._on_error == "fail":
            raise ProcessingError(
                f"Processing failed for {file.path.name}: {error}",
                source_path=file.path,
            ) from cause

    def record(self, file: DiscoveredFile, result: ProcessingResult) -> None:
        """Record the outcome reported by a document processor."""
        if result.status == "success":
            if result.output_path is None:
                self.failed(file, "Internal error: output_path missing")
            else:
                self.processed(file, result.output_path)
        elif result.status == "skipped":
            self.skipped(file, result.error or "Skipped by processor")
        else:
            self.failed(file, result.error or "Unknown error")

    def _advance(self, file: DiscoveredFile) -> None:
        if self._progress is not None:
            self._progress(file.path.name)
