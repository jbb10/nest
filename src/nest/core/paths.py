"""Pure path computation functions for output mirroring.

These functions handle path manipulation for mirroring source file
structure in output directories. No I/O operations - fully testable.
"""

from pathlib import Path


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
