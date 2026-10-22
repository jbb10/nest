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
from nest.adapters.llm_provider import resolve_ai_config
from nest.adapters.noop_processor import NoOpProcessor
from nest.adapters.passthrough_processor import PassthroughProcessor
from nest.core.exceptions import ModelError, NestError
from nest.services.convert_service import ConvertService
from nest.services.output_service import OutputMirrorService
from nest.ui.command import current_output
from nest.ui.conversion import display_convert_summary
from nest.ui.messages import (
    AI_DISABLED_NOTE,
    AI_ENABLE_HINT,
    AI_NOT_CONFIGURED_NOTE,
    error,
    get_console,
)

if TYPE_CHECKING:
    from nest.adapters.llm_provider import AIConfig
    from nest.adapters.protocols import ModelCacheProtocol

logger = logging.getLogger(__name__)


def create_convert_service(
    no_ai: bool = False,
    ai_config: "AIConfig | None" = None,
    ai_only: bool = False,
) -> ConvertService:
    """Composition root for the convert service.

    Wires the same adapters as sync, minus every project artifact: no
    manifest, index, glossary, or error log. AI is used for picture
    descriptions, and with ``ai_only`` also transcribes images and PDFs.

    Args:
        no_ai: If True, skip image descriptions even when configured.
        ai_config: Pre-resolved AI configuration; resolved from the
            environment when omitted.
        ai_only: If True, image files and PDFs bypass Docling and are
            prepared by AI transcription.

    Returns:
        Configured ConvertService with real adapters.

    Raises:
        NestError: If ``ai_only`` is set and no vision model is configured.
    """
    from nest.adapters.llm_provider import create_vision_provider

    vision_provider = None
    if not no_ai:
        ai_config = ai_config or resolve_ai_config()
        vision_provider = create_vision_provider(ai_config) if ai_config else None
    if ai_only and vision_provider is None:
        raise NestError(f"--ai-only requires an AI vision model; {AI_ENABLE_HINT}")

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
        if ai_only:
            from nest.services.ai_transcription_service import AITranscriptionService

            transcriber = AITranscriptionService(vision_provider=vision_provider)

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
    no_ai: Annotated[
        bool,
        typer.Option(
            "--no-ai",
            help="Skip AI image descriptions even when configured",
        ),
    ] = False,
    ai_only: Annotated[
        bool,
        typer.Option(
            "--ai-only",
            help="Prepare images and PDFs by AI transcription instead of Docling",
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
    With --ai-only, each image and PDF page is transcribed by the AI vision
    model instead of Docling layout analysis, OCR, and table recognition.

    \b
    Examples:
        nest convert reports/q1.pdf
        nest convert reports/ --output md/
        nest convert reports/ --output md/ --force
        nest convert screenshots/ --ai-only
    """
    console = get_console()

    target = path.resolve()
    output_dir = output.resolve() if output else None

    try:
        if ai_only and no_ai:
            raise NestError("--ai-only cannot be combined with --no-ai")
        ui = current_output()
        ai_config = None if no_ai else resolve_ai_config()
        service = create_convert_service(no_ai=no_ai, ai_config=ai_config, ai_only=ai_only)
        ui.stage("Discovering documents")
        plan = service.plan(target, output_dir=output_dir, force=force)
        ui.root = plan.root
        ai_status_note = ""
        if no_ai:
            ai_status_note = AI_DISABLED_NOTE
        elif ai_config is None:
            ai_status_note = AI_NOT_CONFIGURED_NOTE

        ui.start(len(plan.pending) + len(plan.skipped))
        result = service.execute(plan, progress_callback=ui.advance, activity_callback=ui.activity)
        ui.finish(failed=result.failed_count > 0)
        display_convert_summary(
            result, console, ai_status_note, verbose=verbose, has_warnings=ui.has_warnings
        )

    except NestError as e:
        error("Convert failed")
        console.print(f"  [dim]Reason: {e}[/dim]")
        raise typer.Exit(1) from None

    if result.failed_count > 0:
        raise typer.Exit(1)
