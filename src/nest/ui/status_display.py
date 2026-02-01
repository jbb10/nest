"""Rich status display helpers.

Responsible for rendering a StatusReport to the terminal.
"""

from __future__ import annotations

from datetime import datetime, timezone

from rich.console import Console
from rich.tree import Tree

from nest.services.status_service import StatusReport


def format_relative_time(dt: datetime | None) -> str:
    """Format datetime as a human-readable relative time string.

    Args:
        dt: Timestamp to format.

    Returns:
        Relative time string (e.g., "2 hours ago", "never").
    """

    if dt is None:
        return "never"

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    delta = datetime.now(timezone.utc) - dt.astimezone(timezone.utc)
    seconds = delta.total_seconds()

    if seconds < 60:
        return "just now"
    if seconds < 3600:
        minutes = int(seconds // 60)
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    if seconds < 86400:
        hours = int(seconds // 3600)
        return f"{hours} hour{'s' if hours != 1 else ''} ago"

    days = int(seconds // 86400)
    return f"{days} day{'s' if days != 1 else ''} ago"


def display_status(report: StatusReport, console: Console) -> None:
    """Render a StatusReport to the console.

    Args:
        report: Computed project status.
        console: Rich console instance.
    """

    tree = Tree(f"📁 Project: [bold]{report.project_name}[/bold]")
    tree.add(f"Nest Version: {report.nest_version}")

    sources = tree.add("Sources")
    sources.add(f"Total files: [bold]{report.source_total}[/bold]")
    sources.add(f"New: [yellow]{report.source_new}[/yellow]")
    sources.add(f"Modified: [yellow]{report.source_modified}[/yellow]")
    sources.add(f"Unchanged: [green]{report.source_unchanged}[/green]")

    context = tree.add("Context")
    context.add(f"Files: [bold]{report.context_files}[/bold]")
    context.add(f"Orphaned: [red]{report.context_orphaned}[/red]")
    context.add(f"Last sync: {format_relative_time(report.last_sync)}")

    console.print()
    console.print(tree)
    console.print()

    if report.pending_count == 0 and report.context_orphaned == 0:
        console.print("[green]✓[/green] All files up to date")
        return

    if report.pending_count > 0:
        console.print(f"Run `nest sync` to process {report.pending_count} pending files")
        return

    # No pending work, but orphans exist
    console.print(f"Run `nest sync` to remove {report.context_orphaned} orphaned files")
