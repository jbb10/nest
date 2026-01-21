from datetime import datetime, timezone
from pathlib import Path

from nest.adapters.protocols import FileSystemProtocol
from nest.core.paths import CONTEXT_DIR, MASTER_INDEX_FILE


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
        self._context_dir = self._root / CONTEXT_DIR

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
        if not self._fs.exists(self._context_dir):
            self._fs.create_directory(self._context_dir)

        index_path = self._context_dir / MASTER_INDEX_FILE
        self._fs.write_text(index_path, content)

    def update_index(self, project_name: str) -> None:
        """Update the master index by scanning all .md files in context directory.

        Scans the entire context directory for all .md files (both manifest-tracked
        and user-curated), sorts them, and generates the index.

        Args:
            project_name: Name of the project.
        """
        # Scan entire context directory for all .md files
        all_files = self._fs.list_files(self._context_dir)
        
        # Filter to .md files and exclude the index itself
        md_files: list[str] = []
        for file_path in all_files:
            if file_path.suffix == ".md":
                relative = file_path.relative_to(self._context_dir).as_posix()
                # Exclude the master index itself
                if relative != MASTER_INDEX_FILE:
                    md_files.append(relative)
        
        content = self.generate_content(md_files, project_name)
        self.write_index(content)
