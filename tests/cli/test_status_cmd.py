"""Tests for status command CLI."""

from pathlib import Path

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

    def test_status_succeeds_with_manifest(self, tmp_path: Path) -> None:
        project_root = tmp_path
        manifest = Manifest(nest_version="0.0.0", project_name="Demo", last_sync=None, files={})
        ManifestAdapter().save(project_root, manifest)

        result = runner.invoke(app, ["status", "--dir", str(project_root)])
        assert result.exit_code == 0
        assert "Project:" in result.output
        assert "Demo" in result.output
