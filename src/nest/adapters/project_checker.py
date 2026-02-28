"""Project state checker adapter."""

from pathlib import Path

from nest.adapters.manifest import ManifestAdapter
from nest.core.models import Manifest
from nest.core.paths import NEST_META_DIR

# Folder names (consistent with init and sync commands)
SOURCE_FOLDER = "_nest_sources"
CONTEXT_FOLDER = "_nest_context"
AGENT_FILE_PATH = ".github/agents/nest.agent.md"

# Legacy manifest filename (pre-.nest/ era)
_LEGACY_MANIFEST = ".nest_manifest.json"


class ProjectChecker:
    """Adapter for project state validation.

    Implements ProjectCheckerProtocol.
    """

    def __init__(self) -> None:
        """Initialize project checker."""
        self._manifest_adapter = ManifestAdapter()

    def manifest_exists(self, project_dir: Path) -> bool:
        """Check if manifest exists.

        Args:
            project_dir: Path to the project root directory.

        Returns:
            True if .nest/manifest.json exists, False otherwise.
        """
        return self._manifest_adapter.exists(project_dir)

    def load_manifest(self, project_dir: Path) -> Manifest:
        """Load manifest (may raise ManifestError).

        Args:
            project_dir: Path to the project root directory.

        Returns:
            The loaded Manifest instance.

        Raises:
            ManifestError: If manifest file is invalid or corrupt.
        """
        return self._manifest_adapter.load(project_dir)

    def agent_file_exists(self, project_dir: Path) -> bool:
        """Check if agent file exists.

        Args:
            project_dir: Path to the project root directory.

        Returns:
            True if .github/agents/nest.agent.md exists, False otherwise.
        """
        return (project_dir / AGENT_FILE_PATH).exists()

    def source_folder_exists(self, project_dir: Path) -> bool:
        """Check if source folder exists.

        Args:
            project_dir: Path to the project root directory.

        Returns:
            True if _nest_sources/ directory exists, False otherwise.
        """
        return (project_dir / SOURCE_FOLDER).is_dir()

    def context_folder_exists(self, project_dir: Path) -> bool:
        """Check if context folder exists.

        Args:
            project_dir: Path to the project root directory.

        Returns:
            True if _nest_context/ directory exists, False otherwise.
        """
        return (project_dir / CONTEXT_FOLDER).is_dir()

    def meta_folder_exists(self, project_dir: Path) -> bool:
        """Check if .nest/ metadata directory exists.

        Args:
            project_dir: Path to the project root directory.

        Returns:
            True if .nest/ directory exists, False otherwise.
        """
        return (project_dir / NEST_META_DIR).is_dir()

    def has_legacy_layout(self, project_dir: Path) -> bool:
        """Check if project uses the legacy metadata layout.

        Returns True if .nest_manifest.json exists at root (old layout).

        Args:
            project_dir: Path to the project root directory.

        Returns:
            True if legacy layout detected, False otherwise.
        """
        return (project_dir / _LEGACY_MANIFEST).exists()
