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

        Given nest init is run via subprocess
        When the command completes
        Then exit code is 0
        And _nest_sources/ exists and is empty
        And _nest_context/ exists and is empty
        And .nest/manifest.json exists with valid JSON
        """
        # Act
        result = run_cli(["init"], cwd=fresh_temp_dir)

        # Assert exit code
        assert result.exit_code == 0, f"Init failed: {result.stderr}"

        # Assert raw_inbox exists and is empty
        raw_inbox = fresh_temp_dir / "_nest_sources"
        assert raw_inbox.exists(), "_nest_sources directory should exist"
        assert raw_inbox.is_dir(), "_nest_sources should be a directory"
        assert list(raw_inbox.iterdir()) == [], "_nest_sources should be empty"

        # Assert processed_context exists and is empty
        processed_context = fresh_temp_dir / "_nest_context"
        assert processed_context.exists(), "_nest_context directory should exist"
        assert processed_context.is_dir(), "_nest_context should be a directory"
        assert list(processed_context.iterdir()) == [], "_nest_context should be empty"

        # Assert manifest exists with valid JSON
        manifest_path = fresh_temp_dir / ".nest" / "manifest.json"
        assert manifest_path.exists(), ".nest/manifest.json should exist"

        # Parse and validate manifest content
        manifest_content = manifest_path.read_text()
        manifest = json.loads(manifest_content)

        assert "nest_version" in manifest, "Manifest should contain nest_version"
        assert "files" in manifest, "Manifest should contain files"

    def test_init_output_shows_success(self, fresh_temp_dir):
        """Test that init displays success message."""
        # Act
        result = run_cli(["init"], cwd=fresh_temp_dir)

        # Assert
        assert result.exit_code == 0
        assert "initialized" in result.stdout.lower()

    def test_init_rejects_positional_argument(self, fresh_temp_dir):
        """Test that init rejects unexpected positional arguments."""
        result = run_cli(["init", "SomeName"], cwd=fresh_temp_dir)

        assert result.exit_code == 2, (
            f"Expected exit code 2 for unexpected arg, got {result.exit_code}"
        )
