"""E2E tests for the status command.

Tests run the actual CLI via subprocess in temp directories.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from .conftest import run_cli


def _write_manifest(project_dir: Path, manifest: dict) -> None:
    (project_dir / ".nest_manifest.json").write_text(json.dumps(manifest, indent=2))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.mark.e2e
class TestStatusE2E:
    def test_status_outside_project_fails(self, fresh_temp_dir: Path) -> None:
        result = run_cli(["status"], cwd=fresh_temp_dir)

        assert result.exit_code == 1
        assert "No Nest project found" in result.stdout
        assert "nest init" in result.stdout

    def test_status_shows_pending_files(self, fresh_temp_dir: Path) -> None:
        project_dir = fresh_temp_dir

        # Minimal project scaffold (avoid running init/docling)
        (project_dir / "_nest_sources").mkdir(parents=True, exist_ok=True)
        (project_dir / "_nest_context").mkdir(parents=True, exist_ok=True)

        _write_manifest(
            project_dir,
            {
                "nest_version": "0.1.1",
                "project_name": "E2EProject",
                "last_sync": None,
                "files": {},
            },
        )

        # Add two new source files
        (project_dir / "_nest_sources" / "a.pdf").write_bytes(b"a")
        (project_dir / "_nest_sources" / "b.pdf").write_bytes(b"b")

        result = run_cli(["status"], cwd=project_dir)

        assert result.exit_code == 0
        assert "Project:" in result.stdout
        assert "E2EProject" in result.stdout
        assert "New:" in result.stdout
        assert "Run `nest sync` to process 2 pending files" in result.stdout

    def test_status_after_sync_shows_up_to_date(self, fresh_temp_dir: Path) -> None:
        project_dir = fresh_temp_dir
        sources = project_dir / "_nest_sources"
        context = project_dir / "_nest_context"
        sources.mkdir(parents=True, exist_ok=True)
        context.mkdir(parents=True, exist_ok=True)

        # Create one source file and a matching context output
        source_path = sources / "report.pdf"
        source_path.write_bytes(b"report")

        output_relative = "report.md"
        (context / output_relative).write_text("# report\n")

        now = datetime.now(timezone.utc)

        _write_manifest(
            project_dir,
            {
                "nest_version": "0.1.1",
                "project_name": "E2EProject",
                "last_sync": now.isoformat(),
                "files": {
                    "report.pdf": {
                        "sha256": _sha256(source_path),
                        "processed_at": now.isoformat(),
                        "output": output_relative,
                        "status": "success",
                        "error": None,
                    }
                },
            },
        )

        result = run_cli(["status"], cwd=project_dir)

        assert result.exit_code == 0
        assert "All files up to date" in result.stdout
        assert "Run `nest sync`" not in result.stdout
