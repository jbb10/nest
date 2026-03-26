"""Unit tests for ProjectChecker adapter."""

from pathlib import Path

import pytest

from nest.adapters.project_checker import ProjectChecker
from nest.core.exceptions import ManifestError
from nest.core.paths import AGENT_DIR, AGENT_FILES


class TestManifestChecks:
    """Tests for manifest validation."""

    def test_manifest_exists_returns_true_when_file_exists(self, tmp_path: Path) -> None:
        """manifest_exists() should return True when manifest file exists."""
        meta_dir = tmp_path / ".nest"
        meta_dir.mkdir()
        manifest_path = meta_dir / "manifest.json"
        manifest_path.write_text('{"nest_version": "1.0.0", "project_name": "test"}')

        checker = ProjectChecker()
        assert checker.manifest_exists(tmp_path) is True

    def test_manifest_exists_returns_false_when_file_missing(self, tmp_path: Path) -> None:
        """manifest_exists() should return False when manifest file missing."""
        checker = ProjectChecker()
        assert checker.manifest_exists(tmp_path) is False

    def test_load_manifest_raises_error_when_invalid_json(self, tmp_path: Path) -> None:
        """load_manifest() should raise ManifestError for invalid JSON."""
        meta_dir = tmp_path / ".nest"
        meta_dir.mkdir()
        manifest_path = meta_dir / "manifest.json"
        manifest_path.write_text("{invalid json")

        checker = ProjectChecker()
        with pytest.raises(ManifestError):
            checker.load_manifest(tmp_path)


class TestAgentFileChecks:
    """Tests for agent file validation."""

    def test_agent_file_exists_returns_true_when_all_files_exist(self, tmp_path: Path) -> None:
        """agent_file_exists() should return True when all agent files exist."""
        agent_dir = tmp_path / AGENT_DIR
        agent_dir.mkdir(parents=True)
        for filename in AGENT_FILES:
            (agent_dir / filename).write_text(f"# {filename}")

        checker = ProjectChecker()
        assert checker.agent_file_exists(tmp_path) is True

    def test_agent_file_exists_returns_false_when_all_missing(self, tmp_path: Path) -> None:
        """agent_file_exists() should return False when no agent files exist."""
        checker = ProjectChecker()
        assert checker.agent_file_exists(tmp_path) is False

    def test_agent_file_exists_returns_false_when_partial(self, tmp_path: Path) -> None:
        """agent_file_exists() should return False when only some agent files exist."""
        agent_dir = tmp_path / AGENT_DIR
        agent_dir.mkdir(parents=True)
        (agent_dir / "nest.agent.md").write_text("# Nest Agent")

        checker = ProjectChecker()
        assert checker.agent_file_exists(tmp_path) is False

    def test_missing_agent_files_returns_empty_when_all_present(self, tmp_path: Path) -> None:
        """missing_agent_files() should return empty list when all files exist."""
        agent_dir = tmp_path / AGENT_DIR
        agent_dir.mkdir(parents=True)
        for filename in AGENT_FILES:
            (agent_dir / filename).write_text(f"# {filename}")

        checker = ProjectChecker()
        assert checker.missing_agent_files(tmp_path) == []

    def test_missing_agent_files_returns_all_when_none_present(self, tmp_path: Path) -> None:
        """missing_agent_files() should return all filenames when none exist."""
        checker = ProjectChecker()
        assert checker.missing_agent_files(tmp_path) == AGENT_FILES

    def test_missing_agent_files_returns_only_missing(self, tmp_path: Path) -> None:
        """missing_agent_files() should return only the missing filenames."""
        agent_dir = tmp_path / AGENT_DIR
        agent_dir.mkdir(parents=True)
        (agent_dir / "nest.agent.md").write_text("# Nest Agent")

        checker = ProjectChecker()
        missing = checker.missing_agent_files(tmp_path)
        assert "nest.agent.md" not in missing
        assert len(missing) == 3
        assert "nest-master-researcher.agent.md" in missing
        assert "nest-master-synthesizer.agent.md" in missing
        assert "nest-master-planner.agent.md" in missing


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
