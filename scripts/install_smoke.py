"""Smoke-test a user-style installation of nest.

CI installs exactly what uv.lock pins, but users install nest with
``uv tool install``, which ignores uv.lock and resolves the newest
versions the pyproject.toml ranges permit (issue #52). This script
exercises an installed ``nest`` executable the way a user would - from
an empty directory, with no NEST_* configuration - so a broken fresh
install (like the typer 0.26 crash in issue #51) fails CI instead of
reaching users.

The workflow installs the tool with isolated ``UV_TOOL_DIR`` and
``UV_TOOL_BIN_DIR``; this script reads the same variables and expects
the tool environment to live at ``$UV_TOOL_DIR/nest`` with the
executable in ``$UV_TOOL_BIN_DIR``. Any Python traceback in a command's
output fails the smoke.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import NamedTuple

_TRACEBACK_MARKER = "Traceback (most recent call last)"

# NEST_* would configure the tool instead of testing a fresh user, and
# PYTHON*/VIRTUAL_ENV would point the executable at a different
# environment than the one a user's shell provides.
_STRIP_ENV_PREFIXES = ("NEST_",)
_STRIP_ENV_NAMES = ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV")

_ENUMERATE_COMMANDS_SNIPPET = """\
from typer.core import TyperGroup
from typer.main import get_command

from nest.cli.main import app


def leaves(node, path):
    if not isinstance(node, TyperGroup):
        print(path)
        return
    for name, child in node.commands.items():
        leaves(child, (path + " " + name).strip())


leaves(get_command(app), "")
"""

_INSTALLED_VERSION_SNIPPET = "from importlib.metadata import version\nprint(version('nest'))\n"


class SmokeFailure(Exception):
    """The installation could not be smoke-tested at all."""


class SmokeCheck(NamedTuple):
    """One CLI invocation the smoke performs, and what it must do."""

    description: str
    arguments: list[str]
    expected_exit: int
    expected_output: str | None


def sanitized_environment(env: Mapping[str, str]) -> dict[str, str]:
    """Drop nest configuration and Python environment leakage."""
    return {
        key: value
        for key, value in env.items()
        if not key.startswith(_STRIP_ENV_PREFIXES) and key not in _STRIP_ENV_NAMES
    }


def find_nest_executable(bin_dir: Path) -> Path:
    """Locate the installed nest executable (``nest`` or ``nest.exe``)."""
    for candidate in (bin_dir / "nest", bin_dir / "nest.exe"):
        if candidate.is_file():
            return candidate
    raise SmokeFailure(f"no nest executable found in {bin_dir}")


def find_tool_python(tool_dir: Path) -> Path:
    """Locate the python interpreter of the ``nest`` tool environment."""
    venv = tool_dir / "nest"
    for candidate in (venv / "bin" / "python", venv / "Scripts" / "python.exe"):
        if candidate.is_file():
            return candidate
    raise SmokeFailure(f"no python interpreter found in the tool environment {venv}")


def _run_tool_python(
    tool_python: Sequence[str], snippet: str, env: Mapping[str, str], timeout: int
) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(
            [*tool_python, "-c", snippet],
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            env=dict(env),
        )
    except subprocess.TimeoutExpired as exc:
        raise SmokeFailure(f"tool python timed out after {timeout}s: {exc.stdout}") from None
    if result.returncode != 0:
        raise SmokeFailure(f"tool python failed: {(result.stderr or '').strip()}")
    return result


def enumerate_commands(
    tool_python: Sequence[str], env: Mapping[str, str], timeout: int = 120
) -> list[str]:
    """List every registered command path from the installed tool."""
    result = _run_tool_python(tool_python, _ENUMERATE_COMMANDS_SNIPPET, env, timeout)
    commands = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if not commands:
        raise SmokeFailure("the installed nest registers no commands")
    return commands


def installed_nest_version(
    tool_python: Sequence[str], env: Mapping[str, str], timeout: int = 120
) -> str:
    """Read the version stamped on the installed nest distribution."""
    result = _run_tool_python(tool_python, _INSTALLED_VERSION_SNIPPET, env, timeout)
    version = result.stdout.strip()
    if not version:
        raise SmokeFailure("the installed nest distribution reports no version")
    return version


def build_checks(commands: Sequence[str], expected_version: str | None) -> list[SmokeCheck]:
    """Build the smoke checks: version, help, every command, status, doctor."""
    checks = [
        SmokeCheck("nest --version", ["--version"], 0, expected_version),
        SmokeCheck("nest --help", ["--help"], 0, "Usage"),
    ]
    for command in commands:
        arguments = [*command.split(), "--help"]
        checks.append(SmokeCheck(f"nest {command} --help", arguments, 0, "Usage"))
    checks.extend(
        [
            SmokeCheck("nest status", ["status"], 1, "No Nest project found"),
            SmokeCheck(
                "nest status --verbose", ["status", "--verbose"], 1, "No Nest project found"
            ),
            SmokeCheck("nest doctor", ["doctor"], 0, None),
        ]
    )
    return checks


def _excerpt(output: str, limit: int = 2000) -> str:
    """Return the tail of a command's output, for failure messages."""
    output = output.strip()
    return output if len(output) <= limit else f"...{output[-limit:]}"


def run_checks(
    nest_argv: Sequence[str],
    checks: Sequence[SmokeCheck],
    work_dir: Path,
    env: Mapping[str, str],
    timeout: int = 300,
) -> list[str]:
    """Run every check from an empty directory, returning failure descriptions."""
    failures: list[str] = []
    for check in checks:
        try:
            result = subprocess.run(
                [*nest_argv, *check.arguments],
                cwd=work_dir,
                capture_output=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                env=dict(env),
            )
        except subprocess.TimeoutExpired as exc:
            failures.append(f"{check.description}: timed out after {timeout}s: {exc.stdout}")
            continue
        output = (result.stdout or "") + (result.stderr or "")
        problems: list[str] = []
        if result.returncode != check.expected_exit:
            problems.append(f"exit {result.returncode}, expected {check.expected_exit}")
        if check.expected_output is not None and check.expected_output not in output:
            problems.append(f"missing expected output {check.expected_output!r}")
        if _TRACEBACK_MARKER in output:
            problems.append("Python traceback in output")
        if problems:
            failures.append(f"{check.description}: {'; '.join(problems)}\n{_excerpt(output)}")
    return failures


def main() -> int:
    """Run the smoke against the tool install described by the environment."""
    tool_dir = os.environ.get("UV_TOOL_DIR")
    bin_dir = os.environ.get("UV_TOOL_BIN_DIR")
    if tool_dir is None or bin_dir is None:
        print(
            "Set UV_TOOL_DIR and UV_TOOL_BIN_DIR to the isolated `uv tool install` "
            "directories (the same variables uv tool install reads).",
            file=sys.stderr,
        )
        return 2
    env = sanitized_environment(os.environ)
    try:
        nest_executable = find_nest_executable(Path(bin_dir))
        tool_python = [str(find_tool_python(Path(tool_dir)))]
        commands = enumerate_commands(tool_python, env)
        expected_version = installed_nest_version(tool_python, env)
        checks = build_checks(commands, expected_version)
        with tempfile.TemporaryDirectory(prefix="nest-install-smoke-") as work_name:
            failures = run_checks([str(nest_executable)], checks, Path(work_name), env)
    except SmokeFailure as failure:
        print(f"install smoke failed: {failure}", file=sys.stderr)
        return 1
    if failures:
        print("install smoke failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1
    print(f"install smoke passed: {len(checks)} checks over {len(commands)} commands")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
