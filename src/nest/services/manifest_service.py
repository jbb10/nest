"""Manifest tracking service for sync operations.

Orchestrates manifest updates during document processing,
recording success/failure status for each file.
"""

from datetime import datetime, timezone
from pathlib import Path

from nest import __version__
from nest.adapters.protocols import ManifestProtocol
from nest.core.models import FileEntry
from nest.core.paths import source_path_to_manifest_key


class ManifestService:
    """Orchestrates manifest tracking and updates during sync.

    Records processing results for each file and commits updates
    to the manifest when sync completes.

    Attributes:
        _manifest_adapter: Protocol-compliant manifest adapter.
        _project_root: Absolute path to project root.
        _raw_inbox: Absolute path to raw_inbox directory.
        _output_dir: Absolute path to processed_context directory.
        _pending_entries: Entries awaiting commit to manifest.
    """

    def __init__(
        self,
        manifest: ManifestProtocol,
        project_root: Path,
        raw_inbox_name: str = "raw_inbox",
        output_dir_name: str = "processed_context",
    ) -> None:
        """Initialize ManifestService.

        Args:
            manifest: Protocol-compliant manifest adapter for file operations.
            project_root: Absolute path to project root directory.
            raw_inbox_name: Name of raw_inbox directory. Defaults to "raw_inbox".
            output_dir_name: Name of output directory. Defaults to "processed_context".
        """
        self._manifest_adapter = manifest
        self._project_root = project_root
        self._raw_inbox = project_root / raw_inbox_name
        self._output_dir = project_root / output_dir_name
        self._pending_entries: dict[str, FileEntry] = {}

    def record_success(
        self,
        source_path: Path,
        checksum: str,
        output_path: Path,
    ) -> FileEntry:
        """Record a successfully processed file.

        Creates a FileEntry with success status and stores it for
        later commit to the manifest.

        Args:
            source_path: Absolute path to the source document.
            checksum: SHA-256 hash of the source file.
            output_path: Absolute path to the generated Markdown file.

        Returns:
            The created FileEntry instance.
        """
        key = source_path_to_manifest_key(source_path, self._raw_inbox)
        output_relative = output_path.relative_to(self._output_dir).as_posix()

        entry = FileEntry(
            sha256=checksum,
            processed_at=datetime.now(timezone.utc),
            output=output_relative,
            status="success",
        )
        self._pending_entries[key] = entry
        return entry

    def record_failure(
        self,
        source_path: Path,
        checksum: str,
        error: str,
    ) -> FileEntry:
        """Record a failed processing attempt.

        Creates a FileEntry with failed status and error message,
        storing it for later commit to the manifest.

        Args:
            source_path: Absolute path to the source document.
            checksum: SHA-256 hash of the source file.
            error: Error message describing the failure.

        Returns:
            The created FileEntry instance.
        """
        key = source_path_to_manifest_key(source_path, self._raw_inbox)

        entry = FileEntry(
            sha256=checksum,
            processed_at=datetime.now(timezone.utc),
            output="",  # No output for failures
            status="failed",
            error=error,
        )
        self._pending_entries[key] = entry
        return entry

    def commit(self) -> None:
        """Write all pending entries to manifest.

        Merges pending entries into the existing manifest, updates
        metadata (last_sync, nest_version), and saves to disk.
        Clears pending entries after successful commit.
        """
        manifest = self._manifest_adapter.load(self._project_root)

        # Merge pending entries into existing files
        manifest.files.update(self._pending_entries)

        # Update metadata
        manifest.last_sync = datetime.now(timezone.utc)
        manifest.nest_version = __version__

        self._manifest_adapter.save(self._project_root, manifest)
        self._pending_entries.clear()
