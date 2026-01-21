"""Filesystem adapter implementation.

Handles directory and file operations for the project.
"""

from pathlib import Path

from nest.core.paths import mirror_path


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

    def get_relative_path(self, source: Path, base: Path) -> Path:
        """Get path of source relative to base directory.

        Args:
            source: Absolute path to compute relative path for.
            base: Base directory to compute relative from.

        Returns:
            Relative Path from base to source.
        """
        return source.relative_to(base)

    def compute_output_path(
        self,
        source: Path,
        raw_dir: Path,
        output_dir: Path,
    ) -> Path:
        """Compute mirrored output path for a source file.

        Preserves subdirectory structure and changes extension to .md.

        Args:
            source: Absolute path to source file.
            raw_dir: Root of sources directory.
            output_dir: Root of context directory.

        Returns:
            Absolute path where output Markdown should be written.
        """
        return mirror_path(source, raw_dir, output_dir, ".md")

    def delete_file(self, path: Path) -> None:
        """Delete a file from the filesystem.

        Args:
            path: Path to the file to delete.

        Note:
            Uses missing_ok=True to handle already-deleted files gracefully.
        """
        path.unlink(missing_ok=True)

    def list_files(self, directory: Path) -> list[Path]:
        """List all files recursively in a directory.

        Args:
            directory: Root directory to search.

        Returns:
            Sorted list of absolute paths to all files (not directories).
            Hidden files (starting with '.') are excluded.
        """
        files: list[Path] = []
        for item in directory.rglob("*"):
            # Skip directories
            if item.is_dir():
                continue
            # Skip hidden files
            if item.name.startswith("."):
                continue
            files.append(item)
        return sorted(files)
