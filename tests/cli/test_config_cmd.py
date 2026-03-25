"""Tests for config command CLI."""

from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from nest.cli.config_cmd import _display_path, _mask_key
from nest.cli.main import app

runner = CliRunner()


class TestMaskKey:
    """Tests for API key masking helper."""

    def test_mask_key_shows_last_four(self) -> None:
        """Long key → shows last 4 chars."""
        assert _mask_key("sk-1234567890abcdef") == "••••cdef"

    def test_mask_key_short_key(self) -> None:
        """Short key (≤4 chars) → fully masked."""
        assert _mask_key("abc") == "••••"

    def test_mask_key_exactly_four(self) -> None:
        """Exactly 4 chars → fully masked."""
        assert _mask_key("abcd") == "••••"

    def test_mask_key_five_chars(self) -> None:
        """5 chars → shows last 4."""
        assert _mask_key("12345") == "••••2345"


class TestDisplayPath:
    """Tests for path display helper."""

    def test_display_path_replaces_home_with_tilde(self) -> None:
        """Home directory is replaced with ~."""
        home = Path.home()
        path = home / ".zshrc"
        assert _display_path(path) == "~/.zshrc"

    def test_display_path_nested(self) -> None:
        """Nested path under home gets ~ prefix."""
        home = Path.home()
        path = home / ".config" / "fish" / "config.fish"
        assert _display_path(path) == "~/.config/fish/config.fish"


class TestConfigAiHelp:
    """Tests for config ai help text."""

    def test_config_ai_help_shows_usage(self) -> None:
        """'nest config ai --help' displays help text."""
        result = runner.invoke(app, ["config", "ai", "--help"])
        assert result.exit_code == 0
        assert "--remove" in result.output

    def test_config_help_shows_ai_subcommand(self) -> None:
        """'nest config --help' lists 'ai' subcommand."""
        result = runner.invoke(app, ["config", "--help"])
        assert result.exit_code == 0
        assert "ai" in result.output


class TestConfigAiRemove:
    """Tests for config ai --remove flag."""

    def test_config_ai_remove_no_block(self, tmp_path: Path) -> None:
        """--remove with no block shows info message."""
        rc_path = tmp_path / ".zshrc"
        rc_path.write_text("# existing\n", encoding="utf-8")

        with (
            patch("nest.cli.config_cmd.ShellRCService.detect_shell", return_value="zsh"),
            patch(
                "nest.cli.config_cmd.ShellRCService.resolve_rc_path",
                return_value=rc_path,
            ),
        ):
            result = runner.invoke(app, ["config", "ai", "--remove"])

        assert result.exit_code == 0
        assert "No Nest AI configuration found" in result.output

    def test_config_ai_remove_with_block(self, tmp_path: Path) -> None:
        """--remove with block shows success message."""
        from nest.services.shell_rc_service import ShellRCService

        rc_path = tmp_path / ".zshrc"
        service = ShellRCService()
        service.write_config(rc_path, "https://ep", "m", "k", "zsh")

        with (
            patch("nest.cli.config_cmd.ShellRCService.detect_shell", return_value="zsh"),
            patch(
                "nest.cli.config_cmd.ShellRCService.resolve_rc_path",
                return_value=rc_path,
            ),
        ):
            result = runner.invoke(app, ["config", "ai", "--remove"])

        assert result.exit_code == 0
        assert "AI configuration removed" in result.output


class TestConfigAiInteractive:
    """Tests for config ai interactive flow."""

    def test_config_ai_displays_shell_info(self, tmp_path: Path) -> None:
        """Command outputs detected shell and RC file path."""
        rc_path = tmp_path / ".zshrc"

        with (
            patch("nest.cli.config_cmd.ShellRCService.detect_shell", return_value="zsh"),
            patch(
                "nest.cli.config_cmd.ShellRCService.resolve_rc_path",
                return_value=rc_path,
            ),
        ):
            result = runner.invoke(
                app,
                ["config", "ai"],
                input="https://api.openai.com/v1\ngpt-4o-mini\nsk-testkey123\n",
            )

        assert result.exit_code == 0
        assert "Shell: zsh" in result.output
        assert "Added to" in result.output

    def test_config_ai_writes_expected_exports_for_azure_endpoint(self, tmp_path: Path) -> None:
        """Azure endpoint input writes standard Nest AI env vars only."""
        rc_path = tmp_path / ".zshrc"

        with (
            patch("nest.cli.config_cmd.ShellRCService.detect_shell", return_value="zsh"),
            patch(
                "nest.cli.config_cmd.ShellRCService.resolve_rc_path",
                return_value=rc_path,
            ),
        ):
            result = runner.invoke(
                app,
                ["config", "ai"],
                input=("https://myorg.openai.azure.com\nmy-deployment\nazure-key-123\n"),
            )

        assert result.exit_code == 0
        content = rc_path.read_text(encoding="utf-8")
        assert 'export NEST_BASE_URL="https://myorg.openai.azure.com"' in content
        assert 'export NEST_TEXT_MODEL="my-deployment"' in content
        assert 'export NEST_API_KEY="azure-key-123"' in content
        assert "NEST_AI_PROVIDER" not in content
