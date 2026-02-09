"""Doctor service for environment and project validation."""

import json
import logging
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Literal

import nest
from nest.adapters.protocols import ModelCheckerProtocol, ProjectCheckerProtocol
from nest.core.checksum import compute_sha256
from nest.core.exceptions import ManifestError
from nest.core.models import FileEntry, Manifest

logger = logging.getLogger("nest.errors")

if TYPE_CHECKING:
    from nest.adapters.protocols import (
        AgentWriterProtocol,
        FileSystemProtocol,
        ManifestProtocol,
    )


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


@dataclass
class RemediationResult:
    """Result of a single remediation action."""

    issue: str  # Description of the issue (e.g., "missing_manifest")
    attempted: bool  # Whether the fix was attempted
    success: bool  # Whether the fix succeeded
    message: str  # Result message for the user


@dataclass
class RemediationReport:
    """Complete remediation report."""

    results: list[RemediationResult]

    @property
    def all_succeeded(self) -> bool:
        """True if all attempted fixes succeeded."""
        attempted = [r for r in self.results if r.attempted]
        if not attempted:
            return True  # Vacuous truth
        return all(r.success for r in attempted)

    @property
    def any_attempted(self) -> bool:
        """True if any fix was attempted."""
        return any(r.attempted for r in self.results)


