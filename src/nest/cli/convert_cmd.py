"""Convert command for nest CLI.

Handles the `nest convert <path>` command: document conversion for any
path on disk, without requiring a Nest project.
"""

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

import typer

from nest.adapters.classification_processor import create_classification_processor
from nest.adapters.file_discovery import FileDiscoveryAdapter
from nest.adapters.filesystem import FileSystemAdapter
from nest.adapters.llm_provider import resolve_llm_config
from nest.adapters.noop_processor import NoOpProcessor
from nest.adapters.passthrough_processor import PassthroughProcessor
from nest.core.exceptions import ModelError, NestError
from nest.services.convert_service import ConvertService
from nest.services.output_service import OutputMirrorService
from nest.ui.command import current_output
from nest.ui.conversion import display_convert_summary
from nest.ui.messages import (
    LLM_DISABLED_NOTE,
    LLM_ENABLE_HINT,
    LLM_NOT_CONFIGURED_NOTE,
    error,
    get_console,
)

if TYPE_CHECKING:
    from nest.adapters.llm_provider import LLMConfig
    from nest.adapters.protocols import ModelCacheProtocol

logger = logging.getLogger(__name__)


def create_convert_service(
    no_llm: bool = False,
    llm_config: "LLMConfig | None" = None,
    llm_only: bool = False,
) -> ConvertService:
    """Composition root for the convert service.

    Wires the same adapters as sync, minus every project artifact: no
    manifest, index, glossary, or error log. LLM is used for picture
    descriptions, and with ``llm_only`` also transcribes images and PDFs.

    Args:
        no_llm: If True, skip image descriptions even when configured.
        llm_config: Pre-resolved LLM configuration; resolved from the
            environment when omitted.
        llm_only: If True, image files and PDFs bypass Docling and are
            prepared by LLM transcription.

    Returns:
        Configured ConvertService with real adapters.

    Raises:
        NestError: If ``llm_only`` is set and no vision model is configured.
    """
    from nest.adapters.llm_provider import create_vision_provider

    vision_provider = None
    if not no_llm:
        llm_config = llm_config or resolve_llm_config()
        vision_provider = create_vision_provider(llm_config) if llm_config else None
    if llm_only and vision_provider is None:
        raise NestError(f"--llm-only requires an LLM vision model; {LLM_ENABLE_HINT}")

    try:
        from nest.adapters.docling_processor import DoclingProcessor

        processor = DoclingProcessor()
    except ImportError:
        processor = NoOpProcessor()

    downloader: ModelCacheProtocol | None = None
    try:
        from nest.adapters.docling_downloader import DoclingModelDownloader

        downloader = DoclingModelDownloader()
        # Eagerly verify docling is importable
        downloader.get_cache_path()
    except (ImportError, ModelError):
        downloader = None

    picture_description = None
    vision_processor = None
    transcriber = None
    if vision_provider is not None:
        vision_processor = create_classification_processor()

        from nest.services.picture_description_service import PictureDescriptionService

        picture_description = PictureDescriptionService(vision_provider=vision_provider)
        if llm_only:
            from nest.services.llm_transcription_service import LLMTranscriptionService

            transcriber = LLMTranscriptionService(vision_provider=vision_provider)

    image_processor = create_classification_processor() if vision_processor is None else None

    return ConvertService(
        output=OutputMirrorService(
            filesystem=FileSystemAdapter(),
            processor=processor,
            passthrough_processor=PassthroughProcessor(),
        ),
        file_discovery=FileDiscoveryAdapter(),
        model_downloader=downloader,
        picture_description=picture_description,
        vision_processor=vision_processor,
        image_processor=image_processor,
        transcriber=transcriber,
    )


def convert_command(
    path: Annotated[
        Path,
        typer.Argument(
            help="File or directory to convert (PDF, DOCX, PPTX, XLSX, HTML, image, or text files)",
        ),
    ],
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-o",
            help="Directory to write outputs into, mirroring the tree (default: next to originals)",
        ),
    ] = None,
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            help="Overwrite existing output files",
        ),
    ] = False,
    no_llm: Annotated[
        bool,
        typer.Option(
            "--no-llm",
            help="Skip LLM image descriptions even when configured",
        ),
    ] = False,
    llm_only: Annotated[
        bool,
        typer.Option(
            "--llm-only",
            help="Prepare images and PDFs by LLM transcription instead of Docling",
        ),
    ] = False,
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose",
            "-v",
            help="Show library diagnostics and per-file skip reasons",
        ),
    ] = False,
) -> None:
    """Convert documents to Markdown anywhere, without a Nest project.

    Converts PDF, DOCX, PPTX, XLSX, HTML, and image files to Markdown next to the
    originals, or into --output mirroring the tree. Text files are copied
    only with --output. Existing outputs are skipped unless --force is set.
    With --llm-only, each image and PDF page is transcribed by the LLM vision
    model instead of Docling layout analysis, OCR, and table recognition.

    \b
    Examples:
        nest convert reports/q1.pdf
        nest convert reports/ --output md/
        nest convert reports/ --output md/ --force
        nest convert screenshots/ --llm-only
    """
    console = get_console()

    target = path.resolve()
    output_dir = output.resolve() if output else None

    try:
        if llm_only and no_llm:
            raise NestError("--llm-only cannot be combined with --no-llm")
        ui = current_output()
        llm_config = None if no_llm else resolve_llm_config()
        service = create_convert_service(no_llm=no_llm, llm_config=llm_config, llm_only=llm_only)
        ui.stage("Discovering documents")
        plan = service.plan(target, output_dir=output_dir, force=force)
        ui.root = plan.root
        llm_status_note = ""
        if no_llm:
            llm_status_note = LLM_DISABLED_NOTE
        elif llm_config is None:
            llm_status_note = LLM_NOT_CONFIGURED_NOTE

        ui.start(len(plan.pending) + len(plan.skipped))
        result = service.execute(plan, progress_callback=ui.advance, activity_callback=ui.activity)
        ui.finish(failed=result.failed_count > 0)
        display_convert_summary(
            result, console, llm_status_note, verbose=verbose, has_warnings=ui.has_warnings
        )

    except NestError as e:
        error("Convert failed")
        console.print(f"  [dim]Reason: {e}[/dim]")
        raise typer.Exit(1) from None

    if result.failed_count > 0:
        raise typer.Exit(1)
