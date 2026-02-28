"""Unit tests for MetadataMigrationService."""

from pathlib import Path

from nest.core.models import MigrationResult
from nest.core.paths import CONTEXT_DIR, NEST_META_DIR
from nest.services.migration_service import MetadataMigrationService


class TestDetectLegacyLayout:
    """Tests for MetadataMigrationService.detect_legacy_layout()."""

    def test_returns_true_when_legacy_manifest_exists(self, tmp_path: Path) -> None:
        """detect_legacy_layout() should return True when .nest_manifest.json exists at root."""
        (tmp_path / ".nest_manifest.json").write_text('{"dummy": true}')

        service = MetadataMigrationService()
        assert service.detect_legacy_layout(tmp_path) is True

    def test_returns_false_when_new_layout(self, tmp_path: Path) -> None:
        """detect_legacy_layout() should return False when .nest/manifest.json exists."""
        meta_dir = tmp_path / NEST_META_DIR
        meta_dir.mkdir()
        (meta_dir / "manifest.json").write_text('{"dummy": true}')

        service = MetadataMigrationService()
        assert service.detect_legacy_layout(tmp_path) is False

    def test_returns_false_for_empty_directory(self, tmp_path: Path) -> None:
        """detect_legacy_layout() should return False for non-Nest directory."""
        service = MetadataMigrationService()
        assert service.detect_legacy_layout(tmp_path) is False


class TestMigrate:
    """Tests for MetadataMigrationService.migrate()."""

    def test_moves_all_existing_files(self, tmp_path: Path) -> None:
        """migrate() should move all legacy files to .nest/ directory."""
        # Create legacy layout files
        (tmp_path / ".nest_manifest.json").write_text('{"manifest": true}')
        (tmp_path / ".nest_errors.log").write_text("error log content")
        context_dir = tmp_path / CONTEXT_DIR
        context_dir.mkdir()
        (context_dir / "00_MASTER_INDEX.md").write_text("# Index")

        service = MetadataMigrationService()
        result = service.migrate(tmp_path)

        assert result.migrated is True
        assert len(result.files_moved) == 3
        assert result.errors == []

        # Verify new locations exist
        meta_dir = tmp_path / NEST_META_DIR
        assert (meta_dir / "manifest.json").exists()
        assert (meta_dir / "errors.log").exists()
        assert (meta_dir / "00_MASTER_INDEX.md").exists()

        # Verify old locations cleaned up
        assert not (tmp_path / ".nest_manifest.json").exists()
        assert not (tmp_path / ".nest_errors.log").exists()
        assert not (context_dir / "00_MASTER_INDEX.md").exists()

    def test_skips_missing_files_gracefully(self, tmp_path: Path) -> None:
        """migrate() should skip files that don't exist without error."""
        # Only create manifest, not error log or index
        (tmp_path / ".nest_manifest.json").write_text('{"manifest": true}')

        service = MetadataMigrationService()
        result = service.migrate(tmp_path)

        assert result.migrated is True
        assert len(result.files_moved) == 1
        assert ".nest_manifest.json" in result.files_moved[0]
        assert result.errors == []

        # Verify new location exists
        assert (tmp_path / NEST_META_DIR / "manifest.json").exists()

    def test_idempotent_second_run(self, tmp_path: Path) -> None:
        """migrate() should be idempotent — no-op on second run."""
        # Create legacy layout and migrate
        (tmp_path / ".nest_manifest.json").write_text('{"manifest": true}')

        service = MetadataMigrationService()
        result1 = service.migrate(tmp_path)
        assert result1.migrated is True
        assert len(result1.files_moved) == 1

        # Second run — nothing to move
        result2 = service.migrate(tmp_path)
        assert result2.migrated is False
        assert result2.files_moved == []
        assert result2.errors == []

    def test_never_overwrites_existing_nest_files(self, tmp_path: Path) -> None:
        """migrate() should not overwrite files already in .nest/."""
        # Create both old and new manifest
        (tmp_path / ".nest_manifest.json").write_text('{"old": true}')
        meta_dir = tmp_path / NEST_META_DIR
        meta_dir.mkdir()
        (meta_dir / "manifest.json").write_text('{"new": true}')

        service = MetadataMigrationService()
        result = service.migrate(tmp_path)

        # Should not move since target exists
        assert result.migrated is False

        # New file should be preserved
        content = (meta_dir / "manifest.json").read_text()
        assert '"new"' in content

    def test_creates_nest_directory(self, tmp_path: Path) -> None:
        """migrate() should create .nest/ if it doesn't exist."""
        (tmp_path / ".nest_manifest.json").write_text('{"manifest": true}')

        service = MetadataMigrationService()
        result = service.migrate(tmp_path)

        assert (tmp_path / NEST_META_DIR).is_dir()
        assert result.migrated is True

    def test_future_proof_hints_files(self, tmp_path: Path) -> None:
        """migrate() should handle future hints files if they exist in _nest_context/."""
        context_dir = tmp_path / CONTEXT_DIR
        context_dir.mkdir()
        (context_dir / "00_INDEX_HINTS.yaml").write_text("hints: true")
        (context_dir / "00_GLOSSARY_HINTS.yaml").write_text("glossary: true")

        service = MetadataMigrationService()
        result = service.migrate(tmp_path)

        assert result.migrated is True
        assert (tmp_path / NEST_META_DIR / "00_INDEX_HINTS.yaml").exists()
        assert (tmp_path / NEST_META_DIR / "00_GLOSSARY_HINTS.yaml").exists()
        assert not (context_dir / "00_INDEX_HINTS.yaml").exists()
        assert not (context_dir / "00_GLOSSARY_HINTS.yaml").exists()

    def test_returns_migration_result_type(self, tmp_path: Path) -> None:
        """migrate() should return MigrationResult instance."""
        service = MetadataMigrationService()
        result = service.migrate(tmp_path)

        assert isinstance(result, MigrationResult)


