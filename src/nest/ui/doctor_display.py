"""Rich doctor display helpers.

Responsible for rendering environment validation reports to the terminal.
"""

from __future__ import annotations

from rich.console import Console
from rich.tree import Tree

from nest.services.doctor_service import EnvironmentReport, EnvironmentStatus


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


def display_doctor_report(report: EnvironmentReport, console: Console) -> None:
    """Render an EnvironmentReport to the console.

    Args:
        report: Environment validation report.
        console: Rich console instance.
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

    console.print(tree)
    console.print()
