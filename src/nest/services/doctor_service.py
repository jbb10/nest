"""Doctor service for environment and project validation."""

import json
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import nest
from nest.adapters.protocols import ModelCheckerProtocol, ProjectCheckerProtocol
from nest.core.exceptions import ManifestError


@dataclass
class EnvironmentStatus:
    """Status for a single environment check."""

    name: str  # "Python", "uv", "Nest"
    status: Literal["pass", "fail", "warning"]
    current_value: str  # "3.11.4", "0.4.12", "1.0.0"
    message: str | None = None  # Optional detail message
    suggestion: str | None = None  # Optional remediation


@dataclass
class EnvironmentReport:
    """Complete environment validation report."""

    python: EnvironmentStatus
    uv: EnvironmentStatus
    nest: EnvironmentStatus

    @property
    def all_pass(self) -> bool:
        """True if all checks passed (no failures)."""
        return all(check.status != "fail" for check in [self.python, self.uv, self.nest])


@dataclass
class ModelStatus:
    """Status for ML model cache check."""

    cached: bool  # True if models are downloaded
    size_bytes: int | None  # Total cache size (None if not cached)
    cache_path: Path  # Path to cache directory
    cache_status: Literal["exists", "empty", "not_created"]
    suggestion: str | None = None  # Remediation hint


@dataclass
class ModelReport:
    """Complete ML model validation report."""

    models: ModelStatus

    @property
    def all_pass(self) -> bool:
        """True if models are cached."""
        return self.models.cached


@dataclass
class ProjectStatus:
    """Status for project state validation."""

    manifest_status: Literal[
        "valid", "missing", "invalid_json", "invalid_structure", "version_mismatch"
    ]
    manifest_version: str | None
    current_version: str
    agent_file_present: bool
    folders_status: Literal["intact", "sources_missing", "context_missing", "both_missing"]
    suggestions: list[str]


@dataclass
class ProjectReport:
    """Complete project state validation report."""

    status: ProjectStatus

    @property
    def all_pass(self) -> bool:
        """True if manifest valid, agent present, folders intact."""
        return (
            self.status.manifest_status == "valid"
            and self.status.agent_file_present
            and self.status.folders_status == "intact"
        )

    @property
    def has_warnings(self) -> bool:
        """True if only warnings (no errors)."""
        return (
            self.status.manifest_status in ("valid", "version_mismatch")
            and self.status.folders_status == "intact"
        )


