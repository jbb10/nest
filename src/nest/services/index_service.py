from datetime import datetime, timezone
from pathlib import Path

from nest.adapters.protocols import FileSystemProtocol


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
        self._processed_dir = self._root / "processed_context"

    def generate_content(self, files: list[str], project_name: str) -> str:
        """Generate content for the master index file.

        Args:
            files: List of file paths (relative to processed_context).
            project_name: Name of the project.

        Returns:
            Formatted Markdown content for the index.
        """
        timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
        sorted_files = sorted(files)
        count = len(sorted_files)

        lines = [
            f"# Nest Project Index: {project_name}",
            f"Generated: {timestamp} | Files: {count}",
            "",
            "## File Listing",
        ]

        if sorted_files:
            lines.extend(sorted_files)
        
        # Ensure trailing newline
        lines.append("")
        
        return "\n".join(lines)

    def write_index(self, content: str) -> None:
        """Write index content to file.

        Args:
            content: The content to write.
        """
        # Ensure directory exists just in case
        if not self._fs.exists(self._processed_dir):
            self._fs.create_directory(self._processed_dir)

        index_path = self._processed_dir / "00_MASTER_INDEX.md"
        self._fs.write_text(index_path, content)

    def update_index(self, files: list[str], project_name: str) -> None:
        """Update the master index with the given list of files.

        Args:
            files: List of file paths (relative to processed_context).
            project_name: Name of the project.
        """
        content = self.generate_content(files, project_name)
        self.write_index(content)
