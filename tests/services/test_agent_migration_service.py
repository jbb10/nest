"""Unit tests for AgentMigrationService."""

from pathlib import Path

from conftest import MockAgentWriter, MockFileSystem, MockManifest
from nest.core.exceptions import ManifestError
from nest.core.models import Manifest
from nest.services.agent_migration_service import (
    AGENT_BACKUP_SUFFIX,
    AGENT_FILE_PATH,
    AgentMigrationService,
)

PROJECT_DIR = Path("/project")
AGENT_PATH = PROJECT_DIR / AGENT_FILE_PATH
BACKUP_PATH = AGENT_PATH.parent / (AGENT_PATH.name + AGENT_BACKUP_SUFFIX)


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
        m._manifest = Manifest(nest_version="1.0.0", project_name="TestProject")
    return AgentMigrationService(agent_writer=w, filesystem=fs, manifest=m), w, fs, m


# =========================================================================
# check_migration_needed
# =========================================================================


class TestCheckMigrationNeeded:
    """Tests for AgentMigrationService.check_migration_needed()."""

    def test_migration_needed_when_content_differs(self) -> None:
        """AC1: Returns migration_needed=True when local differs from template."""
        service, writer, fs, _ = _make_service()
        # Agent file exists with outdated content
        fs.existing_paths.add(AGENT_PATH)
        fs.file_contents[AGENT_PATH] = "old-content"

        result = service.check_migration_needed(PROJECT_DIR)

        assert result.migration_needed is True
        assert result.agent_file_missing is False
        assert result.skipped is False
        assert result.message == "Agent file is outdated"

    def test_up_to_date_when_content_matches(self) -> None:
        """AC2: Returns migration_needed=False when content matches."""
        service, writer, fs, _ = _make_service()
        # Render template and set local file to same content
        rendered = writer.render("TestProject")
        fs.existing_paths.add(AGENT_PATH)
        fs.file_contents[AGENT_PATH] = rendered

        result = service.check_migration_needed(PROJECT_DIR)

        assert result.migration_needed is False
        assert result.message == "Agent file is up to date"

    def test_agent_file_missing(self) -> None:
        """AC5: Returns migration_needed=True and agent_file_missing=True."""
        service, _, fs, _ = _make_service()
        # Agent file does NOT exist (not in existing_paths)

        result = service.check_migration_needed(PROJECT_DIR)

        assert result.migration_needed is True
        assert result.agent_file_missing is True
        assert result.message == "Agent file missing — will be created"

    def test_no_manifest_returns_skipped(self) -> None:
        """AC6: Returns skipped=True when no manifest exists."""
        manifest = MockManifest(manifest_exists=False)
        service, _, _, _ = _make_service(manifest=manifest)

        result = service.check_migration_needed(PROJECT_DIR)

        assert result.migration_needed is False
        assert result.skipped is True
        assert result.message == "Not a Nest project — skipping agent check"

    def test_renders_template_with_project_name_from_manifest(self) -> None:
        """AC8: Uses project_name from manifest when rendering template."""
        manifest = MockManifest(manifest_exists=True)
        manifest._manifest = Manifest(nest_version="1.0.0", project_name="Nike")
        writer = MockAgentWriter()
        fs = MockFileSystem()
        # Set local content to something different so we can verify the rendered name
        fs.existing_paths.add(AGENT_PATH)
        fs.file_contents[AGENT_PATH] = "old-content"

        service = AgentMigrationService(agent_writer=writer, filesystem=fs, manifest=manifest)
        result = service.check_migration_needed(PROJECT_DIR)

        # The writer renders with "Nike" — and since local differs, migration_needed
        assert result.migration_needed is True
        # Verify that if we match the rendered content, it works
        fs.file_contents[AGENT_PATH] = writer.render("Nike")
        result2 = service.check_migration_needed(PROJECT_DIR)
        assert result2.migration_needed is False

    def test_corrupt_manifest_returns_skipped(self) -> None:
        """Corrupt manifest returns skipped result gracefully."""
        manifest = MockManifest(manifest_exists=True)
        # Override load to raise ManifestError
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


# =========================================================================
# execute_migration
# =========================================================================


