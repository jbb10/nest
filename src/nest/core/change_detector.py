"""File change detection logic.

This module provides pure business logic for classifying files
based on their presence and checksum in the manifest.
"""

from pathlib import Path

from nest.core.models import FileStatus


class FileChangeDetector:
    """Classifies files as new, modified, or unchanged based on manifest data.

    This class contains pure business logic with no I/O operations.
    It compares file checksums against a manifest to determine
    the change status of each file.
    """

    def __init__(self, manifest_files: dict[str, str]) -> None:
        """Initialize detector with manifest file data.

        Args:
            manifest_files: Dictionary mapping relative file paths to their
                           SHA-256 checksums from the manifest.
        """
        self._manifest_files = manifest_files

    def classify(self, path: Path, checksum: str) -> FileStatus:
        """Classify a file's change status based on manifest data.

        Args:
            path: Path to the file (relative to project root).
            checksum: Current SHA-256 checksum of the file.

        Returns:
            FileStatus indicating whether the file is:
            - "new": Not present in manifest
            - "modified": Present but checksum differs
            - "unchanged": Present with matching checksum
        """
        # Normalize path to use forward slashes consistently
        path_key = path.as_posix()

        # Check if file exists in manifest
        if path_key not in self._manifest_files:
            return "new"

        # Compare checksums
        manifest_checksum = self._manifest_files[path_key]
        if checksum != manifest_checksum:
            return "modified"

        return "unchanged"
