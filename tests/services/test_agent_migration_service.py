"""Unit tests for AgentMigrationService."""

from pathlib import Path

from conftest import MockAgentWriter, MockFileSystem, MockManifest
from nest.core.exceptions import ManifestError
from nest.core.models import Manifest
from nest.core.paths import AGENT_DIR
from nest.services.agent_migration_service import AgentMigrationService

PROJECT_DIR = Path("/project")
AGENT_DIR_PATH = PROJECT_DIR / AGENT_DIR


def _make_service(
    *,
    writer: MockAgentWriter | None = None,
    filesystem: MockFileSystem | None = None,
    manifest: MockManifest | None = None,
) -> tuple[AgentMigrationService, MockAgentWriter, MockFileSystem, MockManifest]:
    """Create an AgentMigrationService with default mocks."""
    w = writer or MockAgentWriter()
    fs = filesystem or MockFileSystem()
    m = manifest or MockManifest(manifest_exists=True)
    if m._manifest is None:
        m._manifest = Manifest(nest_version="1.0.0")
    return AgentMigrationService(agent_writer=w, filesystem=fs, manifest=m), w, fs, m


def _populate_all_agent_files(fs: MockFileSystem, writer: MockAgentWriter) -> None:
    """Set all 4 agent files to match rendered templates (up-to-date state)."""
    rendered = writer.render_all()
    for filename, content in rendered.items():
        path = AGENT_DIR_PATH / filename
        fs.existing_paths.add(path)
        fs.file_contents[path] = content


# =========================================================================
# check_migration_needed
# =========================================================================


