"""Discovery service for detecting file changes.

This module provides the DiscoveryService which orchestrates file discovery
and change detection against the manifest.
"""

from pathlib import Path

from nest.adapters.protocols import FileDiscoveryProtocol, ManifestProtocol
from nest.core.change_detector import FileChangeDetector
from nest.core.checksum import compute_sha256
from nest.core.paths import SOURCES_DIR, SUPPORTED_EXTENSIONS
from nest.core.models import DiscoveredFile, DiscoveryResult


class DiscoveryService:
    """Service for discovering and classifying file changes.

    Orchestrates file discovery in sources directory and classifies files
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

    def discover_changes(self, project_dir: Path, force: bool = False) -> DiscoveryResult:
        """Discover files in sources directory and classify by change status.

        Args:
            project_dir: Path to the project root directory.
            force: If True, mark all files as 'modified' regardless of checksum.

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

        # Discover files in sources directory
        sources_dir = project_dir / SOURCES_DIR
        discovered_paths = self._file_discovery.discover(
            sources_dir, set(SUPPORTED_EXTENSIONS)
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

            # Classify based on manifest (or force mode)
            if force:
                # Force mode: treat all files as needing reprocessing
                # New files stay "new", existing files become "modified"
                path_key = relative_path.as_posix()
                if path_key in manifest_checksums:
                    status = "modified"
                else:
                    status = "new"
            else:
                # Normal mode: classify based on checksum comparison
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
