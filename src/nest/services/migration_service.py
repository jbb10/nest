"""Metadata directory migration service.

Migrates legacy Nest metadata layout (scattered files) to the
consolidated .nest/ directory structure.
"""

import logging
import shutil
from pathlib import Path

from nest.core.models import MigrationResult
from nest.core.paths import (
    CONTEXT_DIR,
    ERROR_LOG_FILENAME,
    MANIFEST_FILENAME,
    MASTER_INDEX_FILE,
    NEST_META_DIR,
)

logger = logging.getLogger(__name__)

# Legacy file locations → new locations inside .nest/
_MIGRATION_MAP: list[tuple[str, str]] = [
    # (old_path_relative_to_project, new_filename_inside_.nest)
    (".nest_manifest.json", MANIFEST_FILENAME),
    (".nest_errors.log", ERROR_LOG_FILENAME),
    (f"{CONTEXT_DIR}/{MASTER_INDEX_FILE}", MASTER_INDEX_FILE),
    (f"{CONTEXT_DIR}/00_INDEX_HINTS.yaml", "00_INDEX_HINTS.yaml"),
    (f"{CONTEXT_DIR}/00_GLOSSARY_HINTS.yaml", "00_GLOSSARY_HINTS.yaml"),
]

# Old .gitignore entries to remove during migration
_OLD_GITIGNORE_ENTRIES = {".nest_manifest.json", ".nest_errors.log"}

# New .gitignore entries to ensure
_NEW_GITIGNORE_ENTRIES = [".nest/", "_nest_sources/"]


class MetadataMigrationService:
    """Migrates legacy metadata files into .nest/ directory."""

    def detect_legacy_layout(self, project_dir: Path) -> bool:
        """Check if project uses legacy metadata layout.

        Returns True if .nest_manifest.json exists at project root.

        Args:
            project_dir: Path to the project root directory.

        Returns:
            True if legacy layout detected, False otherwise.
        """
        return (project_dir / ".nest_manifest.json").exists()

    def migrate(self, project_dir: Path) -> MigrationResult:
        """Migrate metadata files from legacy layout to .nest/ directory.

        Migration is idempotent: if target files already exist and source
        files don't, migration is silently skipped.

        Args:
            project_dir: Path to the project root directory.

        Returns:
            MigrationResult with details of what was migrated.
        """
        meta_dir = project_dir / NEST_META_DIR
        files_moved: list[str] = []
        errors: list[str] = []

        # Step 1: Create .nest/ directory
        try:
            meta_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            return MigrationResult(
                migrated=False,
                errors=[f"Cannot create .nest/ directory: {e}"],
            )

        # Step 2: Move each file if it exists at old location
        for old_relative, new_filename in _MIGRATION_MAP:
            old_path = project_dir / old_relative
            new_path = meta_dir / new_filename

            if not old_path.exists():
                continue

            # Never overwrite existing .nest/ files
            if new_path.exists():
                continue

            try:
                shutil.move(str(old_path), str(new_path))
                files_moved.append(f"{old_relative} → .nest/{new_filename}")
            except OSError as e:
                logger.warning("Failed to move %s: %s", old_relative, e)
                errors.append(f"Failed to move {old_relative}: {e}")

        # Step 3: Update .gitignore
        self._update_gitignore(project_dir)

        return MigrationResult(
            migrated=len(files_moved) > 0,
            files_moved=files_moved,
            errors=errors,
        )

    @staticmethod
    def _update_gitignore(project_dir: Path) -> None:
        """Update .gitignore: remove old entries, add new entries.

        Args:
            project_dir: Path to the project root directory.
        """
        gitignore = project_dir / ".gitignore"

        if gitignore.exists():
            lines = gitignore.read_text(encoding="utf-8").splitlines()
            # Remove old entries
            lines = [line for line in lines if line.strip() not in _OLD_GITIGNORE_ENTRIES]
            # Add new entries if not present
            existing = {line.strip() for line in lines}
            for entry in _NEW_GITIGNORE_ENTRIES:
                if entry not in existing:
                    lines.append(entry)
            gitignore.write_text("\n".join(lines) + "\n", encoding="utf-8")
        else:
            content = (
                "# Nest - source documents (private/confidential)\n"
                "_nest_sources/\n"
                "# Nest - internal metadata\n"
                ".nest/\n"
            )
            gitignore.write_text(content, encoding="utf-8")
