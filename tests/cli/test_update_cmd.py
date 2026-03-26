"""Unit tests for update CLI command."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.exceptions import Exit as ClickExit
from rich.console import Console  # noqa: F401

from nest.cli.update_cmd import (
    _display_versions,
    _ensure_config,
    _handle_agent_migration,
    _prompt_for_version,
    _run_update,
    create_migration_service,
    create_update_service,
    update_command,
)
from nest.core.exceptions import ConfigError
from nest.core.models import (
    AgentMigrationCheckResult,
    AgentMigrationResult,
    UpdateCheckResult,
    UpdateResult,
    UserConfig,
)
from nest.services.agent_migration_service import AgentMigrationService
from nest.services.update_service import UpdateService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_config() -> UserConfig:
    """Create a minimal UserConfig for testing."""
    from datetime import datetime, timezone

    from nest.core.models import InstallConfig

    return UserConfig(
        install=InstallConfig(
            source="git+https://github.com/jbb10/nest",
            installed_version="1.0.0",
            installed_at=datetime.now(tz=timezone.utc),
        )
    )


def _make_check_result(
    current: str = "1.0.0",
    latest: str | None = "2.0.0",
    update_available: bool = True,
    versions: list[tuple[str, str]] | None = None,
) -> UpdateCheckResult:
    """Create an UpdateCheckResult for testing."""
    if versions is None:
        versions = [
            ("2.0.0", "(latest)"),
            ("1.0.0", "(installed)"),
            ("0.9.0", ""),
        ]
    return UpdateCheckResult(
        current_version=current,
        latest_version=latest,
        annotated_versions=versions,
        update_available=update_available,
        source="git+https://github.com/jbb10/nest",
    )


def _make_no_color_console() -> Console:
    """Create a console with no color for testing."""
    return Console(force_terminal=False, color_system=None, width=120)


# ---------------------------------------------------------------------------
# _ensure_config tests (Task 3.2, 3.3)
# ---------------------------------------------------------------------------


class TestEnsureConfig:
    """Tests for _ensure_config helper."""

    def test_returns_existing_config(self) -> None:
        """Existing config is returned without creating default."""
        adapter = MagicMock()
        existing = _make_config()
        adapter.load.return_value = existing

        result = _ensure_config(adapter)

        assert result is existing
        adapter.save.assert_not_called()

    @patch("nest.cli.update_cmd.create_default_config")
    def test_creates_default_when_none(self, mock_create: MagicMock) -> None:
        """Default config created and saved when load returns None."""
        adapter = MagicMock()
        adapter.load.return_value = None
        default_config = _make_config()
        mock_create.return_value = default_config

        result = _ensure_config(adapter)

        assert result is default_config
        adapter.save.assert_called_once_with(default_config)


# ---------------------------------------------------------------------------
# _display_versions tests (Task 3.4)
# ---------------------------------------------------------------------------


class TestDisplayVersions:
    """Tests for _display_versions helper."""

    def test_renders_version_list(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Version list shows current, latest, and all versions."""
        console = _make_no_color_console()
        check_result = _make_check_result()

        _display_versions(check_result, console)
        output = capsys.readouterr().out

        assert "Current version:" in output
        assert "1.0.0" in output
        assert "Latest version:" in output
        assert "2.0.0" in output
        assert "Available versions:" in output
        assert "(latest)" in output
        assert "(installed)" in output

    def test_renders_empty_versions(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Empty version list still renders headers."""
        console = _make_no_color_console()
        check_result = _make_check_result(
            latest=None,
            update_available=False,
            versions=[],
        )

        _display_versions(check_result, console)
        output = capsys.readouterr().out

        assert "Current version:" in output
        assert "Available versions:" in output


# ---------------------------------------------------------------------------
# update_command tests — --check flag (Task 3.5, 3.6)
# ---------------------------------------------------------------------------


class TestUpdateCheckFlag:
    """Tests for --check flag behavior."""

    @patch("nest.cli.update_cmd.create_migration_service")
    @patch("nest.cli.update_cmd.create_update_service")
    def test_check_up_to_date_exits_0(
        self, mock_create_update: MagicMock, mock_create_migration: MagicMock
    ) -> None:
        """--check with up-to-date version exits 0."""
        mock_service = MagicMock()
        mock_adapter = MagicMock()
        mock_adapter.load.return_value = _make_config()
        mock_service.check_for_updates.return_value = _make_check_result(
            current="2.0.0",
            latest="2.0.0",
            update_available=False,
            versions=[("2.0.0", "(installed) (latest)")],
        )
        mock_create_update.return_value = (mock_service, mock_adapter)

        with pytest.raises(ClickExit) as exc_info:
            update_command(check=True, target_dir=None)

        assert exc_info.value.exit_code == 0

    @patch("nest.cli.update_cmd.create_migration_service")
    @patch("nest.cli.update_cmd.create_update_service")
    def test_check_update_available_exits_1(
        self, mock_create_update: MagicMock, mock_create_migration: MagicMock
    ) -> None:
        """--check with update available exits 1."""
        mock_service = MagicMock()
        mock_adapter = MagicMock()
        mock_adapter.load.return_value = _make_config()
        mock_service.check_for_updates.return_value = _make_check_result()
        mock_create_update.return_value = (mock_service, mock_adapter)

        with pytest.raises(ClickExit) as exc_info:
            update_command(check=True, target_dir=None)

        assert exc_info.value.exit_code == 1


# ---------------------------------------------------------------------------
# update_command tests — already up-to-date (Task 3.7)
# ---------------------------------------------------------------------------


class TestUpdateAlreadyUpToDate:
    """Tests for already-up-to-date scenario."""

    @patch("nest.cli.update_cmd.create_migration_service")
    @patch("nest.cli.update_cmd.create_update_service")
    def test_already_up_to_date_shows_success(
        self,
        mock_create_update: MagicMock,
        mock_create_migration: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Already up-to-date shows success message and exits 0."""
        mock_service = MagicMock()
        mock_adapter = MagicMock()
        mock_adapter.load.return_value = _make_config()
        mock_service.check_for_updates.return_value = _make_check_result(
            current="2.0.0",
            latest="2.0.0",
            update_available=False,
            versions=[("2.0.0", "(installed) (latest)")],
        )
        mock_create_update.return_value = (mock_service, mock_adapter)

        with pytest.raises(ClickExit) as exc_info:
            update_command(check=False, target_dir=None)

        assert exc_info.value.exit_code == 0
        output = capsys.readouterr().out
        assert "Already up to date" in output


# ---------------------------------------------------------------------------
# update_command tests — network error (Task 3.8)
# ---------------------------------------------------------------------------


class TestUpdateNetworkError:
    """Tests for network error during version discovery."""

    @patch("nest.cli.update_cmd.create_migration_service")
    @patch("nest.cli.update_cmd.create_update_service")
    def test_network_error_shows_what_why_action(
        self,
        mock_create_update: MagicMock,
        mock_create_migration: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """ConfigError displays What → Why → Action and exits 1."""
        mock_service = MagicMock()
        mock_adapter = MagicMock()
        mock_adapter.load.return_value = _make_config()
        mock_service.check_for_updates.side_effect = ConfigError("network timeout")
        mock_create_update.return_value = (mock_service, mock_adapter)

        with pytest.raises(ClickExit) as exc_info:
            update_command(check=False, target_dir=None)

        assert exc_info.value.exit_code == 1
        output = capsys.readouterr().out
        assert "Cannot check for updates" in output


# ---------------------------------------------------------------------------
# update_command tests — no versions found (Task 3.9)
# ---------------------------------------------------------------------------


class TestUpdateNoVersions:
    """Tests for no versions found scenario."""

    @patch("nest.cli.update_cmd.create_migration_service")
    @patch("nest.cli.update_cmd.create_update_service")
    def test_no_versions_shows_info(
        self,
        mock_create_update: MagicMock,
        mock_create_migration: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Empty version list shows info message and exits 0."""
        mock_service = MagicMock()
        mock_adapter = MagicMock()
        mock_adapter.load.return_value = _make_config()
        mock_service.check_for_updates.return_value = _make_check_result(
            latest=None,
            update_available=False,
            versions=[],
        )
        mock_create_update.return_value = (mock_service, mock_adapter)

        with pytest.raises(ClickExit) as exc_info:
            update_command(check=False, target_dir=None)

        assert exc_info.value.exit_code == 0
        output = capsys.readouterr().out
        assert "No releases found" in output


# ---------------------------------------------------------------------------
# Successful update (Task 3.10)
# ---------------------------------------------------------------------------


class TestSuccessfulUpdate:
    """Tests for successful update flow."""

    @patch("nest.cli.update_cmd._handle_agent_migration")
    @patch("nest.cli.update_cmd.Prompt")
    @patch("nest.cli.update_cmd.create_migration_service")
    @patch("nest.cli.update_cmd.create_update_service")
    def test_successful_update_shows_success(
        self,
        mock_create_update: MagicMock,
        mock_create_migration: MagicMock,
        mock_prompt: MagicMock,
        mock_handle_migration: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Successful update displays spinner and success message."""
        mock_service = MagicMock()
        mock_adapter = MagicMock()
        mock_adapter.load.return_value = _make_config()
        mock_service.check_for_updates.return_value = _make_check_result()
        mock_service.execute_update.return_value = UpdateResult(
            success=True, version="2.0.0", previous_version="1.0.0"
        )
        mock_create_update.return_value = (mock_service, mock_adapter)
        mock_prompt.ask.return_value = "Y"

        update_command(check=False, target_dir=None)

        mock_service.execute_update.assert_called_once()
        output = capsys.readouterr().out
        assert "Updated to version 2.0.0" in output
        assert "CHANGELOG.md" in output


# ---------------------------------------------------------------------------
# Update failure (Task 3.11)
# ---------------------------------------------------------------------------


class TestUpdateFailure:
    """Tests for update failure scenario."""

    @patch("nest.cli.update_cmd.Prompt")
    @patch("nest.cli.update_cmd.create_migration_service")
    @patch("nest.cli.update_cmd.create_update_service")
    def test_update_failure_shows_error(
        self,
        mock_create_update: MagicMock,
        mock_create_migration: MagicMock,
        mock_prompt: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Failed update displays What → Why → Action and exits 1."""
        mock_service = MagicMock()
        mock_adapter = MagicMock()
        mock_adapter.load.return_value = _make_config()
        mock_service.check_for_updates.return_value = _make_check_result()
        mock_service.execute_update.return_value = UpdateResult(
            success=False,
            version="2.0.0",
            previous_version="1.0.0",
            error="uv tool install returned exit code 1",
        )
        mock_create_update.return_value = (mock_service, mock_adapter)
        mock_prompt.ask.return_value = "Y"

        with pytest.raises(ClickExit) as exc_info:
            update_command(check=False, target_dir=None)

        assert exc_info.value.exit_code == 1
        output = capsys.readouterr().out
        assert "Update failed" in output
        assert "uv tool install returned exit code 1" in output


# ---------------------------------------------------------------------------
# User cancellation (Task 3.12)
# ---------------------------------------------------------------------------


class TestUserCancellation:
    """Tests for user cancellation scenario."""

    @patch("nest.cli.update_cmd.Prompt")
    @patch("nest.cli.update_cmd.create_migration_service")
    @patch("nest.cli.update_cmd.create_update_service")
    def test_user_cancellation_exits_cleanly(
        self,
        mock_create_update: MagicMock,
        mock_create_migration: MagicMock,
        mock_prompt: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """User entering 'n' exits with code 0 and no update."""
        mock_service = MagicMock()
        mock_adapter = MagicMock()
        mock_adapter.load.return_value = _make_config()
        mock_service.check_for_updates.return_value = _make_check_result()
        mock_create_update.return_value = (mock_service, mock_adapter)
        mock_prompt.ask.return_value = "n"

        with pytest.raises(ClickExit) as exc_info:
            update_command(check=False, target_dir=None)

        assert exc_info.value.exit_code == 0
        mock_service.execute_update.assert_not_called()
        output = capsys.readouterr().out
        assert "Update cancelled" in output


# ---------------------------------------------------------------------------
# Agent migration prompt (Task 3.13)
# ---------------------------------------------------------------------------


class TestAgentMigrationPrompt:
    """Tests for agent migration prompt after update."""

    def test_migration_prompt_shown_when_needed(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Migration prompt shown when check returns migration_needed=True."""
        console = _make_no_color_console()
        mock_service = MagicMock()
        mock_service.check_migration_needed.return_value = AgentMigrationCheckResult(
            migration_needed=True,
            message="Agent files need updating (1 outdated)",
            outdated_files=["nest.agent.md"],
        )
        mock_service.execute_migration.return_value = AgentMigrationResult(
            success=True, files_replaced=["nest.agent.md"]
        )

        with patch("nest.cli.update_cmd.Confirm") as mock_confirm:
            mock_confirm.ask.return_value = True
            _handle_agent_migration(mock_service, Path("/tmp/project"), console)

        mock_service.execute_migration.assert_called_once_with(Path("/tmp/project"))
        output = capsys.readouterr().out
        assert "agent files updated" in output

    def test_migration_declined_shows_info(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Declining migration shows info message."""
        console = _make_no_color_console()
        mock_service = MagicMock()
        mock_service.check_migration_needed.return_value = AgentMigrationCheckResult(
            migration_needed=True,
            message="Agent files need updating (1 outdated)",
            outdated_files=["nest.agent.md"],
        )

        with patch("nest.cli.update_cmd.Confirm") as mock_confirm:
            mock_confirm.ask.return_value = False
            _handle_agent_migration(mock_service, Path("/tmp/project"), console)

        mock_service.execute_migration.assert_not_called()
        output = capsys.readouterr().out
        assert "Keeping existing agent files" in output

    def test_migration_up_to_date_no_prompt(self, capsys: pytest.CaptureFixture[str]) -> None:
        """No prompt when agent files are up to date (AC8)."""
        console = _make_no_color_console()
        mock_service = MagicMock()
        mock_service.check_migration_needed.return_value = AgentMigrationCheckResult(
            migration_needed=False,
            message="All agent files are up to date",
        )

        _handle_agent_migration(mock_service, Path("/tmp/project"), console)

        output = capsys.readouterr().out
        assert "All agent files are up to date" in output

    def test_file_level_detail_shown(self, capsys: pytest.CaptureFixture[str]) -> None:
        """AC6: Replace/Create labels shown for individual files."""
        console = _make_no_color_console()
        mock_service = MagicMock()
        mock_service.check_migration_needed.return_value = AgentMigrationCheckResult(
            migration_needed=True,
            agent_file_missing=True,
            message="Agent files need updating (1 outdated, 2 missing)",
            outdated_files=["nest.agent.md"],
            missing_files=["nest-master-researcher.agent.md", "nest-master-planner.agent.md"],
        )
        mock_service.execute_migration.return_value = AgentMigrationResult(
            success=True,
            files_replaced=["nest.agent.md"],
            files_created=["nest-master-researcher.agent.md", "nest-master-planner.agent.md"],
        )

        with patch("nest.cli.update_cmd.Confirm") as mock_confirm:
            mock_confirm.ask.return_value = True
            _handle_agent_migration(mock_service, Path("/tmp/project"), console)

        output = capsys.readouterr().out
        assert "Replace  nest.agent.md" in output
        assert "Create   nest-master-researcher.agent.md" in output
        assert "Create   nest-master-planner.agent.md" in output
        assert "3 agent files updated" in output


# ---------------------------------------------------------------------------
# Agent migration skipped (Task 3.14)
# ---------------------------------------------------------------------------


class TestAgentMigrationSkipped:
    """Tests for agent migration silently skipped."""

    def test_migration_skipped_silently(self, capsys: pytest.CaptureFixture[str]) -> None:
        """No output when migration is skipped (not a Nest project)."""
        console = _make_no_color_console()
        mock_service = MagicMock()
        mock_service.check_migration_needed.return_value = AgentMigrationCheckResult(
            migration_needed=False,
            skipped=True,
            message="Not a Nest project",
        )

        _handle_agent_migration(mock_service, Path("/tmp/not-a-project"), console)

        output = capsys.readouterr().out
        assert output.strip() == ""


# ---------------------------------------------------------------------------
# Agent migration failure (Task 3.15)
# ---------------------------------------------------------------------------


class TestAgentMigrationFailure:
    """Tests for agent migration failure handling."""

    def test_migration_failure_shows_warning(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Migration failure shows warning but doesn't raise."""
        console = _make_no_color_console()
        mock_service = MagicMock()
        mock_service.check_migration_needed.return_value = AgentMigrationCheckResult(
            migration_needed=True,
            message="Agent files need updating (1 outdated)",
            outdated_files=["nest.agent.md"],
        )
        mock_service.execute_migration.return_value = AgentMigrationResult(
            success=False, error="Permission denied"
        )

        with patch("nest.cli.update_cmd.Confirm") as mock_confirm:
            mock_confirm.ask.return_value = True
            _handle_agent_migration(mock_service, Path("/tmp/project"), console)

        output = capsys.readouterr().out
        assert "Agent file update failed" in output
        assert "Permission denied" in output


# ---------------------------------------------------------------------------
# --dir flag (Task 3.16)
# ---------------------------------------------------------------------------


class TestDirFlag:
    """Tests for --dir flag passing correct path."""

    @patch("nest.cli.update_cmd._handle_agent_migration")
    @patch("nest.cli.update_cmd.Prompt")
    @patch("nest.cli.update_cmd.create_migration_service")
    @patch("nest.cli.update_cmd.create_update_service")
    def test_dir_flag_passes_path(
        self,
        mock_create_update: MagicMock,
        mock_create_migration: MagicMock,
        mock_prompt: MagicMock,
        mock_handle_migration: MagicMock,
    ) -> None:
        """--dir flag passes the specified path to migration service."""
        mock_service = MagicMock()
        mock_adapter = MagicMock()
        mock_adapter.load.return_value = _make_config()
        mock_service.check_for_updates.return_value = _make_check_result()
        mock_service.execute_update.return_value = UpdateResult(
            success=True, version="2.0.0", previous_version="1.0.0"
        )
        mock_create_update.return_value = (mock_service, mock_adapter)
        mock_prompt.ask.return_value = "Y"

        custom_dir = Path("/custom/project")
        update_command(check=False, target_dir=custom_dir)

        mock_handle_migration.assert_called_once()
        call_args = mock_handle_migration.call_args
        assert call_args[0][1] == custom_dir


# ---------------------------------------------------------------------------
# Composition root (Task 3.17)
# ---------------------------------------------------------------------------


class TestCompositionRoot:
    """Tests for composition root functions."""

    def test_create_update_service_returns_tuple(self) -> None:
        """create_update_service returns (UpdateService, UserConfigAdapter)."""
        from nest.adapters.user_config import UserConfigAdapter as UCA

        service, adapter = create_update_service()

        assert isinstance(service, UpdateService)
        assert isinstance(adapter, UCA)

    def test_create_migration_service_returns_service(self) -> None:
        """create_migration_service returns AgentMigrationService."""
        service = create_migration_service()

        assert isinstance(service, AgentMigrationService)


# ---------------------------------------------------------------------------
# _prompt_for_version tests
# ---------------------------------------------------------------------------


class TestPromptForVersion:
    """Tests for version prompt handling."""

    def test_y_returns_latest(self) -> None:
        """Entering Y returns latest version."""
        console = _make_no_color_console()
        check_result = _make_check_result()

        with patch("nest.cli.update_cmd.Prompt") as mock_prompt:
            mock_prompt.ask.return_value = "Y"
            result = _prompt_for_version(check_result, console)

        assert result == "2.0.0"

    def test_n_returns_none(self) -> None:
        """Entering n returns None (cancellation)."""
        console = _make_no_color_console()
        check_result = _make_check_result()

        with patch("nest.cli.update_cmd.Prompt") as mock_prompt:
            mock_prompt.ask.return_value = "n"
            result = _prompt_for_version(check_result, console)

        assert result is None

    def test_specific_version_returned(self) -> None:
        """Entering a specific version returns it."""
        console = _make_no_color_console()
        check_result = _make_check_result()

        with patch("nest.cli.update_cmd.Prompt") as mock_prompt:
            mock_prompt.ask.return_value = "1.5.0"
            result = _prompt_for_version(check_result, console)

        assert result == "1.5.0"

    def test_v_prefix_stripped(self) -> None:
        """Entering v-prefixed version strips the v."""
        console = _make_no_color_console()
        check_result = _make_check_result()

        with patch("nest.cli.update_cmd.Prompt") as mock_prompt:
            mock_prompt.ask.return_value = "v1.5.0"
            result = _prompt_for_version(check_result, console)

        assert result == "1.5.0"


# ---------------------------------------------------------------------------
# _run_update tests
# ---------------------------------------------------------------------------


class TestRunUpdate:
    """Tests for _run_update helper."""

    def test_run_update_calls_service(self) -> None:
        """_run_update passes correct args to service."""
        console = _make_no_color_console()
        mock_service = MagicMock()
        expected_result = UpdateResult(success=True, version="2.0.0", previous_version="1.0.0")
        mock_service.execute_update.return_value = expected_result
        check_result = _make_check_result()

        result = _run_update(mock_service, "2.0.0", check_result, console)

        assert result is expected_result
        mock_service.execute_update.assert_called_once_with(
            "2.0.0",
            ["2.0.0", "1.0.0", "0.9.0"],
            "git+https://github.com/jbb10/nest",
        )


# ---------------------------------------------------------------------------
# Agent migration — missing file creates it (AC7 variant)
# ---------------------------------------------------------------------------


class TestAgentMigrationMissingFile:
    """Tests for agent migration when files are missing."""

    def test_missing_agent_file_prompt(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Missing agent files shows create prompt."""
        console = _make_no_color_console()
        mock_service = MagicMock()
        mock_service.check_migration_needed.return_value = AgentMigrationCheckResult(
            migration_needed=True,
            agent_file_missing=True,
            message="Agent files need updating (4 missing)",
            missing_files=[
                "nest.agent.md",
                "nest-master-researcher.agent.md",
                "nest-master-synthesizer.agent.md",
                "nest-master-planner.agent.md",
            ],
        )
        mock_service.execute_migration.return_value = AgentMigrationResult(
            success=True,
            files_created=[
                "nest.agent.md",
                "nest-master-researcher.agent.md",
                "nest-master-synthesizer.agent.md",
                "nest-master-planner.agent.md",
            ],
        )

        with patch("nest.cli.update_cmd.Confirm") as mock_confirm:
            mock_confirm.ask.return_value = True
            _handle_agent_migration(mock_service, Path("/tmp/project"), console)

        output = capsys.readouterr().out
        assert "4 agent files updated" in output
