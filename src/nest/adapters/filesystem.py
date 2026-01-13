"""Filesystem adapter implementation.

Handles directory and file operations for the project.
"""

from pathlib import Path


class FileSystemAdapter:
    """Adapter for filesystem operations.

    Implements FileSystemProtocol for directory/file operations.
    All methods use pathlib.Path for path handling.
    """

    def create_directory(self, path: Path) -> None:
        """Create a directory, including parent directories.

        Args:
            path: Path to the directory to create.
        """
        path.mkdir(parents=True, exist_ok=True)

    def write_text(self, path: Path, content: str) -> None:
        """Write text content to a file.

        Args:
            path: Path to the file to write.
            content: Text content to write.
        """
        path.write_text(content)

    def read_text(self, path: Path) -> str:
        """Read text content from a file.

        Args:
            path: Path to the file to read.

        Returns:
            The text content of the file.

        Raises:
            FileNotFoundError: If file doesn't exist.
        """
        return path.read_text()

    def exists(self, path: Path) -> bool:
        """Check if a path exists.

        Args:
            path: Path to check.

        Returns:
            True if path exists, False otherwise.
        """
        return path.exists()

    def append_text(self, path: Path, content: str) -> None:
        """Append text content to a file.

        Args:
            path: Path to the file to append to.
            content: Text content to append.
        """
        with path.open("a") as f:
            f.write(content)
