"""Protocol definitions for adapter interfaces.

These protocols define the contracts that adapters must implement.
Services depend on these protocols, not concrete implementations.
"""

from pathlib import Path
from typing import Protocol, runtime_checkable

from nest.core.models import Manifest


@runtime_checkable
class ManifestProtocol(Protocol):
    """Protocol for manifest file operations.

    Implementations handle reading, writing, and checking manifest files.
    """

    def exists(self, project_dir: Path) -> bool:
        """Check if a manifest file exists in the project directory.

        Args:
            project_dir: Path to the project root directory.

        Returns:
            True if .nest_manifest.json exists, False otherwise.
        """
        ...

    def create(self, project_dir: Path, project_name: str) -> Manifest:
        """Create a new manifest file with initial values.

        Args:
            project_dir: Path to the project root directory.
            project_name: Human-readable project name.

        Returns:
            The newly created Manifest instance.
        """
        ...

    def load(self, project_dir: Path) -> Manifest:
        """Load an existing manifest from file.

        Args:
            project_dir: Path to the project root directory.

        Returns:
            The loaded Manifest instance.

        Raises:
            FileNotFoundError: If manifest file doesn't exist.
            json.JSONDecodeError: If manifest file is invalid JSON.
        """
        ...

    def save(self, project_dir: Path, manifest: Manifest) -> None:
        """Save manifest to file.

        Args:
            project_dir: Path to the project root directory.
            manifest: The Manifest instance to save.
        """
        ...


@runtime_checkable
class FileSystemProtocol(Protocol):
    """Protocol for filesystem operations.

    Implementations handle directory and file operations.
    """

    def create_directory(self, path: Path) -> None:
        """Create a directory, including parent directories.

        Args:
            path: Path to the directory to create.
        """
        ...

    def write_text(self, path: Path, content: str) -> None:
        """Write text content to a file.

        Args:
            path: Path to the file to write.
            content: Text content to write.
        """
        ...

    def read_text(self, path: Path) -> str:
        """Read text content from a file.

        Args:
            path: Path to the file to read.

        Returns:
            The text content of the file.

        Raises:
            FileNotFoundError: If file doesn't exist.
        """
        ...

    def exists(self, path: Path) -> bool:
        """Check if a path exists.

        Args:
            path: Path to check.

        Returns:
            True if path exists, False otherwise.
        """
        ...

    def append_text(self, path: Path, content: str) -> None:
        """Append text content to a file.

        Args:
            path: Path to the file to append to.
            content: Text content to append.
        """
        ...


@runtime_checkable
class AgentWriterProtocol(Protocol):
    """Protocol for generating agent instruction files.

    Extensibility: Implementations can support different platforms
    (VS Code, Cursor, generic Markdown, etc.).
    """

    def generate(self, project_name: str, output_path: Path) -> None:
        """Generate agent file at specified path.

        Args:
            project_name: Name of the project for interpolation.
            output_path: Full path where agent file should be written.

        Raises:
            IOError: If file cannot be written.
        """
        ...
