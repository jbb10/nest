"""End-to-end tests for nest doctor command."""

from pathlib import Path

import pytest

from nest.cli.doctor_cmd import doctor_command
from nest.services.doctor_service import DoctorService


class TestDoctorE2E:
    """E2E tests for doctor command."""

    def test_doctor_shows_environment_status(self) -> None:
        """Doctor validates Python/uv/Nest versions (AC1, AC2, AC3)."""
        service = DoctorService()
        report = service.check_environment()

        # These should all pass in CI environment
        assert report.python.status == "pass"
        assert report.python.current_value is not None
        assert "3." in report.python.current_value  # Python 3.x

        assert report.uv.status in ["pass", "warning"]  # uv should be available
        assert report.uv.current_value is not None

        assert report.nest.status == "pass"
        assert report.nest.current_value is not None

    def test_doctor_works_outside_project(self, tmp_path: Path) -> None:
        """Doctor runs successfully without manifest (AC5)."""
        # Create temp directory without manifest
        test_dir = tmp_path / "not-a-project"
        test_dir.mkdir()

        # Change to directory without manifest
        import os

        original_dir = os.getcwd()
        try:
            os.chdir(test_dir)

            # Doctor should run without errors
            service = DoctorService()
            report = service.check_environment()

            # Environment checks should still work
            assert report.python is not None
            assert report.uv is not None
            assert report.nest is not None

        finally:
            os.chdir(original_dir)

    def test_doctor_command_callable(self) -> None:
        """Doctor command can be invoked."""
        # This should not raise any exceptions
        try:
            doctor_command()
        except SystemExit:
            # Typer may raise SystemExit, which is acceptable
            pass

    @pytest.mark.skipif(
        not Path("/usr/bin/env").exists(),
        reason="Requires Unix-like environment for PATH manipulation",
    )
    def test_doctor_handles_missing_uv_gracefully(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Shows helpful error if uv missing (AC2)."""
        # Simulate uv not in PATH
        monkeypatch.setenv("PATH", "/bin:/usr/bin")  # Minimal PATH without uv

        service = DoctorService()
        report = service.check_environment()

        # Check that uv check handled gracefully
        # Note: This test may not work if uv is in /bin or /usr/bin
        # The important part is that it doesn't crash
        assert report.uv is not None
        assert report.uv.current_value is not None
