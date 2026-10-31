"""Tests for status command CLI."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from nest.adapters.manifest import ManifestAdapter
from nest.cli.main import app
from nest.core.models import Manifest

runner = CliRunner()


class TestStatusCommandHelp:
    def test_status_help_includes_dir_flag(self) -> None:
        result = runner.invoke(app, ["status", "--help"])
        assert result.exit_code == 0
        assert "--dir" in result.output


class TestStatusProjectValidation:
    def test_status_fails_when_no_manifest(self, tmp_path: Path) -> None:
        result = runner.invoke(app, ["status", "--dir", str(tmp_path)])
        assert result.exit_code == 1
        assert "No Nest project found" in result.output
        assert "nest init" in result.output

    @pytest.mark.parametrize("verbose_flag", [[], ["--verbose"], ["-v"]])
    def test_status_parses_arguments_without_crashing_outside_a_project(
        self, tmp_path: Path, verbose_flag: list[str]
    ) -> None:
        """Every invocation parses and runs; none dies in argument parsing.

        Regression test for typer 0.26+, which vendors Click: a standalone-Click
        option injected into a typer command crashed parsing with
        AttributeError '_param_default_explicit' before the command ran. The
        controlled `typer.Exit(1)` surfaces as SystemExit, never as a parse
        error.
        """
        result = runner.invoke(app, ["status", "--dir", str(tmp_path), *verbose_flag])
        assert result.exit_code == 1
        assert "No Nest project found" in result.output
        assert result.exception is None or isinstance(result.exception, SystemExit)

    def test_status_succeeds_with_manifest(self, tmp_path: Path) -> None:
        project_root = tmp_path
        manifest = Manifest(nest_version="0.0.0", last_sync=None, files={})
        ManifestAdapter().save(project_root, manifest)

        result = runner.invoke(app, ["status", "--dir", str(project_root)])
        assert result.exit_code == 0
        assert "Nest Project" in result.output
        assert "Nest Version:" in result.output
