"""Service for extracting structural metadata from context files.

Extracts headings, first paragraph, line count, and table columns
from text files in the context directory for index enrichment hints.
"""

import hashlib
import json
import logging
import re
from pathlib import Path
from typing import cast

import yaml

from nest.adapters.protocols import FileSystemProtocol
from nest.core.models import FileMetadata, HeadingInfo
from nest.core.paths import (
    CONTEXT_TEXT_EXTENSIONS,
    GLOSSARY_HINTS_FILE,
    INDEX_HINTS_FILE,
    MASTER_INDEX_FILE,
)

logger = logging.getLogger(__name__)

HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)


def _compute_content_hash(headings: list[HeadingInfo], first_paragraph: str, lines: int) -> str:
    """Deterministic hash of extracted metadata for change detection.

    Args:
        headings: List of heading info objects.
        first_paragraph: First paragraph text.
        lines: Line count.

    Returns:
        16-character hex prefix of SHA-256 hash.
    """
    payload = json.dumps(
        {
            "headings": [{"level": h.level, "text": h.text} for h in headings],
            "first_paragraph": first_paragraph,
            "lines": lines,
        },
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def _extract_headings(content: str) -> list[HeadingInfo]:
    """Extract Markdown headings from content.

    Args:
        content: File content as string.

    Returns:
        List of HeadingInfo objects.
    """
    return [
        HeadingInfo(level=len(match.group(1)), text=match.group(2).strip())
        for match in HEADING_PATTERN.finditer(content)
    ]


def _extract_first_paragraph(content: str, *, is_markdown: bool) -> str:
    """Extract first non-empty, non-heading paragraph from content.

    Args:
        content: File content as string.
        is_markdown: Whether the file is a Markdown file.

    Returns:
        First paragraph text, truncated to 200 characters.
    """
    if not content.strip():
        return ""

    if is_markdown:
        for line in content.splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                return stripped[:200]
    else:
        for line in content.splitlines():
            stripped = line.strip()
            if stripped:
                return stripped[:200]

    return ""


def _extract_csv_columns(content: str) -> list[str]:
    """Extract header row columns from CSV content.

    Args:
        content: CSV file content as string.

    Returns:
        List of column header strings.
    """
    if not content.strip():
        return []

    first_line = content.splitlines()[0].strip()
    if not first_line:
        return []

    return [col.strip().strip('"').strip("'") for col in first_line.split(",")]


class MetadataExtractorService:
    """Service for extracting file metadata for index enrichment hints."""

    def __init__(self, filesystem: FileSystemProtocol, project_root: Path) -> None:
        """Initialize MetadataExtractorService.

        Args:
            filesystem: FileSystemProtocol implementation for file I/O.
            project_root: Root directory of the project.
        """
        self._fs = filesystem
        self._project_root = project_root

    def extract_file_metadata(self, file_path: Path, context_dir: Path) -> FileMetadata:
        """Extract structural metadata from a single file.

        Args:
            file_path: Absolute path to the file.
            context_dir: Root of the context directory.

        Returns:
            FileMetadata with extracted information.
        """
        relative = file_path.relative_to(context_dir).as_posix()
        suffix = file_path.suffix.lower()
        is_markdown = suffix == ".md"

        try:
            content = self._fs.read_text(file_path)
        except (OSError, UnicodeDecodeError) as e:
            logger.warning("Cannot read %s: %s", file_path, e)
            # Return minimal metadata for unreadable files
            empty_hash = _compute_content_hash([], "", 0)
            return FileMetadata(
                path=relative,
                content_hash=empty_hash,
                lines=0,
                headings=[],
                first_paragraph="",
                table_columns=[],
            )

        lines = len(content.splitlines()) if content else 0
        headings = _extract_headings(content) if is_markdown else []
        first_paragraph = _extract_first_paragraph(content, is_markdown=is_markdown)
        table_columns = _extract_csv_columns(content) if suffix == ".csv" else []
        content_hash = _compute_content_hash(headings, first_paragraph, lines)

        return FileMetadata(
            path=relative,
            content_hash=content_hash,
            lines=lines,
            headings=headings,
            first_paragraph=first_paragraph,
            table_columns=table_columns,
        )

    def extract_all(self, context_dir: Path) -> list[FileMetadata]:
        """Extract metadata for all supported text files in context directory.

        Excludes 00_MASTER_INDEX.md and 00_INDEX_HINTS.yaml.

        Args:
            context_dir: Absolute path to the context directory.

        Returns:
            List of FileMetadata for all supported files.
        """
        all_files = self._fs.list_files(context_dir)
        supported = {ext.lower() for ext in CONTEXT_TEXT_EXTENSIONS}
        excluded = {MASTER_INDEX_FILE, INDEX_HINTS_FILE, GLOSSARY_HINTS_FILE}

        results: list[FileMetadata] = []
        for file_path in all_files:
            if file_path.suffix.lower() not in supported:
                continue
            if file_path.name in excluded:
                continue
            results.append(self.extract_file_metadata(file_path, context_dir))

        return results

    def load_previous_hints(self, hints_path: Path) -> dict[str, str]:
        """Load previous hints file and return path→content_hash mapping.

        Args:
            hints_path: Absolute path to the hints YAML file.

        Returns:
            Dict mapping file path to content_hash. Empty dict if file
            doesn't exist or is corrupt.
        """
        if not self._fs.exists(hints_path):
            return {}

        try:
            content = self._fs.read_text(hints_path)
            data = yaml.safe_load(content)
            if not isinstance(data, dict) or "files" not in data:
                logger.warning("Invalid hints file structure at %s", hints_path)
                return {}
            result: dict[str, str] = {}
            raw_files = cast(list[dict[str, str]], data["files"])
            for entry in raw_files:
                if "path" in entry and "content_hash" in entry:
                    result[entry["path"]] = entry["content_hash"]
            return result
        except (OSError, yaml.YAMLError) as e:
            logger.warning("Cannot parse hints file %s: %s", hints_path, e)
            return {}

    def write_hints(self, hints: list[FileMetadata], hints_path: Path) -> None:
        """Write extracted metadata to hints YAML file.

        Args:
            hints: List of FileMetadata to write.
            hints_path: Absolute path to write the hints file.
        """
        data = {
            "files": [
                {
                    "path": h.path,
                    "content_hash": h.content_hash,
                    "lines": h.lines,
                    "headings": [{"level": hd.level, "text": hd.text} for hd in h.headings],
                    "first_paragraph": h.first_paragraph,
                    "table_columns": h.table_columns,
                }
                for h in hints
            ]
        }
        header = "# Auto-generated by nest sync \u2014 do not edit manually\n"
        yaml_content = yaml.safe_dump(
            data, default_flow_style=False, allow_unicode=True, sort_keys=False
        )
        content = header + yaml_content

        # Ensure parent directory exists
        parent = hints_path.parent
        if not self._fs.exists(parent):
            self._fs.create_directory(parent)

        self._fs.write_text(hints_path, content)
