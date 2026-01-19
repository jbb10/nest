"""E2E-specific fixtures for CLI testing.

Provides fixtures for running CLI commands via subprocess and managing
temporary project directories.
"""

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest


def docling_available() -> bool:
    """Check if Docling models are downloaded."""
    cache_dir = Path.home() / ".cache" / "docling"
    return cache_dir.exists() and any(cache_dir.iterdir())


skip_without_docling = pytest.mark.skipif(
    not docling_available(),
    reason="Docling models not downloaded. Run 'nest init' first.",
)


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """Print temp directory path at the end of E2E test runs."""
    # Only print if we actually ran E2E tests (check if any were collected)
    if not any(item.get_closest_marker("e2e") for item in session.items):
        return

    # Get the pytest temp directory from environment
    tmpdir = os.environ.get("TMPDIR", "/tmp")
    user = os.environ.get("USER", "unknown")
    pytest_tmp = Path(tmpdir) / f"pytest-of-{user}" / "pytest-current"

    if pytest_tmp.exists():
        # Resolve symlink to actual path
        actual_path = pytest_tmp.resolve()
        print(f"\n\n📁 E2E test artifacts: {actual_path}")
        print(f"   Quick access: open $TMPDIR/pytest-of-{user}/pytest-current\n")


@dataclass
class CLIResult:
    """Result from running a CLI command."""

    exit_code: int
    stdout: str
    stderr: str


def run_cli(args: list[str], cwd: Path, timeout: int = 300) -> CLIResult:
    """Run a nest CLI command via subprocess.

    Args:
        args: Command arguments (without 'nest' prefix).
        cwd: Working directory for the command.
        timeout: Timeout in seconds. Default 300s for Docling processing.

    Returns:
        CLIResult with exit code, stdout, and stderr.
    """
    result = subprocess.run(
        ["nest", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return CLIResult(
        exit_code=result.returncode,
        stdout=result.stdout,
        stderr=result.stderr,
    )


@pytest.fixture
def fresh_temp_dir(tmp_path: Path) -> Path:
    """Create a fresh temp directory for a single test.

    Use this when tests need isolated directories that don't share state.
    Tests that don't need nest init (like init tests themselves) use this.
    """
    return tmp_path


@pytest.fixture
def initialized_project(fresh_temp_dir: Path) -> Path:
    """Create an initialized Nest project.

    Runs `nest init` in a fresh temp directory. Each test gets its own
    initialized project for isolation. Init is fast (~5s) so this is
    acceptable overhead for test reliability.

    Returns:
        Path to the project directory (containing raw_inbox/, processed_context/, etc.).
    """
    result = run_cli(["init", "E2ETestProject"], cwd=fresh_temp_dir)
    assert result.exit_code == 0, f"Init failed: {result.stderr}"
    return fresh_temp_dir


@pytest.fixture
def sample_documents(initialized_project: Path) -> Path:
    """Copy fixture files to raw_inbox in nested structure.

    Depends on initialized_project to ensure raw_inbox/ exists.

    Creates:
        raw_inbox/reports/quarterly.pdf
        raw_inbox/reports/summary.docx
        raw_inbox/presentations/deck.pptx
        raw_inbox/presentations/data.xlsx

    Returns:
        Path to the project directory (for use in sync tests).
    """
    fixtures_dir = Path(__file__).parent / "fixtures"
    raw_inbox = initialized_project / "raw_inbox"

    # Create nested structure
    reports_dir = raw_inbox / "reports"
    presentations_dir = raw_inbox / "presentations"
    reports_dir.mkdir(parents=True, exist_ok=True)
    presentations_dir.mkdir(parents=True, exist_ok=True)

    # Copy fixtures to nested structure
    shutil.copy(fixtures_dir / "quarterly.pdf", reports_dir / "quarterly.pdf")
    shutil.copy(fixtures_dir / "summary.docx", reports_dir / "summary.docx")
    shutil.copy(fixtures_dir / "deck.pptx", presentations_dir / "deck.pptx")
    shutil.copy(fixtures_dir / "data.xlsx", presentations_dir / "data.xlsx")

    return initialized_project