class DoctorService:
    """Validates development environment and project state."""

    def __init__(
        self,
        model_checker: ModelCheckerProtocol | None = None,
        project_checker: ProjectCheckerProtocol | None = None,
        manifest_adapter: "ManifestProtocol | None" = None,
        filesystem: "FileSystemProtocol | None" = None,
        agent_writer: "AgentWriterProtocol | None" = None,
    ) -> None:
        """Initialize doctor service.

        Args:
            model_checker: Optional model checker for ML validation.
                          If None, model checks will be skipped.
            project_checker: Optional project checker for project validation.
                            If None, project checks will be skipped.
            manifest_adapter: Optional manifest adapter for manifest operations.
                             If None, manifest rebuild will not be available.
            filesystem: Optional filesystem adapter for file operations.
                       If None, folder recreation will not be available.
            agent_writer: Optional agent writer for file regeneration.
                         If None, agent file regeneration will not be available.
        """
        self._model_checker = model_checker
        self._project_checker = project_checker
        self._manifest_adapter = manifest_adapter
        self._filesystem = filesystem
        self._agent_writer = agent_writer

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

    def rebuild_manifest(
        self,
        project_dir: Path,
        project_name: str,
    ) -> RemediationResult:
        """Rebuild manifest from processed files.

        Scans _nest_sources to find tracked files, computes their checksums,
        and checks if they have corresponding processed output in _nest_context.
        Builds a new manifest reflecting the current state.

        Args:
            project_dir: Path to the project root directory.
            project_name: Name of the project.

        Returns:
            RemediationResult indicating success or failure.
        """
        if self._manifest_adapter is None:
            return RemediationResult(
                issue="corrupt_manifest",
                attempted=False,
                success=False,
                message="Manifest adapter not available",
            )

        if self._filesystem is None:
            return RemediationResult(
                issue="corrupt_manifest",
                attempted=False,
                success=False,
                message="Filesystem adapter not available",
            )

        try:
            manifest = Manifest(
                nest_version=nest.__version__,
                project_name=project_name,
                last_sync=datetime.now(timezone.utc),
                files={},
            )

            sources_dir = project_dir / "_nest_sources"
            context_dir = project_dir / "_nest_context"

            if not self._filesystem.exists(sources_dir):
                self._manifest_adapter.save(project_dir, manifest)
                return RemediationResult(
                    issue="corrupt_manifest",
                    attempted=True,
                    success=True,
                    message="Manifest rebuilt (empty - no sources found)",
                )

            source_files = self._filesystem.list_files(sources_dir)

            restored_count = 0
            for source_path in source_files:
                rel_path = source_path.relative_to(sources_dir)
                key = str(rel_path)
                sha256 = compute_sha256(source_path)

                output_rel_path = rel_path.with_suffix(".md")
                output_path = context_dir / output_rel_path

                if self._filesystem.exists(output_path):
                    processed_at = datetime.now(timezone.utc)

                    entry = FileEntry(
                        sha256=sha256,
                        processed_at=processed_at,
                        output=str(output_rel_path),
                        status="success",
                    )
                    manifest.files[key] = entry
                    restored_count += 1

            self._manifest_adapter.save(project_dir, manifest)

            return RemediationResult(
                issue="corrupt_manifest",
                attempted=True,
                success=True,
                message=f"Manifest rebuilt successfully ({restored_count} files restored)",
            )
        except Exception as e:
            logger.exception("Failed to rebuild manifest in %s", project_dir)
            return RemediationResult(
                issue="corrupt_manifest",
                attempted=True,
                success=False,
                message=f"Failed to rebuild manifest: {e}",
            )

    def recreate_folders(self, project_dir: Path) -> RemediationResult:
        """Recreate missing project folders.

        Args:
            project_dir: Path to the project root directory.

        Returns:
            RemediationResult indicating success or failure.
        """
        if self._filesystem is None:
            return RemediationResult(
                issue="missing_folders",
                attempted=False,
                success=False,
                message="Filesystem adapter not available",
            )

        sources_dir = project_dir / "_nest_sources"
        context_dir = project_dir / "_nest_context"

        sources_exist = self._filesystem.exists(sources_dir)
        context_exist = self._filesystem.exists(context_dir)

        if sources_exist and context_exist:
            return RemediationResult(
                issue="missing_folders",
                attempted=False,
                success=True,
                message="Folders already exist",
            )

        created: list[str] = []
        if not sources_exist:
            self._filesystem.create_directory(sources_dir)
            created.append("_nest_sources/")
        if not context_exist:
            self._filesystem.create_directory(context_dir)
            created.append("_nest_context/")

        return RemediationResult(
            issue="missing_folders",
            attempted=True,
            success=True,
            message=f"Created folders: {', '.join(created)}",
        )

    def regenerate_agent_file(
        self,
        project_dir: Path,
        project_name: str,
    ) -> RemediationResult:
        """Regenerate agent file.

        Args:
            project_dir: Path to the project root directory.
            project_name: Name of the project.

        Returns:
            RemediationResult indicating success or failure.
        """
        if self._agent_writer is None:
            return RemediationResult(
                issue="missing_agent_file",
                attempted=False,
                success=False,
                message="Agent writer not available",
            )

        try:
            output_path = project_dir / ".github" / "agents" / "nest.agent.md"
            self._agent_writer.generate(project_name, output_path)
            return RemediationResult(
                issue="missing_agent_file",
                attempted=True,
                success=True,
                message=f"Agent file regenerated at {output_path.relative_to(project_dir)}",
            )
        except Exception as e:
            logger.exception("Failed to regenerate agent file in %s", project_dir)
            return RemediationResult(
                issue="missing_agent_file",
                attempted=True,
                success=False,
                message=f"Failed to regenerate agent file: {e}",
            )

    def download_models(self) -> RemediationResult:
        """Download ML models.

        Returns:
            RemediationResult indicating success or failure.
        """
        if self._model_checker is None:
            return RemediationResult(
                issue="missing_models",
                attempted=False,
                success=False,
                message="Model checker not available",
            )

        # Get the download method if it exists
        download_method = getattr(self._model_checker, "download_if_needed", None)
        if download_method is None:
            return RemediationResult(
                issue="missing_models",
                attempted=False,
                success=False,
                message="Model checker does not support download",
            )

        try:
            downloaded = download_method(progress=True)
            if downloaded:
                message = "Models downloaded successfully"
            else:
                message = "Models already cached"
            return RemediationResult(
                issue="missing_models",
                attempted=True,
                success=True,
                message=message,
            )
        except Exception as e:
            logger.exception("Failed to download ML models")
            return RemediationResult(
                issue="missing_models",
                attempted=True,
                success=False,
                message=f"Failed to download models: {e}",
            )

    def remediate_issues_auto(
        self,
        project_dir: Path,
        env_report: EnvironmentReport,
        model_report: ModelReport | None,
        project_report: ProjectReport | None,
    ) -> RemediationReport:
        """Remediate all detected issues automatically.

        Args:
            project_dir: Path to the project root directory.
            env_report: Environment validation report.
            model_report: ML model validation report (if available).
            project_report: Project state validation report (if available).

        Returns:
            RemediationReport with all remediation results.
        """
        results: list[RemediationResult] = []

        # Check ML models
        if model_report and not model_report.all_pass:
            result = self.download_models()
            results.append(result)

        # Check project issues if in a project
        if project_report:
            # Recreate folders
            if project_report.status.folders_status != "intact":
                result = self.recreate_folders(project_dir)
                results.append(result)

            # Rebuild manifest
            if project_report.status.manifest_status in (
                "missing",
                "invalid_json",
                "invalid_structure",
            ):
                project_name = self._get_project_name(project_dir)
                result = self.rebuild_manifest(project_dir, project_name)
                results.append(result)

            # Regenerate agent file
            if not project_report.status.agent_file_present:
                project_name = self._get_project_name(project_dir)
                result = self.regenerate_agent_file(project_dir, project_name)
                results.append(result)

        return RemediationReport(results=results)

    def remediate_issues_interactive(
        self,
        project_dir: Path,
        env_report: EnvironmentReport,
        model_report: ModelReport | None,
        project_report: ProjectReport | None,
        confirm_callback: Callable[[str], bool] | None = None,
        input_callback: Callable[[str], str] | None = None,
    ) -> RemediationReport:
        """Remediate issues sequentially with user confirmation.

        Args:
            project_dir: Path to the project root directory.
            env_report: Environment validation report.
            model_report: ML model validation report.
            project_report: Project state validation report.
            confirm_callback: Function that returns True if user confirms action.
            input_callback: Function that returns user string input.

        Returns:
            RemediationReport with results.
        """
        results: list[RemediationResult] = []

        def _confirm(msg: str) -> bool:
            if confirm_callback:
                return confirm_callback(msg)
            return True

        # Resolve project name once if needed for manifest or agent file fixes
        project_name = self._get_project_name(project_dir)
        if project_report:
            needs_name = (
                project_report.status.manifest_status
                in ("missing", "invalid_json", "invalid_structure")
                or not project_report.status.agent_file_present
            )
            if needs_name and project_name == "Nest Project" and input_callback:
                user_input = input_callback(
                    "Enter project name (default: Nest Project)"
                )
                if user_input.strip():
                    project_name = user_input.strip()

        # 1. ML models (Foundational)
        if model_report and not model_report.all_pass:
            if _confirm("Download missing ML models?"):
                result = self.download_models()
                results.append(result)
            else:
                results.append(
                    RemediationResult("missing_models", False, False, "User declined")
                )

        # 2. Folders (Structural)
        if project_report and project_report.status.folders_status != "intact":
            if _confirm("Recreate missing project folders?"):
                result = self.recreate_folders(project_dir)
                results.append(result)
            else:
                results.append(
                    RemediationResult("missing_folders", False, False, "User declined")
                )

        # 3. Manifest (State)
        if project_report and project_report.status.manifest_status in (
            "missing",
            "invalid_json",
            "invalid_structure",
        ):
            if _confirm(f"Rebuild manifest for '{project_name}'?"):
                result = self.rebuild_manifest(project_dir, project_name)
                results.append(result)
            else:
                results.append(
                    RemediationResult("corrupt_manifest", False, False, "User declined")
                )

        # 4. Agent file (Last)
        if project_report and not project_report.status.agent_file_present:
            if _confirm("Regenerate agent file?"):
                result = self.regenerate_agent_file(project_dir, project_name)
                results.append(result)
            else:
                results.append(
                    RemediationResult("missing_agent_file", False, False, "User declined")
                )

        return RemediationReport(results=results)

    def _get_project_name(self, project_dir: Path) -> str:
        """Get project name from manifest or return default.

        Args:
            project_dir: Path to the project root directory.

        Returns:
            Project name from manifest or "Nest Project" as default.
        """
        if self._manifest_adapter and self._manifest_adapter.exists(project_dir):
            try:
                manifest = self._manifest_adapter.load(project_dir)
                return manifest.project_name
            except Exception:
                pass
        return "Nest Project"
