"""Tests for UserConfigAdapter.

Tests user configuration TOML operations including load, save,
error handling, directory creation, and default config factory.
"""

from datetime import datetime, timezone
from pathlib import Path

import pytest

from nest.adapters.user_config import (
    UserConfigAdapter,
    _serialize_toml,
    create_default_config,
)
from nest.core.exceptions import ConfigError
from nest.core.models import InstallConfig, UserConfig

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_config() -> UserConfig:
    """A valid UserConfig for testing."""
    return UserConfig(
        install=InstallConfig(
            source="git+https://github.com/jbb10/nest",
            installed_version="0.1.3",
            installed_at=datetime(2026, 2, 12, 10, 30, 0, tzinfo=timezone.utc),
        )
    )


@pytest.fixture
def valid_toml() -> str:
    """Valid TOML content matching sample_config."""
    return (
        "[install]\n"
        'source = "git+https://github.com/jbb10/nest"\n'
        'installed_version = "0.1.3"\n'
        'installed_at = "2026-02-12T10:30:00+00:00"\n'
    )


# ---------------------------------------------------------------------------
# Task 6.2: Test loading valid config (AC #2)
# ---------------------------------------------------------------------------


class TestLoad:
    """Tests for UserConfigAdapter.load()."""

    def test_load_valid_config(self, tmp_path: Path, valid_toml: str) -> None:
        """AC #2: load() returns validated UserConfig when file is valid."""
        config_file = tmp_path / "config.toml"
        config_file.write_text(valid_toml)
        adapter = UserConfigAdapter(config_dir=tmp_path)

        result = adapter.load()

        assert result is not None
        assert result.install.source == "git+https://github.com/jbb10/nest"
        assert result.install.installed_version == "0.1.3"
        assert isinstance(result.install.installed_at, datetime)

    # -----------------------------------------------------------------------
    # Task 6.3: Test loading returns None when missing (AC #3)
    # -----------------------------------------------------------------------

    def test_load_returns_none_when_missing(self, tmp_path: Path) -> None:
        """AC #3: load() returns None (not error) when config file doesn't exist."""
        adapter = UserConfigAdapter(config_dir=tmp_path)

        result = adapter.load()

        assert result is None


# ---------------------------------------------------------------------------
# Task 6.6: Test corrupt TOML raises ConfigError (AC #4)
# ---------------------------------------------------------------------------


class TestLoadErrors:
    """Tests for UserConfigAdapter.load() error handling."""

    def test_corrupt_toml_raises_config_error(self, tmp_path: Path) -> None:
        """AC #4: Corrupt TOML raises ConfigError with clear message."""
        config_file = tmp_path / "config.toml"
        config_file.write_text("this is not [valid toml =")
        adapter = UserConfigAdapter(config_dir=tmp_path)

        with pytest.raises(ConfigError) as exc_info:
            adapter.load()

        error_msg = str(exc_info.value)
        assert "corrupt" in error_msg.lower()
        assert "config.toml" in error_msg

    def test_invalid_structure_raises_config_error(self, tmp_path: Path) -> None:
        """AC #4: Valid TOML with wrong structure raises ConfigError."""
        config_file = tmp_path / "config.toml"
        config_file.write_text('[wrong]\nkey = "value"\n')
        adapter = UserConfigAdapter(config_dir=tmp_path)

        with pytest.raises(ConfigError) as exc_info:
            adapter.load()

        error_msg = str(exc_info.value)
        assert "corrupt" in error_msg.lower()

    def test_error_message_suggests_delete_and_regenerate(self, tmp_path: Path) -> None:
        """AC #4: Error message suggests deleting config and regenerating."""
        config_file = tmp_path / "config.toml"
        config_file.write_text("not valid toml {{{}}")
        adapter = UserConfigAdapter(config_dir=tmp_path)

        with pytest.raises(ConfigError) as exc_info:
            adapter.load()

        error_msg = str(exc_info.value)
        assert "delete" in error_msg.lower()
        assert "re-run" in error_msg.lower()


# ---------------------------------------------------------------------------
# Task 6.4: Test saving creates directories (AC #6)
# ---------------------------------------------------------------------------


