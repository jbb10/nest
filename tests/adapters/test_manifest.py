"""Tests for ManifestAdapter.

Tests manifest file operations including error handling.
"""

import json
from pathlib import Path

import pytest

from nest.adapters.manifest import ManifestAdapter
from nest.core.exceptions import ManifestError


class TestManifestAdapterLoad:
    """Tests for ManifestAdapter.load() error handling."""

    def test_load_raises_manifest_error_when_json_invalid(self, tmp_path: Path) -> None:
        """AC #4: Invalid JSON raises ManifestError with actionable message."""
        # Arrange
        manifest_path = tmp_path / ".nest_manifest.json"
        manifest_path.write_text("{ invalid json without quotes")
        adapter = ManifestAdapter()

        # Act & Assert
        with pytest.raises(ManifestError) as exc_info:
            adapter.load(tmp_path)

        error_msg = str(exc_info.value)
        assert "corrupt" in error_msg.lower()
        assert "nest doctor" in error_msg.lower()

    def test_load_raises_manifest_error_when_pydantic_validation_fails(
        self, tmp_path: Path
    ) -> None:
        """AC #4: Invalid structure raises ManifestError with actionable message."""
        # Arrange - valid JSON but missing required fields
        manifest_path = tmp_path / ".nest_manifest.json"
        manifest_path.write_text('{"wrong_field": "value"}')
        adapter = ManifestAdapter()

        # Act & Assert
        with pytest.raises(ManifestError) as exc_info:
            adapter.load(tmp_path)

        error_msg = str(exc_info.value)
        assert "corrupt" in error_msg.lower()
        assert "nest doctor" in error_msg.lower()

    def test_load_error_message_includes_doctor_guidance(self, tmp_path: Path) -> None:
        """AC #4: Error message advises user to run nest doctor."""
        # Arrange
        manifest_path = tmp_path / ".nest_manifest.json"
        manifest_path.write_text("not valid json at all")
        adapter = ManifestAdapter()

        # Act & Assert
        with pytest.raises(ManifestError) as exc_info:
            adapter.load(tmp_path)

        assert "nest doctor" in str(exc_info.value).lower()

    def test_load_raises_file_not_found_when_missing(self, tmp_path: Path) -> None:
        """FileNotFoundError when manifest file doesn't exist."""
        # Arrange
        adapter = ManifestAdapter()

        # Act & Assert
        with pytest.raises(FileNotFoundError):
            adapter.load(tmp_path)

    def test_load_succeeds_with_valid_manifest(self, tmp_path: Path) -> None:
        """Successfully loads valid manifest file."""
        # Arrange
        manifest_data = {
            "nest_version": "1.0.0",
            "project_name": "test-project",
            "last_sync": None,
            "files": {},
        }
        manifest_path = tmp_path / ".nest_manifest.json"
        manifest_path.write_text(json.dumps(manifest_data))
        adapter = ManifestAdapter()

        # Act
        result = adapter.load(tmp_path)

        # Assert
        assert result.nest_version == "1.0.0"
        assert result.project_name == "test-project"
        assert result.files == {}
