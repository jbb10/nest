"""Orphan detection logic.

Detects orphaned output files that no longer have corresponding source files.
"""

from pathlib import Path


class OrphanDetector:
    """Detects orphaned output files with no corresponding source."""

    def detect(
        self,
        output_files: list[Path],
        manifest_outputs: set[str],
        output_dir: Path,
    ) -> list[Path]:
        """Find output files that don't exist in manifest.

        Args:
            output_files: All files in processed_context/.
            manifest_outputs: Set of output paths from manifest entries.
            output_dir: Base output directory for relative path computation.

        Returns:
            List of orphan file paths (absolute) to remove.
        """
        orphans = []

        for file_path in output_files:
            relative = file_path.relative_to(output_dir).as_posix()

            # Exclude system files
            if relative == "00_MASTER_INDEX.md":
                continue

            # If not in manifest, it's an orphan
            if relative not in manifest_outputs:
                orphans.append(file_path)

        return orphans
