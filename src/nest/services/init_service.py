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
from nest.core.paths import CONTEXT_DIR, NEST_META_DIR, SOURCES_DIR
from nest.ui.messages import info, status_done, status_start

# Directories to create during init
INIT_DIRECTORIES = [
    SOURCES_DIR,
    CONTEXT_DIR,
    NEST_META_DIR,
    ".github/agents",
]

# Entries for .gitignore
_GITIGNORE_ENTRIES = [
    ("# Nest - source documents (private/confidential)", "_nest_sources/"),
    ("# Nest - internal metadata", ".nest/"),
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

        Creates the project structure including directories
        and manifest file.

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
        status_done()

        # Create/update .gitignore
        self._setup_gitignore(target_dir)

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

    @staticmethod
    def _setup_gitignore(target_dir: Path) -> None:
        """Create or update .gitignore with Nest entries.

        If .gitignore exists, appends missing entries.
        If it doesn't exist, creates one with all Nest entries.

        Args:
            target_dir: Path to the project root directory.
        """
        gitignore = target_dir / ".gitignore"

        if gitignore.exists():
            content = gitignore.read_text(encoding="utf-8")
            existing = {line.strip() for line in content.splitlines()}
            additions: list[str] = []
            for comment, entry in _GITIGNORE_ENTRIES:
                if entry not in existing:
                    additions.append(comment)
                    additions.append(entry)
            if additions:
                # Ensure existing content ends with newline
                if content and not content.endswith("\n"):
                    content += "\n"
                content += "\n".join(additions) + "\n"
                gitignore.write_text(content, encoding="utf-8")
        else:
            lines: list[str] = []
            for comment, entry in _GITIGNORE_ENTRIES:
                lines.append(comment)
                lines.append(entry)
            gitignore.write_text("\n".join(lines) + "\n", encoding="utf-8")

