"""Service for checking and executing agent template migrations.

Compares the local agent file against the current bundled template
and performs backup + regeneration when templates change.
"""

from pathlib import Path

from nest.adapters.protocols import (
    AgentWriterProtocol,
    FileSystemProtocol,
    ManifestProtocol,
)
from nest.core.exceptions import ManifestError
from nest.core.models import AgentMigrationCheckResult, AgentMigrationResult

AGENT_FILE_PATH = Path(".github") / "agents" / "nest.agent.md"
AGENT_BACKUP_SUFFIX = ".bak"


class AgentMigrationService:
    """Service for checking and executing agent template migrations.

    Compares the local agent file against the current bundled template
    and performs backup + regeneration when templates change.
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
        """Check whether the local agent file needs migration.

        Compares the local agent file content against the current bundled
        template rendered with the project name from the manifest.

        Args:
            project_dir: Path to the project root directory.

        Returns:
            AgentMigrationCheckResult indicating migration status.
        """
        # AC6: Check manifest exists
        if not self._manifest.exists(project_dir):
            return AgentMigrationCheckResult(
                migration_needed=False,
                skipped=True,
                message="Not a Nest project — skipping agent check",
            )

        # Load manifest to verify it is valid (AC8)
        try:
            self._manifest.load(project_dir)
        except (ManifestError, FileNotFoundError):
            return AgentMigrationCheckResult(
                migration_needed=False,
                skipped=True,
                message="Manifest is corrupt — skipping agent check",
            )

        agent_path = project_dir / AGENT_FILE_PATH

        # AC5: Check if agent file exists
        if not self._filesystem.exists(agent_path):
            return AgentMigrationCheckResult(
                migration_needed=True,
                agent_file_missing=True,
                message="Agent file missing — will be created",
            )

        # AC1/AC2: Compare rendered template with local file
        rendered = self._agent_writer.render()
        local_content = self._filesystem.read_text(agent_path)

        if rendered != local_content:
            return AgentMigrationCheckResult(
                migration_needed=True,
                message="Agent file is outdated",
            )

        return AgentMigrationCheckResult(
            migration_needed=False,
            message="Agent file is up to date",
        )

    def execute_migration(
        self,
        project_dir: Path,
    ) -> AgentMigrationResult:
        """Execute agent template migration with backup.

        Backs up the existing agent file (if present), then regenerates
        from the current bundled template.

        Args:
            project_dir: Path to the project root directory.

        Returns:
            AgentMigrationResult indicating success/failure.
        """
        # Verify manifest is loadable before attempting migration
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

        agent_path = project_dir / AGENT_FILE_PATH
        backup_path = agent_path.parent / (agent_path.name + AGENT_BACKUP_SUFFIX)
        backed_up = False

        try:
            # AC3/AC9: Backup existing file before regeneration
            if self._filesystem.exists(agent_path):
                current_content = self._filesystem.read_text(agent_path)
                self._filesystem.write_text(backup_path, current_content)
                backed_up = True

            # AC3/AC7: Regenerate agent file
            self._agent_writer.generate(agent_path)

            return AgentMigrationResult(
                success=True,
                backed_up=backed_up,
            )
        except OSError as exc:
            # AC10: Filesystem error during migration
            return AgentMigrationResult(
                success=False,
                backed_up=backed_up,
                error=str(exc),
            )
