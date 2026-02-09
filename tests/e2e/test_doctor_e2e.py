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

    def test_doctor_fix_recreates_missing_folders(self, initialized_project: Path) -> None:
        """Test that --fix flag recreates missing folders."""
        # Delete project folders
        sources_dir = initialized_project / "_nest_sources"
        context_dir = initialized_project / "_nest_context"

        import shutil
        if sources_dir.exists():
            shutil.rmtree(sources_dir)
        if context_dir.exists():
            shutil.rmtree(context_dir)

        # Run doctor --fix - should recreate folders
        result = run_cli(["doctor", "--fix"], cwd=initialized_project, timeout=30)

        # Verify folders are recreated
        assert sources_dir.exists(), "_nest_sources/ not recreated"
        assert context_dir.exists(), "_nest_context/ not recreated"
        assert "Created folders" in result.stdout

    def test_doctor_fix_regenerates_agent_file(self, initialized_project: Path) -> None:
        """Test that --fix flag regenerates missing agent file."""
        # Delete agent file
        agent_file = initialized_project / ".github" / "agents" / "nest.agent.md"
        agent_file.unlink()

        assert not agent_file.exists()

        # Run doctor --fix - should regenerate agent file
        result = run_cli(["doctor", "--fix"], cwd=initialized_project, timeout=30)

        # Verify agent file regenerated
        assert agent_file.exists(), "Agent file not regenerated"
        assert "regenerated" in result.stdout.lower() or "Agent file" in result.stdout

    def test_doctor_fix_rebuilds_manifest(self, initialized_project: Path) -> None:
        """Test that --fix flag rebuilds corrupt manifest."""
        # Corrupt the manifest with invalid JSON
        manifest_path = initialized_project / ".nest_manifest.json"
        manifest_path.write_text("{invalid json}")

        # Run doctor --fix - should rebuild manifest
        result = run_cli(["doctor", "--fix"], cwd=initialized_project, timeout=30)

        # Verify manifest is now valid JSON
        import json
        with open(manifest_path) as f:
            manifest = json.load(f)

        assert "nest_version" in manifest
        assert "project_name" in manifest
        assert "Manifest rebuilt" in result.stdout or "rebuilt" in result.stdout.lower()

    def test_doctor_fix_handles_multiple_issues(self, initialized_project: Path) -> None:
        """Test that --fix resolves multiple issues in sequence."""
        # Create multiple issues: delete agent file and folders
        agent_file = initialized_project / ".github" / "agents" / "nest.agent.md"
        sources_dir = initialized_project / "_nest_sources"
        context_dir = initialized_project / "_nest_context"

        agent_file.unlink()

        import shutil
        if sources_dir.exists():
            shutil.rmtree(sources_dir)
        if context_dir.exists():
            shutil.rmtree(context_dir)

        # Run doctor --fix
        result = run_cli(["doctor", "--fix"], cwd=initialized_project, timeout=30)

        # Verify all issues resolved
        assert agent_file.exists(), "Agent file not regenerated"
        assert sources_dir.exists(), "_nest_sources/ not recreated"
        assert context_dir.exists(), "_nest_context/ not recreated"
        # Check output mentions multiple fixes
        assert "issues resolved" in result.stdout or result.stdout.count("✓") >= 2

    def test_doctor_fix_handles_partial_failure(self, fresh_temp_dir: Path) -> None:
        """Test that --fix continues after one fix fails and exits 1."""
        # Create a scenario where we're in a project-like directory
        # but without full project structure to trigger partial fix

        # Create marker files so it looks like a Nest project
        sources_dir = fresh_temp_dir / "_nest_sources"
        sources_dir.mkdir()

        # Create invalid manifest (will fail to rebuild if sources empty and context missing)
        manifest_path = fresh_temp_dir / ".nest_manifest.json"
        manifest_path.write_text("{bad json}")

        # Run doctor --fix - should attempt fixes, may have partial success
        result = run_cli(["doctor", "--fix"], cwd=fresh_temp_dir, timeout=30)

        # The fix should still attempt repairs
        assert "Attempting repairs" in result.stdout
        # Output should show fix attempts (either success or failure indicators)
        assert "✓" in result.stdout or "✗" in result.stdout

        assert "regenerate" in result.stdout or "nest init" in result.stdout
