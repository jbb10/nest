"""Tests for sync command CLI."""

import typer
from typer.testing import CliRunner

from nest.cli.main import app
from nest.cli.sync_cmd import _validate_on_error

runner = CliRunner()


class TestValidateOnError:
    """Tests for --on-error validation."""

    def test_valid_skip_value(self) -> None:
        """'skip' should be accepted."""
        result = _validate_on_error("skip")
        assert result == "skip"

    def test_valid_fail_value(self) -> None:
        """'fail' should be accepted."""
        result = _validate_on_error("fail")
        assert result == "fail"

    def test_invalid_value_raises_bad_parameter(self) -> None:
        """Invalid values should raise BadParameter."""
        import pytest

        with pytest.raises(typer.BadParameter, match="Must be 'skip' or 'fail'"):
            _validate_on_error("invalid")


class TestSyncCommandHelp:
    """Tests for sync command help text."""

    def test_sync_help_displays_all_flags(self) -> None:
        """Help should show all flags."""
        result = runner.invoke(app, ["sync", "--help"])

        assert result.exit_code == 0
        assert "--on-error" in result.output
        assert "--dry-run" in result.output
        assert "--force" in result.output
        assert "--no-clean" in result.output
        assert "--dir" in result.output


class TestSyncCommandFlags:
    """Tests for sync command flag parsing."""

    def test_default_on_error_is_skip(self) -> None:
        """Default --on-error should be 'skip'."""
        # This is tested implicitly - the CLI accepts no --on-error
        result = runner.invoke(app, ["sync", "--help"])
        assert "default: skip" in result.output

    def test_dry_run_flag_accepted(self) -> None:
        """--dry-run flag should be parsed."""
        # Note: Will fail because no project exists, but flag should be parsed
        result = runner.invoke(app, ["sync", "--dry-run"])
        # Check that it didn't fail due to flag parsing
        assert "--dry-run" not in result.output or "error" not in result.output.lower()

    def test_force_flag_accepted(self) -> None:
        """--force flag should be parsed."""
        result = runner.invoke(app, ["sync", "--force"])
        # Check that it didn't fail due to flag parsing
        assert "--force" not in result.output or "error" not in result.output.lower()
