"""Core domain models for the Nest application.

These Pydantic models define the structure of core business entities.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


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
