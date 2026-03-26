"""Service for checking and executing agent template migrations.

Compares the local agent files against the current bundled templates
and performs selective regeneration when templates change.
"""

from pathlib import Path

from nest.adapters.protocols import (
    AgentWriterProtocol,
    FileSystemProtocol,
    ManifestProtocol,
)
from nest.core.exceptions import ManifestError
from nest.core.models import AgentMigrationCheckResult, AgentMigrationResult
from nest.core.paths import AGENT_DIR


class AgentMigrationService:
    """Service for checking and executing agent template migrations.

    Compares the local agent files against the current bundled templates
    and performs selective regeneration when templates change.
    """

    def __init__(
        self,
        agent_writer: AgentWriterProtocol,
        filesystem: FileSystemProtocol,
        manifest: ManifestProtocol,
    ) -> None:
        self._agent_writer = agent_writer
        self._filesystem = filesystem
        self._manifest = manifest

    def check_migration_needed(
        self,
        project_dir: Path,
    ) -> AgentMigrationCheckResult:
        """Check whether local agent files need migration.

        Compares all local agent files against the current bundled
        templates and reports which are outdated or missing.

        Args:
            project_dir: Path to the project root directory.

        Returns:
            AgentMigrationCheckResult indicating migration status.
        """
        if not self._manifest.exists(project_dir):
            return AgentMigrationCheckResult(
                migration_needed=False,
                skipped=True,
                message="Not a Nest project — skipping agent check",
            )

        try:
            self._manifest.load(project_dir)
        except (ManifestError, FileNotFoundError):
            return AgentMigrationCheckResult(
                migration_needed=False,
                skipped=True,
                message="Manifest is corrupt — skipping agent check",
            )

        rendered = self._agent_writer.render_all()
        agent_dir = project_dir / AGENT_DIR
        outdated: list[str] = []
        missing: list[str] = []

        try:
            for filename, expected_content in rendered.items():
                local_path = agent_dir / filename
                if not self._filesystem.exists(local_path):
                    missing.append(filename)
                elif self._filesystem.read_text(local_path) != expected_content:
                    outdated.append(filename)
        except OSError as exc:
            return AgentMigrationCheckResult(
                migration_needed=False,
                skipped=True,
                message=f"Cannot read agent files — {exc}",
            )

        if not outdated and not missing:
            return AgentMigrationCheckResult(
                migration_needed=False,
                message="All agent files are up to date",
            )

        parts: list[str] = []
        if outdated:
            parts.append(f"{len(outdated)} outdated")
        if missing:
            parts.append(f"{len(missing)} missing")
        message = f"Agent files need updating ({', '.join(parts)})"

        return AgentMigrationCheckResult(
            migration_needed=True,
            agent_file_missing=bool(missing),
            message=message,
            outdated_files=outdated,
            missing_files=missing,
        )

    def execute_migration(
        self,
        project_dir: Path,
    ) -> AgentMigrationResult:
        """Execute agent template migration for outdated/missing files.

        Only writes files that differ from the current template or are missing.

        Args:
            project_dir: Path to the project root directory.

        Returns:
            AgentMigrationResult indicating success/failure.
        """
        if not self._manifest.exists(project_dir):
            return AgentMigrationResult(
                success=False,
                error="Failed to load manifest: manifest not found",
            )
        try:
            self._manifest.load(project_dir)
        except (ManifestError, FileNotFoundError) as exc:
            return AgentMigrationResult(
                success=False,
                error=f"Failed to load manifest: {exc}",
            )

        agent_dir = project_dir / AGENT_DIR
        rendered = self._agent_writer.render_all()
        files_replaced: list[str] = []
        files_created: list[str] = []

        try:
            if not self._filesystem.exists(agent_dir):
                self._filesystem.create_directory(agent_dir)

            for filename, expected_content in rendered.items():
                local_path = agent_dir / filename
                if self._filesystem.exists(local_path):
                    local_content = self._filesystem.read_text(local_path)
                    if local_content == expected_content:
                        continue
                    self._filesystem.write_text(local_path, expected_content)
                    files_replaced.append(filename)
                else:
                    self._filesystem.write_text(local_path, expected_content)
                    files_created.append(filename)

            return AgentMigrationResult(
                success=True,
                files_replaced=files_replaced,
                files_created=files_created,
            )
        except OSError as exc:
            return AgentMigrationResult(
                success=False,
                files_replaced=files_replaced,
                files_created=files_created,
                error=str(exc),
            )
