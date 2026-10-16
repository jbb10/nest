"""Detection of a Nest project's on-disk layout.

The single definition of which markers make a directory a Nest project.
"""

from dataclasses import dataclass
from pathlib import Path

from nest.core.paths import (
    AGENT_DIR,
    AGENT_FILES,
    CONTEXT_DIR,
    MANIFEST_FILENAME,
    NEST_META_DIR,
    SOURCES_DIR,
)

LEGACY_MANIFEST_FILENAME = ".nest_manifest.json"


@dataclass(frozen=True)
class ProjectLayout:
    """Snapshot of which Nest project markers exist under ``root``."""

    root: Path
    manifest: bool
    legacy_manifest: bool
    sources_dir: bool
    context_dir: bool
    meta_dir: bool
    missing_agent_files: tuple[str, ...]

    @property
    def initialized(self) -> bool:
        """True when the project has a current-layout manifest."""
        return self.manifest

    @property
    def agent_files_present(self) -> bool:
        return not self.missing_agent_files

    @property
    def is_nest_project(self) -> bool:
        """True when any Nest marker exists, including damaged or legacy projects."""
        return (
            self.manifest
            or self.legacy_manifest
            or self.agent_files_present
            or self.sources_dir
            or self.context_dir
        )


def detect_project(root: Path) -> ProjectLayout:
    """Inspect ``root`` for Nest project markers."""
    agent_dir = root / AGENT_DIR
    return ProjectLayout(
        root=root,
        manifest=(root / NEST_META_DIR / MANIFEST_FILENAME).exists(),
        legacy_manifest=(root / LEGACY_MANIFEST_FILENAME).exists(),
        sources_dir=(root / SOURCES_DIR).is_dir(),
        context_dir=(root / CONTEXT_DIR).is_dir(),
        meta_dir=(root / NEST_META_DIR).is_dir(),
        missing_agent_files=tuple(f for f in AGENT_FILES if not (agent_dir / f).exists()),
    )
