"""Update workflow orchestration service.

Handles version discovery, user version selection validation,
uv-based installation, and config persistence.
"""

import subprocess
from datetime import datetime, timezone

from nest.adapters.protocols import (
    GitClientProtocol,
    SubprocessRunnerProtocol,
    UserConfigProtocol,
)
from nest.core.exceptions import ConfigError
from nest.core.models import UpdateCheckResult, UpdateResult
from nest.core.version import compare_versions, is_newer, sort_versions

UV_INSTALL_TIMEOUT = 120  # seconds — uv install can be slow


class UpdateService:
    """Service for orchestrating Nest version updates.

    Handles version discovery, user version selection validation,
    uv-based installation, and config persistence.
    """

    def __init__(
        self,
        git_client: GitClientProtocol,
        user_config: UserConfigProtocol,
        subprocess_runner: SubprocessRunnerProtocol,
    ) -> None:
        """Initialize the service.

        Args:
            git_client: Adapter for querying git remote tags.
            user_config: Adapter for reading/writing user config.
            subprocess_runner: Adapter for executing subprocess commands.
        """
        self._git_client = git_client
        self._user_config = user_config
        self._subprocess_runner = subprocess_runner

    def check_for_updates(self) -> UpdateCheckResult:
        """Query available versions and compare to installed.

        Returns:
            UpdateCheckResult with version comparison data.

        Raises:
            ConfigError: If no user config exists.
        """
        config = self._user_config.load()
        if config is None:
            raise ConfigError("No user config found. Run any nest command first to create config.")

        source = config.install.source
        current = config.install.installed_version

        tags = self._git_client.list_tags(source)
        available = sort_versions(tags)

        if not available:
            return UpdateCheckResult(
                current_version=current,
                latest_version=None,
                annotated_versions=[],
                update_available=False,
                source=source,
            )

        latest = available[0]
        annotated = compare_versions(current, available)
        update_available = is_newer(latest, current)

        return UpdateCheckResult(
            current_version=current,
            latest_version=latest,
            annotated_versions=annotated,
            update_available=update_available,
            source=source,
        )

    def execute_update(
        self,
        version: str,
        available_versions: list[str],
        source: str,
    ) -> UpdateResult:
        """Install a specific version via uv.

        Args:
            version: Target version string (without v prefix).
            available_versions: List of valid version strings.
            source: Git remote URL (e.g., "git+https://...").

        Returns:
            UpdateResult indicating success or failure.
        """
        config = self._user_config.load()
        current_version = config.install.installed_version if config else "unknown"

        validation_error = self.validate_version(version, available_versions)
        if validation_error is not None:
            return UpdateResult(
                success=False,
                version=version,
                previous_version=current_version,
                error=validation_error,
            )

        cmd = _build_install_command(source, version)

        try:
            self._subprocess_runner.run(cmd, timeout=UV_INSTALL_TIMEOUT)
        except subprocess.CalledProcessError as err:
            return UpdateResult(
                success=False,
                version=version,
                previous_version=current_version,
                error=f"Update failed: uv tool install returned exit code {err.returncode}",
            )
        except subprocess.TimeoutExpired:
            return UpdateResult(
                success=False,
                version=version,
                previous_version=current_version,
                error=f"Update timed out after {UV_INSTALL_TIMEOUT} seconds",
            )

        # Update config on success
        config = self._user_config.load()
        if config is not None:
            updated = config.model_copy(
                update={
                    "install": config.install.model_copy(
                        update={
                            "installed_version": version,
                            "installed_at": datetime.now(tz=timezone.utc),
                        }
                    )
                }
            )
            self._user_config.save(updated)

        return UpdateResult(
            success=True,
            version=version,
            previous_version=current_version,
        )

    def validate_version(
        self,
        version: str,
        available: list[str],
    ) -> str | None:
        """Check if version exists in available list.

        Args:
            version: Version string to validate.
            available: List of available version strings.

        Returns:
            None if valid, error message string if invalid.
        """
        if version in available:
            return None
        available_str = ", ".join(available)
        return f"Version {version} not found. Available: {available_str}"


def _build_install_command(source: str, version: str) -> list[str]:
    """Build the uv tool install command.

    Args:
        source: Git remote URL (preserves git+ prefix).
        version: Version string without v prefix.

    Returns:
        Command args list for subprocess execution.
    """
    return ["uv", "tool", "install", "--force", f"{source}@v{version}"]
