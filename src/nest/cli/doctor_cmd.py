"""Doctor command for nest CLI.

Handles the `nest doctor` command.
"""

from pathlib import Path

import typer
from rich.prompt import Confirm

from nest.adapters.filesystem import FileSystemAdapter
from nest.adapters.git_client import GitClientAdapter
from nest.adapters.manifest import ManifestAdapter
from nest.adapters.project_checker import ProjectChecker
from nest.adapters.protocols import ModelCacheProtocol
from nest.adapters.user_config import UserConfigAdapter
from nest.agents.vscode_writer import VSCodeAgentWriter
from nest.core.exceptions import ModelError
from nest.core.project_layout import detect_project
from nest.services.doctor_service import DoctorService, list_issues
from nest.ui.command import current_output
from nest.ui.doctor_display import (
    display_doctor_report,
    display_issue_summary,
    display_remediation_report,
    display_success_message,
)
from nest.ui.messages import get_console


def create_doctor_service(project_checker: ProjectChecker) -> DoctorService:
    """Composition root for doctor service.

    Returns:
        Configured DoctorService.
    """
    try:
        from nest.adapters.docling_downloader import DoclingModelDownloader

        model_checker: ModelCacheProtocol | None = DoclingModelDownloader()
        # Eagerly verify docling is importable
        model_checker.get_cache_path()
    except (ImportError, ModelError):
        model_checker = None

    filesystem = FileSystemAdapter()
    return DoctorService(
        model_checker=model_checker,
        project_checker=project_checker,
        manifest_adapter=ManifestAdapter(),
        filesystem=filesystem,
        agent_writer=VSCodeAgentWriter(filesystem),
        git_client=GitClientAdapter(),
        user_config=UserConfigAdapter(),
    )


def doctor_command(
    fix: bool = typer.Option(False, "--fix", help="Automatically fix detected issues"),
) -> None:
    """Validate development environment and project state.

    Checks Python version, uv installation, Nest version, and optionally
    project-specific validations if run inside a Nest project.

    \b
    Examples:
        nest doctor
        nest doctor --fix
    """
    console = get_console()
    ui = current_output()

    ui.stage("Checking environment")
    project_checker = ProjectChecker()
    service = create_doctor_service(project_checker)
    env_report = service.check_environment()
    ui.stage("Checking conversion models")
    model_report = service.check_ml_models()

    # Check if we're in a Nest project
    project_dir = Path.cwd()
    if detect_project(project_dir).is_nest_project:
        ui.stage("Checking project")
        project_report = service.check_project(project_dir)
    else:
        project_report = None

    # Detect issues
    issues = list_issues(env_report, model_report, project_report)

    ui.pause()
    display_doctor_report(env_report, console, model_report, project_report)

    if issues:
        display_issue_summary(issues, console)

        if fix:
            # Auto-fix mode (AC4)
            console.print("\n🔧 [bold]Attempting repairs...[/bold]\n")
            ui.stage("Repairing environment")
            remediation_report = service.remediate_issues_auto(
                project_dir, env_report, model_report, project_report
            )
            ui.finish(failed=not remediation_report.all_succeeded)
            display_remediation_report(remediation_report, console)

            # Exit code 1 if any fix failed (AC5)
            if not remediation_report.all_succeeded:
                raise typer.Exit(code=1)

        elif console.is_terminal:

            def confirm_repair(message: str) -> bool:
                ui.pause()
                confirmed = Confirm.ask(message)
                ui.stage("Repairing environment")
                return confirmed

            # Interactive mode — prompt for repair (AC8)
            if Confirm.ask("Attempt automatic repair?", default=False):
                console.print()
                ui.stage("Repairing environment")
                remediation_report = service.remediate_issues_interactive(
                    project_dir,
                    env_report,
                    model_report,
                    project_report,
                    confirm_callback=confirm_repair,
                )
                ui.finish(failed=not remediation_report.all_succeeded)
                display_remediation_report(remediation_report, console)

                # Exit code 1 if any fix failed (AC5)
                if not remediation_report.all_succeeded:
                    raise typer.Exit(code=1)
        # Non-interactive mode without --fix: issue summary already shown

    elif fix:
        # --fix with no issues (AC6)
        display_success_message(console, fix_mode=True)
    else:
        # All pass (AC3)
        display_success_message(console)

    # Show hint when outside project
    if project_report is None:
        console.print("\n[dim]ℹ Run in a Nest project for full diagnostics[/dim]")
