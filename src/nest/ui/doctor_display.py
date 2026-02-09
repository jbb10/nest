"""Rich doctor display helpers.

Responsible for rendering environment validation reports to the terminal.
"""

from __future__ import annotations

from rich.console import Console
from rich.tree import Tree

from nest.services.doctor_service import (
    EnvironmentReport,
    EnvironmentStatus,
    ModelReport,
    ProjectReport,
    RemediationReport,
)


def _format_status_indicator(status: EnvironmentStatus) -> str:
    """Format status indicator with color.

    Args:
        status: Environment status to format.

    Returns:
        Colored status indicator string.
    """
    if status.status == "pass":
        return "[green]✓[/green]"
    elif status.status == "fail":
        return "[red]✗[/red]"
    else:  # warning
        return "[yellow]⚠[/yellow]"


def _format_status_line(status: EnvironmentStatus) -> str:
    """Format a status line with name, value, and indicator.

    Args:
        status: Environment status to format.

    Returns:
        Formatted status line.
    """
    indicator = _format_status_indicator(status)
    base = f"{status.name}: {status.current_value} {indicator}"

    if status.message:
        base += f" [dim]({status.message})[/dim]"

    return base


def format_size(size_bytes: int) -> str:
    """Format bytes as human-readable size.

    Args:
        size_bytes: Size in bytes.

    Returns:
        Human-readable string (e.g., "1.8 GB", "892 MB").
    """
    size = float(size_bytes)
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            if unit in ["B", "KB"]:
                return f"{int(size)} {unit}"
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def display_model_report(report: ModelReport, tree: Tree) -> None:
    """Render a ModelReport to the tree.

    Args:
        report: Model validation report.
        tree: Rich tree to add model section to.
    """
    models = tree.add("ML Models")

    # Models status line
    if report.models.cached:
        size_str = format_size(report.models.size_bytes) if report.models.size_bytes else "unknown"
        models_line = f"Models: cached [green]✓[/green] [dim]({size_str})[/dim]"
    else:
        models_line = "Models: not found [red]✗[/red]"

    models_node = models.add(models_line)

    # Add suggestion if models not cached
    if report.models.suggestion:
        models_node.add(f"→ {report.models.suggestion}")

    # Cache path with status
    cache_path_str = str(report.models.cache_path)
    if report.models.cache_status == "not_created":
        cache_line = f"Cache path: {cache_path_str} [dim](not created)[/dim]"
    elif report.models.cache_status == "empty":
        cache_line = f"Cache path: {cache_path_str} [dim](empty)[/dim]"
    else:
        cache_line = f"Cache path: {cache_path_str}"

    models.add(cache_line)


def display_project_report(report: ProjectReport, tree: Tree) -> None:
    """Render a ProjectReport to the tree.

    Args:
        report: Project validation report.
        tree: Rich tree to add project section to.
    """
    project = tree.add("Project")
    status = report.status

    # Manifest status line
    if status.manifest_status == "valid":
        manifest_line = "Manifest: valid [green]✓[/green]"
    elif status.manifest_status == "missing":
        manifest_line = "Manifest: missing [red]✗[/red]"
    elif status.manifest_status == "invalid_json":
        manifest_line = "Manifest: invalid JSON [red]✗[/red]"
    elif status.manifest_status == "invalid_structure":
        manifest_line = "Manifest: invalid structure [red]✗[/red]"
    else:  # version_mismatch
        manifest_line = (
            f"Manifest: v{status.manifest_version} [yellow]⚠[/yellow] "
            "[dim](migration available)[/dim]"
        )

    manifest_node = project.add(manifest_line)

    # Agent file status
    if status.agent_file_present:
        agent_line = "Agent file: present [green]✓[/green]"
    else:
        agent_line = "Agent file: missing [red]✗[/red]"

    agent_node = project.add(agent_line)

    # Folders status
    if status.folders_status == "intact":
        folders_line = "Folders: intact [green]✓[/green]"
    elif status.folders_status == "sources_missing":
        folders_line = "Folders: _nest_sources/ missing [red]✗[/red]"
    elif status.folders_status == "context_missing":
        folders_line = "Folders: _nest_context/ missing [red]✗[/red]"
    else:  # both_missing
        folders_line = "Folders: both missing [red]✗[/red]"

    folders_node = project.add(folders_line)

    # Add suggestions to appropriate nodes
    for suggestion in status.suggestions:
        suggestion_lower = suggestion.lower()
        if "agent" in suggestion_lower:
            agent_node.add(f"→ {suggestion}")
        elif "folder" in suggestion_lower or "_nest_" in suggestion_lower:
            folders_node.add(f"→ {suggestion}")
        else:
            manifest_node.add(f"→ {suggestion}")


def display_doctor_report(
    report: EnvironmentReport,
    console: Console,
    model_report: ModelReport | None = None,
    project_report: ProjectReport | None = None,
) -> None:
    """Render an EnvironmentReport to the console.

    Args:
        report: Environment validation report.
        console: Rich console instance.
        model_report: Optional ML model validation report.
        project_report: Optional project validation report.
    """
    console.print()
    tree = Tree("🩺 [bold]Nest Doctor[/bold]")

    env = tree.add("Environment")

    # Python
    python_node = env.add(_format_status_line(report.python))
    if report.python.suggestion:
        python_node.add(f"→ {report.python.suggestion}")

    # uv
    uv_node = env.add(_format_status_line(report.uv))
    if report.uv.suggestion:
        uv_node.add(f"→ {report.uv.suggestion}")

    # Nest
    nest_node = env.add(_format_status_line(report.nest))
    if report.nest.suggestion:
        nest_node.add(f"→ {report.nest.suggestion}")

    # ML Models section (if report provided)
    if model_report:
        display_model_report(model_report, tree)

    # Project section (if report provided)
    if project_report:
        display_project_report(project_report, tree)

    console.print(tree)
    console.print()


def display_remediation_report(
    report: RemediationReport,
    console: Console,
) -> None:
    """Render a RemediationReport to the console.

    Args:
        report: Remediation validation report.
        console: Rich console instance.
    """
    if not report.any_attempted:
        return

    # Display results with [•] prefix per AC7
    for result in report.results:
        if not result.attempted:
            console.print(f"   [dim]○[/dim] {result.message}")
            continue

        if result.success:
            console.print(f"   [•] {result.message} [green]✓[/green]")
        else:
            console.print(f"   [•] {result.message} [red]✗[/red]")

    attempted_count = len([r for r in report.results if r.attempted])
    failed_count = len([r for r in report.results if r.attempted and not r.success])

    if report.all_succeeded:
        console.print(
            f"\n   [green]{attempted_count} issues resolved.[/green] Run `nest doctor` to verify."
        )
    else:
        console.print(
            f"\n   [yellow]{failed_count} fixes failed[/yellow] out of {attempted_count} attempted."
        )
