"""File discovery adapter for finding documents in directories.

This module provides the FileDiscoveryAdapter which implements recursive
file discovery with extension filtering.
"""

import logging
import os
from collections.abc import Iterator
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
        (starting with '.') are excluded. Directory links (symlinks and
        Windows junctions) are followed; links that loop are skipped.

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

        for path in _walk(directory):
            # Warn about broken links (target missing) and skip them.
            # lexists() does not follow links; exists() does. This also covers
            # Windows junctions, which is_symlink() does not report.
            if os.path.lexists(path) and not path.exists():
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


def _walk(directory: Path) -> Iterator[Path]:
    """Yield every entry below ``directory``, descending into directory links.

    Hidden directories are not entered. A directory that resolves to itself or
    one of its ancestors is skipped with a warning, since entering it would
    recurse forever.
    """
    root = Path(os.path.abspath(directory))
    root_ancestors = frozenset(
        _identity(p) for base in (root, Path(os.path.realpath(root))) for p in (base, *base.parents)
    )
    pending: list[tuple[Path, frozenset[str]]] = [(directory, root_ancestors)]
    while pending:
        current, ancestors = pending.pop()
        try:
            with os.scandir(current) as it:
                entries = list(it)
        except OSError as e:
            if current is not directory:
                logger.warning("Skipping unreadable directory: %s (%s)", current, e)
            continue
        for entry in entries:
            path = current / entry.name
            yield path
            if entry.name.startswith("."):
                continue
            try:
                # entry.is_dir() is True for a dangling junction on Windows.
                if not (entry.is_dir() and os.path.isdir(path)):
                    continue
            except OSError:
                continue
            identity = _identity(path)
            if identity in ancestors:
                logger.warning("Skipping symlink loop: %s", path)
                continue
            pending.append((path, ancestors | {identity}))


def _identity(path: Path) -> str:
    return os.path.normcase(os.path.realpath(path))
