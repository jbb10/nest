"""Project-free document conversion for `nest convert`.

Converts a single file or a directory tree to Markdown using the same
discovery, collision, and conversion rules as sync, without a manifest,
index, glossary, or any other project artifact.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from nest.adapters.protocols import FileDiscoveryProtocol, ModelCacheProtocol
from nest.core.checksum import compute_sha256
from nest.core.exceptions import NestError
from nest.core.models import (
    Activity,
    ConvertPlan,
    ConvertResult,
    DiscoveredFile,
)
from nest.core.paths import (
    ALL_SOURCE_EXTENSIONS,
    is_passthrough_extension,
    mirror_path,
    passthrough_mirror_path,
)
from nest.services.sync_conversion import ConversionPhase
from nest.services.sync_outcomes import OutcomeRecorder, ProgressCallback, SyncLedger

if TYPE_CHECKING:
    from nest.adapters.docling_processor import DoclingProcessor
    from nest.services.ai_transcription_service import AITranscriptionService
    from nest.services.output_service import OutputMirrorService
    from nest.services.picture_description_service import PictureDescriptionService

logger = logging.getLogger(__name__)

_ALL_EXTENSIONS = frozenset(ALL_SOURCE_EXTENSIONS)


class ConvertService:
    """Converts documents to Markdown without requiring a Nest project."""

    def __init__(
        self,
        output: OutputMirrorService,
        file_discovery: FileDiscoveryProtocol,
        model_downloader: ModelCacheProtocol | None = None,
        picture_description: PictureDescriptionService | None = None,
        vision_processor: DoclingProcessor | None = None,
        image_processor: DoclingProcessor | None = None,
        transcriber: AITranscriptionService | None = None,
    ) -> None:
        """Initialize with required collaborators.

        Args:
            output: Service that routes files to conversion or passthrough copy.
            file_discovery: Adapter for recursive directory discovery.
            model_downloader: Model cache consulted before Docling conversion;
                None skips the download check.
            picture_description: Optional vision service for image descriptions.
            vision_processor: Optional classification-enabled Docling processor
                backing the vision pipeline.
            image_processor: Optional classification-enabled Docling processor
                for standalone image files when vision is unavailable.
            transcriber: Optional service that prepares the files it handles
                by AI transcription instead of Docling.
        """
        self._output = output
        self._file_discovery = file_discovery
        self._model_downloader = model_downloader
        self._picture_description = picture_description
        self._vision_processor = vision_processor
        self._image_processor = image_processor
        self._transcriber = transcriber

    def plan(
        self,
        target: Path,
        output_dir: Path | None = None,
        force: bool = False,
    ) -> ConvertPlan:
        """Classify every supported file under ``target`` as pending or skipped.

        Args:
            target: File or directory to convert.
            output_dir: Directory to mirror outputs into; None writes outputs
                next to the originals.
            force: Re-convert files whose output already exists.

        Returns:
            ConvertPlan with pending and pre-classified skipped files.

        Raises:
            NestError: If ``target`` does not exist, or a single target file
                has an unsupported extension.
        """
        if not target.exists():
            raise NestError(f"Path not found: {target}")

        if target.is_file():
            if target.suffix.lower() not in _ALL_EXTENSIONS:
                raise NestError(
                    f"Unsupported file type: {target.suffix.lower() or target.name}. "
                    f"Supported: {', '.join(ALL_SOURCE_EXTENSIONS)}"
                )
            root = target.parent
            files = [target]
        else:
            root = target
            files = self._file_discovery.discover(target, set(_ALL_EXTENSIONS))

        pending: list[DiscoveredFile] = []
        skipped: list[DiscoveredFile] = []
        for path in files:
            file = self._discovered_file(path)
            if file.collision_reason is not None:
                skipped.append(file)
                continue
            if is_passthrough_extension(path.suffix) and output_dir is None:
                file.collision_reason = "Text file; left in place (use --output to copy)"
                skipped.append(file)
                continue
            if self._output_path(path, root, output_dir).exists() and not force:
                file.collision_reason = "Output already exists (use --force to overwrite)"
                skipped.append(file)
                continue
            pending.append(file)

        return ConvertPlan(root=root, output_dir=output_dir, pending=pending, skipped=skipped)

    def execute(
        self,
        plan: ConvertPlan,
        progress_callback: ProgressCallback | None = None,
        activity_callback: Callable[[Activity], None] | None = None,
    ) -> ConvertResult:
        """Run a plan, recording exactly one outcome per attempted file.

        Failed files do not stop the run; every failure is collected with its
        reason on the result.

        Args:
            plan: Plan produced by ``plan``.
            progress_callback: Called once per attempted file with its name.
            activity_callback: Reports the current stage before blocking work begins.

        Returns:
            ConvertResult with counts, skip/failure reasons, and vision totals.
        """
        ledger = SyncLedger()
        recorder = OutcomeRecorder(
            manifest=None,
            ledger=ledger,
            on_error="skip",
            error_logger=None,
            progress_callback=progress_callback,
        )
        for file in plan.skipped:
            recorder.skipped(file, file.collision_reason or "Skipped")

        phase = ConversionPhase(
            output=self._output,
            sources_dir=plan.root,
            context_dir=plan.output_dir if plan.output_dir is not None else plan.root,
            picture_description=self._picture_description,
            vision_processor=self._vision_processor,
            image_processor=self._image_processor,
            transcriber=self._transcriber,
        )
        needs_models = any(phase.uses_docling(f.path) for f in plan.pending)
        if needs_models and self._model_downloader is not None:
            if activity_callback is not None:
                activity_callback(Activity(stage="preparing"))
                if not self._model_downloader.are_models_cached():
                    activity_callback(Activity(stage="downloading"))
            self._model_downloader.download_if_needed(progress=True)

        if plan.pending:
            phase.run(plan.pending, recorder, ledger, activity_callback=activity_callback)

        return ConvertResult(
            root=plan.root,
            processed_count=ledger.processed,
            skipped_count=ledger.skipped,
            failed_count=ledger.failed,
            skips=list(ledger.skips),
            failures=list(ledger.failures),
            images_described=sum(v.images_described for v in ledger.vision),
            images_skipped=sum(v.images_skipped for v in ledger.vision),
            images_failed=sum(v.images_failed for v in ledger.vision),
            pages_transcribed=sum(t.pages for t in ledger.transcriptions),
            vision_prompt_tokens=ledger.vision_prompt_tokens,
            vision_completion_tokens=ledger.vision_completion_tokens,
        )

    def _discovered_file(self, path: Path) -> DiscoveredFile:
        """Build a DiscoveredFile, classifying plan-time skips on collision_reason."""
        try:
            checksum = compute_sha256(path)
        except OSError as e:
            logger.warning("Unreadable file %s: %s", path, e)
            return DiscoveredFile(
                path=path,
                status="new",
                checksum="",
                collision_reason=f"Unreadable file: {e}",
            )
        return DiscoveredFile(path=path, status="new", checksum=checksum)

    def _output_path(self, source: Path, root: Path, output_dir: Path | None) -> Path:
        """Compute where a source's output will be written."""
        target_root = output_dir if output_dir is not None else root
        if is_passthrough_extension(source.suffix):
            return passthrough_mirror_path(source, root, target_root)
        return mirror_path(source, root, target_root, ".md")
