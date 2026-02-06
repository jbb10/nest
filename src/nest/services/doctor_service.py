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
from typing import Literal, Protocol

import nest


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
        return all(
            check.status != "fail" for check in [self.python, self.uv, self.nest]
        )


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


class ModelCheckerProtocol(Protocol):
    """Protocol for ML model cache operations."""

    def are_models_cached(self) -> bool:
        """Check if models are cached."""
        ...

    def get_cache_path(self) -> Path:
        """Get cache directory path."""
        ...

    def get_cache_size(self) -> int:
        """Get total cache size in bytes."""
        ...

    def get_cache_status(self) -> Literal["exists", "empty", "not_created"]:
        """Get cache directory status."""
        ...


class DoctorService:
    """Validates development environment and project state."""

    def __init__(self, model_checker: ModelCheckerProtocol | None = None) -> None:
        """Initialize doctor service.

        Args:
            model_checker: Optional model checker for ML validation.
                          If None, model checks will be skipped.
        """
        self._model_checker = model_checker

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
