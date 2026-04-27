"""File discovery adapter for finding documents in directories.

This module provides the FileDiscoveryAdapter which implements recursive
file discovery with extension filtering.
"""

import logging
import os
from pathlib import Path

from nest.adapters.protocols import FileDiscoveryProtocol

logger = logging.getLogger(__name__)


class FileDiscoveryAdapter(FileDiscoveryProtocol):
    """Adapter for discovering files recursively with extension filtering.

    Searches directories recursively for files matching specified extensions,
    excluding hidden files and directories (those starting with '.').
    """

    def discover(self, directory: Path, extensions: set[str]) -> list[Path]:
        """Discover files recursively in a directory, filtered by extension.

        Searches the given directory and all subdirectories for files
        matching the specified extensions. Hidden files and directories
        (starting with '.') are excluded.

        Args:
            directory: Root directory to search.
            extensions: Set of allowed file extensions (e.g., {".pdf", ".docx"}).
                        Extensions should be lowercase with leading dot.

        Returns:
            Sorted list of absolute paths to discovered files.
            Sorting ensures deterministic ordering.
        """
        # Normalize extensions to lowercase for case-insensitive matching
        normalized_extensions = {ext.lower() for ext in extensions}

        discovered: list[Path] = []

        for path in directory.rglob("*"):
            # Warn about broken symlinks (target missing) and skip them.
            # is_symlink() does not follow the link; exists() does.
            if path.is_symlink() and not path.exists():
                logger.warning("Skipping broken symlink: %s", path)
                continue

            # Ensure it's a regular file (skips directories, sockets, devices, etc.)
            # is_file() follows symlinks, so symlinked files are accepted.
            if not path.is_file():
                continue

            # Skip hidden files (name starts with .)
            if path.name.startswith("."):
                continue

            # Skip files in hidden directories
            if any(part.startswith(".") for part in path.relative_to(directory).parts):
                continue

            # Check extension (case-insensitive)
            if path.suffix.lower() in normalized_extensions:
                # Use abspath() rather than resolve() so symlinks remain under
                # the sources directory (resolve() would dereference the link
                # to its real location, breaking relative_to(sources_dir)).
                discovered.append(Path(os.path.abspath(path)))

        # Sort for deterministic ordering
        return sorted(discovered)
