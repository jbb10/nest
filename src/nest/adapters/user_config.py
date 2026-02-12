"""User configuration adapter for ~/.config/nest/config.toml.

Handles reading, writing, and default creation of user-level config
that tracks installation source and version for self-update support.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

from nest import __version__
from nest.core.exceptions import ConfigError
from nest.core.models import InstallConfig, UserConfig

if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomli as tomllib  # type: ignore[no-redef]
    except ModuleNotFoundError as _err:  # pragma: no cover
        raise ModuleNotFoundError(
            "Python <3.11 requires 'tomli'. Install with: pip install tomli>=2.0.0"
        ) from _err

DEFAULT_INSTALL_SOURCE = "git+https://github.com/jbjornsson/nest"
CONFIG_DIR = Path.home() / ".config" / "nest"
CONFIG_FILE = "config.toml"


def _parse_toml(text: str) -> dict[str, Any]:
    """Parse a TOML string into a dictionary.

    Wrapper around tomllib.loads to provide explicit typing for pyright
    strict mode when using the tomli backport on Python <3.11.

    Args:
        text: TOML-formatted string.

    Returns:
        Parsed dictionary.

    Raises:
        ConfigError: If the TOML is malformed.
    """
    try:
        result = cast(dict[str, Any], tomllib.loads(text))  # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType]
    except Exception as exc:
        raise ConfigError(
            "User config is corrupt. Delete ~/.config/nest/config.toml "
            "and re-run any nest command to regenerate."
        ) from exc
    return result


def create_default_config() -> UserConfig:
    """Create a UserConfig with default values.

    Uses the current Nest version and default git install source.

    Returns:
        UserConfig populated with defaults and current timestamp.
    """
    return UserConfig(
        install=InstallConfig(
            source=DEFAULT_INSTALL_SOURCE,
            installed_version=__version__,
            installed_at=datetime.now(tz=timezone.utc),
        )
    )


def _serialize_toml(config: UserConfig) -> str:
    """Serialize UserConfig to TOML string.

    Manual formatting because the schema is flat and simple.
    Avoids adding a write-dependency (tomli_w) for 3 fields.

    Args:
        config: The UserConfig to serialize.

    Returns:
        TOML-formatted string.
    """
    return (
        "[install]\n"
        f'source = "{config.install.source}"\n'
        f'installed_version = "{config.install.installed_version}"\n'
        f'installed_at = "{config.install.installed_at.isoformat()}"\n'
    )


class UserConfigAdapter:
    """Adapter for user-level configuration stored as TOML.

    Reads and writes ~/.config/nest/config.toml. Accepts an optional
    config_dir override for testability (avoids touching real filesystem).

    Args:
        config_dir: Override directory for config file. Defaults to ~/.config/nest/.
    """

    def __init__(self, config_dir: Path | None = None) -> None:
        self._config_dir = config_dir or CONFIG_DIR

    def config_path(self) -> Path:
        """Return the full path to the config file.

        Returns:
            Path to config.toml within the configured directory.
        """
        return self._config_dir / CONFIG_FILE

    def load(self) -> UserConfig | None:
        """Load user configuration from disk.

        Returns:
            UserConfig if file exists and is valid, None if file doesn't exist.

        Raises:
            ConfigError: If config file exists but is corrupt or invalid TOML.
        """
        path = self.config_path()
        if not path.exists():
            return None

        try:
            raw = path.read_bytes()
            data = _parse_toml(raw.decode("utf-8"))
            return UserConfig(**data)
        except ConfigError:
            raise
        except Exception as exc:
            raise ConfigError(
                "User config is corrupt. Delete ~/.config/nest/config.toml "
                "and re-run any nest command to regenerate."
            ) from exc

    def save(self, config: UserConfig) -> None:
        """Save user configuration to disk.

        Creates parent directories if they don't exist.

        Args:
            config: The UserConfig instance to persist.
        """
        self._config_dir.mkdir(parents=True, exist_ok=True)
        self.config_path().write_text(_serialize_toml(config), encoding="utf-8")
