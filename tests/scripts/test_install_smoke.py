"""Tests for scripts/install_smoke.py."""

from __future__ import annotations

import stat
import sys
import textwrap
from pathlib import Path

import pytest

import nest
from install_smoke import (
    SmokeCheck,
    SmokeFailure,
    build_checks,
    enumerate_commands,
    find_nest_executable,
    find_tool_python,
    installed_nest_version,
    main,
    run_checks,
    sanitized_environment,
)


class TestSanitizedEnvironment:
    def test_strips_nest_configuration_and_python_leakage(self) -> None:
        env = {
            "PATH": "/usr/bin",
            "NEST_LLM_API_KEY": "secret",
            "NEST_LLM_ENDPOINT": "https://example.invalid",
            "PYTHONPATH": "/somewhere",
            "PYTHONHOME": "/somewhere",
            "VIRTUAL_ENV": "/somewhere",
            "PYTHONUTF8": "1",
        }

        sanitized = sanitized_environment(env)

        assert sanitized == {"PATH": "/usr/bin", "PYTHONUTF8": "1"}


class TestFindNestExecutable:
    def test_finds_posix_executable(self, tmp_path: Path) -> None:
        executable = tmp_path / "nest"
        executable.write_text("", encoding="utf-8")

        assert find_nest_executable(tmp_path) == executable

    def test_finds_windows_executable(self, tmp_path: Path) -> None:
        executable = tmp_path / "nest.exe"
        executable.write_text("", encoding="utf-8")

        assert find_nest_executable(tmp_path) == executable

    def test_raises_when_missing(self, tmp_path: Path) -> None:
        with pytest.raises(SmokeFailure, match="no nest executable"):
            find_nest_executable(tmp_path)


class TestFindToolPython:
    def test_finds_posix_layout(self, tmp_path: Path) -> None:
        python = tmp_path / "nest" / "bin" / "python"
        python.parent.mkdir(parents=True)
        python.write_text("", encoding="utf-8")

        assert find_tool_python(tmp_path) == python

    def test_finds_windows_layout(self, tmp_path: Path) -> None:
        python = tmp_path / "nest" / "Scripts" / "python.exe"
        python.parent.mkdir(parents=True)
        python.write_text("", encoding="utf-8")

        assert find_tool_python(tmp_path) == python

    def test_raises_when_missing(self, tmp_path: Path) -> None:
        with pytest.raises(SmokeFailure, match="no python interpreter"):
            find_tool_python(tmp_path)


class TestEnumerateCommands:
    def test_lists_every_registered_command(self) -> None:
        commands = enumerate_commands([sys.executable], {})

        assert sorted(commands) == [
            "config llm",
            "convert",
            "doctor",
            "init",
            "status",
            "sync",
            "update",
        ]

    def test_raises_when_the_tool_python_fails(self, tmp_path: Path) -> None:
        with pytest.raises(SmokeFailure, match="tool python failed"):
            enumerate_commands([sys.executable, str(tmp_path / "nothing")], {})


class TestInstalledNestVersion:
    def test_reports_the_installed_distribution_version(self) -> None:
        assert installed_nest_version([sys.executable], {}) == nest.__version__


class TestBuildChecks:
    def test_checks_cover_version_help_commands_status_and_doctor(self) -> None:
        checks = build_checks(["status", "config llm"], "3.0.0")

        assert checks == [
            SmokeCheck("nest --version", ["--version"], 0, "3.0.0"),
            SmokeCheck("nest --help", ["--help"], 0, "Usage"),
            SmokeCheck("nest status --help", ["status", "--help"], 0, "Usage"),
            SmokeCheck("nest config llm --help", ["config", "llm", "--help"], 0, "Usage"),
            SmokeCheck("nest status", ["status"], 1, "No Nest project found"),
            SmokeCheck(
                "nest status --verbose", ["status", "--verbose"], 1, "No Nest project found"
            ),
            SmokeCheck("nest doctor", ["doctor"], 0, None),
        ]