class TestUpdateGitignore:
    """Tests for MetadataMigrationService._update_gitignore()."""

    def test_updates_existing_gitignore(self, tmp_path: Path) -> None:
        """_update_gitignore() should add .nest/ and remove old entries from existing .gitignore."""
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text(".nest_manifest.json\n.nest_errors.log\n_nest_sources/\n")

        MetadataMigrationService._update_gitignore(tmp_path)

        content = gitignore.read_text()
        assert ".nest/" in content
        assert "_nest_sources/" in content
        assert ".nest_manifest.json" not in content
        assert ".nest_errors.log" not in content

    def test_creates_new_gitignore_if_missing(self, tmp_path: Path) -> None:
        """_update_gitignore() should create .gitignore if it doesn't exist."""
        MetadataMigrationService._update_gitignore(tmp_path)

        gitignore = tmp_path / ".gitignore"
        assert gitignore.exists()
        content = gitignore.read_text()
        assert ".nest/" in content
        assert "_nest_sources/" in content

    def test_preserves_other_entries(self, tmp_path: Path) -> None:
        """_update_gitignore() should preserve non-Nest entries."""
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("*.pyc\n__pycache__/\n.nest_manifest.json\n")

        MetadataMigrationService._update_gitignore(tmp_path)

        content = gitignore.read_text()
        assert "*.pyc" in content
        assert "__pycache__/" in content
        assert ".nest/" in content
        assert ".nest_manifest.json" not in content

    def test_does_not_duplicate_entries(self, tmp_path: Path) -> None:
        """_update_gitignore() should not add .nest/ if already present."""
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text(".nest/\n_nest_sources/\n")

        MetadataMigrationService._update_gitignore(tmp_path)

        content = gitignore.read_text()
        assert content.count(".nest/") == 1
        assert content.count("_nest_sources/") == 1
