"""Pure path computation functions for output mirroring.

These functions handle path manipulation for mirroring source file
structure in output directories. No I/O operations - fully testable.
"""

from pathlib import Path

# Folder name constants
SOURCES_DIR = "_nest_sources"
CONTEXT_DIR = "_nest_context"
NEST_META_DIR = ".nest"
MASTER_INDEX_FILE = "00_MASTER_INDEX.md"
INDEX_HINTS_FILE = "00_INDEX_HINTS.yaml"
GLOSSARY_FILE = "glossary.md"
INDEX_TABLE_START = "<!-- nest:index-table-start -->"
INDEX_TABLE_END = "<!-- nest:index-table-end -->"
GLOSSARY_TABLE_START = "<!-- nest:glossary-start -->"
GLOSSARY_TABLE_END = "<!-- nest:glossary-end -->"
MANIFEST_FILENAME = "manifest.json"
ERROR_LOG_FILENAME = "errors.log"
AI_SEEN_MARKER = ".ai_seen"
SUPPORTED_EXTENSIONS = [".pdf", ".docx", ".pptx", ".xlsx", ".html"]

# Agent file constants (Epic 10: Multi-Agent Architecture)
AGENT_DIR = Path(".github") / "agents"
AGENT_FILES = [
    "nest.agent.md",
    "nest-master-researcher.agent.md",
    "nest-master-synthesizer.agent.md",
    "nest-master-planner.agent.md",
]
TEMPLATE_TO_AGENT_FILE = {
    "coordinator.md.jinja": "nest.agent.md",
    "researcher.md.jinja": "nest-master-researcher.agent.md",
    "synthesizer.md.jinja": "nest-master-synthesizer.agent.md",
    "planner.md.jinja": "nest-master-planner.agent.md",
}

# Text file extensions supported in context directory (for indexing and counting)
CONTEXT_TEXT_EXTENSIONS = [
    ".md",
    ".txt",
    ".text",
    ".rst",
    ".csv",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".xml",
]

# All file extensions recognized in _nest_sources/ (Docling-convertible + passthrough text)
ALL_SOURCE_EXTENSIONS = sorted(set(SUPPORTED_EXTENSIONS + CONTEXT_TEXT_EXTENSIONS))

# Pre-computed set for O(1) passthrough extension lookups
_PASSTHROUGH_EXTENSIONS = frozenset(ext.lower() for ext in CONTEXT_TEXT_EXTENSIONS)


def is_passthrough_extension(suffix: str) -> bool:
    """Check if file extension should be passthrough-copied (not Docling-converted).

    Args:
        suffix: File extension including leading dot (e.g., ".txt").

    Returns:
        True if the extension is a text format that should be copied as-is.
    """
    return suffix.lower() in _PASSTHROUGH_EXTENSIONS


def passthrough_mirror_path(
    source: Path,
    source_root: Path,
    target_root: Path,
) -> Path:
    """Compute mirrored output path preserving original extension.

    Unlike mirror_path() which changes the suffix to .md, this preserves
    the original file extension for passthrough text files.

    Args:
        source: Absolute path to source file.
        source_root: Root directory of source files.
        target_root: Root directory for output files.

    Returns:
        Absolute path to output file in target directory.

    Raises:
        ValueError: If source is not under source_root.
    """
    relative = source.relative_to(source_root)
    return target_root / relative


def mirror_path(
    source: Path,
    source_root: Path,
    target_root: Path,
    new_suffix: str = ".md",
) -> Path:
    """Compute mirrored output path preserving directory structure.

    Takes a source file path and computes where its output should be
    written to maintain the same subdirectory structure in the target.

    Example:
        source = Path("/project/raw_inbox/contracts/2024/alpha.pdf")
        source_root = Path("/project/raw_inbox")
        target_root = Path("/project/processed_context")

        Result: Path("/project/processed_context/contracts/2024/alpha.md")

    Args:
        source: Absolute path to source file.
        source_root: Root directory of source files.
        target_root: Root directory for output files.
        new_suffix: File extension for output (including dot).

    Returns:
        Absolute path to output file in target directory.

    Raises:
        ValueError: If source is not under source_root.
    """
    # Get path relative to source root
    relative = source.relative_to(source_root)

    # Change suffix
    output_relative = relative.with_suffix(new_suffix)

    # Join with target root
    return target_root / output_relative


def relative_to_project(path: Path, project_root: Path) -> str:
    """Convert absolute path to relative string for manifest storage.

    Converts an absolute path to a portable, forward-slash-separated
    relative path string suitable for storage in manifest files.

    Args:
        path: Absolute path to convert.
        project_root: Project root directory.

    Returns:
        Forward-slash separated relative path string (portable).

    Raises:
        ValueError: If path is not under project_root.

    Example:
        path = Path("/project/processed_context/contracts/alpha.md")
        project_root = Path("/project")

        Result: "processed_context/contracts/alpha.md"
    """
    relative = path.relative_to(project_root)
    # Use forward slashes for cross-platform manifest portability
    return relative.as_posix()


def source_path_to_manifest_key(source: Path, raw_inbox: Path) -> str:
    """Convert absolute source path to manifest key (portable relative path).

    Takes an absolute path to a source file and the raw_inbox root directory,
    returning a forward-slash-separated relative path string suitable for
    use as a manifest file key.

    Args:
        source: Absolute path to source file.
        raw_inbox: Absolute path to raw_inbox directory.

    Returns:
        Forward-slash separated relative path string.

    Raises:
        ValueError: If source is not under raw_inbox.

    Example:
        source = Path("/project/raw_inbox/contracts/2024/alpha.pdf")
        raw_inbox = Path("/project/raw_inbox")

        Result: "contracts/2024/alpha.pdf"
    """
    relative = source.relative_to(raw_inbox)
    return relative.as_posix()
