from datetime import datetime, timezone
from pathlib import Path

from nest.adapters.protocols import FileSystemProtocol
from nest.core.models import FileMetadata
from nest.core.paths import (
    INDEX_TABLE_END,
    INDEX_TABLE_START,
    NEST_META_DIR,
)


def parse_index_descriptions(content: str) -> dict[str, str]:
    """Extract file→description mapping from existing index table.

    Parses the Markdown table between nest:index-table-start/end markers
    and extracts the description for each file path.

    Args:
        content: Full content of the master index file.

    Returns:
        Dict mapping file path to description string.
    """
    start = content.find(INDEX_TABLE_START)
    end = content.find(INDEX_TABLE_END)
    if start == -1 or end == -1:
        return {}
    table_block = content[start:end]
    descriptions: dict[str, str] = {}
    for line in table_block.splitlines():
        if not line.startswith("|"):
            continue
        parts = [p.strip() for p in line.split("|")]
        # parts: ['', 'file.md', '123', 'description text', '']
        if len(parts) < 5:
            continue
        file_path = parts[1]
        if not file_path or file_path == "File" or file_path.startswith("--"):
            continue
        # Handle descriptions containing pipe characters:
        # Join parts[3:-1] to reconstruct the full description
        description = " | ".join(parts[3:-1]).strip()
        descriptions[file_path] = description
    return descriptions


class IndexService:
    """Service for generating the master index of processed documents."""

    def __init__(self, filesystem: FileSystemProtocol, project_root: Path):
        """Initialize IndexService.

        Args:
            filesystem: FileSystemProtocol implementation.
            project_root: Root directory of the project.
        """
        self._fs = filesystem
        self._root = project_root
        self._meta_dir = self._root / NEST_META_DIR

    def generate_content(
        self,
        files: list[FileMetadata],
        old_descriptions: dict[str, str],
        old_hints: dict[str, str],
        project_name: str,
    ) -> str:
        """Generate content for the master index file in table format.

        Args:
            files: List of FileMetadata for all context files.
            old_descriptions: Dict of path→description from previous index.
            old_hints: Dict of path→content_hash from previous hints.
            project_name: Name of the project.

        Returns:
            Formatted Markdown content for the index.
        """
        timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
        # Sort files case-insensitively for better UX
        sorted_files = sorted(files, key=lambda f: f.path.casefold())
        count = len(sorted_files)

        lines = [
            f"# Nest Project Index: {project_name}",
            f"Generated: {timestamp} | Files: {count}",
            "",
            "## File Listing",
            "",
            INDEX_TABLE_START,
            "| File | Lines | Description |",
            "|------|------:|-------------|",
        ]

        for file_meta in sorted_files:
            # Carry forward description if content_hash unchanged
            description = ""
            if file_meta.path in old_hints and old_hints[file_meta.path] == file_meta.content_hash:
                description = old_descriptions.get(file_meta.path, "")
            lines.append(f"| {file_meta.path} | {file_meta.lines} | {description} |")

        lines.append(INDEX_TABLE_END)

        # Ensure trailing newline
        lines.append("")

        return "\n".join(lines)

    def write_index(self, content: str) -> None:
        """Write index content to file.

        Args:
            content: The content to write.
        """
        # Ensure .nest/ directory exists
        if not self._fs.exists(self._meta_dir):
            self._fs.create_directory(self._meta_dir)

        index_path = self._meta_dir / "00_MASTER_INDEX.md"
        self._fs.write_text(index_path, content)

    def read_index_content(self) -> str:
        """Read the current master index content if it exists.

        Returns:
            Index file content, or empty string if file doesn't exist.
        """
        index_path = self._meta_dir / "00_MASTER_INDEX.md"
        if not self._fs.exists(index_path):
            return ""
        try:
            return self._fs.read_text(index_path)
        except OSError:
            return ""
