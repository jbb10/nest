"""Doctor command for nest CLI.

Handles the `nest doctor` command.
"""

from pathlib import Path

import typer
from rich.prompt import Confirm, Prompt

from nest.adapters.docling_downloader import DoclingModelDownloader
from nest.adapters.filesystem import FileSystemAdapter
from nest.adapters.manifest import ManifestAdapter
from nest.adapters.project_checker import ProjectChecker
from nest.agents.vscode_writer import VSCodeAgentWriter
from nest.services.doctor_service import DoctorService
from nest.ui.doctor_display import display_doctor_report, display_remediation_report
from nest.ui.messages import get_console


def create_doctor_service(project_checker: ProjectChecker) -> DoctorService:
    """Composition root for doctor service.

    Returns:
        Configured DoctorService.
    """
    filesystem = FileSystemAdapter()
    return DoctorService(
        model_checker=DoclingModelDownloader(),
        project_checker=project_checker,
        manifest_adapter=ManifestAdapter(),
        filesystem=filesystem,
        agent_writer=VSCodeAgentWriter(filesystem),
    )


def _is_nest_project(project_dir: Path, project_checker: ProjectChecker) -> bool:
    """Check whether a directory looks like a Nest project.

    Args:
        project_dir: Directory to check.
        project_checker: Project checker adapter.

    Returns:
        True if any Nest project markers exist, False otherwise.
    """
    return (
        project_checker.manifest_exists(project_dir)
        or project_checker.agent_file_exists(project_dir)
        or project_checker.source_folder_exists(project_dir)
        or project_checker.context_folder_exists(project_dir)
    )


def doctor_command(
    fix: bool = typer.Option(False, "--fix", help="Automatically fix detected issues"),
) -> None:
    """Validate development environment and project state.

    Checks Python version, uv installation, Nest version, and optionally
    project-specific validations if run inside a Nest project.

    Examples:
        nest doctor
        nest doctor --fix
    """
    console = get_console()

    project_checker = ProjectChecker()
    service = create_doctor_service(project_checker)
    env_report = service.check_environment()
    model_report = service.check_ml_models()

    # Check if we're in a Nest project
    project_dir = Path.cwd()
    if _is_nest_project(project_dir, project_checker):
        project_report = service.check_project(project_dir)
    else:
        project_report = None

    display_doctor_report(env_report, console, model_report, project_report)

    # Handle remediation if --fix flag or if issues detected
    has_issues = False
    if model_report and not model_report.all_pass:
        has_issues = True
    if project_report and not project_report.all_pass:
        has_issues = True

    if has_issues:
        if fix:
            # Auto-fix mode
            console.print("\n🔧 [bold]Attempting repairs...[/bold]\n")
            remediation_report = service.remediate_issues_auto(
                project_dir, env_report, model_report, project_report
            )
            display_remediation_report(remediation_report, console)

            # Exit code 1 if any fix failed (AC8)
            if not remediation_report.all_succeeded:
                raise typer.Exit(code=1)

        elif console.is_terminal:
            # Interactive mode - prompt for repair
            console.print()
            if Confirm.ask("⚠ Issues detected. Attempt automatic repair?"):
                console.print()
                remediation_report = service.remediate_issues_interactive(
                    project_dir,
                    env_report,
                    model_report,
                    project_report,
                    confirm_callback=lambda msg: Confirm.ask(msg),
                    input_callback=lambda msg: Prompt.ask(msg),
                )
                display_remediation_report(remediation_report, console)

                # Exit code 1 if any fix failed (AC8)
                if not remediation_report.all_succeeded:
                    raise typer.Exit(code=1)
        # Non-interactive mode without --fix: just show report (no prompt)

    # Show hint when outside project
    if project_report is None:
        console.print("\n[dim]ℹ Run in a Nest project for full diagnostics[/dim]")
