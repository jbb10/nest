"""Core domain models for the Nest application.

These Pydantic models define the structure of core business entities.
"""

from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# Type alias for file change status during discovery
FileStatus = Literal["new", "modified", "unchanged"]

# Type alias for processing status
ProcessingStatus = Literal["success", "skipped", "failed"]


class ProcessingResult(BaseModel):
    """Result of a document processing operation.

    Returned by DocumentProcessorProtocol implementations to indicate
    success, failure, or skip status for individual file processing.

    Attributes:
        source_path: Path to the source document that was processed.
        status: Processing outcome (success/skipped/failed).
        output_path: Path to the generated Markdown file (if successful).
        error: Error message describing failure (if status is "failed").
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    source_path: Path
    status: ProcessingStatus
    output_path: Path | None = None
    error: str | None = None


class FileEntry(BaseModel):
    """Represents a processed file entry in the manifest.

    Attributes:
        sha256: Cryptographic hash of the source file.
        processed_at: Timestamp when the file was processed.
        output: Relative path to the output Markdown file.
        status: Processing status (success/failed/skipped).
        error: Error message if processing failed (optional).
    """

    sha256: str
    processed_at: datetime
    output: str
    status: Literal["success", "failed", "skipped"]
    error: str | None = None


class Manifest(BaseModel):
    """Represents the .nest_manifest.json file structure.

    Attributes:
        nest_version: Version of nest that created/updated this manifest.
        project_name: Human-readable project name.
        last_sync: Timestamp of the last successful sync (optional).
        files: Dictionary mapping source file paths to their FileEntry data.
    """

    nest_version: str
    project_name: str
    last_sync: datetime | None = None
    files: dict[str, FileEntry] = Field(default_factory=dict)


class DiscoveredFile(BaseModel):
    """Represents a file discovered during sync with its status.

    Attributes:
        path: Absolute path to the discovered file.
        status: Change status compared to manifest (new/modified/unchanged).
        checksum: SHA-256 hash of the file content.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    path: Path
    status: FileStatus
    checksum: str


class DiscoveryResult(BaseModel):
    """Result of file discovery operation.

    Groups discovered files by their change status for efficient
    batch processing during sync.

    Attributes:
        new_files: Files not present in manifest.
        modified_files: Files with different checksums than manifest.
        unchanged_files: Files with matching checksums (to be skipped).
    """

    new_files: list[DiscoveredFile] = Field(default_factory=lambda: [])
    modified_files: list[DiscoveredFile] = Field(default_factory=lambda: [])
    unchanged_files: list[DiscoveredFile] = Field(default_factory=lambda: [])

    @property
    def pending_count(self) -> int:
        """Count of files requiring processing (new + modified)."""
        return len(self.new_files) + len(self.modified_files)

    @property
    def total_count(self) -> int:
        """Total count of all discovered files."""
        return len(self.new_files) + len(self.modified_files) + len(self.unchanged_files)


class OrphanCleanupResult(BaseModel):
    """Result of orphan cleanup operation.

    Attributes:
        orphans_detected: Relative paths of orphaned files detected.
        orphans_removed: Relative paths of orphans actually removed (only if cleanup enabled).
        skipped: True if --no-clean flag was set (orphans detected but not removed).
    """

    orphans_detected: list[str] = Field(default_factory=lambda: [])
    orphans_removed: list[str] = Field(default_factory=lambda: [])
    skipped: bool = False


class DryRunResult(BaseModel):
    """Result of a dry-run sync operation.

    Shows what WOULD happen if sync were run without --dry-run flag.

    Attributes:
        new_count: Number of new files that would be processed.
        modified_count: Number of modified files that would be reprocessed.
        unchanged_count: Number of unchanged files that would be skipped.
        orphan_count: Number of orphan files that would be removed.
    """

    new_count: int = 0
    modified_count: int = 0
    unchanged_count: int = 0
    orphan_count: int = 0


class SyncResult(BaseModel):
    """Result of a sync operation.

    Contains counts of processed, skipped, and failed files along with
    orphan cleanup information.

    Attributes:
        processed_count: Number of files successfully processed.
        skipped_count: Number of unchanged files skipped.
        failed_count: Number of files that failed processing.
        orphans_removed: Number of orphan files removed.
        orphans_detected: Number of orphan files detected.
        skipped_orphan_cleanup: True if --no-clean was set.
        user_curated_count: Number of user-curated files preserved (not in manifest).
    """

    processed_count: int = 0
    skipped_count: int = 0
    failed_count: int = 0
    orphans_removed: int = 0
    orphans_detected: int = 0
    skipped_orphan_cleanup: bool = False
    user_curated_count: int = 0


class InstallConfig(BaseModel):
    """Installation source and version tracking.

    Attributes:
        source: Git URL for `uv tool install` (e.g., "git+https://github.com/jbjornsson/nest").
        installed_version: Currently installed Nest version string.
        installed_at: Timestamp when this version was installed/updated.
    """

    source: str
    installed_version: str
    installed_at: datetime


class UserConfig(BaseModel):
    """User-level configuration stored at ~/.config/nest/config.toml.

    Attributes:
        install: Installation source and version tracking.
    """

    install: InstallConfig


class UpdateCheckResult(BaseModel):
    """Result of checking for available updates.

    Attributes:
        current_version: Currently installed version string.
        latest_version: Newest available version (None if no versions found).
        annotated_versions: List of (version, annotation) tuples for display.
        update_available: True if a newer version exists.
        source: Git remote URL from user config.
    """

    current_version: str
    latest_version: str | None
    annotated_versions: list[tuple[str, str]]
    update_available: bool
    source: str


class UpdateResult(BaseModel):
    """Result of executing a version update.

    Attributes:
        success: Whether the update completed successfully.
        version: The version that was installed (or attempted).
        previous_version: The version before the update.
        error: Error message if update failed.
    """

    success: bool
    version: str
    previous_version: str
    error: str | None = None


class AgentMigrationCheckResult(BaseModel):
    """Result of checking whether agent template needs migration.

    Attributes:
        migration_needed: True if local agent file differs from current template.
        agent_file_missing: True if agent file doesn't exist at all.
        skipped: True if check was skipped (e.g., not a Nest project).
        message: Human-readable status description.
    """

    migration_needed: bool
    agent_file_missing: bool = False
    skipped: bool = False
    message: str


class AgentMigrationResult(BaseModel):
    """Result of executing agent template migration.

    Attributes:
        success: Whether the migration completed successfully.
        backed_up: Whether the old file was backed up before replacement.
        error: Error message if migration failed.
    """

    success: bool
    backed_up: bool = False
    error: str | None = None
