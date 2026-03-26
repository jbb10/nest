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
from nest.core.paths import (
    AGENT_DIR,
    CONTEXT_DIR,
    CONTEXT_TEXT_EXTENSIONS,
    NEST_META_DIR,
    SOURCES_DIR,
    SUPPORTED_EXTENSIONS,
)
from nest.ui.messages import info, status_done, status_start

# Directories to create during init
INIT_DIRECTORIES = [
    SOURCES_DIR,
    CONTEXT_DIR,
    NEST_META_DIR,
    ".github/agents",
]

# Entries for .gitignore — only per-machine runtime artifacts
_GITIGNORE_ENTRIES = [
    ("# Nest - per-machine runtime artifacts", ".nest/errors.log"),
]

# Comment block delimiter for detecting existing Nest gitattributes
_GITATTRIBUTES_MARKER = "# Nest — cross-platform line ending normalization"

_NEST_METADATA_TEXT_EXTENSIONS = (".json", ".md", ".yaml")


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

    def execute(self, target_dir: Path) -> None:
        """Execute project initialization.

        Creates the project structure including directories
        and manifest file.

        Args:
            target_dir: Path to the project root directory.

        Raises:
            NestError: If project already exists.
        """
        # Check for existing project
        if self._manifest.exists(target_dir):
            raise NestError("Nest project already exists. Use `nest sync` to process documents.")

        # Create directories with progress
        status_start("Creating project structure")
        for dir_name in INIT_DIRECTORIES:
            dir_path = target_dir / dir_name
            self._filesystem.create_directory(dir_path)

        # Create manifest
        self._manifest.create(target_dir)
        status_done()

        # Create/update .gitignore
        self._setup_gitignore(target_dir)

        # Create/update .gitattributes for cross-platform line endings
        self._setup_gitattributes(target_dir)

        # Generate agent files with progress
        status_start("Generating agent files")
        agent_dir = target_dir / AGENT_DIR
        self._agent_writer.generate_all(agent_dir)
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
                gitignore.write_text(content, encoding="utf-8", newline="\n")
        else:
            lines: list[str] = []
            for comment, entry in _GITIGNORE_ENTRIES:
                lines.append(comment)
                lines.append(entry)
            gitignore.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")

    @staticmethod
    def _setup_gitattributes(target_dir: Path) -> None:
        """Create or update .gitattributes with Nest line ending rules.

        Generates entries for binary source documents and text files
        across _nest_sources/, _nest_context/, and .nest/ directories.
        Uses a comment marker for idempotent append.

        Args:
            target_dir: Path to the project root directory.
        """
        gitattributes = target_dir / ".gitattributes"

        # Build the Nest block
        block_lines: list[str] = [_GITATTRIBUTES_MARKER]
        block_lines.append("# Binary source documents — never touch line endings")
        for ext in SUPPORTED_EXTENSIONS:
            block_lines.append(f"{SOURCES_DIR}/**/*{ext} binary")

        block_lines.append("")
        block_lines.append("# Text source files — normalize to LF for consistent checksums")
        for ext in CONTEXT_TEXT_EXTENSIONS:
            block_lines.append(f"{SOURCES_DIR}/**/*{ext} text eol=lf")

        block_lines.append("")
        block_lines.append("# Context output — same LF normalization")
        for ext in CONTEXT_TEXT_EXTENSIONS:
            block_lines.append(f"{CONTEXT_DIR}/**/*{ext} text eol=lf")

        block_lines.append("")
        block_lines.append("# Nest metadata — LF normalized")
        for ext in _NEST_METADATA_TEXT_EXTENSIONS:
            block_lines.append(f"{NEST_META_DIR}/**/*{ext} text eol=lf")

        nest_block = "\n".join(block_lines) + "\n"

        if gitattributes.exists():
            content = gitattributes.read_text(encoding="utf-8")
            # Skip if Nest block already present
            if _GITATTRIBUTES_MARKER in content:
                return
            # Append with separator
            if content and not content.endswith("\n"):
                content += "\n"
            content += "\n" + nest_block
            gitattributes.write_text(content, encoding="utf-8", newline="\n")
        else:
            gitattributes.write_text(nest_block, encoding="utf-8", newline="\n")
