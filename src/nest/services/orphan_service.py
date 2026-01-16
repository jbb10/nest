"""Orphan cleanup service.

Orchestrates detection and removal of orphaned output files.
"""

from pathlib import Path

from nest.adapters.protocols import FileSystemProtocol, ManifestProtocol
from nest.core.models import OrphanCleanupResult
from nest.core.orphan_detector import OrphanDetector


class OrphanService:
    """Detects and optionally removes orphan files."""

    def __init__(
        self,
        filesystem: FileSystemProtocol,
        manifest: ManifestProtocol,
        project_root: Path,
    ) -> None:
        """Initialize orphan service.

        Args:
            filesystem: Filesystem operations adapter.
            manifest: Manifest operations adapter.
            project_root: Root directory of the project.
        """
        self._filesystem = filesystem
        self._manifest = manifest
        self._project_root = project_root
        self._detector = OrphanDetector()

    def cleanup(self, no_clean: bool = False) -> OrphanCleanupResult:
        """Detect and optionally remove orphan files.

        Args:
            no_clean: If True, detect but don't delete orphans.

        Returns:
            OrphanCleanupResult with detection/removal details.
        """
        output_dir = self._project_root / "processed_context"

        # Load manifest to get successful output paths
        manifest = self._manifest.load(self._project_root)
        manifest_outputs = {
            entry.output
            for entry in manifest.files.values()
            if entry.status == "success"
        }

        # List all files in processed_context
        output_files = self._filesystem.list_files(output_dir)

        # Detect orphans
        orphans = self._detector.detect(output_files, manifest_outputs, output_dir)

        # Convert to relative paths for result
        orphans_detected = [
            orphan.relative_to(output_dir).as_posix() for orphan in orphans
        ]

        orphans_removed: list[str] = []

        if not no_clean:
            # Remove orphan files
            for orphan in orphans:
                self._filesystem.delete_file(orphan)

            # Remove orphan entries from manifest
            orphan_outputs = {
                orphan.relative_to(output_dir).as_posix() for orphan in orphans
            }
            keys_to_remove = [
                key
                for key, entry in manifest.files.items()
                if entry.output in orphan_outputs
            ]
            for key in keys_to_remove:
                del manifest.files[key]

            # Save updated manifest
            self._manifest.save(self._project_root, manifest)

            orphans_removed = orphans_detected

        return OrphanCleanupResult(
            orphans_detected=orphans_detected,
            orphans_removed=orphans_removed,
            skipped=no_clean,
        )
