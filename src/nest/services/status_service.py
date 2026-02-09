"""Status service for project state inspection.

Computes an at-a-glance status report for a Nest project without
modifying any project files.

This service is used by the `nest status` CLI command.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from nest import __version__
from nest.adapters.protocols import FileSystemProtocol, ManifestProtocol
from nest.core.checksum import compute_sha256
from nest.core.models import Manifest
from nest.core.orphan_detector import OrphanDetector
from nest.core.paths import (
    CONTEXT_DIR,
    CONTEXT_TEXT_EXTENSIONS,
    MASTER_INDEX_FILE,
    SOURCES_DIR,
    SUPPORTED_EXTENSIONS,
)


@dataclass(frozen=True, slots=True)
class StatusReport:
    """Computed project status for display."""

    project_name: str
    nest_version: str

    source_total: int
    source_new: int
    source_modified: int
    source_unchanged: int

    context_files: int
    context_orphaned: int

    last_sync: datetime | None

    pending_count: int  # new + modified


class StatusService:
    """Compute project status by comparing sources, context, and manifest."""

    def __init__(self, filesystem: FileSystemProtocol, manifest: ManifestProtocol) -> None:
        """Initialize status service.

        Args:
            filesystem: Filesystem operations adapter.
            manifest: Manifest operations adapter.
        """

        self._filesystem = filesystem
        self._manifest = manifest
        self._orphan_detector = OrphanDetector()

    def get_status(self, project_root: Path) -> StatusReport:
        """Compute project status report.

        Args:
            project_root: Project root directory.

        Returns:
            StatusReport with counts and timestamps.

        Raises:
            FileNotFoundError: If the project manifest does not exist.
        """

        manifest = self._manifest.load(project_root)

        (
            source_total,
            source_new,
            source_modified,
            source_unchanged,
        ) = self.analyze_source_files(
            project_root,
            manifest_checksums={k: v.sha256 for k, v in manifest.files.items()},
        )

        context_files, context_orphaned = self.analyze_context_files(project_root, manifest)

        pending_count = source_new + source_modified

        return StatusReport(
            project_name=manifest.project_name,
            nest_version=__version__,
            source_total=source_total,
            source_new=source_new,
            source_modified=source_modified,
            source_unchanged=source_unchanged,
            context_files=context_files,
            context_orphaned=context_orphaned,
            last_sync=manifest.last_sync,
            pending_count=pending_count,
        )

    def analyze_source_files(
        self,
        project_root: Path,
        *,
        manifest_checksums: dict[str, str],
    ) -> tuple[int, int, int, int]:
        """Analyze source files for new/modified/unchanged.

        Args:
            project_root: Project root directory.
            manifest_checksums: Mapping of manifest source keys to sha256.
                Manifest keys are relative to the sources directory.

        Returns:
            Tuple of (total, new, modified, unchanged).
        """

        sources_dir = project_root / SOURCES_DIR
        if not self._filesystem.exists(sources_dir):
            return (0, 0, 0, 0)

        supported = {ext.lower() for ext in SUPPORTED_EXTENSIONS}
        source_files = [
            p for p in self._filesystem.list_files(sources_dir) if p.suffix.lower() in supported
        ]

        new_count = 0
        modified_count = 0
        unchanged_count = 0

        for source_path in source_files:
            key = source_path.relative_to(sources_dir).as_posix()
            try:
                checksum = compute_sha256(source_path)
            except (OSError, PermissionError):
                # If unreadable, treat as unchanged for status (don’t block status).
                unchanged_count += 1
                continue

            if key not in manifest_checksums:
                new_count += 1
            elif checksum != manifest_checksums[key]:
                modified_count += 1
            else:
                unchanged_count += 1

        return (len(source_files), new_count, modified_count, unchanged_count)

    def analyze_context_files(self, project_root: Path, manifest: Manifest) -> tuple[int, int]:
        """Analyze context directory files and detect orphans.

        Only counts files whose extension is in CONTEXT_TEXT_EXTENSIONS.
        Unsupported file types (e.g., .png, .zip) are excluded from counts.

        Args:
            project_root: Project root directory.
            manifest: Loaded manifest model.

        Returns:
            Tuple of (context_files_count, orphaned_count).
        """

        context_dir = project_root / CONTEXT_DIR
        sources_dir = project_root / SOURCES_DIR

        if not self._filesystem.exists(context_dir):
            return (0, 0)

        output_files = self._filesystem.list_files(context_dir)
        supported_text = {ext.lower() for ext in CONTEXT_TEXT_EXTENSIONS}

        context_files = 0
        for path in output_files:
            rel = path.relative_to(context_dir).as_posix()
            if rel == MASTER_INDEX_FILE:
                continue
            if path.suffix.lower() not in supported_text:
                continue
            context_files += 1

        manifest_sources: dict[Path, str] = {}
        for key, entry in manifest.files.items():
            if entry.status == "success":
                manifest_sources[sources_dir / key] = entry.output

        orphans = self._orphan_detector.detect(output_files, manifest_sources, context_dir)
        orphaned_count = len(orphans)

        return (context_files, orphaned_count)
