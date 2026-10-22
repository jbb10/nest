"""Sync command for nest CLI.

Handles the `nest sync` command with flags for error handling,
dry-run, force reprocessing, and orphan cleanup control.
"""

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Literal

import typer

from nest.adapters.classification_processor import create_classification_processor
from nest.adapters.file_discovery import FileDiscoveryAdapter
from nest.adapters.filesystem import FileSystemAdapter
from nest.adapters.llm_provider import resolve_llm_config
from nest.adapters.manifest import ManifestAdapter
from nest.adapters.noop_processor import NoOpProcessor
from nest.adapters.passthrough_processor import PassthroughProcessor
from nest.core.exceptions import NestError, ProcessingError
from nest.core.models import DryRunResult, SyncResult
from nest.core.paths import (
    CONTEXT_DIR,
    ERROR_LOG_FILENAME,
    LEGACY_LLM_SEEN_MARKER,
    LLM_SEEN_MARKER,
    NEST_META_DIR,
    SOURCES_DIR,
)
from nest.core.project_layout import detect_project
from nest.services.discovery_service import DiscoveryService
from nest.services.index_service import IndexService
from nest.services.manifest_service import ManifestService
from nest.services.metadata_service import MetadataExtractorService
from nest.services.orphan_service import OrphanService
from nest.services.output_service import OutputMirrorService
from nest.services.sync_service import SyncService
from nest.ui.command import current_output
from nest.ui.logger import setup_error_logger
from nest.ui.messages import (
    LLM_DISABLED_NOTE,
    LLM_NOT_CONFIGURED_NOTE,
    display_path,
    error,
    get_console,
    print_needs_llm_block,
    success,
)

if TYPE_CHECKING:
    from rich.console import Console

    from nest.adapters.llm_provider import LLMConfig


def create_sync_service(
    project_root: Path,
    error_logger: "logging.Logger | logging.LoggerAdapter[logging.Logger] | None" = None,
    no_llm: bool = False,
    llm_config: "LLMConfig | None" = None,
) -> SyncService:
    """Composition root for sync service.

    This is the dependency injection entry point for the sync command.
    All adapters are wired here and injected into services.

    Adapter wiring:
        - FileSystemAdapter: Real filesystem operations (read/write/delete)
        - ManifestAdapter: JSON manifest persistence
        - DoclingProcessor: Document processing (PDF/DOCX/PPTX/XLSX → Markdown)
        - FileDiscoveryAdapter: Filesystem scanning for document files

    Service wiring:
        - DiscoveryService: File discovery + checksum comparison
        - OutputMirrorService: Document processing + output file creation
        - ManifestService: Manifest state tracking
        - OrphanService: Orphan detection and cleanup
        - IndexService: Master index generation

    Flag flow (handled by sync_command, passed to service.sync()):
        - on_error: Error handling strategy (skip/fail)
        - dry_run: Preview mode without modifications
        - force: Reprocess all files regardless of checksum
        - no_clean: Skip orphan removal

    Args:
        project_root: Root directory of the project.
        error_logger: Logger for writing errors to .nest/errors.log.
        no_llm: If True, skip LLM enrichment even when API key is configured.
        llm_config: Pre-resolved LLM configuration; resolved from the environment when omitted.

    Returns:
        Configured SyncService with real adapters.
    """
    # Adapters: External system wrappers
    try:
        from nest.adapters.docling_processor import DoclingProcessor

        processor = DoclingProcessor()
    except ImportError:
        processor = NoOpProcessor()

    filesystem = FileSystemAdapter()
    manifest_adapter = ManifestAdapter()

    # Project paths
    raw_inbox = project_root / SOURCES_DIR
    output_dir = project_root / CONTEXT_DIR

    # LLM enrichment and vision (optional, independent of each other)
    llm_enrichment = None
    llm_glossary = None
    vision_docling_processor = None
    picture_description_service = None
    if not no_llm:
        from nest.adapters.llm_provider import (
            create_llm_provider,
            create_vision_provider,
            resolve_llm_config,
        )

        llm_config = llm_config or resolve_llm_config()
        llm_provider = create_llm_provider(llm_config) if llm_config else None
        if llm_provider is not None:
            from nest.services.llm_enrichment_service import LLMEnrichmentService

            llm_enrichment = LLMEnrichmentService(llm_provider=llm_provider)

            from nest.services.llm_glossary_service import LLMGlossaryService

            llm_glossary = LLMGlossaryService(
                llm_provider=llm_provider,
                filesystem=filesystem,
            )

        vision_provider = create_vision_provider(llm_config) if llm_config else None
        if vision_provider is not None:
            vision_docling_processor = create_classification_processor()

            from nest.services.picture_description_service import PictureDescriptionService

            picture_description_service = PictureDescriptionService(vision_provider=vision_provider)

    image_docling_processor = (
        create_classification_processor() if vision_docling_processor is None else None
    )

    # Wire up services with their dependencies
    return SyncService(
        discovery=DiscoveryService(
            file_discovery=FileDiscoveryAdapter(),
            manifest=manifest_adapter,
        ),
        output=OutputMirrorService(
            filesystem=filesystem,
            processor=processor,
            passthrough_processor=PassthroughProcessor(),
        ),
        manifest=ManifestService(
            manifest=manifest_adapter,
            project_root=project_root,
            raw_inbox=raw_inbox,
            output_dir=output_dir,
        ),
        orphan=OrphanService(
            filesystem=filesystem,
            manifest=manifest_adapter,
            project_root=project_root,
        ),
        index=IndexService(
            filesystem=filesystem,
            project_root=project_root,
        ),
        metadata=MetadataExtractorService(
            filesystem=filesystem,
            project_root=project_root,
        ),
        project_root=project_root,
        error_logger=error_logger,
        llm_enrichment=llm_enrichment,
        llm_glossary=llm_glossary,
        picture_description_service=picture_description_service,
        vision_docling_processor=vision_docling_processor,
        image_docling_processor=image_docling_processor,
    )