class DoctorService:
    """Validates development environment and project state."""

    def __init__(
        self,
        model_checker: ModelCheckerProtocol | None = None,
        project_checker: ProjectCheckerProtocol | None = None,
    ) -> None:
        """Initialize doctor service.

        Args:
            model_checker: Optional model checker for ML validation.
                          If None, model checks will be skipped.
            project_checker: Optional project checker for project validation.
                            If None, project checks will be skipped.
        """
        self._model_checker = model_checker
        self._project_checker = project_checker

    def check_environment(self) -> EnvironmentReport:
        """Check Python, uv, and Nest versions.

        Returns:
            Complete environment validation report.
        """
        return EnvironmentReport(
            python=self._check_python_version(),
            uv=self._check_uv_installation(),
            nest=self._check_nest_version(),
        )

    def _check_python_version(self) -> EnvironmentStatus:
        """Check if Python version meets minimum requirement.

        Returns:
            Environment status for Python version check.
        """
        current = sys.version_info
        required = (3, 10, 0)

        version_str = f"{current[0]}.{current[1]}.{current[2]}"

        if current >= required:
            return EnvironmentStatus(
                name="Python",
                status="pass",
                current_value=version_str,
            )
        else:
            return EnvironmentStatus(
                name="Python",
                status="fail",
                current_value=version_str,
                message="requires 3.10+",
                suggestion="Upgrade Python to 3.10 or higher",
            )

    def _check_uv_installation(self) -> EnvironmentStatus:
        """Check if uv is installed and get version.

        Returns:
            Environment status for uv installation check.
        """
        uv_path = shutil.which("uv")

        if not uv_path:
            return EnvironmentStatus(
                name="uv",
                status="fail",
                current_value="not found",
                suggestion="Install uv: https://docs.astral.sh/uv/",
            )

        try:
            result = subprocess.run(
                ["uv", "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )

            if result.returncode == 0:
                # Parse version from "uv 0.4.12 (abc123)"
                parts = result.stdout.strip().split()
                if len(parts) >= 2:
                    version = parts[1]
                    return EnvironmentStatus(
                        name="uv",
                        status="pass",
                        current_value=version,
                    )
                return EnvironmentStatus(
                    name="uv",
                    status="warning",
                    current_value="found",
                    message="could not determine version",
                )
            else:
                return EnvironmentStatus(
                    name="uv",
                    status="warning",
                    current_value="found",
                    message="could not determine version",
                )
        except (subprocess.TimeoutExpired, Exception):
            return EnvironmentStatus(
                name="uv",
                status="warning",
                current_value="found",
                message="version check failed",
            )

    def _check_nest_version(self) -> EnvironmentStatus:
        """Check Nest version.

        Returns:
            Environment status for Nest version check.
        """
        current_version = nest.__version__
        latest_version = self._fetch_latest_version()

        if latest_version and self._is_newer_version(latest_version, current_version):
            return EnvironmentStatus(
                name="Nest",
                status="warning",
                current_value=current_version,
                message=f"{latest_version} available",
                suggestion="Run `nest update` to upgrade",
            )

        return EnvironmentStatus(
            name="Nest",
            status="pass",
            current_value=current_version,
        )

    def _fetch_latest_version(self) -> str | None:
        """Fetch the latest Nest version from PyPI.

        Returns:
            Latest version string or None if unavailable.
        """
        url = "https://pypi.org/pypi/nest/json"
        request = urllib.request.Request(url, headers={"User-Agent": "nest-doctor"})
        try:
            with urllib.request.urlopen(request, timeout=2) as response:
                if response.status != 200:
                    return None
                data = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, ValueError, OSError):
            return None

        version = data.get("info", {}).get("version")
        if isinstance(version, str) and version:
            return version
        return None

    def _is_newer_version(self, latest: str, current: str) -> bool:
        """Compare two version strings.

        Args:
            latest: Latest available version string.
            current: Current installed version string.

        Returns:
            True if latest is newer than current.
        """
        latest_parts = self._parse_version(latest)
        current_parts = self._parse_version(current)

        if latest_parts is None or current_parts is None:
            return False

        return latest_parts > current_parts

    def _parse_version(self, version: str) -> tuple[int, ...] | None:
        """Parse a version string into comparable numeric parts.

        Args:
            version: Version string to parse.

        Returns:
            Tuple of numeric parts or None if parsing fails.
        """
        normalized = version.strip().lstrip("v")
        parts = re.split(r"[.+-]", normalized)
        numbers: list[int] = []

        for part in parts:
            if part.isdigit():
                numbers.append(int(part))
            else:
                break

        return tuple(numbers) if numbers else None

    def check_ml_models(self) -> ModelReport | None:
        """Check ML model cache status.

        Returns:
            ModelReport if model checker is configured, None otherwise.
        """
        if self._model_checker is None:
            return None

        cached = self._model_checker.are_models_cached()
        cache_path = self._model_checker.get_cache_path()
        cache_status = self._model_checker.get_cache_status()

        size_bytes = None
        suggestion = None

        if cached:
            size_bytes = self._model_checker.get_cache_size()
        else:
            suggestion = "Run `nest init` to download models"

        return ModelReport(
            models=ModelStatus(
                cached=cached,
                size_bytes=size_bytes,
                cache_path=cache_path,
                cache_status=cache_status,
                suggestion=suggestion,
            )
        )

    def check_project(self, project_dir: Path) -> ProjectReport | None:
        """Check project state.

        Args:
            project_dir: Path to project root directory.

        Returns:
            ProjectReport if project checker is configured, None otherwise.
        """
        if self._project_checker is None:
            return None

        suggestions: list[str] = []

        # Check manifest
        if not self._project_checker.manifest_exists(project_dir):
            manifest_status = "missing"
            manifest_version = None
            suggestions.append("Run `nest init` to create project")
        else:
            try:
                manifest = self._project_checker.load_manifest(project_dir)
                manifest_version = manifest.nest_version

                # Check version compatibility
                if manifest_version != nest.__version__:
                    manifest_status = "version_mismatch"
                    suggestions.append("Run `nest update` to migrate")
                else:
                    manifest_status = "valid"
            except ManifestError as e:
                if "invalid JSON" in str(e) or "JSON" in str(e):
                    manifest_status = "invalid_json"
                else:
                    manifest_status = "invalid_structure"
                manifest_version = None
                suggestions.append("Run `nest doctor --fix` to rebuild")

        # Check agent file
        agent_present = self._project_checker.agent_file_exists(project_dir)
        if not agent_present:
            suggestions.append("Run `nest init` to regenerate agent file")

        # Check folders
        sources_exist = self._project_checker.source_folder_exists(project_dir)
        context_exist = self._project_checker.context_folder_exists(project_dir)

        if sources_exist and context_exist:
            folders_status = "intact"
        elif not sources_exist and not context_exist:
            folders_status = "both_missing"
            suggestions.append("Run `nest init` to recreate folders")
        elif not sources_exist:
            folders_status = "sources_missing"
            suggestions.append("Run `nest init` to recreate _nest_sources/")
        else:
            folders_status = "context_missing"
            suggestions.append("Run `nest init` to recreate _nest_context/")

        return ProjectReport(
            status=ProjectStatus(
                manifest_status=manifest_status,
                manifest_version=manifest_version,
                current_version=nest.__version__,
                agent_file_present=agent_present,
                folders_status=folders_status,
                suggestions=suggestions,
            )
        )
