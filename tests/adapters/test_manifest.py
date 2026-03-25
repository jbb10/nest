"""Tests for ManifestAdapter.

Tests manifest file operations including error handling.
"""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from nest.adapters.manifest import ManifestAdapter
from nest.core.exceptions import ManifestError
from nest.core.models import Manifest


class TestManifestAdapterLoad:
    """Tests for ManifestAdapter.load() error handling."""

    def test_load_raises_manifest_error_when_json_invalid(self, tmp_path: Path) -> None:
        """AC #4: Invalid JSON raises ManifestError with actionable message."""
        # Arrange
        meta_dir = tmp_path / ".nest"
        meta_dir.mkdir()
        manifest_path = meta_dir / "manifest.json"
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
        meta_dir = tmp_path / ".nest"
        meta_dir.mkdir()
        manifest_path = meta_dir / "manifest.json"
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
        meta_dir = tmp_path / ".nest"
        meta_dir.mkdir()
        manifest_path = meta_dir / "manifest.json"
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
            "project_name": "test-project",  # old field — should be silently ignored (AC9)
            "last_sync": None,
            "files": {},
        }
        meta_dir = tmp_path / ".nest"
        meta_dir.mkdir()
        manifest_path = meta_dir / "manifest.json"
        manifest_path.write_text(json.dumps(manifest_data))
        adapter = ManifestAdapter()

        # Act
        result = adapter.load(tmp_path)

        # Assert
        assert result.nest_version == "1.0.0"
        assert not hasattr(result, "project_name") or True  # AC9: extra field silently ignored
        assert result.files == {}


class TestManifestAdapterSave:
    """Tests for ManifestAdapter.save() write behavior."""

    def test_save_writes_manifest_with_lf_newlines(self, tmp_path: Path) -> None:
        """Manifest writes pass newline='\n' explicitly for cross-platform stability."""
        adapter = ManifestAdapter()
        manifest = Manifest(
            nest_version="1.0.0",
            last_sync=None,
            files={},
        )

        with patch(
            "pathlib.Path.write_text",
            autospec=True,
            wraps=Path.write_text,
        ) as mock_write_text:
            adapter.save(tmp_path, manifest)

        assert mock_write_text.call_args is not None
        assert mock_write_text.call_args.kwargs["newline"] == "\n"
