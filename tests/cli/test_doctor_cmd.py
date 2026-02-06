"""Unit tests for doctor CLI command."""

import unittest.mock
from pathlib import Path
from unittest.mock import MagicMock, patch

from nest.adapters.project_checker import ProjectChecker
from nest.services.doctor_service import EnvironmentReport, EnvironmentStatus


class TestDoctorCommand:
    """Tests for doctor CLI command."""

    def test_doctor_command_composition_root(self) -> None:
        """Doctor command composition root should create service."""
        from nest.cli.doctor_cmd import create_doctor_service

        project_checker = ProjectChecker()
        service = create_doctor_service(project_checker)

        assert service is not None
        assert hasattr(service, "check_environment")
        assert hasattr(service, "check_project")

    def test_doctor_command_callable(self) -> None:
        """Doctor command function should be callable."""
        from nest.cli.doctor_cmd import doctor_command

        assert callable(doctor_command)

    def test_doctor_executes_service(self) -> None:
        """Doctor should call service and display report."""
        mock_report = EnvironmentReport(
            python=EnvironmentStatus("Python", "pass", "3.11.4"),
            uv=EnvironmentStatus("uv", "pass", "0.4.12"),
            nest=EnvironmentStatus("Nest", "pass", "1.0.0"),
        )
        mock_model_report = MagicMock()

        with patch("nest.cli.doctor_cmd.DoctorService") as MockService:
            with patch("nest.cli.doctor_cmd.display_doctor_report") as mock_display:
                with patch("nest.cli.doctor_cmd.ProjectChecker"):
                    mock_service = MockService.return_value
                    mock_service.check_environment.return_value = mock_report
                    mock_service.check_ml_models.return_value = mock_model_report
                    mock_service.check_project.return_value = None

                    from nest.cli.doctor_cmd import doctor_command

                    doctor_command()

                    mock_service.check_environment.assert_called_once()
                    mock_service.check_ml_models.assert_called_once()
                    mock_display.assert_called_once_with(
                        mock_report,
                        unittest.mock.ANY,
                        mock_model_report,
                        None,
                    )

    def test_doctor_shows_outside_project_message(self, tmp_path: Path) -> None:
        """Doctor should show message when run outside project."""
        mock_report = EnvironmentReport(
            python=EnvironmentStatus("Python", "pass", "3.11.4"),
            uv=EnvironmentStatus("uv", "pass", "0.4.12"),
            nest=EnvironmentStatus("Nest", "pass", "1.0.0"),
        )

        with patch("nest.cli.doctor_cmd.DoctorService") as MockService:
            with patch("nest.cli.doctor_cmd.display_doctor_report"):
                with patch("nest.cli.doctor_cmd.Path.exists", return_value=False):
                    with patch("nest.cli.doctor_cmd.get_console") as mock_console:
                        mock_service = MockService.return_value
                        mock_service.check_environment.return_value = mock_report

                        from nest.cli.doctor_cmd import doctor_command

                        doctor_command()

                        # Verify console.print was called with outside project message
                        console = mock_console.return_value
                        calls = [str(call) for call in console.print.call_args_list]
                        assert any("full diagnostics" in str(call).lower() for call in calls)
