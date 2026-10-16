"""Conversion phase of the sync pipeline.

Turns every pending source file into exactly one recorded outcome. Owns
collision resolution between passthrough and Docling outputs and the
two-pass vision pipeline (convert sequentially, describe images in parallel).
"""

from __future__ import annotations

import logging
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import TYPE_CHECKING, Any

from docling_core.types.doc.base import ImageRefMode

from nest.core.exceptions import ProcessingError
from nest.core.models import DiscoveredFile
from nest.core.paths import is_passthrough_extension

if TYPE_CHECKING:
    from nest.adapters.docling_processor import DoclingProcessor
    from nest.services.output_service import OutputMirrorService
    from nest.services.picture_description_service import PictureDescriptionService
    from nest.services.sync_outcomes import OutcomeRecorder, SyncLedger

logger = logging.getLogger(__name__)


class ConversionPhase:
    """Converts pending files and records each file's outcome."""

    def __init__(
        self,
        output: OutputMirrorService,
        sources_dir: Path,
        context_dir: Path,
        picture_description: PictureDescriptionService | None = None,
        vision_processor: DoclingProcessor | None = None,
    ) -> None:
        self._output = output
        self._sources_dir = sources_dir
        self._context_dir = context_dir
        self._picture_description = picture_description
        self._vision_processor = vision_processor

    @property
    def vision_enabled(self) -> bool:
        return self._picture_description is not None and self._vision_processor is not None

    def run(
        self,
        files: list[DiscoveredFile],
        recorder: OutcomeRecorder,
        ledger: SyncLedger,
    ) -> None:
        """Convert ``files``, recording one outcome per file.

        Raises:
            ProcessingError: Propagated from ``recorder`` in fail mode.
        """
        files, collisions = resolve_collisions(files, self._sources_dir)
        for skipped in collisions:
            recorder.skipped(
                skipped,
                skipped.collision_reason or "Output path collision with passthrough file",
            )

        if files:
            logger.info("Processing %d files...", len(files))

        deferred: list[tuple[DiscoveredFile, Any, Path]] = []
        for file in files:
            if self._uses_vision(file):
                converted = self._convert_for_vision(file, recorder)
                if converted is not None:
                    deferred.append(converted)
            else:
                self._convert(file, recorder)

        if deferred:
            self._describe_images(deferred, recorder, ledger)

    def _uses_vision(self, file: DiscoveredFile) -> bool:
        return self.vision_enabled and not is_passthrough_extension(file.path.suffix)

    def _convert(self, file: DiscoveredFile, recorder: OutcomeRecorder) -> None:
        try:
            result = self._output.process_file(file.path, self._sources_dir, self._context_dir)
        except ProcessingError:
            raise
        except Exception as e:
            recorder.failed(file, str(e), cause=e)
            return
        recorder.record(file, result)

    def _convert_for_vision(
        self, file: DiscoveredFile, recorder: OutcomeRecorder
    ) -> tuple[DiscoveredFile, Any, Path] | None:
        assert self._vision_processor is not None
        try:
            conversion = self._vision_processor.convert(file.path)
        except Exception as e:
            recorder.failed(file, f"Docling convert failed: {e}", cause=e)
            return None
        output_path = self._output.compute_docling_output_path(
            file.path, self._sources_dir, self._context_dir
        )
        return file, conversion, output_path

    def _describe_images(
        self,
        deferred: list[tuple[DiscoveredFile, Any, Path]],
        recorder: OutcomeRecorder,
        ledger: SyncLedger,
    ) -> None:
        assert self._picture_description is not None
        with ThreadPoolExecutor() as executor:
            futures: dict[Future[Any], tuple[DiscoveredFile, Any, Path]] = {
                executor.submit(self._picture_description.describe, item[1]): item
                for item in deferred
            }
            for future in as_completed(futures):
                file, conversion, output_path = futures[future]
                try:
                    description = future.result()
                    markdown = conversion.document.export_to_markdown(
                        image_mode=ImageRefMode.PLACEHOLDER,
                    )
                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    output_path.write_text(markdown, encoding="utf-8", newline="\n")
                except Exception as e:
                    recorder.failed(file, f"Vision describe failed: {e}", cause=e)
                    continue
                ledger.vision.append(description)
                recorder.processed(file, output_path)


def resolve_collisions(
    files: list[DiscoveredFile],
    sources_dir: Path,
) -> tuple[list[DiscoveredFile], list[DiscoveredFile]]:
    """Split ``files`` into those to convert and those skipped for output collisions.

    When a passthrough file and a Docling-convertible file map to the same
    output path (``report.md`` vs ``report.pdf``), the passthrough file wins.
    Between two files of the same kind, the later one wins.
    """
    output_map: dict[str, tuple[DiscoveredFile, bool]] = {}
    skipped: list[DiscoveredFile] = []

    for file in files:
        is_pt = is_passthrough_extension(file.path.suffix)
        try:
            relative = file.path.relative_to(sources_dir)
        except ValueError:
            output_map[file.path.as_posix()] = (file, is_pt)
            continue

        output_key = relative.as_posix() if is_pt else relative.with_suffix(".md").as_posix()

        if output_key not in output_map:
            output_map[output_key] = (file, is_pt)
            continue

        existing, existing_is_pt = output_map[output_key]
        if not is_pt and existing_is_pt:
            loser, winner = file, existing
        else:
            loser, winner = existing, file
            output_map[output_key] = (file, is_pt)

        if is_pt != existing_is_pt:
            reason = (
                f"Skipping Docling conversion of {loser.path.name} "
                f"— output path {output_key} conflicts with passthrough "
                f"source file {winner.path.name}"
            )
        else:
            reason = (
                f"Output path collision: {existing.path.name} and "
                f"{file.path.name} both produce {output_key} "
                f"— keeping {file.path.name}"
            )
        logger.warning(reason)
        loser.collision_reason = reason
        skipped.append(loser)

    return [f for f, _ in output_map.values()], skipped
