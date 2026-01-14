"""Discovery service for detecting file changes.

This module provides the DiscoveryService which orchestrates file discovery
and change detection against the manifest.
"""

from pathlib import Path

from nest.adapters.protocols import FileDiscoveryProtocol, ManifestProtocol
from nest.core.change_detector import FileChangeDetector
from nest.core.checksum import compute_sha256
from nest.core.constants import SUPPORTED_EXTENSIONS
from nest.core.models import DiscoveredFile, DiscoveryResult


class DiscoveryService:
    """Service for discovering and classifying file changes.

    Orchestrates file discovery in raw_inbox/ and classifies files
    as new, modified, or unchanged based on manifest checksums.
    """

    def __init__(
        self,
        file_discovery: FileDiscoveryProtocol,
        manifest: ManifestProtocol,
    ) -> None:
        """Initialize discovery service with dependencies.

        Args:
            file_discovery: Adapter for discovering files in directories.
            manifest: Adapter for reading/writing manifest files.
        """
        self._file_discovery = file_discovery
        self._manifest = manifest

    def discover_changes(self, project_dir: Path) -> DiscoveryResult:
        """Discover files in raw_inbox/ and classify by change status.

        Args:
            project_dir: Path to the project root directory.

        Returns:
            DiscoveryResult containing lists of new, modified, and unchanged files.
        """
        # Load manifest to get existing file entries
        try:
            manifest = self._manifest.load(project_dir)
            manifest_files = manifest.files
        except FileNotFoundError:
            # Manifest doesn't exist yet (first run) or is missing
            manifest_files = {}

        # Build checksum lookup from manifest
        manifest_checksums: dict[str, str] = {
            path: entry.sha256 for path, entry in manifest_files.items()
        }

        # Create change detector with manifest data
        detector = FileChangeDetector(manifest_checksums)

        # Discover files in raw_inbox/
        raw_inbox = project_dir / "raw_inbox"
        discovered_paths = self._file_discovery.discover(
            raw_inbox, set(SUPPORTED_EXTENSIONS)
        )

        # Classify each discovered file
        result = DiscoveryResult()

        for file_path in discovered_paths:
            # Compute checksum
            try:
                checksum = compute_sha256(file_path)
            except (OSError, PermissionError):
                # Skip files that cannot be read (e.g., locked, deleted race condition)
                continue

            # Get relative path for manifest comparison
            relative_path = file_path.relative_to(project_dir)

            # Classify based on manifest
            status = detector.classify(relative_path, checksum)

            # Create discovered file entry
            discovered = DiscoveredFile(
                path=file_path,
                status=status,
                checksum=checksum,
            )

            # Add to appropriate list based on status
            if status == "new":
                result.new_files.append(discovered)
            elif status == "modified":
                result.modified_files.append(discovered)
            else:
                result.unchanged_files.append(discovered)

        return result
