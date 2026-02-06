"""E2E tests for nest doctor command."""

from pathlib import Path

import pytest

from .conftest import run_cli


@pytest.mark.e2e
class TestDoctorE2E:
    """E2E tests for nest doctor command."""

    def test_doctor_command_runs_successfully(self, fresh_temp_dir: Path) -> None:
        """Test that nest doctor command executes without errors."""
        result = run_cli(["doctor"], cwd=fresh_temp_dir, timeout=30)

        assert result.exit_code == 0

    def test_doctor_shows_environment_section(self, fresh_temp_dir: Path) -> None:
        """Test that doctor displays Environment section with key components."""
        result = run_cli(["doctor"], cwd=fresh_temp_dir, timeout=30)

        assert result.exit_code == 0
        assert "Environment" in result.stdout
        assert "Python:" in result.stdout
        assert "uv:" in result.stdout
        assert "Nest:" in result.stdout

    def test_doctor_shows_model_status(self, fresh_temp_dir: Path) -> None:
        """Test that doctor displays ML Models section.

        Note: In CI/dev environments, models are typically cached, so we expect
        to see either "cached" or "not found" status. The important thing is
        that the section appears.
        """
        result = run_cli(["doctor"], cwd=fresh_temp_dir, timeout=30)

        assert result.exit_code == 0
        assert "ML Models" in result.stdout
        assert "Models:" in result.stdout

    def test_doctor_shows_model_cache_path(self, fresh_temp_dir: Path) -> None:
        """Test that doctor displays cache path for ML models."""
        result = run_cli(["doctor"], cwd=fresh_temp_dir, timeout=30)

        assert result.exit_code == 0
        assert "Cache path:" in result.stdout
        # Cache path should contain docling models path
        assert "docling" in result.stdout.lower()

    def test_doctor_shows_project_section_in_project(self, initialized_project: Path) -> None:
        """Test that doctor displays Project section when inside Nest project."""
        result = run_cli(["doctor"], cwd=initialized_project, timeout=30)

        assert result.exit_code == 0
        assert "Project" in result.stdout
        assert "Manifest:" in result.stdout
        assert "Agent file:" in result.stdout
        assert "Folders:" in result.stdout

    def test_doctor_skips_project_section_outside_project(self, fresh_temp_dir: Path) -> None:
        """Test that doctor skips Project section when outside Nest project."""
        result = run_cli(["doctor"], cwd=fresh_temp_dir, timeout=30)

        assert result.exit_code == 0
        # Should still show Environment and ML Models
        assert "Environment" in result.stdout
        assert "ML Models" in result.stdout
        # But should NOT show Project section
        assert "Project" not in result.stdout
        # Should show hint message
        assert "Run in a Nest project for full diagnostics" in result.stdout

    def test_doctor_detects_missing_manifest(self, initialized_project: Path) -> None:
        """Test that doctor detects and reports missing manifest."""
        # Delete the manifest
        manifest_path = initialized_project / ".nest_manifest.json"
        manifest_path.unlink()

        # Run doctor - should detect missing manifest
        result = run_cli(["doctor"], cwd=initialized_project, timeout=30)

        assert result.exit_code == 0
        assert "Manifest:" in result.stdout
        assert "missing" in result.stdout
        assert "nest init" in result.stdout

    def test_doctor_detects_missing_agent_file(self, initialized_project: Path) -> None:
        """Test that doctor detects and reports missing agent file."""
        # Delete the agent file
        agent_file = initialized_project / ".github" / "agents" / "nest.agent.md"
        agent_file.unlink()

        # Run doctor - should detect missing agent file
        result = run_cli(["doctor"], cwd=initialized_project, timeout=30)

        assert result.exit_code == 0
        assert "Agent file:" in result.stdout
        assert "missing" in result.stdout
        assert "regenerate" in result.stdout or "nest init" in result.stdout