class TestCheckMigrationNeeded:
    """Tests for AgentMigrationService.check_migration_needed()."""

    def test_all_files_current_returns_no_migration(self) -> None:
        """AC7: All 4 files current → migration_needed=False."""
        service, writer, fs, _ = _make_service()
        _populate_all_agent_files(fs, writer)

        result = service.check_migration_needed(PROJECT_DIR)

        assert result.migration_needed is False
        assert result.message == "All agent files are up to date"
        assert result.outdated_files == []
        assert result.missing_files == []

    def test_one_file_outdated(self) -> None:
        """AC1/AC2: One file outdated → migration_needed=True with correct lists."""
        service, writer, fs, _ = _make_service()
        _populate_all_agent_files(fs, writer)
        # Make coordinator outdated
        fs.file_contents[AGENT_DIR_PATH / "nest.agent.md"] = "old-content"

        result = service.check_migration_needed(PROJECT_DIR)

        assert result.migration_needed is True
        assert result.agent_file_missing is False
        assert result.outdated_files == ["nest.agent.md"]
        assert result.missing_files == []

    def test_two_files_missing(self) -> None:
        """AC2: Two files missing → migration_needed=True, agent_file_missing=True."""
        service, writer, fs, _ = _make_service()
        _populate_all_agent_files(fs, writer)
        # Remove two subagent files
        for name in ["nest-master-researcher.agent.md", "nest-master-synthesizer.agent.md"]:
            path = AGENT_DIR_PATH / name
            fs.existing_paths.discard(path)
            del fs.file_contents[path]

        result = service.check_migration_needed(PROJECT_DIR)

        assert result.migration_needed is True
        assert result.agent_file_missing is True
        assert result.outdated_files == []
        assert set(result.missing_files) == {
            "nest-master-researcher.agent.md",
            "nest-master-synthesizer.agent.md",
        }

    def test_legacy_scenario_one_outdated_three_missing(self) -> None:
        """AC5: Legacy project — coordinator outdated, 3 subagents missing."""
        service, writer, fs, _ = _make_service()
        # Only coordinator exists with old content
        coordinator_path = AGENT_DIR_PATH / "nest.agent.md"
        fs.existing_paths.add(coordinator_path)
        fs.file_contents[coordinator_path] = "old-generalist-content"

        result = service.check_migration_needed(PROJECT_DIR)

        assert result.migration_needed is True
        assert result.agent_file_missing is True
        assert result.outdated_files == ["nest.agent.md"]
        assert len(result.missing_files) == 3

    def test_all_files_missing(self) -> None:
        """No agent files at all → agent_file_missing=True, all 4 in missing_files."""
        service, _, _, _ = _make_service()

        result = service.check_migration_needed(PROJECT_DIR)

        assert result.migration_needed is True
        assert result.agent_file_missing is True
        assert result.outdated_files == []
        assert len(result.missing_files) == 4

    def test_no_manifest_returns_skipped(self) -> None:
        """AC8: Returns skipped=True when no manifest exists."""
        manifest = MockManifest(manifest_exists=False)
        service, _, _, _ = _make_service(manifest=manifest)

        result = service.check_migration_needed(PROJECT_DIR)

        assert result.migration_needed is False
        assert result.skipped is True
        assert result.message == "Not a Nest project — skipping agent check"

    def test_corrupt_manifest_returns_skipped(self) -> None:
        """Corrupt manifest returns skipped result gracefully."""
        manifest = MockManifest(manifest_exists=True)
        manifest.load = lambda _: (_ for _ in ()).throw(ManifestError("corrupt"))  # type: ignore[assignment]

        service = AgentMigrationService(
            agent_writer=MockAgentWriter(),
            filesystem=MockFileSystem(),
            manifest=manifest,
        )

        result = service.check_migration_needed(PROJECT_DIR)

        assert result.migration_needed is False
        assert result.skipped is True
        assert "corrupt" in result.message.lower()

    def test_descriptive_message_for_mixed(self) -> None:
        """Message describes both outdated and missing counts."""
        service, writer, fs, _ = _make_service()
        # Coordinator outdated, one subagent missing
        coordinator_path = AGENT_DIR_PATH / "nest.agent.md"
        fs.existing_paths.add(coordinator_path)
        fs.file_contents[coordinator_path] = "old-content"
        # Add two subagents as current
        for name in ["nest-master-researcher.agent.md", "nest-master-synthesizer.agent.md"]:
            path = AGENT_DIR_PATH / name
            fs.existing_paths.add(path)
            fs.file_contents[path] = writer.template_content

        result = service.check_migration_needed(PROJECT_DIR)

        assert "1 outdated" in result.message
        assert "1 missing" in result.message

    def test_filesystem_error_returns_skipped(self) -> None:
        """Filesystem read error returns skipped result gracefully."""
        service, writer, fs, _ = _make_service()
        # File exists but read_text raises
        coordinator_path = AGENT_DIR_PATH / "nest.agent.md"
        fs.existing_paths.add(coordinator_path)
        fs.read_text = lambda _: (_ for _ in ()).throw(OSError("Permission denied"))  # type: ignore[assignment]

        result = service.check_migration_needed(PROJECT_DIR)

        assert result.migration_needed is False
        assert result.skipped is True
        assert "permission denied" in result.message.lower()


# =========================================================================
# execute_migration
# =========================================================================


