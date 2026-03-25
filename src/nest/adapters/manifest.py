"""Manifest file adapter implementation.

Handles reading and writing .nest/manifest.json files.
"""

import json
from pathlib import Path

from pydantic import ValidationError

from nest import __version__
from nest.core.exceptions import ManifestError
from nest.core.models import Manifest
from nest.core.paths import MANIFEST_FILENAME, NEST_META_DIR


class ManifestAdapter:
    """Adapter for manifest file operations.

    Implements ManifestProtocol for reading/writing .nest/manifest.json files.
    """

    def exists(self, project_dir: Path) -> bool:
        """Check if a manifest file exists in the project directory.

        Args:
            project_dir: Path to the project root directory.

        Returns:
            True if .nest/manifest.json exists, False otherwise.
        """
        manifest_path = project_dir / NEST_META_DIR / MANIFEST_FILENAME
        return manifest_path.exists()

    def create(self, project_dir: Path) -> Manifest:
        """Create a new manifest file with initial values.

        Args:
            project_dir: Path to the project root directory.

        Returns:
            The newly created Manifest instance.
        """
        manifest = Manifest(
            nest_version=__version__,
            last_sync=None,
            files={},
        )
        self.save(project_dir, manifest)
        return manifest

    def load(self, project_dir: Path) -> Manifest:
        """Load an existing manifest from file.

        Args:
            project_dir: Path to the project root directory.

        Returns:
            The loaded Manifest instance.

        Raises:
            FileNotFoundError: If manifest file doesn't exist.
            ManifestError: If manifest file is invalid JSON or has invalid structure.
        """
        manifest_path = project_dir / NEST_META_DIR / MANIFEST_FILENAME
        if not manifest_path.exists():
            raise FileNotFoundError(f"Manifest not found: {manifest_path}")

        content = manifest_path.read_text(encoding="utf-8")

        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            raise ManifestError(
                f"Manifest file is corrupt (invalid JSON). "
                f"Run `nest doctor` to repair. Details: {e}"
            ) from e

        try:
            return Manifest.model_validate(data)
        except ValidationError as e:
            raise ManifestError(
                f"Manifest file is corrupt (invalid structure). "
                f"Run `nest doctor` to repair. Details: {e}"
            ) from e

    def save(self, project_dir: Path, manifest: Manifest) -> None:
        """Save manifest to file.

        Args:
            project_dir: Path to the project root directory.
            manifest: The Manifest instance to save.
        """
        meta_dir = project_dir / NEST_META_DIR
        meta_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = meta_dir / MANIFEST_FILENAME
        json_str = manifest.model_dump_json(indent=2)
        manifest_path.write_text(json_str, encoding="utf-8", newline="\n")
