"""Convert command for nest CLI.

Handles the `nest convert <path>` command: document conversion for any
path on disk, without requiring a Nest project.
"""

import logging
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

import typer

from nest.adapters.file_discovery import FileDiscoveryAdapter
from nest.adapters.filesystem import FileSystemAdapter
from nest.adapters.llm_provider import resolve_ai_config
from nest.adapters.noop_processor import NoOpProcessor
from nest.adapters.passthrough_processor import PassthroughProcessor
from nest.core.exceptions import ModelError, NestError
from nest.core.models import ConvertFileOutcome, ConvertResult
from nest.services.convert_service import ConvertService
from nest.services.output_service import OutputMirrorService
from nest.ui.logger import enable_verbose_logging
from nest.ui.messages import error, get_console, success
from nest.ui.progress import SyncProgress

if TYPE_CHECKING:
    from rich.console import Console

    from nest.adapters.llm_provider import AIConfig
    from nest.adapters.protocols import ModelCacheProtocol

logger = logging.getLogger(__name__)


def create_convert_service(
    no_ai: bool = False,
    ai_config: "AIConfig | None" = None,
) -> ConvertService:
    """Composition root for the convert service.

    Wires the same adapters as sync, minus every project artifact: no
    manifest, index, glossary, or error log. AI is used only for picture
    descriptions.

    Args:
        no_ai: If True, skip image descriptions even when configured.
        ai_config: Pre-resolved AI configuration; resolved from the
            environment when omitted.

    Returns:
        Configured ConvertService with real adapters.
    """
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
    if not no_ai:
        from nest.adapters.llm_provider import create_vision_provider

        ai_config = ai_config or resolve_ai_config()
        vision_provider = create_vision_provider(ai_config) if ai_config else None
        if vision_provider is not None:
            from nest.adapters.docling_processor import DoclingProcessor as ClassificationProcessor

            vision_processor = ClassificationProcessor(enable_classification=True)

            from nest.services.picture_description_service import PictureDescriptionService

            picture_description = PictureDescriptionService(vision_provider=vision_provider)

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
    )


def convert_command(
    path: Annotated[
        Path,
        typer.Argument(
            help="File or directory to convert (PDF, DOCX, PPTX, XLSX, HTML, or text files)",
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
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose",
            "-v",
            help="Show detailed processing logs (Docling, HTTP, etc.)",
        ),
    ] = False,
) -> None:
    """Convert documents to Markdown anywhere, without a Nest project.

    Converts PDF, DOCX, PPTX, XLSX, and HTML files to Markdown next to the
    originals, or into --output mirroring the tree. Text files are copied
    only with --output. Existing outputs are skipped unless --force is set.

    Examples:
        nest convert reports/q1.pdf
        nest convert reports/ --output md/
        nest convert reports/ --output md/ --force
    """
    console = get_console()

    if verbose:
        enable_verbose_logging()

    target = path.resolve()
    output_dir = output.resolve() if output else None

    try:
        ai_config = None if no_ai else resolve_ai_config()
        service = create_convert_service(no_ai=no_ai, ai_config=ai_config)

        plan = service.plan(target, output_dir=output_dir, force=force)

        ai_status_note = ""
        if no_ai:
            ai_status_note = "disabled (--no-ai)"
        elif ai_config is None:
            ai_status_note = "not configured (run 'nest config ai' or set NEST_AI_API_KEY)"

        total = len(plan.pending) + len(plan.skipped)
        with SyncProgress(console=console, disabled=total == 0) as progress:
            progress.start(total=total)
            result = service.execute(plan, progress_callback=progress.advance)

        _display_convert_summary(result, console, ai_status_note)

    except NestError as e:
        error("Convert failed")
        console.print(f"  [dim]Reason: {e}[/dim]")
        raise typer.Exit(1) from None

    if result.failed_count > 0:
        raise typer.Exit(1)


def _display_convert_summary(
    result: ConvertResult,
    console: "Console",
    ai_status_note: str = "",
) -> None:
    """Display convert completion summary.

    Shows counts, per-file skip and failure reasons, and AI activity.

    Args:
        result: ConvertResult with all counts and reasons.
        console: Rich console for output.
        ai_status_note: Optional human-readable AI status note.
    """
    success("Convert complete")
    console.print()

    console.print(f"  Converted: {result.processed_count} files")
    console.print(f"  Skipped:   {result.skipped_count}")
    console.print(f"  Failed:    {result.failed_count}")

    _print_reason_list(console, "Skipped files", result.skips, result.root)
    _print_reason_list(console, "Failed files", result.failures, result.root)

    if ai_status_note:
        console.print()
        console.print(f"  AI: {ai_status_note}")

    if result.images_described > 0:
        console.print(f"  Images described: {result.images_described}")
    if result.images_skipped > 0:
        console.print(f"  Images skipped:  {result.images_skipped} (logos/signatures)")

    total_tokens = result.vision_prompt_tokens + result.vision_completion_tokens
    if total_tokens > 0:
        console.print(
            f"  AI tokens: {total_tokens:,} "
            f"(prompt: {result.vision_prompt_tokens:,}, "
            f"completion: {result.vision_completion_tokens:,})"
        )


def _print_reason_list(
    console: "Console",
    title: str,
    outcomes: Sequence[ConvertFileOutcome],
    root: Path,
) -> None:
    """Print a titled list of per-file outcomes with reasons, when non-empty."""
    if not outcomes:
        return
    console.print()
    console.print(f"  {title}:")
    for outcome in outcomes:
        console.print(f"    [dim]{_relative_display(outcome.path, root)}: {outcome.reason}[/dim]")


def _relative_display(path: Path, root: Path) -> str:
    """Render a path relative to the conversion root, falling back to its name."""
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.name
