"""Sync command for nest CLI.

Handles the `nest sync` command with flags for error handling,
dry-run, force reprocessing, and orphan cleanup control.
"""

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Literal

import typer

from nest.adapters.docling_processor import DoclingProcessor
from nest.adapters.file_discovery import FileDiscoveryAdapter
from nest.adapters.filesystem import FileSystemAdapter
from nest.adapters.manifest import ManifestAdapter
from nest.core.exceptions import NestError, ProcessingError
from nest.core.models import DryRunResult, SyncResult
from nest.core.paths import CONTEXT_DIR, SOURCES_DIR
from nest.services.discovery_service import DiscoveryService
from nest.services.index_service import IndexService
from nest.services.manifest_service import ManifestService
from nest.services.orphan_service import OrphanService
from nest.services.output_service import OutputMirrorService
from nest.services.sync_service import SyncService
from nest.ui.logger import log_processing_error, setup_error_logger
from nest.ui.messages import error, get_console, success
from nest.ui.progress import SyncProgress

if TYPE_CHECKING:
    from rich.console import Console


def create_sync_service(
    project_root: Path,
    error_logger: "logging.Logger | logging.LoggerAdapter[logging.Logger] | None" = None,
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
        error_logger: Logger for writing errors to .nest_errors.log.

    Returns:
        Configured SyncService with real adapters.
    """
    # Adapters: External system wrappers
    filesystem = FileSystemAdapter()
    manifest_adapter = ManifestAdapter()
    processor = DoclingProcessor()

    # Project paths
    raw_inbox = project_root / SOURCES_DIR
    output_dir = project_root / CONTEXT_DIR

    # Wire up services with their dependencies
    return SyncService(
        discovery=DiscoveryService(
            file_discovery=FileDiscoveryAdapter(),
            manifest=manifest_adapter,
        ),
        output=OutputMirrorService(
            filesystem=filesystem,
            processor=processor,
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
        project_root=project_root,
        error_logger=error_logger,
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
    manifest_path = project_root / ".nest_manifest.json"
    if not manifest_path.exists():
        error("No Nest project found")
        console.print(f"  Reason: .nest_manifest.json not found in {project_root}")
        console.print('  Action: Run `nest init "Project Name"` to initialize')
        raise typer.Exit(1)

    # Validate flags
    validated_on_error = _validate_on_error(on_error)

    # Setup error logger
    error_log_path = project_root / ".nest_errors.log"
    # cast is needed because LoggerAdapter generic handling varies by python version
    error_logger = setup_error_logger(error_log_path, service_name="sync")

    try:
        service = create_sync_service(project_root, error_logger=error_logger)

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

        # Execute sync with progress bar
        with SyncProgress(console=console, disabled=files_to_process_count == 0) as progress:
            progress.start(total=files_to_process_count)

            result = service.sync(
                no_clean=no_clean,
                on_error=validated_on_error,
                dry_run=False,
                force=force,
                progress_callback=progress.advance,
                changes=changes,
            )

        # Normal sync complete - display summary
        _display_sync_summary(result, console, error_log_path)  # type: ignore[arg-type]

    except ProcessingError as e:
        # Fail mode triggered - error already logged by SyncService
        # Log to file if source_path available (for fail-fast abort)
        if e.source_path:
            log_processing_error(error_logger, e.source_path, e.message)
        error("Sync aborted due to processing failure")
        console.print(f"  [dim]Reason: {e.message}[/dim]")
        console.print(f"  [dim]See {error_log_path} for details[/dim]")
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


def _display_sync_summary(result: SyncResult, console: "Console", error_log_path: Path) -> None:
    """Display sync completion summary.

    Shows:
    ✓ Sync complete

      Processed: 15 files
      Skipped:   32 unchanged
      Failed:    2 (see .nest_errors.log)
      Orphans:   3 removed



    Args:
        result: SyncResult from sync with all counts.
        console: Rich console for output.
        error_log_path: Path to error log file.
    """
    success("Sync complete")
    console.print()

    # Show processing counts
    console.print(f"  Processed: {result.processed_count} files")
    console.print(f"  Skipped:   {result.skipped_count} unchanged")

    # Show failed count with error log reference
    if result.failed_count > 0:
        console.print(f"  Failed:    {result.failed_count} (see {error_log_path.name})")
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
    console.print("  Index updated: 00_MASTER_INDEX.md")
