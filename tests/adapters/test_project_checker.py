"""Unit tests for ProjectChecker adapter."""

from pathlib import Path

import pytest

from nest.adapters.project_checker import ProjectChecker
from nest.core.exceptions import ManifestError


class TestManifestChecks:
    """Tests for manifest validation."""

    def test_manifest_exists_returns_true_when_file_exists(self, tmp_path: Path) -> None:
        """manifest_exists() should return True when manifest file exists."""
        manifest_path = tmp_path / ".nest_manifest.json"
        manifest_path.write_text('{"nest_version": "1.0.0", "project_name": "test"}')

        checker = ProjectChecker()
        assert checker.manifest_exists(tmp_path) is True

    def test_manifest_exists_returns_false_when_file_missing(self, tmp_path: Path) -> None:
        """manifest_exists() should return False when manifest file missing."""
        checker = ProjectChecker()
        assert checker.manifest_exists(tmp_path) is False

    def test_load_manifest_raises_error_when_invalid_json(self, tmp_path: Path) -> None:
        """load_manifest() should raise ManifestError for invalid JSON."""
        manifest_path = tmp_path / ".nest_manifest.json"
        manifest_path.write_text("{invalid json")

        checker = ProjectChecker()
        with pytest.raises(ManifestError):
            checker.load_manifest(tmp_path)


class TestAgentFileChecks:
    """Tests for agent file validation."""

    def test_agent_file_exists_returns_true_when_file_exists(self, tmp_path: Path) -> None:
        """agent_file_exists() should return True when agent file exists."""
        agent_dir = tmp_path / ".github" / "agents"
        agent_dir.mkdir(parents=True)
        agent_file = agent_dir / "nest.agent.md"
        agent_file.write_text("# Nest Agent")

        checker = ProjectChecker()
        assert checker.agent_file_exists(tmp_path) is True

    def test_agent_file_exists_returns_false_when_file_missing(self, tmp_path: Path) -> None:
        """agent_file_exists() should return False when agent file missing."""
        checker = ProjectChecker()
        assert checker.agent_file_exists(tmp_path) is False


class TestFolderChecks:
    """Tests for folder structure validation."""

    def test_source_folder_exists_returns_true_when_folder_exists(self, tmp_path: Path) -> None:
        """source_folder_exists() should return True when folder exists."""
        source_dir = tmp_path / "_nest_sources"
        source_dir.mkdir()

        checker = ProjectChecker()
        assert checker.source_folder_exists(tmp_path) is True

    def test_source_folder_exists_returns_false_when_folder_missing(self, tmp_path: Path) -> None:
        """source_folder_exists() should return False when folder missing."""
        checker = ProjectChecker()
        assert checker.source_folder_exists(tmp_path) is False

    def test_context_folder_exists_returns_true_when_folder_exists(self, tmp_path: Path) -> None:
        """context_folder_exists() should return True when folder exists."""
        context_dir = tmp_path / "_nest_context"
        context_dir.mkdir()

        checker = ProjectChecker()
        assert checker.context_folder_exists(tmp_path) is True

    def test_context_folder_exists_returns_false_when_folder_missing(self, tmp_path: Path) -> None:
        """context_folder_exists() should return False when folder missing."""
        checker = ProjectChecker()
        assert checker.context_folder_exists(tmp_path) is False