def _validate_on_error(value: str) -> Literal["skip", "fail"]:
    """Validate --on-error value.

    Args:
        value: Value from CLI.

    Returns:
        Validated literal value.

    Raises:
        typer.BadParameter: If value is not 'skip' or 'fail'.
    """
    if value not in ("skip", "fail"):
        raise typer.BadParameter("Must be 'skip' or 'fail'")
    return value  # type: ignore[return-value]


def sync_command(
    on_error: Annotated[
        str,
        typer.Option(
            "--on-error",
            help="Error handling: 'skip' to continue, 'fail' to abort",
        ),
    ] = "skip",
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run",
            help="Preview what would be processed without making changes",
        ),
    ] = False,
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            help="Reprocess all files regardless of checksum",
        ),
    ] = False,
    no_clean: Annotated[
        bool,
        typer.Option(
            "--no-clean",
            help="Detect orphans but don't remove them",
        ),
    ] = False,
    no_llm: Annotated[
        bool,
        typer.Option(
            "--no-llm",
            help="Skip LLM enrichment even when API key is configured",
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
    target_dir: Annotated[
        Path | None,
        typer.Option(
            "--dir",
            "-d",
            help="Target directory for sync operation",
        ),
    ] = None,
) -> None:
    """Sync documents from sources to context directory.

    Processes PDF, DOCX, PPTX, XLSX, HTML, and image files from _nest_sources/
    and converts them to Markdown in _nest_context/.

    \b
    Examples:
        nest sync
        nest sync --dry-run
        nest sync --force
        nest sync --on-error=fail
    """
    console = get_console()

    ui = current_output()

    project_root = (target_dir or Path.cwd()).resolve()
    ui.root = project_root

    if not detect_project(project_root).initialized:
        error("No Nest project found")
        console.print(f"  Reason: .nest/manifest.json not found in {project_root}")
        console.print('  Action: Run `nest init "Project Name"` to initialize')
        raise typer.Exit(1)

    # Validate flags
    validated_on_error = _validate_on_error(on_error)

    # Setup error logger
    error_log_path = project_root / NEST_META_DIR / ERROR_LOG_FILENAME
    # Ensure .nest/ directory exists for log file
    error_log_path.parent.mkdir(parents=True, exist_ok=True)
    # cast is needed because LoggerAdapter generic handling varies by python version
    error_logger = setup_error_logger(error_log_path, service_name="sync")

    try:
        llm_config = None if no_llm else resolve_llm_config()
        service = create_sync_service(
            project_root, error_logger=error_logger, no_llm=no_llm, llm_config=llm_config
        )

        # 1. Discovery phase
        ui.stage("Discovering documents")
        changes = service.discover(force=force)

        # For dry-run, no progress bar needed
        if dry_run:
            result = service.sync(
                no_clean=no_clean,
                on_error=validated_on_error,
                dry_run=True,
                force=force,
                changes=changes,
            )
            ui.finish()
            _display_dry_run_result(result, console)  # type: ignore[arg-type]
            return

        # Calculate total for progress using discovered changes
        files_to_process_count = len(changes.new_files) + len(changes.modified_files)

        llm_detected_key = llm_config.api_key_var if llm_config else ""

        llm_status_note = ""
        if no_llm:
            llm_status_note = LLM_DISABLED_NOTE
        elif not llm_detected_key:
            llm_status_note = LLM_NOT_CONFIGURED_NOTE

        # LLM progress callback for console display
        def llm_progress_callback(message: str) -> None:
            if message == "start":
                ui.stage("Generating document descriptions and glossary")

        # Execute sync with progress bar
        ui.start(files_to_process_count)
        result = service.sync(
            no_clean=no_clean,
            on_error=validated_on_error,
            dry_run=False,
            force=force,
            progress_callback=ui.advance,
            llm_progress_callback=llm_progress_callback,
            activity_callback=ui.activity,
            changes=changes,
        )
        assert isinstance(result, SyncResult)
        ui.finish(failed=result.failed_count > 0)

        # Normal sync complete - display summary
        _display_sync_summary(
            result,  # type: ignore[arg-type]
            console,
            error_log_path,
            llm_detected_key=llm_detected_key,
            llm_status_note=llm_status_note,
            project_root=project_root,
            has_warnings=ui.has_warnings,
        )
        if result.failed_count:
            raise typer.Exit(1)

    except ProcessingError as e:
        # Fail mode triggered - error already logged by SyncService
        error("Sync aborted due to processing failure")
        console.print(f"  [dim]Reason: {e.message}[/dim]")
        console.print(f"  [dim]See .nest/{ERROR_LOG_FILENAME} for details[/dim]")
        raise typer.Exit(1) from None

    except NestError as e:
        error("Sync failed")
        console.print(f"  [dim]Reason: {e}[/dim]")
        raise typer.Exit(1) from None


def _display_dry_run_result(result: DryRunResult, console: "Console") -> None:
    """Display dry-run preview output.

    Args:
        result: DryRunResult with counts.
        console: Rich console for output.
    """
    console.print()
    console.print("[bold cyan]🔍 Dry Run Preview[/bold cyan]")
    console.print()
    console.print(f"  Would process: {result.new_count} new, {result.modified_count} modified")
    console.print(f"  Would skip:    {result.unchanged_count} unchanged")
    console.print(f"  Would remove:  {result.orphan_count} orphans")
    console.print()
    console.print("[dim]Run without --dry-run to execute.[/dim]")


def _display_sync_summary(
    result: SyncResult,
    console: "Console",
    error_log_path: Path,
    llm_detected_key: str = "",
    llm_status_note: str = "",
    project_root: Path | None = None,
    has_warnings: bool = False,
) -> None:
    """Display sync completion summary.

    Shows:
    ✓ Sync complete

      Processed: 15 files
      Skipped:   32 unchanged
      Failed:    2 (see .nest/errors.log)
      Orphans:   3 removed



    Args:
        result: SyncResult from sync with all counts.
        console: Rich console for output.
        error_log_path: Path to error log file.
        llm_detected_key: Name of the env var that triggered LLM (e.g., ``"OPENAI_API_KEY"``).
        llm_status_note: Optional human-readable LLM status note for disabled or unconfigured cases.
        project_root: Project root directory for marker file operations.
    """
    if result.failed_count:
        error("Sync finished with failures")
    elif has_warnings:
        console.print("Sync complete with warnings", style="yellow")
    else:
        success("Sync complete")
    console.print()

    # Show processing counts
    console.print(f"  Processed: {result.processed_count} files")
    console.print(f"  Skipped:   {result.skipped_count} unchanged")

    # Show failed count with error log reference
    if result.failed_count > 0:
        log_relative = f"{NEST_META_DIR}/{ERROR_LOG_FILENAME}"
        console.print(f"  Failed:    {result.failed_count} (see {log_relative})")
    else:
        console.print(f"  Failed:    {result.failed_count}")
    for source, reason in result.failure_reasons.items():
        console.print(f"    {display_path(Path(source), project_root)}: {reason}", markup=False)
    print_needs_llm_block(
        console,
        [display_path(Path(source), project_root) for source in result.needs_llm_files],
        llm_disabled=llm_status_note == LLM_DISABLED_NOTE,
        command="nest sync",
    )

    # Show orphan info
    if result.orphans_removed > 0:
        console.print(f"  Orphans:   {result.orphans_removed} removed")
    elif result.skipped_orphan_cleanup and result.orphans_detected > 0:
        console.print(f"  Orphans:   {result.orphans_detected} detected (not removed)")
    else:
        console.print(f"  Orphans:   {result.orphans_detected} detected")

    # Show user-curated file count
    if result.user_curated_count > 0:
        console.print(f"  User-curated: {result.user_curated_count} preserved")

    console.print()
    console.print("  Index updated: .nest/00_MASTER_INDEX.md")

    if llm_status_note:
        console.print(f"  LLM:           {llm_status_note}")

    # Aggregated LLM token display
    total_prompt = (
        result.llm_prompt_tokens + result.llm_glossary_prompt_tokens + result.vision_prompt_tokens
    )
    total_completion = (
        result.llm_completion_tokens
        + result.llm_glossary_completion_tokens
        + result.vision_completion_tokens
    )
    total_tokens = total_prompt + total_completion

    if total_tokens > 0:
        console.print(
            f"  LLM tokens:    {total_tokens:,} "
            f"(prompt: {total_prompt:,}, completion: {total_completion:,})"
        )

    # Show LLM activity counts (enrichment + glossary) on separate detail lines
    if result.llm_files_enriched > 0:
        console.print(f"  LLM enriched:  {result.llm_files_enriched} descriptions")

    if result.llm_glossary_terms_added > 0:
        console.print(f"  LLM glossary:  {result.llm_glossary_terms_added} terms defined")

    # Show image description counts
    if result.images_described > 0:
        mermaid_note = (
            f" ({result.images_mermaid} as Mermaid diagrams)" if result.images_mermaid > 0 else ""
        )
        console.print(f"  Images described: {result.images_described}{mermaid_note}")
    if result.images_skipped > 0:
        console.print(f"  Images skipped:  {result.images_skipped} (logos/signatures)")
    if result.images_failed > 0:
        console.print(f"  Image descriptions failed: {result.images_failed}")

    # First-run LLM discovery message
    llm_was_used = (
        result.llm_files_enriched > 0
        or result.llm_glossary_terms_added > 0
        or (result.llm_prompt_tokens + result.llm_glossary_prompt_tokens) > 0
        or result.images_described > 0
        or result.vision_prompt_tokens > 0
    )

    if llm_was_used and llm_detected_key and project_root is not None:
        meta_dir = project_root / NEST_META_DIR
        llm_marker = meta_dir / LLM_SEEN_MARKER
        legacy_marker = meta_dir / LEGACY_LLM_SEEN_MARKER
        if legacy_marker.exists() and not llm_marker.exists():
            legacy_marker.rename(llm_marker)
        if not llm_marker.exists():
            console.print()
            console.print(f"  🤖 LLM enrichment enabled (found {llm_detected_key})")
            console.print(
                "  💡 Run 'nest config llm' to change LLM settings. Use --no-llm to skip."
            )
            # Create marker file
            llm_marker.touch()
