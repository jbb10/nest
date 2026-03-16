"""Sync command for nest CLI.

Handles the `nest sync` command with flags for error handling,
dry-run, force reprocessing, and orphan cleanup control.
"""

import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Literal

import typer

from nest.adapters.file_discovery import FileDiscoveryAdapter
from nest.adapters.filesystem import FileSystemAdapter
from nest.adapters.manifest import ManifestAdapter
from nest.adapters.passthrough_processor import PassthroughProcessor
from nest.core.exceptions import NestError, ProcessingError
from nest.core.models import DryRunResult, ProcessingResult, SyncResult
from nest.core.paths import (
    AI_SEEN_MARKER,
    CONTEXT_DIR,
    ERROR_LOG_FILENAME,
    NEST_META_DIR,
    SOURCES_DIR,
)
from nest.services.discovery_service import DiscoveryService
from nest.services.index_service import IndexService
from nest.services.manifest_service import ManifestService
from nest.services.metadata_service import MetadataExtractorService
from nest.services.orphan_service import OrphanService
from nest.services.output_service import OutputMirrorService
from nest.services.sync_service import SyncService
from nest.ui.logger import setup_error_logger
from nest.ui.messages import error, get_console, success
from nest.ui.progress import SyncProgress

if TYPE_CHECKING:
    from rich.console import Console


class NoOpProcessor:
    """Fallback processor when docling is missing."""

    def process(self, source: Path, output: Path) -> ProcessingResult:
        """Fail all processing."""
        return ProcessingResult(
            source_path=source,
            status="failed",
            error="Docling is not installed",
        )


def create_sync_service(
    project_root: Path,
    error_logger: "logging.Logger | logging.LoggerAdapter[logging.Logger] | None" = None,
    no_ai: bool = False,
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
        no_ai: If True, skip AI enrichment even when API key is configured.

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

    # AI enrichment (optional)
    ai_enrichment = None
    ai_glossary = None
    if not no_ai:
        from nest.adapters.llm_provider import create_llm_provider

        llm_provider = create_llm_provider()
        if llm_provider is not None:
            from nest.services.ai_enrichment_service import AIEnrichmentService

            ai_enrichment = AIEnrichmentService(llm_provider=llm_provider)

            from nest.services.ai_glossary_service import AIGlossaryService

            ai_glossary = AIGlossaryService(
                llm_provider=llm_provider,
                filesystem=filesystem,
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
        ai_enrichment=ai_enrichment,
        ai_glossary=ai_glossary,
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
    no_ai: Annotated[
        bool,
        typer.Option(
            "--no-ai",
            help="Skip AI enrichment even when API key is configured",
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

    Processes PDF, DOCX, PPTX, XLSX, and HTML files from _nest_sources/
    and converts them to Markdown in _nest_context/.

    Examples:
        nest sync
        nest sync --dry-run
        nest sync --force
        nest sync --on-error=fail
    """
    console = get_console()
    project_root = (target_dir or Path.cwd()).resolve()

    # AC3: Check for Nest project (manifest must exist)
    manifest_path = project_root / NEST_META_DIR / "manifest.json"
    if not manifest_path.exists():
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
        service = create_sync_service(project_root, error_logger=error_logger, no_ai=no_ai)

        # 1. Discovery phase
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
            _display_dry_run_result(result, console)  # type: ignore[arg-type]
            return

        # Calculate total for progress using discovered changes
        files_to_process_count = len(changes.new_files) + len(changes.modified_files)

        # Detect AI env var key for first-run message
        ai_detected_key = ""
        if not no_ai:
            if os.environ.get("NEST_AI_API_KEY"):
                ai_detected_key = "NEST_AI_API_KEY"
            elif os.environ.get("OPENAI_API_KEY"):
                ai_detected_key = "OPENAI_API_KEY"

        # AI progress callback for console display
        def ai_progress_callback(message: str) -> None:
            if message == "start":
                console.print("  🤖 AI enrichment...", end="")
            else:
                console.print(f" {message}")

        # Execute sync with progress bar
        with SyncProgress(console=console, disabled=files_to_process_count == 0) as progress:
            progress.start(total=files_to_process_count)

            result = service.sync(
                no_clean=no_clean,
                on_error=validated_on_error,
                dry_run=False,
                force=force,
                progress_callback=progress.advance,
                ai_progress_callback=ai_progress_callback,
                changes=changes,
            )

        # Normal sync complete - display summary
        _display_sync_summary(
            result,  # type: ignore[arg-type]
            console,
            error_log_path,
            ai_detected_key=ai_detected_key,
            project_root=project_root,
        )

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
    ai_detected_key: str = "",
    project_root: Path | None = None,
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
        ai_detected_key: Name of the env var that triggered AI (e.g., ``"OPENAI_API_KEY"``).
        project_root: Project root directory for marker file operations.
    """
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

    # Aggregated AI token display
    total_prompt = result.ai_prompt_tokens + result.ai_glossary_prompt_tokens
    total_completion = result.ai_completion_tokens + result.ai_glossary_completion_tokens
    total_tokens = total_prompt + total_completion

    if total_tokens > 0:
        console.print(
            f"  AI tokens:    {total_tokens:,} "
            f"(prompt: {total_prompt:,}, completion: {total_completion:,})"
        )

    # Show AI activity counts (enrichment + glossary) on separate detail lines
    if result.ai_files_enriched > 0:
        console.print(f"  AI enriched:  {result.ai_files_enriched} descriptions")

    if result.ai_glossary_terms_added > 0:
        console.print(f"  AI glossary:  {result.ai_glossary_terms_added} terms defined")

    # First-run AI discovery message
    ai_was_used = (
        result.ai_files_enriched > 0
        or result.ai_glossary_terms_added > 0
        or (result.ai_prompt_tokens + result.ai_glossary_prompt_tokens) > 0
    )

    if ai_was_used and ai_detected_key and project_root is not None:
        ai_marker = project_root / NEST_META_DIR / AI_SEEN_MARKER
        if not ai_marker.exists():
            console.print()
            console.print(f"  🤖 AI enrichment enabled (found {ai_detected_key})")
            console.print("  💡 Run 'nest config ai' to change AI settings. Use --no-ai to skip.")
            # Create marker file
            ai_marker.touch()
