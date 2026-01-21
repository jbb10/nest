"""Orphan cleanup service.

Orchestrates detection and removal of orphaned output files.
"""

import logging
from pathlib import Path

from nest.adapters.protocols import FileSystemProtocol, ManifestProtocol
from nest.core.models import OrphanCleanupResult
from nest.core.orphan_detector import OrphanDetector
from nest.core.paths import CONTEXT_DIR

logger = logging.getLogger(__name__)


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

    def detect_orphans(self) -> list[str]:
        """Detect orphan files without removing them.

        Returns:
            List of relative paths (posix format) of orphaned files.
        """
        output_dir = self._project_root / CONTEXT_DIR

        # Load manifest to build source->output mapping
        manifest = self._manifest.load(self._project_root)
        
        # Build mapping: source_path -> output_path (for successful entries only)
        manifest_sources: dict[Path, str] = {}
        for key, entry in manifest.files.items():
            if entry.status == "success":
                source_path = self._project_root / key
                manifest_sources[source_path] = entry.output

        # List all files in context directory
        output_files = self._filesystem.list_files(output_dir)

        # Detect orphans (manifest files with missing sources)
        orphans = self._detector.detect(output_files, manifest_sources, output_dir)

        # Convert to relative paths
        return [orphan.relative_to(output_dir).as_posix() for orphan in orphans]

    def cleanup(self, no_clean: bool = False) -> OrphanCleanupResult:
        """Detect and optionally remove orphan files.

        Args:
            no_clean: If True, detect but don't delete orphans.

        Returns:
            OrphanCleanupResult with detection/removal details.
        """
        output_dir = self._project_root / CONTEXT_DIR

        # Load manifest to build source->output mapping
        manifest = self._manifest.load(self._project_root)
        
        # Build mapping: source_path -> output_path (for successful entries only)
        manifest_sources: dict[Path, str] = {}
        for key, entry in manifest.files.items():
            if entry.status == "success":
                source_path = self._project_root / key
                manifest_sources[source_path] = entry.output

        # List all files in context directory
        output_files = self._filesystem.list_files(output_dir)

        # Detect orphans (manifest files with missing sources)
        orphans = self._detector.detect(output_files, manifest_sources, output_dir)

        # Convert to relative paths for result
        orphans_detected = [orphan.relative_to(output_dir).as_posix() for orphan in orphans]

        orphans_removed: list[str] = []

        if not no_clean:
            try:
                # Remove orphan files with logging
                for orphan in orphans:
                    relative_path = orphan.relative_to(output_dir).as_posix()
                    logger.info("Removing orphan file: %s", relative_path)
                    self._filesystem.delete_file(orphan)

                # Build reverse lookup for O(1) manifest entry removal
                orphan_outputs = {orphan.relative_to(output_dir).as_posix() for orphan in orphans}
                output_to_key = {entry.output: key for key, entry in manifest.files.items()}

                # Remove orphan entries from manifest
                for orphan_output in orphan_outputs:
                    if orphan_output in output_to_key:
                        key = output_to_key[orphan_output]
                        logger.debug("Removing manifest entry: %s -> %s", key, orphan_output)
                        del manifest.files[key]

                # Save updated manifest
                self._manifest.save(self._project_root, manifest)
                logger.info("Orphan cleanup complete: %d files removed", len(orphans))

                orphans_removed = orphans_detected
            except Exception as e:
                logger.error("Orphan cleanup failed: %s", e)
                raise

        return OrphanCleanupResult(
            orphans_detected=orphans_detected,
            orphans_removed=orphans_removed,
            skipped=no_clean,
        )

    def count_user_curated_files(self) -> int:
        """Count files in context directory that are NOT in manifest (user-curated).

        Returns:
            Number of user-curated files.
        """
        output_dir = self._project_root / CONTEXT_DIR

        # Load manifest to get tracked outputs
        manifest = self._manifest.load(self._project_root)
        manifest_outputs = {entry.output for entry in manifest.files.values()}

        # List all files in context directory
        output_files = self._filesystem.list_files(output_dir)

        # Count files NOT in manifest (excluding system files)
        user_curated = 0
        for file_path in output_files:
            relative = file_path.relative_to(output_dir).as_posix()
            # Skip system files
            if relative == "00_MASTER_INDEX.md":
                continue
            # Count if NOT in manifest
            if relative not in manifest_outputs:
                user_curated += 1

        return user_curated