class TestExecuteMigration:
    """Tests for AgentMigrationService.execute_migration()."""

    def test_selective_write_only_changed_files(self) -> None:
        """AC3: Only outdated/missing files are written; current files left untouched."""
        service, writer, fs, _ = _make_service()
        _populate_all_agent_files(fs, writer)
        # Make 2 files outdated
        fs.file_contents[AGENT_DIR_PATH / "nest.agent.md"] = "old-1"
        fs.file_contents[AGENT_DIR_PATH / "nest-master-planner.agent.md"] = "old-2"
        # Mark agent dir as existing
        fs.existing_paths.add(AGENT_DIR_PATH)

        result = service.execute_migration(PROJECT_DIR)

        assert result.success is True
        assert set(result.files_replaced) == {"nest.agent.md", "nest-master-planner.agent.md"}
        assert result.files_created == []
        # Verify up-to-date files were NOT written
        assert AGENT_DIR_PATH / "nest-master-researcher.agent.md" not in fs.written_files
        assert AGENT_DIR_PATH / "nest-master-synthesizer.agent.md" not in fs.written_files
        # Verify written content matches template
        rendered = writer.render_all()
        for name in result.files_replaced:
            assert fs.written_files[AGENT_DIR_PATH / name] == rendered[name]

    def test_mixed_replace_and_create(self) -> None:
        """AC3: Mix of replaced and created files tracked correctly."""
        service, writer, fs, _ = _make_service()
        # Coordinator exists but outdated
        coordinator_path = AGENT_DIR_PATH / "nest.agent.md"
        fs.existing_paths.add(coordinator_path)
        fs.file_contents[coordinator_path] = "old-content"
        fs.existing_paths.add(AGENT_DIR_PATH)

        result = service.execute_migration(PROJECT_DIR)

        assert result.success is True
        assert result.files_replaced == ["nest.agent.md"]
        assert len(result.files_created) == 3
        # Verify all written content matches templates
        rendered = writer.render_all()
        for name in result.files_replaced + result.files_created:
            assert fs.written_files[AGENT_DIR_PATH / name] == rendered[name]

    def test_all_missing_creates_all(self) -> None:
        """All files missing → all 4 created."""
        service, _, fs, _ = _make_service()
        fs.existing_paths.add(AGENT_DIR_PATH)

        result = service.execute_migration(PROJECT_DIR)

        assert result.success is True
        assert result.files_replaced == []
        assert len(result.files_created) == 4

    def test_creates_directory_if_missing(self) -> None:
        """Agent directory created if it doesn't exist."""
        service, _, fs, _ = _make_service()
        # Agent dir does NOT exist

        result = service.execute_migration(PROJECT_DIR)

        assert result.success is True
        assert AGENT_DIR_PATH in fs.created_dirs

    def test_filesystem_error_returns_failure(self) -> None:
        """Filesystem error returns success=False with partial lists preserved."""
        service, _, fs, _ = _make_service()
        fs.existing_paths.add(AGENT_DIR_PATH)
        # Make write_text raise on any write
        fs.write_text = lambda *_: (_ for _ in ()).throw(OSError("disk full"))  # type: ignore[assignment]

        result = service.execute_migration(PROJECT_DIR)

        assert result.success is False
        assert result.error is not None
        assert "disk full" in result.error

    def test_returns_error_when_manifest_missing(self) -> None:
        """Returns error when manifest doesn't exist."""
        manifest = MockManifest(manifest_exists=False)
        service, _, _, _ = _make_service(manifest=manifest)

        result = service.execute_migration(PROJECT_DIR)

        assert result.success is False
        assert result.error is not None
        assert "manifest" in result.error.lower()

    def test_returns_error_when_manifest_load_fails(self) -> None:
        """Returns error when manifest cannot be loaded."""
        manifest = MockManifest(manifest_exists=True)
        service = AgentMigrationService(
            agent_writer=MockAgentWriter(),
            filesystem=MockFileSystem(),
            manifest=manifest,
        )

        result = service.execute_migration(PROJECT_DIR)

        assert result.success is False
        assert result.error is not None
        assert "manifest" in result.error.lower()

    def test_no_bak_files_created(self) -> None:
        """AC4: No .bak backup files are created anywhere."""
        service, writer, fs, _ = _make_service()
        _populate_all_agent_files(fs, writer)
        # Make all files outdated
        for filename in writer.render_all():
            fs.file_contents[AGENT_DIR_PATH / filename] = "old-content"
        fs.existing_paths.add(AGENT_DIR_PATH)

        result = service.execute_migration(PROJECT_DIR)

        assert result.success is True
        for written_path in fs.written_files:
            assert not str(written_path).endswith(".bak")
