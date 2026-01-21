"""E2E tests for the init command.

Tests run actual CLI commands via subprocess in temp directories.
"""

import json

import pytest

from .conftest import run_cli


@pytest.mark.e2e
class TestInitE2E:
    """E2E tests for nest init command."""

    def test_init_creates_expected_structure(self, fresh_temp_dir):
        """Test that init creates required directories and manifest.

        AC4: Given nest init "TestProject" is run via subprocess
        When the command completes
        Then exit code is 0
        And raw_inbox/ exists and is empty
        And processed_context/ exists and is empty
        And .nest_manifest.json exists with valid JSON containing project name
        """
        # Act
        result = run_cli(["init", "TestProject"], cwd=fresh_temp_dir)

        # Assert exit code
        assert result.exit_code == 0, f"Init failed: {result.stderr}"

        # Assert raw_inbox exists and is empty
        raw_inbox = fresh_temp_dir / "raw_inbox"
        assert raw_inbox.exists(), "raw_inbox directory should exist"
        assert raw_inbox.is_dir(), "raw_inbox should be a directory"
        assert list(raw_inbox.iterdir()) == [], "raw_inbox should be empty"

        # Assert processed_context exists and is empty
        processed_context = fresh_temp_dir  "_nest_context"
        assert processed_context.exists(), "processed_context directory should exist"
        assert processed_context.is_dir(), "processed_context should be a directory"
        assert list(processed_context.iterdir()) == [], "processed_context should be empty"

        # Assert manifest exists with valid JSON
        manifest_path = fresh_temp_dir / ".nest_manifest.json"
        assert manifest_path.exists(), ".nest_manifest.json should exist"

        # Parse and validate manifest content
        manifest_content = manifest_path.read_text()
        manifest = json.loads(manifest_content)

        assert "project_name" in manifest, "Manifest should contain project_name"
        assert manifest["project_name"] == "TestProject", "Manifest project_name should match"

    def test_init_output_shows_success(self, fresh_temp_dir):
        """Test that init displays success message."""
        # Act
        result = run_cli(["init", "MyProject"], cwd=fresh_temp_dir)

        # Assert
        assert result.exit_code == 0
        # Output should show project name and "initialized" (actual: '✓ Project "X" initialized!')
        assert "MyProject" in result.stdout
        assert "initialized" in result.stdout.lower()
