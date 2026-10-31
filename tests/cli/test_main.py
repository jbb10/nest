"""Tests for the CLI process entry point.

The CLI runs Docling's native stack (torch, OpenMP, pdfium), which faults
intermittently on Windows during CPython teardown after all work is done
(issue #41). The entry point therefore terminates the process directly once
the command finishes and its output is flushed, instead of unwinding the
interpreter. These tests pin that contract.
"""

import os
import subprocess
import sys
import textwrap
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SRC_PATH = _REPO_ROOT / "src"


def _probe_script(args: list[str]) -> str:
    """Build a script that registers an atexit marker and calls main()."""
    return textwrap.dedent(
        f"""
        import atexit
        import sys

        atexit.register(print, "ATEXIT_RAN", file=sys.stderr)

        from nest.cli.main import main

        sys.argv = ["nest"] + {args!r}
        main()
        print("MAIN_RETURNED", file=sys.stderr)
        """
    )


def _run_probe(args: list[str], work_dir: Path) -> subprocess.CompletedProcess[str]:
    """Run the probe script as a child process and collect its output.

    The 60s timeout is ample for commands that load no Docling models; it
    only guards against a hang.
    """
    script = work_dir / "cli_exit_probe.py"
    script.write_text(_probe_script(args), encoding="utf-8")
    env = {**os.environ, "PYTHONPATH": str(_SRC_PATH)}
    return subprocess.run(
        [sys.executable, str(script)],
        capture_output=True,
        text=True,
        timeout=60,
        env=env,
    )


def test_cli_exit_terminates_process_without_interpreter_finalization(
    tmp_path: Path,
) -> None:
    """A successful command flushes its output and never unwinds the interpreter."""
    result = _run_probe(["--help"], tmp_path)

    assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"
    assert "Usage" in result.stdout
    assert "ATEXIT_RAN" not in result.stderr
    assert "MAIN_RETURNED" not in result.stderr


def test_cli_exit_preserves_error_exit_code(tmp_path: Path) -> None:
    """A failing command still exits 1 through the direct-termination path."""
    result = _run_probe(["convert", "missing.pdf"], tmp_path)

    assert result.returncode == 1, f"stdout: {result.stdout}\nstderr: {result.stderr}"
    output = result.stdout + result.stderr
    assert "Convert failed" in output
    assert "Path not found" in output
    assert "ATEXIT_RAN" not in result.stderr
    assert "MAIN_RETURNED" not in result.stderr
