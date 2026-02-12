"""Tests for UpdateService.

Covers AC1-AC5, AC7-AC10: Version checking, update execution,
cancellation, validation, subprocess failure, and edge cases.
"""

import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest

from nest.core.exceptions import ConfigError
from nest.core.models import InstallConfig, UpdateCheckResult, UserConfig
from nest.services.update_service import UpdateService

# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------

_DEFAULT_SOURCE = "git+https://github.com/jbjornsson/nest"


def _make_config(
    version: str = "1.0.0",
    source: str = _DEFAULT_SOURCE,
) -> UserConfig:
    return UserConfig(
        install=InstallConfig(
            source=source,
            installed_version=version,
            installed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
    )


class MockGitClient:
    def __init__(self, tags: list[str] | None = None) -> None:
        self.tags = tags or []
        self.called_with: str | None = None

    def list_tags(self, remote_url: str) -> list[str]:
        self.called_with = remote_url
        return self.tags


class MockUserConfig:
    def __init__(self, config: UserConfig | None = None) -> None:
        self.config = config
        self.saved: UserConfig | None = None

    def load(self) -> UserConfig | None:
        return self.config

    def save(self, config: UserConfig) -> None:
        self.saved = config

    def config_path(self) -> Path:
        return Path("/mock/.config/nest/config.toml")


class MockSubprocessRunner:
    def __init__(
        self,
        *,
        raise_error: Exception | None = None,
    ) -> None:
        self.calls: list[list[str]] = []
        self._raise_error = raise_error

    def run(
        self,
        args: list[str],
        *,
        timeout: int | None = None,
    ) -> subprocess.CompletedProcess[str]:
        self.calls.append(args)
        if self._raise_error:
            raise self._raise_error
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")


# ---------------------------------------------------------------------------
# AC1: Version Display — check_for_updates returns correct UpdateCheckResult
# ---------------------------------------------------------------------------


class TestCheckForUpdates:
    """AC1: check_for_updates returns UpdateCheckResult with annotated versions."""

    def test_returns_update_check_result(self) -> None:
        config = _make_config(version="1.0.0")
        git = MockGitClient(tags=["v1.2.0", "v1.1.0", "v1.0.0"])
        service = UpdateService(git, MockUserConfig(config), MockSubprocessRunner())

        result = service.check_for_updates()

        assert isinstance(result, UpdateCheckResult)
        assert result.current_version == "1.0.0"
        assert result.latest_version == "1.2.0"
        assert result.update_available is True
        assert result.source == _DEFAULT_SOURCE

    def test_annotated_versions_correct(self) -> None:
        config = _make_config(version="1.1.0")
        git = MockGitClient(tags=["v1.2.0", "v1.1.0", "v1.0.0"])
        service = UpdateService(git, MockUserConfig(config), MockSubprocessRunner())

        result = service.check_for_updates()

        assert result.annotated_versions == [
            ("1.2.0", "(latest)"),
            ("1.1.0", "(installed)"),
            ("1.0.0", ""),
        ]

    def test_uses_source_url_from_config(self) -> None:
        custom_source = "git+https://github.com/custom/repo"
        config = _make_config(source=custom_source)
        git = MockGitClient(tags=["v1.0.0"])
        service = UpdateService(git, MockUserConfig(config), MockSubprocessRunner())

        result = service.check_for_updates()

        assert git.called_with == custom_source
        assert result.source == custom_source


# ---------------------------------------------------------------------------
# AC8: Already Up-to-Date
# ---------------------------------------------------------------------------


class TestAlreadyUpToDate:
    """AC8: current equals latest → update_available=False."""

    def test_current_is_latest(self) -> None:
        config = _make_config(version="1.2.0")
        git = MockGitClient(tags=["v1.2.0", "v1.1.0", "v1.0.0"])
        service = UpdateService(git, MockUserConfig(config), MockSubprocessRunner())

        result = service.check_for_updates()

        assert result.update_available is False
        assert result.latest_version == "1.2.0"
        assert result.current_version == "1.2.0"


# ---------------------------------------------------------------------------
# AC9: No Config Available
# ---------------------------------------------------------------------------


class TestNoConfig:
    """AC9: No config → ConfigError."""

    def test_raises_config_error(self) -> None:
        service = UpdateService(
            MockGitClient(), MockUserConfig(None), MockSubprocessRunner()
        )

        with pytest.raises(ConfigError, match="No user config found"):
            service.check_for_updates()


# ---------------------------------------------------------------------------
# AC10: No Versions Available
# ---------------------------------------------------------------------------


class TestNoVersions:
    """AC10: No tags → empty versions, update_available=False."""

    def test_empty_tags(self) -> None:
        config = _make_config(version="1.0.0")
        git = MockGitClient(tags=[])
        service = UpdateService(git, MockUserConfig(config), MockSubprocessRunner())

        result = service.check_for_updates()

        assert result.latest_version is None
        assert result.update_available is False
        assert result.annotated_versions == []

    def test_non_semver_tags_only(self) -> None:
        config = _make_config(version="1.0.0")
        git = MockGitClient(tags=["latest", "beta", "docs-update"])
        service = UpdateService(git, MockUserConfig(config), MockSubprocessRunner())

        result = service.check_for_updates()

        assert result.latest_version is None
        assert result.update_available is False


# ---------------------------------------------------------------------------
# AC2: Update to Latest Version — execute_update
# ---------------------------------------------------------------------------


class TestExecuteUpdate:
    """AC2: execute_update runs uv command and updates config."""

    def test_runs_correct_uv_command(self) -> None:
        config = _make_config(version="1.0.0")
        runner = MockSubprocessRunner()
        service = UpdateService(
            MockGitClient(), MockUserConfig(config), runner
        )

        result = service.execute_update("1.2.0", ["1.2.0", "1.1.0", "1.0.0"], _DEFAULT_SOURCE)

        assert result.success is True
        assert result.version == "1.2.0"
        assert result.previous_version == "1.0.0"
        assert len(runner.calls) == 1
        assert runner.calls[0] == [
            "uv", "tool", "install", "--force",
            f"{_DEFAULT_SOURCE}@v1.2.0",
        ]

    def test_updates_config_on_success(self) -> None:
        config = _make_config(version="1.0.0")
        user_cfg = MockUserConfig(config)
        service = UpdateService(MockGitClient(), user_cfg, MockSubprocessRunner())

        service.execute_update("1.2.0", ["1.2.0", "1.0.0"], _DEFAULT_SOURCE)

        assert user_cfg.saved is not None
        assert user_cfg.saved.install.installed_version == "1.2.0"
        assert user_cfg.saved.install.installed_at.tzinfo == timezone.utc

    def test_preserves_git_plus_prefix(self) -> None:
        config = _make_config(version="1.0.0")
        runner = MockSubprocessRunner()
        source = "git+https://github.com/jbjornsson/nest"
        service = UpdateService(MockGitClient(), MockUserConfig(config), runner)

        service.execute_update("1.2.0", ["1.2.0", "1.0.0"], source)

        cmd = runner.calls[0]
        assert "git+https://github.com/jbjornsson/nest@v1.2.0" in cmd


# ---------------------------------------------------------------------------
# AC4: Install Specific Version
# ---------------------------------------------------------------------------


class TestInstallSpecificVersion:
    """AC4: user enters a specific valid version."""

    def test_installs_specific_version(self) -> None:
        config = _make_config(version="1.0.0")
        runner = MockSubprocessRunner()
        service = UpdateService(MockGitClient(), MockUserConfig(config), runner)

        result = service.execute_update(
            "1.1.0", ["1.2.0", "1.1.0", "1.0.0"], _DEFAULT_SOURCE
        )

        assert result.success is True
        assert result.version == "1.1.0"
        assert f"{_DEFAULT_SOURCE}@v1.1.0" in runner.calls[0]


# ---------------------------------------------------------------------------
# AC5: Invalid Version Rejection
# ---------------------------------------------------------------------------


class TestValidateVersion:
    """AC5: validate_version accepts/rejects versions."""

    def test_valid_version_returns_none(self) -> None:
        service = UpdateService(
            MockGitClient(), MockUserConfig(), MockSubprocessRunner()
        )

        assert service.validate_version("1.2.0", ["1.2.0", "1.1.0"]) is None

    def test_invalid_version_returns_error(self) -> None:
        service = UpdateService(
            MockGitClient(), MockUserConfig(), MockSubprocessRunner()
        )

        error = service.validate_version("1.9.9", ["1.4.0", "1.3.1"])

        assert error is not None
        assert "1.9.9 not found" in error
        assert "1.4.0" in error
        assert "1.3.1" in error

    def test_execute_update_rejects_invalid_before_subprocess(self) -> None:
        config = _make_config(version="1.0.0")
        runner = MockSubprocessRunner()
        service = UpdateService(MockGitClient(), MockUserConfig(config), runner)

        result = service.execute_update("9.9.9", ["1.2.0", "1.0.0"], _DEFAULT_SOURCE)

        assert result.success is False
        assert "9.9.9 not found" in (result.error or "")
        assert len(runner.calls) == 0  # No subprocess executed


# ---------------------------------------------------------------------------
# AC7: Subprocess Failure Handling
# ---------------------------------------------------------------------------


class TestSubprocessFailure:
    """AC7: subprocess failures return UpdateResult with error."""

    def test_called_process_error(self) -> None:
        config = _make_config(version="1.0.0")
        error = subprocess.CalledProcessError(
            returncode=1, cmd=["uv"], stderr="install failed"
        )
        runner = MockSubprocessRunner(raise_error=error)
        user_cfg = MockUserConfig(config)
        service = UpdateService(MockGitClient(), user_cfg, runner)

        result = service.execute_update("1.2.0", ["1.2.0", "1.0.0"], _DEFAULT_SOURCE)

        assert result.success is False
        assert "exit code 1" in (result.error or "")
        assert user_cfg.saved is None  # Config NOT updated

    def test_timeout_expired(self) -> None:
        config = _make_config(version="1.0.0")
        error = subprocess.TimeoutExpired(cmd=["uv"], timeout=120)
        runner = MockSubprocessRunner(raise_error=error)
        user_cfg = MockUserConfig(config)
        service = UpdateService(MockGitClient(), user_cfg, runner)

        result = service.execute_update("1.2.0", ["1.2.0", "1.0.0"], _DEFAULT_SOURCE)

        assert result.success is False
        assert "timed out" in (result.error or "")
        assert user_cfg.saved is None  # Config NOT updated

    def test_does_not_update_config_on_failure(self) -> None:
        config = _make_config(version="1.0.0")
        error = subprocess.CalledProcessError(returncode=2, cmd=["uv"])
        user_cfg = MockUserConfig(config)
        service = UpdateService(
            MockGitClient(), user_cfg, MockSubprocessRunner(raise_error=error)
        )

        service.execute_update("1.2.0", ["1.2.0", "1.0.0"], _DEFAULT_SOURCE)

        assert user_cfg.saved is None
