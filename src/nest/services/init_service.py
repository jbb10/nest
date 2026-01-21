"""Init service for project scaffolding.

Orchestrates the creation of a new Nest project structure.
"""

from pathlib import Path

from nest.adapters.protocols import (
    AgentWriterProtocol,
    FileSystemProtocol,
    ManifestProtocol,
    ModelDownloaderProtocol,
)
from nest.core.exceptions import NestError
from nest.core.paths import CONTEXT_DIR, SOURCES_DIR
from nest.ui.messages import info, status_done, status_start

# Gitignore content
GITIGNORE_COMMENT = (
    f"# Raw documents excluded from version control (processed versions in {CONTEXT_DIR}/)"
)
GITIGNORE_ENTRY = f"{SOURCES_DIR}/"

# Directories to create during init
INIT_DIRECTORIES = [
    SOURCES_DIR,
    CONTEXT_DIR,
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
        model_downloader: ModelDownloaderProtocol,
    ) -> None:
        """Initialize the service with required adapters.

        Args:
            filesystem: Adapter for filesystem operations.
            manifest: Adapter for manifest operations.
            agent_writer: Adapter for agent file generation.
            model_downloader: Adapter for ML model downloads.
        """
        self._filesystem = filesystem
        self._manifest = manifest
        self._agent_writer = agent_writer
        self._model_downloader = model_downloader

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
            raise NestError("Project name required. Usage: nest init 'Project Name'")

        # Check for existing project
        if self._manifest.exists(target_dir):
            raise NestError("Nest project already exists. Use `nest sync` to process documents.")

        # Create directories with progress
        status_start("Creating project structure")
        for dir_name in INIT_DIRECTORIES:
            dir_path = target_dir / dir_name
            self._filesystem.create_directory(dir_path)

        # Create manifest
        self._manifest.create(target_dir, project_name.strip())

        # Handle gitignore
        self._update_gitignore(target_dir)
        status_done()

        # Generate agent file with progress
        status_start("Generating agent file")
        agent_path = target_dir / ".github" / "agents" / "nest.agent.md"
        self._agent_writer.generate(project_name.strip(), agent_path)
        status_done()

        # Download ML models if needed
        status_start("Checking ML models")
        if self._model_downloader.are_models_cached():
            status_done("cached")
        else:
            status_done("downloading")
            self._model_downloader.download_if_needed(progress=True)
            cache_path = self._model_downloader.get_cache_path()
            info(f"Models cached at {cache_path}")

    def _update_gitignore(self, target_dir: Path) -> None:
        """Update or create .gitignore with sources directory entry.

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