class TestRunChecks:
    @pytest.fixture
    def fake_nest(self, tmp_path: Path) -> Path:
        """A fake nest executable: python running a script from argv[1]."""
        script = tmp_path / "fake_nest.py"
        script.write_text(
            textwrap.dedent(
                """\
                import sys

                arguments = sys.argv[1:]
                if "--version" in arguments:
                    print("3.0.0")
                    sys.exit(0)
                if "--help" in arguments:
                    print("Usage: nest [OPTIONS] COMMAND [ARGS]...")
                    sys.exit(0)
                command = next((a for a in arguments if not a.startswith("-")), "")
                if command == "status":
                    print("No Nest project found. Run `nest init` first.")
                    sys.exit(1)
                if command == "doctor":
                    sys.exit(0)
                print(f"unexpected arguments: {arguments}", file=sys.stderr)
                sys.exit(2)
                """
            ),
            encoding="utf-8",
        )
        return script

    def test_all_passing_checks_produce_no_failures(self, fake_nest: Path, tmp_path: Path) -> None:
        checks = build_checks(["status"], "3.0.0")

        failures = run_checks([sys.executable, str(fake_nest)], checks, tmp_path, {})

        assert failures == []

    def test_wrong_exit_code_is_reported(self, fake_nest: Path, tmp_path: Path) -> None:
        checks = [SmokeCheck("nest status", ["status"], 0, None)]

        failures = run_checks([sys.executable, str(fake_nest)], checks, tmp_path, {})

        assert len(failures) == 1
        assert "exit 1, expected 0" in failures[0]

    def test_missing_expected_output_is_reported(self, fake_nest: Path, tmp_path: Path) -> None:
        checks = [SmokeCheck("nest status", ["status"], 1, "No project here")]

        failures = run_checks([sys.executable, str(fake_nest)], checks, tmp_path, {})

        assert len(failures) == 1
        assert "missing expected output 'No project here'" in failures[0]

    def test_traceback_in_output_is_reported(self, fake_nest: Path, tmp_path: Path) -> None:
        script = fake_nest.with_name("crashing_nest.py")
        script.write_text(
            "import sys\n"
            "print('Traceback (most recent call last):')\n"
            "print('AttributeError: ctx._param_default_explicit')\n"
            "sys.exit(1)\n",
            encoding="utf-8",
        )
        checks = [SmokeCheck("nest status", ["status"], 1, "No Nest project found")]

        failures = run_checks([sys.executable, str(script)], checks, tmp_path, {})

        assert len(failures) == 1
        assert "Python traceback in output" in failures[0]
        assert "AttributeError" in failures[0]

    def test_timeout_is_reported(self, fake_nest: Path, tmp_path: Path) -> None:
        script = fake_nest.with_name("hanging_nest.py")
        script.write_text("import time\ntime.sleep(30)\n", encoding="utf-8")
        checks = [SmokeCheck("nest status", ["status"], 1, None)]

        failures = run_checks([sys.executable, str(script)], checks, tmp_path, {}, timeout=1)

        assert len(failures) == 1
        assert "timed out" in failures[0]

    def test_commands_run_in_the_given_working_directory(
        self, fake_nest: Path, tmp_path: Path
    ) -> None:
        work_dir = tmp_path / "empty-workspace"
        work_dir.mkdir()
        script = fake_nest.with_name("cwd_nest.py")
        script.write_text("import os, sys\nprint(os.getcwd())\nsys.exit(0)\n", encoding="utf-8")
        checks = [SmokeCheck("nest status", ["status"], 0, str(work_dir.resolve()))]

        failures = run_checks([sys.executable, str(script)], checks, work_dir, {})

        assert failures == []


def _install_fake_tool(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, nest_command: str) -> None:
    """Create a fake ``uv tool install`` layout and point ``UV_TOOL_*`` at it.

    The nest shim runs ``nest_command`` under the tool python. Both shims are
    wrappers rather than symlinks: CPython locates pyvenv.cfg next to argv[0],
    so an extra symlink layer would lose the venv's site-packages.
    """
    tool_dir = tmp_path / "tool"
    bin_dir = tmp_path / "tool-bin"
    venv_bin = tool_dir / "nest" / "bin"
    venv_bin.mkdir(parents=True)
    bin_dir.mkdir()
    python_shim = venv_bin / "python"
    python_shim.write_text(f'#!/bin/sh\nexec "{sys.executable}" "$@"\n', encoding="utf-8")
    python_shim.chmod(python_shim.stat().st_mode | stat.S_IXUSR)
    nest_shim = bin_dir / "nest"
    nest_shim.write_text(f'#!/bin/sh\nexec "{python_shim}" {nest_command} "$@"\n', encoding="utf-8")
    nest_shim.chmod(nest_shim.stat().st_mode | stat.S_IXUSR)
    monkeypatch.setenv("UV_TOOL_DIR", str(tool_dir))
    monkeypatch.setenv("UV_TOOL_BIN_DIR", str(bin_dir))


class TestMain:
    def test_missing_environment_variables_fail_fast(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("UV_TOOL_DIR", raising=False)
        monkeypatch.delenv("UV_TOOL_BIN_DIR", raising=False)

        assert main() == 2

    @pytest.mark.skipif(sys.platform != "linux", reason="posix executable shims")
    def test_main_passes_against_a_real_tool_layout(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _install_fake_tool(tmp_path, monkeypatch, "-m nest.cli.main")
        monkeypatch.setenv("NEST_LLM_API_KEY", "must-be-ignored")
        monkeypatch.setenv("PYTHONPATH", "must-be-ignored")

        assert main() == 0

    @pytest.mark.skipif(sys.platform != "linux", reason="posix executable shims")
    def test_main_fails_when_the_cli_crashes(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _install_fake_tool(tmp_path, monkeypatch, '-c "raise SystemExit(3)"')

        assert main() == 1
