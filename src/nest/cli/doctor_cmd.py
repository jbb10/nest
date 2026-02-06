"""Doctor command for nest CLI.

Handles the `nest doctor` command.
"""

from pathlib import Path

from nest.adapters.docling_downloader import DoclingModelDownloader
from nest.adapters.project_checker import ProjectChecker
from nest.services.doctor_service import DoctorService
from nest.ui.doctor_display import display_doctor_report
from nest.ui.messages import get_console


def create_doctor_service(project_checker: ProjectChecker) -> DoctorService:
    """Composition root for doctor service.

    Returns:
        Configured DoctorService.
    """
    return DoctorService(
        model_checker=DoclingModelDownloader(),
        project_checker=project_checker,
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


def doctor_command() -> None:
    """Validate development environment and project state.

    Checks Python version, uv installation, Nest version, and optionally
    project-specific validations if run inside a Nest project.

    Examples:
        nest doctor
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

    # Show hint when outside project
    if project_report is None:
        console.print("\n[dim]ℹ Run in a Nest project for full diagnostics[/dim]")
