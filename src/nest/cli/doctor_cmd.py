"""Doctor command for nest CLI.

Handles the `nest doctor` command.
"""

from pathlib import Path

from nest.adapters.docling_downloader import DoclingModelDownloader
from nest.services.doctor_service import DoctorService
from nest.ui.doctor_display import display_doctor_report
from nest.ui.messages import get_console


def create_doctor_service() -> DoctorService:
    """Composition root for doctor service.

    Returns:
        Configured DoctorService.
    """
    return DoctorService(model_checker=DoclingModelDownloader())


def doctor_command() -> None:
    """Validate development environment and project state.

    Checks Python version, uv installation, Nest version, and optionally
    project-specific validations if run inside a Nest project.

    Examples:
        nest doctor
    """
    console = get_console()

    service = create_doctor_service()
    env_report = service.check_environment()
    model_report = service.check_ml_models()

    display_doctor_report(env_report, console, model_report)

    # Check if we're in a project (optional)
    if not Path(".nest_manifest.json").exists():
        console.print("\n[dim]ℹ Run in a Nest project for full diagnostics[/dim]")
