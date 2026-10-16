"""Project state checker adapter."""

from pathlib import Path

from nest.adapters.manifest import ManifestAdapter
from nest.core.models import Manifest
from nest.core.project_layout import detect_project


class ProjectChecker:
    """Adapter for project state validation.

    Implements ProjectCheckerProtocol. Marker checks delegate to
    ``detect_project`` so every command shares one definition of the layout.
    """

    def __init__(self) -> None:
        self._manifest_adapter = ManifestAdapter()

    def manifest_exists(self, project_dir: Path) -> bool:
        return detect_project(project_dir).manifest

    def load_manifest(self, project_dir: Path) -> Manifest:
        """Load the manifest.

        Raises:
            ManifestError: If manifest file is invalid or corrupt.
        """
        return self._manifest_adapter.load(project_dir)

    def agent_file_exists(self, project_dir: Path) -> bool:
        return detect_project(project_dir).agent_files_present

    def missing_agent_files(self, project_dir: Path) -> list[str]:
        return list(detect_project(project_dir).missing_agent_files)

    def source_folder_exists(self, project_dir: Path) -> bool:
        return detect_project(project_dir).sources_dir

    def context_folder_exists(self, project_dir: Path) -> bool:
        return detect_project(project_dir).context_dir

    def meta_folder_exists(self, project_dir: Path) -> bool:
        return detect_project(project_dir).meta_dir

    def has_legacy_layout(self, project_dir: Path) -> bool:
        return detect_project(project_dir).legacy_manifest
