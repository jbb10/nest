"""Unit tests for doctor display."""

from io import StringIO

from rich.console import Console

from nest.services.doctor_service import EnvironmentReport, EnvironmentStatus
from nest.ui.doctor_display import display_doctor_report


class TestDoctorDisplay:
    """Tests for doctor output formatting."""

    def test_display_all_passing(self) -> None:
        """All passing checks should show green checkmarks."""
        report = EnvironmentReport(
            python=EnvironmentStatus("Python", "pass", "3.11.4"),
            uv=EnvironmentStatus("uv", "pass", "0.4.12"),
            nest=EnvironmentStatus("Nest", "pass", "1.0.0"),
        )

        output = StringIO()
        console = Console(file=output, force_terminal=True, width=120)

        display_doctor_report(report, console)

        result = output.getvalue()
        assert "Nest Doctor" in result
        assert "Python: 3.11.4" in result
        assert "uv: 0.4.12" in result
        assert "Nest: 1.0.0" in result

    def test_display_with_failure(self) -> None:
        """Failed checks should show red X."""
        report = EnvironmentReport(
            python=EnvironmentStatus(
                "Python",
                "fail",
                "3.9.1",
                message="requires 3.10+",
                suggestion="Upgrade Python to 3.10 or higher",
            ),
            uv=EnvironmentStatus("uv", "pass", "0.4.12"),
            nest=EnvironmentStatus("Nest", "pass", "1.0.0"),
        )

        output = StringIO()
        console = Console(file=output, force_terminal=True, width=120)

        display_doctor_report(report, console)

        result = output.getvalue()
        assert "Python: 3.9.1" in result
        assert "requires 3.10+" in result
        assert "Upgrade Python" in result

    def test_display_with_warning(self) -> None:
        """Warning checks should show yellow warning symbol."""
        report = EnvironmentReport(
            python=EnvironmentStatus("Python", "pass", "3.11.4"),
            uv=EnvironmentStatus(
                "uv",
                "warning",
                "found",
                message="version check failed",
            ),
            nest=EnvironmentStatus("Nest", "pass", "1.0.0"),
        )

        output = StringIO()
        console = Console(file=output, force_terminal=True, width=120)

        display_doctor_report(report, console)

        result = output.getvalue()
        assert "uv: found" in result
        assert "version check failed" in result

    def test_display_shows_suggestions(self) -> None:
        """Suggestions should appear as sub-items."""
        report = EnvironmentReport(
            python=EnvironmentStatus("Python", "pass", "3.11.4"),
            uv=EnvironmentStatus(
                "uv",
                "fail",
                "not found",
                suggestion="Install uv: https://docs.astral.sh/uv/",
            ),
            nest=EnvironmentStatus("Nest", "pass", "1.0.0"),
        )

        output = StringIO()
        console = Console(file=output, force_terminal=True, width=120)

        display_doctor_report(report, console)

        result = output.getvalue()
        assert "→" in result
        assert "astral.sh" in result
