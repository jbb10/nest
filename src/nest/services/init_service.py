"""Init service for project scaffolding.

Orchestrates the creation of a new Nest project structure.
"""

from pathlib import Path

from nest.adapters.protocols import (
    AgentWriterProtocol,
    FileSystemProtocol,
    ManifestProtocol,
)
from nest.core.exceptions import NestError

# Gitignore content
GITIGNORE_COMMENT = (
    "# Raw documents excluded from version control "
    "(processed versions in processed_context/)"
)
GITIGNORE_ENTRY = "raw_inbox/"

# Directories to create during init
INIT_DIRECTORIES = [
    "raw_inbox",
    "processed_context",
    ".github/agents",
]


class InitService:
    """Service for initializing new Nest projects.

    Handles project scaffolding including:
    - Creating required directory structure
    - Creating manifest file
    - Setting up .gitignore
    """

    def __init__(
        self,
        filesystem: FileSystemProtocol,
        manifest: ManifestProtocol,
        agent_writer: AgentWriterProtocol,
    ) -> None:
        """Initialize the service with required adapters.

        Args:
            filesystem: Adapter for filesystem operations.
            manifest: Adapter for manifest operations.
            agent_writer: Adapter for agent file generation.
        """
        self._filesystem = filesystem
        self._manifest = manifest
        self._agent_writer = agent_writer

    def execute(self, project_name: str, target_dir: Path) -> None:
        """Execute project initialization.

        Creates the project structure including directories,
        manifest file, and gitignore configuration.

        Args:
            project_name: Human-readable project name (e.g., "Nike").
            target_dir: Path to the project root directory.

        Raises:
            NestError: If project name is missing or project already exists.
        """
        # Validate project name
        if not project_name or not project_name.strip():
            raise NestError("Project name required. Usage: nest init 'Client Name'")

        # Check for existing project
        if self._manifest.exists(target_dir):
            raise NestError(
                "Nest project already exists. Use `nest sync` to process documents."
            )

        # Create directories
        for dir_name in INIT_DIRECTORIES:
            dir_path = target_dir / dir_name
            self._filesystem.create_directory(dir_path)

        # Create manifest
        self._manifest.create(target_dir, project_name.strip())

        # Generate agent file
        agent_path = target_dir / ".github" / "agents" / "nest.agent.md"
        self._agent_writer.generate(project_name.strip(), agent_path)

        # Handle gitignore
        self._update_gitignore(target_dir)

    def _update_gitignore(self, target_dir: Path) -> None:
        """Update or create .gitignore with raw_inbox entry.

        Args:
            target_dir: Path to the project root directory.
        """
        gitignore_path = target_dir / ".gitignore"

        if self._filesystem.exists(gitignore_path):
            # Check if entry already exists
            content = self._filesystem.read_text(gitignore_path)
            if GITIGNORE_ENTRY in content:
                return  # Already present, skip

            # Append entry
            self._filesystem.write_text(
                gitignore_path,
                content + f"\n{GITIGNORE_COMMENT}\n{GITIGNORE_ENTRY}\n",
            )
        else:
            # Create new gitignore
            self._filesystem.write_text(
                gitignore_path,
                f"{GITIGNORE_COMMENT}\n{GITIGNORE_ENTRY}\n",
            )