class TestExecuteMigration:
    """Tests for AgentMigrationService.execute_migration()."""

    def test_creates_backup_and_regenerates(self) -> None:
        """AC3: Backs up existing file then regenerates."""
        service, writer, fs, _ = _make_service()
        fs.existing_paths.add(AGENT_PATH)
        fs.file_contents[AGENT_PATH] = "old-agent-content"

        result = service.execute_migration(PROJECT_DIR)

        assert result.success is True
        assert result.backed_up is True
        # Verify backup was written
        assert BACKUP_PATH in fs.written_files
        assert fs.written_files[BACKUP_PATH] == "old-agent-content"
        # Verify generate was called
        assert len(writer.generated_agents) == 1
        assert writer.generated_agents[0] == ("TestProject", AGENT_PATH)

    def test_creates_file_without_backup_when_missing(self) -> None:
        """AC7: Creates file fresh without backup when agent file missing."""
        service, writer, fs, _ = _make_service()
        # Agent file does NOT exist

        result = service.execute_migration(PROJECT_DIR)

        assert result.success is True
        assert result.backed_up is False
        # No backup written
        assert BACKUP_PATH not in fs.written_files
        # Generate was called
        assert len(writer.generated_agents) == 1

    def test_overwrites_existing_bak_file(self) -> None:
        """AC9: Overwrites existing .bak file with current agent content."""
        service, writer, fs, _ = _make_service()
        fs.existing_paths.add(AGENT_PATH)
        fs.file_contents[AGENT_PATH] = "current-agent-content"
        # Pre-existing .bak file
        fs.existing_paths.add(BACKUP_PATH)
        fs.file_contents[BACKUP_PATH] = "old-bak-content"

        result = service.execute_migration(PROJECT_DIR)

        assert result.success is True
        assert result.backed_up is True
        # .bak overwritten with current content
        assert fs.written_files[BACKUP_PATH] == "current-agent-content"

    def test_returns_error_on_filesystem_failure(self) -> None:
        """AC10: Returns error result on filesystem failure."""
        service, _, fs, _ = _make_service()
        fs.existing_paths.add(AGENT_PATH)
        # Make read_text raise OSError during backup
        fs.read_text = lambda _: (_ for _ in ()).throw(OSError("disk full"))  # type: ignore[assignment]

        result = service.execute_migration(PROJECT_DIR)

        assert result.success is False
        assert result.error is not None
        assert "disk full" in result.error

    def test_returns_error_when_manifest_load_fails(self) -> None:
        """Returns error result when manifest cannot be loaded."""
        manifest = MockManifest(manifest_exists=True)
        # load() will raise FileNotFoundError because _manifest is None
        service = AgentMigrationService(
            agent_writer=MockAgentWriter(),
            filesystem=MockFileSystem(),
            manifest=manifest,
        )

        result = service.execute_migration(PROJECT_DIR)

        assert result.success is False
        assert result.error is not None
        assert "manifest" in result.error.lower()

    def test_loads_project_name_from_manifest(self) -> None:
        """Uses project name from manifest for regeneration."""
        manifest = MockManifest(manifest_exists=True)
        manifest._manifest = Manifest(nest_version="1.0.0", project_name="Nike")
        writer = MockAgentWriter()
        fs = MockFileSystem()
        service = AgentMigrationService(agent_writer=writer, filesystem=fs, manifest=manifest)

        result = service.execute_migration(PROJECT_DIR)

        assert result.success is True
        assert writer.generated_agents[0][0] == "Nike"

    def test_generate_error_preserves_backup(self) -> None:
        """AC10: If generate fails after backup, backup still exists."""
        service, writer, fs, _ = _make_service()
        fs.existing_paths.add(AGENT_PATH)
        fs.file_contents[AGENT_PATH] = "original-content"
        # Make generate raise
        writer.generate = lambda *_args: (_ for _ in ()).throw(OSError("write failed"))  # type: ignore[assignment]

        result = service.execute_migration(PROJECT_DIR)

        assert result.success is False
        assert result.backed_up is True  # backup was created before failure
        assert fs.written_files[BACKUP_PATH] == "original-content"
