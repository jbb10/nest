"""Sync command for nest CLI.

Handles the `nest sync` command with flags for error handling,
dry-run, force reprocessing, and orphan cleanup control.
"""

from pathlib import Path
import logging
from typing import TYPE_CHECKING, Annotated, Literal

import typer

from nest.adapters.docling_processor import DoclingProcessor
from nest.adapters.file_discovery import FileDiscoveryAdapter
from nest.adapters.filesystem import FileSystemAdapter
from nest.adapters.manifest import ManifestAdapter
from nest.core.exceptions import NestError, ProcessingError
from nest.core.models import DryRunResult, OrphanCleanupResult
from nest.services.discovery_service import DiscoveryService
from nest.services.index_service import IndexService
from nest.services.manifest_service import ManifestService
from nest.services.orphan_service import OrphanService
from nest.services.output_service import OutputMirrorService
from nest.services.sync_service import SyncService
from nest.ui.logger import log_processing_error, setup_error_logger
from nest.ui.messages import error, get_console, info, success, warning

if TYPE_CHECKING:
    from rich.console import Console


def create_sync_service(
    project_root: Path,
    error_logger: "logging.Logger | logging.LoggerAdapter | None" = None,  # type: ignore[type-arg]
) -> SyncService:
    """Composition root for sync service.

    Args:
        project_root: Root directory of the project.
        error_logger: Logger for writing errors to .nest_errors.log.

    Returns:
        Configured SyncService with real adapters.
    """
    filesystem = FileSystemAdapter()
    manifest_adapter = ManifestAdapter()
    processor = DoclingProcessor()

    raw_inbox = project_root / "raw_inbox"
    output_dir = project_root / "processed_context"

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
    """Sync documents from raw_inbox to processed_context.

    Processes PDF, DOCX, PPTX, XLSX, and HTML files from raw_inbox/
    and converts them to Markdown in processed_context/.

    Examples:
        nest sync
        nest sync --dry-run
        nest sync --force
        nest sync --on-error=fail
    """
    console = get_console()
    project_root = (target_dir or Path.cwd()).resolve()

    # Validate flags
    validated_on_error = _validate_on_error(on_error)

    # Setup error logger
    error_log_path = project_root / ".nest_errors.log"
    error_logger = setup_error_logger(error_log_path, service_name="sync")

    try:
        service = create_sync_service(project_root, error_logger=error_logger)

        # Execute sync with flags
        result = service.sync(
            no_clean=no_clean,
            on_error=validated_on_error,
            dry_run=dry_run,
            force=force,
        )

        # Handle dry-run result
        if isinstance(result, DryRunResult):
            _display_dry_run_result(result, console)
            return

        # Normal sync complete - display summary
        _display_sync_summary(result, console, error_log_path)

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


def _display_sync_summary(
    result: "OrphanCleanupResult", console: "Console", error_log_path: Path
) -> None:
    """Display sync completion summary.

    Args:
        result: OrphanCleanupResult from sync.
        console: Rich console for output.
        error_log_path: Path to error log file.
    """
    success("Sync complete")
    console.print()

    # Show orphan info if any
    orphan_count = len(result.orphans_removed)
    if orphan_count > 0:
        info(f"Orphans: {orphan_count} removed")
    elif result.skipped and len(result.orphans_detected) > 0:
        warning(f"Orphans: {len(result.orphans_detected)} detected (not removed)")

    # Check if error log has content
    if error_log_path.exists() and error_log_path.stat().st_size > 0:
        console.print()
        warning(f"Some files failed (see {error_log_path})")
