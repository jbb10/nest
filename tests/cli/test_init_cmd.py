"""Tests for nest init CLI command."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from nest.cli.main import app
from nest.core.exceptions import ModelError, NestError

runner = CliRunner()


@patch("nest.cli.init_cmd.create_init_service")
def test_init_command_available_in_main_app(mock_create_service: MagicMock) -> None:
    """Verify init command is available in main app."""
    # Mock service to avoid real file operations
    mock_service = MagicMock()
    mock_create_service.return_value = mock_service

    result = runner.invoke(app, ["init", "Nike"])

    # Command should execute (even if it fails, it means it's registered)
    assert result.exit_code in [0, 1]  # 0 = success, 1 = expected error
    mock_create_service.assert_called_once()


@patch("nest.cli.init_cmd.create_init_service")
def test_init_success_output_format(mock_create_service: MagicMock, tmp_path: Path) -> None:
    """Verify success message format matches AC1."""
    # Mock service
    mock_service = MagicMock()
    mock_create_service.return_value = mock_service

    result = runner.invoke(app, ["init", "Nike", "--dir", str(tmp_path)])

    # Should show success (AC1)
    assert 'Project "Nike" initialized!' in result.output
    assert "Next steps:" in result.output
    assert "Drop your documents into raw_inbox/" in result.output
    assert "nest sync" in result.output
    assert "@nest in Copilot Chat" in result.output
    assert "Supported formats: PDF, DOCX, PPTX, XLSX, HTML" in result.output


@patch("nest.cli.init_cmd.create_init_service")
def test_init_error_already_exists(mock_create_service: MagicMock) -> None:
    """Verify error message format for existing project."""
    # Mock service to raise NestError
    mock_service = MagicMock()
    mock_service.execute.side_effect = NestError("Nest project already exists")
    mock_create_service.return_value = mock_service

    result = runner.invoke(app, ["init", "Nike"])

    # Should show error in What → Why → Action format
    assert result.exit_code == 1
    assert "already exists" in result.output.lower()
    assert "reason:" in result.output.lower()
    assert "action:" in result.output.lower()
    assert "nest sync" in result.output.lower()  # Should suggest using sync instead


@patch("nest.cli.init_cmd.create_init_service")
def test_init_error_model_download_failure(mock_create_service: MagicMock) -> None:
    """Verify error message format for model download failures."""
    # Mock service to raise ModelError
    mock_service = MagicMock()
    mock_service.execute.side_effect = ModelError("Network timeout after 3 retries")
    mock_create_service.return_value = mock_service

    result = runner.invoke(app, ["init", "Nike"])

    # Should show error in What → Why → Action format
    assert result.exit_code == 1
    assert "cannot download ml models" in result.output.lower()
    assert "reason:" in result.output.lower()
    assert "action:" in result.output.lower()
    assert "internet connection" in result.output.lower()


def test_no_duplicate_init_commands() -> None:
    """Verify only ONE init command exists in the app."""
    # Get all registered commands
    commands = list(app.registered_commands)

    # Count init commands (exclude _placeholder)
    init_commands = [cmd for cmd in commands if cmd.name == "init"]

    assert len(init_commands) == 1, f"Found {len(init_commands)} init commands, expected 1"


@patch("nest.cli.init_cmd.create_init_service")
def test_init_completes_all_steps_successfully(
    mock_create_service: MagicMock, tmp_path: Path
) -> None:
    """Verify init command completes all steps and shows success message."""
    # Mock service
    mock_service = MagicMock()
    mock_create_service.return_value = mock_service

    result = runner.invoke(app, ["init", "Nike", "--dir", str(tmp_path)])

    # Verify command completed successfully
    assert result.exit_code == 0
    # Verify success message appears (indicates all steps completed)
    assert 'Project "Nike" initialized!' in result.output
    # Verify service.execute was called with correct args
    mock_service.execute.assert_called_once()


@patch("nest.cli.init_cmd.create_init_service")
def test_init_error_missing_project_name(mock_create_service: MagicMock) -> None:
    """Verify error handling for missing project name (AC4)."""
    # Mock service to raise NestError for empty name
    mock_service = MagicMock()
    mock_service.execute.side_effect = NestError(
        "Project name required. Usage: nest init 'Project Name'"
    )
    mock_create_service.return_value = mock_service

    result = runner.invoke(app, ["init", ""])

    # Should show error in What → Why → Action format (AC4)
    assert result.exit_code == 1
    assert "project name required" in result.output.lower()
    assert "reason:" in result.output.lower()
    assert "action:" in result.output.lower()
