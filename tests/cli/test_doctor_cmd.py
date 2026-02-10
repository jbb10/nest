"""Unit tests for doctor CLI command."""

import unittest.mock
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch

from rich.console import Console

from nest.adapters.project_checker import ProjectChecker
from nest.cli.doctor_cmd import _count_issues
from nest.services.doctor_service import (
    EnvironmentReport,
    EnvironmentStatus,
    ModelReport,
    ModelStatus,
    ProjectReport,
    ProjectStatus,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_env_report(
    python: str = "pass",
    uv: str = "pass",
    nest: str = "pass",
    python_msg: str | None = None,
) -> EnvironmentReport:
    return EnvironmentReport(
        python=EnvironmentStatus("Python", python, "3.11.4", message=python_msg),
        uv=EnvironmentStatus("uv", uv, "0.4.12"),
        nest=EnvironmentStatus("Nest", nest, "1.0.0"),
    )


def _make_model_report(cached: bool = True) -> ModelReport:
    return ModelReport(
        models=ModelStatus(
            cached=cached,
            size_bytes=1_800_000_000 if cached else None,
            cache_path=Path.home() / ".cache" / "docling" / "models",
            cache_status="exists" if cached else "not_created",
        ),
    )


def _make_project_report(
    manifest: str = "valid",
    agent: bool = True,
    folders: str = "intact",
) -> ProjectReport:
    return ProjectReport(
        status=ProjectStatus(
            manifest_status=manifest,
            manifest_version="1.0.0" if manifest == "valid" else None,
            current_version="1.0.0",
            agent_file_present=agent,
            folders_status=folders,
            suggestions=[],
        ),
    )


# ---------------------------------------------------------------------------
# _count_issues tests  (Task 8.1)
# ---------------------------------------------------------------------------

class TestCountIssues:
    """Tests for _count_issues helper."""

    def test_all_pass_returns_empty(self) -> None:
        """No issues when everything passes."""
        issues = _count_issues(
            _make_env_report(),
            _make_model_report(cached=True),
            _make_project_report(),
        )
        assert issues == []

    def test_env_failure_reported(self) -> None:
        """Environment failure appears in issue list."""
        issues = _count_issues(
            _make_env_report(python="fail", python_msg="requires 3.10+"),
            None,
            None,
        )
        assert len(issues) == 1
        assert "Python check failed" in issues[0]
        assert "requires 3.10+" in issues[0]

    def test_model_not_cached(self) -> None:
        """Missing ML models appear in issue list."""
        issues = _count_issues(
            _make_env_report(),
            _make_model_report(cached=False),
            None,
        )
        assert issues == ["ML models not cached"]

    def test_manifest_missing(self) -> None:
        """Missing manifest appears in issue list."""
        issues = _count_issues(
            _make_env_report(),
            None,
            _make_project_report(manifest="missing"),
        )
        assert "Manifest missing" in issues

    def test_manifest_invalid_json(self) -> None:
        """Invalid JSON manifest appears in issue list."""
        issues = _count_issues(
            _make_env_report(),
            None,
            _make_project_report(manifest="invalid_json"),
        )
        assert "Manifest has invalid JSON" in issues

    def test_agent_file_missing(self) -> None:
        """Missing agent file appears in issue list."""
        issues = _count_issues(
            _make_env_report(),
            None,
            _make_project_report(agent=False),
        )
        assert "Agent file missing" in issues

    def test_folders_both_missing(self) -> None:
        """Both folders missing appears in issue list."""
        issues = _count_issues(
            _make_env_report(),
            None,
            _make_project_report(folders="both_missing"),
        )
        assert "Project folders missing" in issues

    def test_folders_sources_missing(self) -> None:
        """Sources folder missing appears in issue list."""
        issues = _count_issues(
            _make_env_report(),
            None,
            _make_project_report(folders="sources_missing"),
        )
        assert "_nest_sources/ folder missing" in issues

    def test_folders_context_missing(self) -> None:
        """Context folder missing appears in issue list."""
        issues = _count_issues(
            _make_env_report(),
            None,
            _make_project_report(folders="context_missing"),
        )
        assert "_nest_context/ folder missing" in issues

    def test_multiple_issues(self) -> None:
        """Multiple issues from different categories detected."""
        issues = _count_issues(
            _make_env_report(),
            _make_model_report(cached=False),
            _make_project_report(manifest="missing", agent=False, folders="both_missing"),
        )
        assert len(issues) == 4
        assert "ML models not cached" in issues
        assert "Manifest missing" in issues
        assert "Agent file missing" in issues
        assert "Project folders missing" in issues

    def test_none_reports_returns_env_only(self) -> None:
        """None for model and project reports only checks env."""
        issues = _count_issues(_make_env_report(), None, None)
        assert issues == []

    def test_version_mismatch_reported(self) -> None:
        """Version mismatch appears in issue list."""
        issues = _count_issues(
            _make_env_report(),
            None,
            _make_project_report(manifest="version_mismatch"),
        )
        assert "Manifest version mismatch" in issues


# ---------------------------------------------------------------------------
# display_issue_summary tests  (Task 8.3)
# ---------------------------------------------------------------------------

class TestDisplayIssueSummary:
    """Tests for display_issue_summary."""

    def test_display_single_issue(self) -> None:
        """Single issue renders with singular label."""
        from nest.ui.doctor_display import display_issue_summary

        buf = StringIO()
        console = Console(file=buf, force_terminal=False, color_system=None, width=120)
        display_issue_summary(["ML models not cached"], console)
        output = buf.getvalue()

        assert "1 issue found:" in output
        assert "1. ML models not cached" in output
        assert "nest doctor --fix" in output

    def test_display_multiple_issues(self) -> None:
        """Multiple issues render with plural label and numbered list."""
        from nest.ui.doctor_display import display_issue_summary

        buf = StringIO()
        console = Console(file=buf, force_terminal=False, color_system=None, width=120)
        display_issue_summary(["ML models not cached", "Agent file missing"], console)
        output = buf.getvalue()

        assert "2 issues found:" in output
        assert "1. ML models not cached" in output
        assert "2. Agent file missing" in output


# ---------------------------------------------------------------------------
# display_success_message tests  (Task 8.4)
# ---------------------------------------------------------------------------

class TestDisplaySuccessMessage:
    """Tests for display_success_message."""

    def test_display_success(self) -> None:
        """Success message renders without fix mode suffix."""
        from nest.ui.doctor_display import display_success_message

        buf = StringIO()
        console = Console(file=buf, force_terminal=False, color_system=None, width=120)
        display_success_message(console)
        output = buf.getvalue()

        assert "All systems operational" in output
        assert "No repairs needed" not in output

    def test_display_success_fix_mode(self) -> None:
        """Success message with fix_mode=True includes 'No repairs needed.'"""
        from nest.ui.doctor_display import display_success_message

        buf = StringIO()
        console = Console(file=buf, force_terminal=False, color_system=None, width=120)
        display_success_message(console, fix_mode=True)
        output = buf.getvalue()

        assert "All systems operational" in output
        assert "No repairs needed" in output


# ---------------------------------------------------------------------------
# display_remediation_report tests  (Task 8.5)
# ---------------------------------------------------------------------------

class TestDisplayRemediationReport:
    """Tests for display_remediation_report."""

    def test_display_all_success(self) -> None:
        """All-success report shows resolved count."""
        from nest.services.doctor_service import RemediationReport, RemediationResult
        from nest.ui.doctor_display import display_remediation_report

        report = RemediationReport(results=[
            RemediationResult(
                "missing_folders", True, True,
                "Created folders: _nest_sources/, _nest_context/",
            ),
            RemediationResult(
                "missing_agent_file", True, True, "Agent file regenerated",
            ),
        ])
        buf = StringIO()
        console = Console(file=buf, force_terminal=False, color_system=None, width=120)
        display_remediation_report(report, console)
        output = buf.getvalue()

        assert "2 issues resolved" in output
        assert "Created folders" in output
        assert "Agent file regenerated" in output

    def test_display_partial_failure(self) -> None:
        """Partial failure report shows failure count."""
        from nest.services.doctor_service import RemediationReport, RemediationResult
        from nest.ui.doctor_display import display_remediation_report

        report = RemediationReport(results=[
            RemediationResult("missing_folders", True, True, "Created folders"),
            RemediationResult("corrupt_manifest", True, False, "Failed to rebuild manifest"),
        ])
        buf = StringIO()
        console = Console(file=buf, force_terminal=False, color_system=None, width=120)
        display_remediation_report(report, console)
        output = buf.getvalue()

        assert "1 fixes failed" in output
        assert "2 attempted" in output

    def test_display_nothing_attempted(self) -> None:
        """No-op when nothing was attempted."""
        from nest.services.doctor_service import RemediationReport
        from nest.ui.doctor_display import display_remediation_report

        report = RemediationReport(results=[])
        buf = StringIO()
        console = Console(file=buf, force_terminal=False, color_system=None, width=120)
        display_remediation_report(report, console)
        output = buf.getvalue()

        # Should produce no output (no header, no summary)
        assert output.strip() == ""


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
