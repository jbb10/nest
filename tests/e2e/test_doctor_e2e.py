"""End-to-end tests for nest doctor command."""

from __future__ import annotations

from pathlib import Path

import pytest

from .conftest import run_cli


@pytest.mark.e2e
class TestDoctorE2E:
    """E2E tests for doctor command."""

    def test_doctor_shows_environment_status(self, fresh_temp_dir: Path) -> None:
        """Doctor validates Python/uv/Nest versions (AC1, AC2, AC3)."""
        result = run_cli(["doctor"], cwd=fresh_temp_dir)

        assert result.exit_code == 0
        assert "Nest Doctor" in result.stdout
        assert "Environment" in result.stdout
        assert "Python:" in result.stdout
        assert "uv:" in result.stdout
        assert "Nest:" in result.stdout

    def test_doctor_works_outside_project(self, fresh_temp_dir: Path) -> None:
        """Doctor runs successfully without manifest (AC5)."""
        result = run_cli(["doctor"], cwd=fresh_temp_dir)

        assert result.exit_code == 0
        assert "Run in a Nest project for full diagnostics" in result.stdout

    def test_doctor_handles_missing_uv_gracefully(self, fresh_temp_dir: Path) -> None:
        """Shows helpful output if uv missing (AC2)."""
        result = run_cli(
            ["doctor"],
            cwd=fresh_temp_dir,
            env={"PATH": "/bin:/usr/bin"},
        )

        assert result.exit_code == 0
        assert "uv:" in result.stdout
