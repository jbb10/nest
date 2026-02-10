"""Doctor command for nest CLI.

Handles the `nest doctor` command.
"""

from pathlib import Path

import typer
from rich.prompt import Confirm, Prompt

from nest.adapters.filesystem import FileSystemAdapter
from nest.adapters.manifest import ManifestAdapter
from nest.adapters.project_checker import ProjectChecker
from nest.agents.vscode_writer import VSCodeAgentWriter
from nest.services.doctor_service import (
    DoctorService,
    EnvironmentReport,
    ModelReport,
    ProjectReport,
)
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
    from nest.adapters.docling_downloader import DoclingModelDownloader

    filesystem = FileSystemAdapter()
    return DoctorService(
        model_checker=DoclingModelDownloader(),
        project_checker=project_checker,
        manifest_adapter=ManifestAdapter(),
        filesystem=filesystem,
        agent_writer=VSCodeAgentWriter(filesystem),
    )


def _count_issues(
    env_report: EnvironmentReport,
    model_report: ModelReport | None,
    project_report: ProjectReport | None,
) -> list[str]:
    """Count and describe all detected issues.

    Args:
        env_report: Environment validation report.
        model_report: ML model validation report (if available).
        project_report: Project state validation report (if available).

    Returns:
        List of issue description strings. Empty if all pass.
    """
    issues: list[str] = []

    # Environment failures
    for check in [env_report.python, env_report.uv, env_report.nest]:
        if check.status == "fail":
            msg = f"{check.name} check failed"
            if check.message:
                msg += f" ({check.message})"
            issues.append(msg)

    # ML model issues
    if model_report and not model_report.all_pass:
        issues.append("ML models not cached")

    # Project issues
    if project_report:
        status = project_report.status
        if status.manifest_status != "valid":
            label_map = {
                "missing": "Manifest missing",
                "invalid_json": "Manifest has invalid JSON",
                "invalid_structure": "Manifest has invalid structure",
                "version_mismatch": "Manifest version mismatch",
            }
            issues.append(label_map.get(status.manifest_status, "Manifest issue"))
        if not status.agent_file_present:
            issues.append("Agent file missing")
        if status.folders_status != "intact":
            folder_map = {
                "sources_missing": "_nest_sources/ folder missing",
                "context_missing": "_nest_context/ folder missing",
                "both_missing": "Project folders missing",
            }
            issues.append(folder_map.get(status.folders_status, "Folders issue"))

    return issues


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

    # Detect issues
    issues = _count_issues(env_report, model_report, project_report)

    display_doctor_report(env_report, console, model_report, project_report)

    if issues:
        display_issue_summary(issues, console)

        if fix:
            # Auto-fix mode (AC4)
            console.print("\n🔧 [bold]Attempting repairs...[/bold]\n")
            remediation_report = service.remediate_issues_auto(
                project_dir, env_report, model_report, project_report
            )
            display_remediation_report(remediation_report, console)

            # Exit code 1 if any fix failed (AC5)
            if not remediation_report.all_succeeded:
                raise typer.Exit(code=1)

        elif console.is_terminal:
            # Interactive mode — prompt for repair (AC8)
            if Confirm.ask("Attempt automatic repair?", default=False):
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