class TestSave:
    """Tests for UserConfigAdapter.save()."""

    def test_save_creates_directory(self, tmp_path: Path, sample_config: UserConfig) -> None:
        """AC #6: save() creates directories automatically."""
        config_dir = tmp_path / "nested" / "dir"
        adapter = UserConfigAdapter(config_dir=config_dir)

        adapter.save(sample_config)

        assert (config_dir / "config.toml").exists()

    # -----------------------------------------------------------------------
    # Task 6.5: Test saving updates fields (AC #5)
    # -----------------------------------------------------------------------

    def test_save_updates_fields(self, tmp_path: Path, sample_config: UserConfig) -> None:
        """AC #5: save() persists updated fields correctly."""
        adapter = UserConfigAdapter(config_dir=tmp_path)
        adapter.save(sample_config)

        loaded = adapter.load()
        assert loaded is not None
        assert loaded.install.source == sample_config.install.source
        assert loaded.install.installed_version == sample_config.install.installed_version
        assert loaded.install.installed_at == sample_config.install.installed_at

    def test_save_preserves_all_fields_on_update(
        self, tmp_path: Path, sample_config: UserConfig
    ) -> None:
        """AC #5: Updating version preserves source field."""
        adapter = UserConfigAdapter(config_dir=tmp_path)
        adapter.save(sample_config)

        # Update version
        updated = UserConfig(
            install=InstallConfig(
                source=sample_config.install.source,
                installed_version="0.2.0",
                installed_at=datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc),
            )
        )
        adapter.save(updated)

        loaded = adapter.load()
        assert loaded is not None
        assert loaded.install.source == "git+https://github.com/jbb10/nest"
        assert loaded.install.installed_version == "0.2.0"

    def test_save_overwrites_existing_file(self, tmp_path: Path, sample_config: UserConfig) -> None:
        """save() overwrites previous config content."""
        adapter = UserConfigAdapter(config_dir=tmp_path)
        adapter.save(sample_config)

        new_config = UserConfig(
            install=InstallConfig(
                source="git+https://github.com/other/repo",
                installed_version="1.0.0",
                installed_at=datetime(2026, 6, 1, 0, 0, 0, tzinfo=timezone.utc),
            )
        )
        adapter.save(new_config)

        loaded = adapter.load()
        assert loaded is not None
        assert loaded.install.source == "git+https://github.com/other/repo"


# ---------------------------------------------------------------------------
# Task 6.7: Test config_path returns correct path (AC #7)
# ---------------------------------------------------------------------------


class TestConfigPath:
    """Tests for UserConfigAdapter.config_path()."""

    def test_config_path_returns_correct_path(self, tmp_path: Path) -> None:
        """AC #7: config_path() returns expected path."""
        adapter = UserConfigAdapter(config_dir=tmp_path)
        assert adapter.config_path() == tmp_path / "config.toml"

    def test_default_config_path_uses_home(self) -> None:
        """AC #7: Default config path uses ~/.config/nest/config.toml."""
        adapter = UserConfigAdapter()
        expected = Path.home() / ".config" / "nest" / "config.toml"
        assert adapter.config_path() == expected


# ---------------------------------------------------------------------------
# Task 6.8: Test default config factory values (AC #1)
# ---------------------------------------------------------------------------


class TestCreateDefaultConfig:
    """Tests for create_default_config() factory."""

    def test_default_config_has_correct_source(self) -> None:
        """AC #1: Default source matches expected git URL."""
        config = create_default_config()
        assert config.install.source == "git+https://github.com/jbb10/nest"

    def test_default_config_has_current_version(self) -> None:
        """AC #1: Default version matches nest.__version__."""
        from nest import __version__

        config = create_default_config()
        assert config.install.installed_version == __version__

    def test_default_config_has_utc_timestamp(self) -> None:
        """AC #1: Default installed_at is a UTC datetime."""
        before = datetime.now(tz=timezone.utc)
        config = create_default_config()
        after = datetime.now(tz=timezone.utc)

        assert config.install.installed_at >= before
        assert config.install.installed_at <= after
        assert config.install.installed_at.tzinfo is not None

    def test_default_config_roundtrips_through_adapter(self, tmp_path: Path) -> None:
        """AC #1: Default config can be saved and loaded back."""
        config = create_default_config()
        adapter = UserConfigAdapter(config_dir=tmp_path)

        adapter.save(config)
        loaded = adapter.load()

        assert loaded is not None
        assert loaded.install.source == config.install.source
        assert loaded.install.installed_version == config.install.installed_version


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------


class TestSerializeToml:
    """Tests for _serialize_toml helper."""

    def test_serialization_format(self, sample_config: UserConfig) -> None:
        """TOML output is properly formatted."""
        result = _serialize_toml(sample_config)

        assert "[install]" in result
        assert 'source = "git+https://github.com/jbb10/nest"' in result
        assert 'installed_version = "0.1.3"' in result
        assert "installed_at" in result
